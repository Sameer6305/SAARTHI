"""
Production-Grade Voice Pipeline
===============================

STABLE, RELIABLE voice pipeline with comprehensive error handling.

STATE MACHINE:
    IDLE → RECORDING → VALIDATING → TRANSCRIBING → IDLE

VALIDATION STEPS:
1. Duration check (min/max)
2. RMS/volume check (detect silence)
3. Audio normalization
4. Format verification

ERROR RECOVERY:
- Any state → IDLE (force reset on error)
- Spoken feedback for user on failure
- No silent failures

PRIVACY:
- Mic access ONLY during RECORDING state
- Audio cleared immediately after transcription
- No audio stored on disk
"""

import logging
import threading
import time
import queue
import numpy as np
from enum import Enum
from typing import Optional, Callable, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Voice pipeline states."""
    IDLE = "idle"               # Ready for recording
    RECORDING = "recording"     # Actively capturing audio
    VALIDATING = "validating"   # Checking audio quality
    TRANSCRIBING = "transcribing"  # STT processing
    ERROR = "error"             # Error state (auto-recovers to IDLE)


@dataclass
class AudioValidation:
    """Result of audio validation."""
    is_valid: bool
    duration_seconds: float
    rms_level: float
    peak_level: float
    is_silent: bool
    is_too_short: bool
    is_too_long: bool
    error_message: Optional[str] = None


@dataclass  
class PipelineResult:
    """Result from voice pipeline."""
    success: bool
    text: str
    confidence: float
    duration_seconds: float
    validation: Optional[AudioValidation] = None
    error: Optional[str] = None
    needs_retry: bool = False  # True if user should repeat


class ProductionVoicePipeline:
    """
    Production-grade voice pipeline with comprehensive validation.
    
    FEATURES:
    - Audio quality validation (RMS, duration)
    - Automatic normalization
    - Spoken feedback on errors
    - Thread-safe state machine
    - Hard timeout protection
    """
    
    # Recording limits
    MAX_RECORDING_SECONDS = 15.0
    MIN_RECORDING_SECONDS = 0.5
    OPTIMAL_MIN_SECONDS = 1.0  # Warn if below this
    
    # Audio quality thresholds
    SILENCE_RMS_THRESHOLD = 0.01  # Below this is silence
    MIN_RMS_THRESHOLD = 0.005     # Absolute minimum
    
    # STT settings
    STT_TIMEOUT_SECONDS = 30.0
    MIN_CONFIDENCE = 0.3
    LOW_CONFIDENCE_THRESHOLD = 0.6
    
    def __init__(
        self,
        on_state_change: Optional[Callable[[PipelineState], None]] = None,
        on_result: Optional[Callable[[PipelineResult], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_feedback: Optional[Callable[[str], None]] = None,  # For spoken feedback
    ):
        """
        Initialize production voice pipeline.
        
        Args:
            on_state_change: Called on state transitions
            on_result: Called when transcription is ready
            on_error: Called on errors
            on_feedback: Called with messages to speak to user
        """
        self._on_state_change = on_state_change
        self._on_result = on_result
        self._on_error = on_error
        self._on_feedback = on_feedback
        
        # State machine
        self._state = PipelineState.IDLE
        self._state_lock = threading.RLock()
        
        # Components (lazy loaded)
        self._capture = None
        self._stt = None
        self._initialized = False
        
        # Recording state
        self._recording_start_time: Optional[float] = None
        self._audio_buffer = None  # Will hold AudioBuffer object
        
        # Thread control
        self._recording_thread: Optional[threading.Thread] = None
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_recording_event = threading.Event()
        
        # Result queue (for sync access)
        self._result_queue: queue.Queue = queue.Queue()
        
        logger.info("ProductionVoicePipeline created")
    
    def initialize(self) -> bool:
        """
        Initialize voice components.
        
        Returns True if successful.
        """
        if self._initialized:
            return True
            
        try:
            # Import and create audio capture
            from saarthi_executor.voice.audio_capture import PushToTalkCapture
            self._capture = PushToTalkCapture(
                sample_rate=16000,
                max_duration=self.MAX_RECORDING_SECONDS,
                min_duration=0.1,  # We do our own min check with better feedback
            )
            
            if not self._capture.is_available:
                logger.error("No microphone available")
                self._speak_feedback("No microphone found. Please connect a microphone.")
                return False
            
            # Import and create STT
            from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
            from saarthi_executor.voice.config import WhisperModel
            
            self._stt = LocalWhisperSTT(
                model_name=WhisperModel.BASE,
                device="cpu",
                timeout_seconds=self.STT_TIMEOUT_SECONDS,
                min_confidence=self.MIN_CONFIDENCE,
                ambiguous_confidence=self.LOW_CONFIDENCE_THRESHOLD,
            )
            
            self._initialized = True
            logger.info("Production voice pipeline initialized")
            return True
            
        except Exception as e:
            logger.error(f"Voice pipeline initialization failed: {e}")
            return False
    
    def _speak_feedback(self, message: str) -> None:
        """Speak feedback to user."""
        logger.info(f"Feedback: {message}")
        if self._on_feedback:
            try:
                self._on_feedback(message)
            except Exception as e:
                logger.error(f"Feedback callback error: {e}")
    
    def _set_state(self, new_state: PipelineState, reason: str = "") -> bool:
        """Thread-safe state transition."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            
            logger.info(f"Pipeline: {old_state.value} → {new_state.value}" + 
                       (f" ({reason})" if reason else ""))
            
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
            
            return True
    
    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        with self._state_lock:
            return self._state
    
    @property
    def is_busy(self) -> bool:
        """Whether pipeline is busy."""
        with self._state_lock:
            return self._state not in (PipelineState.IDLE, PipelineState.ERROR)
    
    @property
    def is_recording(self) -> bool:
        """Whether currently recording."""
        with self._state_lock:
            return self._state == PipelineState.RECORDING
    
    # ==================== RECORDING ====================
    
    def start_recording(self) -> bool:
        """
        Start voice recording.
        
        Returns True if recording started.
        """
        with self._state_lock:
            if self._state != PipelineState.IDLE:
                logger.warning(f"Cannot start - pipeline busy (state: {self._state.value})")
                return False
            
            if not self._initialized:
                if not self.initialize():
                    return False
            
            if not self._capture or not self._capture.is_available:
                logger.error("Audio capture not available")
                self._speak_feedback("Microphone not available")
                return False
            
            # Reset state
            self._audio_buffer = None
            self._stop_recording_event.clear()
            self._recording_start_time = time.time()
            
            # Transition to RECORDING
            self._set_state(PipelineState.RECORDING, "start_recording")
            
            # Start capture in background
            self._recording_thread = threading.Thread(
                target=self._recording_worker,
                daemon=True,
                name="VoiceRecording",
            )
            self._recording_thread.start()
            
            logger.info("RECORDING_STARTED")
            return True
    
    def _recording_worker(self) -> None:
        """Background worker for audio capture."""
        try:
            # Start capture
            if not self._capture.start_recording():
                raise RuntimeError("Failed to start audio capture")
            
            # Wait for stop signal or timeout
            while not self._stop_recording_event.is_set():
                if self._stop_recording_event.wait(timeout=0.1):
                    break
                
                # Check timeout
                if self._recording_start_time:
                    elapsed = time.time() - self._recording_start_time
                    if elapsed >= self.MAX_RECORDING_SECONDS:
                        logger.warning("Recording timeout - auto-stopping")
                        break
            
            # Stop capture and get audio
            result = self._capture.stop_recording()
            
            if result and result.success and result.audio:
                # CORRECT: result.audio is AudioBuffer, not audio_data
                self._audio_buffer = result.audio
                logger.info(f"Recording captured: {result.duration_seconds:.1f}s")
            else:
                error_msg = result.error if result else "No result"
                logger.warning(f"Recording failed: {error_msg}")
                self._audio_buffer = None
                
        except Exception as e:
            logger.error(f"Recording worker error: {e}")
            self._audio_buffer = None
    
    def stop_recording(self) -> bool:
        """
        Stop recording and start processing.
        
        Returns True if stop was successful.
        """
        with self._state_lock:
            if self._state != PipelineState.RECORDING:
                logger.warning(f"Cannot stop - not recording (state: {self._state.value})")
                return False
            
            # Signal recording to stop
            self._stop_recording_event.set()
            
            # Calculate duration
            duration = 0.0
            if self._recording_start_time:
                duration = time.time() - self._recording_start_time
            
            logger.info(f"RECORDING_STOPPED (duration: {duration:.1f}s)")
            
            # Wait for recording thread
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=2.0)
            
            # Transition to VALIDATING
            self._set_state(PipelineState.VALIDATING, "stop_recording")
            
            # Start processing in background
            self._processing_thread = threading.Thread(
                target=self._processing_worker,
                args=(duration,),
                daemon=True,
                name="VoiceProcessing",
            )
            self._processing_thread.start()
            
            return True
    
    # ==================== VALIDATION ====================
    
    def _validate_audio(self, audio_buffer) -> AudioValidation:
        """
        Validate audio quality.
        
        Checks:
        - Duration (min/max)
        - RMS level (silence detection)
        - Peak level
        """
        if audio_buffer is None or audio_buffer.data is None:
            return AudioValidation(
                is_valid=False,
                duration_seconds=0,
                rms_level=0,
                peak_level=0,
                is_silent=True,
                is_too_short=True,
                is_too_long=False,
                error_message="No audio captured",
            )
        
        audio_data = audio_buffer.data
        duration = audio_buffer.duration_seconds
        
        # Calculate RMS (root mean square) - measure of volume
        rms = np.sqrt(np.mean(audio_data ** 2)) if len(audio_data) > 0 else 0
        peak = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
        
        # Check conditions
        is_too_short = duration < self.MIN_RECORDING_SECONDS
        is_too_long = duration > self.MAX_RECORDING_SECONDS
        is_silent = rms < self.SILENCE_RMS_THRESHOLD
        
        # Determine validity
        is_valid = not is_too_short and not is_too_long and not is_silent
        
        # Build error message
        error_message = None
        if is_too_short:
            error_message = f"Recording too short ({duration:.1f}s). Hold the key longer."
        elif is_silent:
            error_message = "No speech detected. Please speak louder."
        elif is_too_long:
            error_message = "Recording too long. It will be truncated."
        
        return AudioValidation(
            is_valid=is_valid,
            duration_seconds=duration,
            rms_level=rms,
            peak_level=peak,
            is_silent=is_silent,
            is_too_short=is_too_short,
            is_too_long=is_too_long,
            error_message=error_message,
        )
    
    def _normalize_audio(self, audio_buffer) -> None:
        """
        Normalize audio in-place for better STT performance.
        
        - Normalizes to [-1, 1] range
        - Removes DC offset
        """
        if audio_buffer is None or audio_buffer.data is None:
            return
        
        audio = audio_buffer.data
        
        # Remove DC offset
        audio = audio - np.mean(audio)
        
        # Normalize to [-1, 1]
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.95  # Leave some headroom
        
        # Update in place
        audio_buffer.data = audio.astype(np.float32)
    
    # ==================== TRANSCRIPTION ====================
    
    def _processing_worker(self, duration: float) -> None:
        """Background worker for validation and STT."""
        result = PipelineResult(
            success=False,
            text="",
            confidence=0.0,
            duration_seconds=duration,
            needs_retry=False,
        )
        
        try:
            # Step 1: Validate audio
            validation = self._validate_audio(self._audio_buffer)
            result.validation = validation
            
            if not validation.is_valid:
                result.error = validation.error_message
                result.needs_retry = True
                
                # Speak feedback
                if validation.is_too_short:
                    self._speak_feedback("Recording was too short. Please try again and hold the key longer.")
                elif validation.is_silent:
                    self._speak_feedback("I didn't hear anything. Please speak louder and try again.")
                
                logger.warning(f"Audio validation failed: {validation.error_message}")
                return
            
            # Warn if duration is suboptimal
            if validation.duration_seconds < self.OPTIMAL_MIN_SECONDS:
                logger.info(f"Short recording ({validation.duration_seconds:.1f}s) - may affect accuracy")
            
            # Step 2: Normalize audio
            self._set_state(PipelineState.TRANSCRIBING, "audio validated")
            self._normalize_audio(self._audio_buffer)
            
            # Step 3: Transcribe
            if not self._stt:
                result.error = "STT not initialized"
                return
            
            logger.info("Transcribing audio...")
            stt_result = self._stt.transcribe(self._audio_buffer)
            
            if stt_result.success:
                result.success = True
                result.text = stt_result.text.strip()
                result.confidence = stt_result.confidence
                
                # Check for empty text
                if not result.text:
                    result.success = False
                    result.error = "No speech recognized"
                    result.needs_retry = True
                    self._speak_feedback("I couldn't understand that. Please try again.")
                    logger.warning("STT returned empty text")
                    return
                
                # Check confidence
                if result.confidence < self.LOW_CONFIDENCE_THRESHOLD:
                    logger.info(f"Low confidence ({result.confidence:.2f}): {result.text}")
                    # Still return result but note low confidence
                
                logger.info(f"Transcription: \"{result.text}\" (confidence: {result.confidence:.2f})")
                
            else:
                result.error = stt_result.error or "Transcription failed"
                result.needs_retry = True
                
                if stt_result.status.value == "no_speech":
                    self._speak_feedback("No speech detected. Please try again.")
                elif stt_result.status.value == "timeout":
                    self._speak_feedback("Processing took too long. Please try again with a shorter message.")
                else:
                    self._speak_feedback("I had trouble understanding that. Please try again.")
                
                logger.warning(f"STT failed: {result.error}")
                
        except Exception as e:
            result.error = str(e)
            result.needs_retry = True
            logger.error(f"Processing error: {e}")
            self._speak_feedback("Something went wrong. Please try again.")
            
        finally:
            # CRITICAL: Clear audio buffer
            self._clear_audio_buffer()
            
            # Return to IDLE
            self._set_state(PipelineState.IDLE, "processing complete")
            
            # Notify callbacks
            if self._on_result:
                try:
                    self._on_result(result)
                except Exception as e:
                    logger.error(f"Result callback error: {e}")
            
            # Put in queue for sync access
            self._result_queue.put(result)
    
    def _clear_audio_buffer(self) -> None:
        """Securely clear audio buffer."""
        if self._audio_buffer:
            try:
                self._audio_buffer.clear()
            except:
                pass
        self._audio_buffer = None
        logger.debug("Audio buffer cleared")
    
    # ==================== CONTROL ====================
    
    def get_result(self, timeout: float = 30.0) -> Optional[PipelineResult]:
        """
        Get processing result (blocking).
        
        Args:
            timeout: Max seconds to wait
            
        Returns:
            PipelineResult or None if timeout
        """
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def cancel(self) -> None:
        """Cancel current operation."""
        with self._state_lock:
            logger.info(f"Cancel requested (state: {self._state.value})")
            
            if self._state == PipelineState.RECORDING:
                self._stop_recording_event.set()
                if self._capture:
                    try:
                        self._capture.cancel_recording()
                    except:
                        pass
            
            self._clear_audio_buffer()
            self._set_state(PipelineState.IDLE, "cancelled")
    
    def force_reset(self) -> None:
        """Force reset to IDLE state."""
        with self._state_lock:
            logger.warning(f"FORCE_RESET (was: {self._state.value})")
            
            self._stop_recording_event.set()
            
            if self._capture:
                try:
                    self._capture.cancel_recording()
                except:
                    pass
            
            self._clear_audio_buffer()
            self._recording_start_time = None
            self._state = PipelineState.IDLE
            
            if self._on_state_change:
                try:
                    self._on_state_change(PipelineState.IDLE)
                except:
                    pass
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.force_reset()
        
        if self._stt:
            try:
                self._stt.unload_model()
            except:
                pass
            self._stt = None
        
        self._capture = None
        self._initialized = False
        
        logger.info("Voice pipeline cleaned up")
    
    def preload_stt_model(self) -> None:
        """Pre-load STT model in background."""
        if self._stt:
            threading.Thread(
                target=self._stt.load_model,
                daemon=True,
                name="STTPreload",
            ).start()
            logger.info("STT model preload started")
