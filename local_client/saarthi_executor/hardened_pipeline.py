"""
Hardened Voice Pipeline
=======================

Thread-safe, non-blocking voice pipeline with explicit state machine.

STATE MACHINE:
    IDLE → RECORDING → PROCESSING → IDLE
    
ERROR HANDLING:
    Any state → IDLE (force reset on error)

CRITICAL GUARANTEES:
- Recording runs in NON-BLOCKING background thread
- Hard timeout (max 15 seconds)
- No stuck states
- Force reset on any error
- Mic immediately released on stop

PRIVACY:
- Mic access ONLY during RECORDING state
- Audio cleared immediately after processing
- No audio stored on disk
"""

import logging
import threading
import time
import queue
from enum import Enum
from typing import Optional, Callable, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Voice pipeline states."""
    IDLE = "idle"               # Ready for recording
    RECORDING = "recording"     # Actively capturing audio
    PROCESSING = "processing"   # Transcribing audio
    ERROR = "error"             # Error state (auto-recovers to IDLE)


@dataclass
class PipelineResult:
    """Result from voice pipeline."""
    success: bool
    text: str
    confidence: float
    duration_seconds: float
    error: Optional[str] = None


class HardenedVoicePipeline:
    """
    Thread-safe, hardened voice pipeline.
    
    ARCHITECTURE:
    - Main thread controls state transitions
    - Background thread handles audio capture
    - Separate background thread for STT processing
    - All state changes are synchronized
    
    SAFETY:
    - If pipeline is busy, new requests are safely ignored
    - Automatic timeout prevents stuck recording
    - Force reset available for recovery
    """
    
    # Hard limits
    MAX_RECORDING_SECONDS = 15.0
    MIN_RECORDING_SECONDS = 0.3
    STT_TIMEOUT_SECONDS = 30.0
    
    def __init__(
        self,
        on_state_change: Optional[Callable[[PipelineState], None]] = None,
        on_result: Optional[Callable[[PipelineResult], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize hardened voice pipeline.
        
        Args:
            on_state_change: Called on state transitions
            on_result: Called when transcription is ready
            on_error: Called on errors
        """
        self._on_state_change = on_state_change
        self._on_result = on_result
        self._on_error = on_error
        
        # State machine
        self._state = PipelineState.IDLE
        self._state_lock = threading.RLock()
        
        # Components (lazy loaded)
        self._capture = None
        self._stt = None
        
        # Recording state
        self._recording_start_time: Optional[float] = None
        self._audio_buffer: Optional[bytes] = None
        
        # Thread control
        self._recording_thread: Optional[threading.Thread] = None
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_recording_event = threading.Event()
        
        # Result queue (for async processing)
        self._result_queue: queue.Queue = queue.Queue()
        
        logger.info("HardenedVoicePipeline created")
    
    def initialize(self) -> bool:
        """
        Initialize voice components.
        
        Returns True if successful.
        """
        try:
            # Import and create audio capture
            from saarthi_executor.voice.audio_capture import PushToTalkCapture
            self._capture = PushToTalkCapture(
                sample_rate=16000,
                max_duration=self.MAX_RECORDING_SECONDS,
                min_duration=self.MIN_RECORDING_SECONDS,
            )
            
            # Import and create STT
            from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
            from saarthi_executor.voice.config import WhisperModel
            
            self._stt = LocalWhisperSTT(
                model_name=WhisperModel.BASE,
                device="cpu",
                timeout_seconds=self.STT_TIMEOUT_SECONDS,
            )
            
            logger.info("Voice pipeline initialized")
            return True
            
        except Exception as e:
            logger.error(f"Voice pipeline initialization failed: {e}")
            return False
    
    def _set_state(self, new_state: PipelineState, reason: str = "") -> bool:
        """
        Thread-safe state transition.
        
        Returns True if transition was successful.
        """
        with self._state_lock:
            old_state = self._state
            
            # Log state change
            logger.info(f"Pipeline state: {old_state.value} -> {new_state.value}" + 
                       (f" ({reason})" if reason else ""))
            
            self._state = new_state
            
            # Notify callback
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
        """Whether pipeline is busy (recording or processing)."""
        with self._state_lock:
            return self._state in (PipelineState.RECORDING, PipelineState.PROCESSING)
    
    def start_recording(self) -> bool:
        """
        Start voice recording.
        
        THREAD-SAFE: Can be called from any thread.
        NON-BLOCKING: Returns immediately, recording happens in background.
        
        Returns True if recording started.
        """
        with self._state_lock:
            # Check if already busy
            if self._state != PipelineState.IDLE:
                logger.warning(f"Cannot start recording - pipeline busy (state: {self._state.value})")
                return False
            
            # Check components
            if not self._capture:
                logger.error("Audio capture not initialized")
                return False
            
            # Transition to RECORDING
            self._set_state(PipelineState.RECORDING, "start_recording called")
            self._recording_start_time = time.time()
            self._stop_recording_event.clear()
            self._audio_buffer = None
            
            # Start capture in background thread
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
            timeout_remaining = self.MAX_RECORDING_SECONDS
            while not self._stop_recording_event.is_set():
                if self._stop_recording_event.wait(timeout=0.1):
                    break
                
                # Check timeout
                if self._recording_start_time:
                    elapsed = time.time() - self._recording_start_time
                    if elapsed >= self.MAX_RECORDING_SECONDS:
                        logger.warning("Recording timeout - forcing stop")
                        break
            
            # Stop capture and get audio
            result = self._capture.stop_recording()
            
            if result and result.success:
                # BUGFIX: CaptureResult has .audio (AudioBuffer), NOT .audio_data
                self._audio_buffer = result.audio
                logger.info(f"Recording captured: {result.duration_seconds:.1f}s")
            else:
                logger.warning(f"Recording failed: {result.error if result else 'No result'}")
                self._audio_buffer = None
                
        except Exception as e:
            logger.error(f"Recording worker error: {e}")
            self._audio_buffer = None
    
    def stop_recording(self) -> bool:
        """
        Stop recording and start processing.
        
        THREAD-SAFE: Can be called from any thread.
        NON-BLOCKING: Processing happens in background.
        
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
            
            # Wait for recording thread to finish (brief wait)
            if self._recording_thread and self._recording_thread.is_alive():
                self._recording_thread.join(timeout=2.0)
            
            # Transition to PROCESSING
            self._set_state(PipelineState.PROCESSING, "stop_recording called")
            
            # Start processing in background
            self._processing_thread = threading.Thread(
                target=self._processing_worker,
                args=(duration,),
                daemon=True,
                name="VoiceProcessing",
            )
            self._processing_thread.start()
            
            return True
    
    def _processing_worker(self, duration: float) -> None:
        """Background worker for STT processing."""
        result = PipelineResult(
            success=False,
            text="",
            confidence=0.0,
            duration_seconds=duration,
        )
        
        try:
            # Check if we have audio
            if not self._audio_buffer:
                result.error = "No audio captured"
                return
            
            # Check duration
            if duration < self.MIN_RECORDING_SECONDS:
                result.error = f"Recording too short ({duration:.1f}s)"
                return
            
            # Initialize STT if needed
            if not self._stt:
                result.error = "STT not initialized"
                return
            
            # Transcribe
            logger.info("Transcribing audio...")
            stt_result = self._stt.transcribe(self._audio_buffer)
            
            if stt_result.success:
                result.success = True
                result.text = stt_result.text
                result.confidence = stt_result.confidence
                logger.info(f"Transcription successful: \"{result.text[:50]}...\"" 
                           if len(result.text) > 50 else f"Transcription: \"{result.text}\"")
            else:
                result.error = stt_result.error or "Transcription failed"
                logger.warning(f"Transcription failed: {result.error}")
                
        except Exception as e:
            result.error = str(e)
            logger.error(f"Processing worker error: {e}")
            
        finally:
            # CRITICAL: Clear audio buffer immediately
            self._audio_buffer = None
            
            # Return to IDLE
            self._set_state(PipelineState.IDLE, "processing complete")
            
            # Notify result callback
            if self._on_result:
                try:
                    self._on_result(result)
                except Exception as e:
                    logger.error(f"Result callback error: {e}")
            
            # Put result in queue (for synchronous access)
            self._result_queue.put(result)
    
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
        """
        Cancel current operation.
        
        Safe to call from any state.
        """
        with self._state_lock:
            logger.info(f"Cancel requested (state: {self._state.value})")
            
            if self._state == PipelineState.RECORDING:
                # Stop recording
                self._stop_recording_event.set()
                
                if self._capture:
                    try:
                        self._capture.cancel_recording()
                    except:
                        pass
            
            # Clear audio
            self._audio_buffer = None
            
            # Return to IDLE
            self._set_state(PipelineState.IDLE, "cancelled")
    
    def force_reset(self) -> None:
        """
        Force reset the pipeline to IDLE state.
        
        Use for recovery from stuck states.
        """
        with self._state_lock:
            logger.warning(f"PIPELINE_RESET forced (was: {self._state.value})")
            
            # Signal stop
            self._stop_recording_event.set()
            
            # Cancel capture
            if self._capture:
                try:
                    self._capture.cancel_recording()
                except:
                    pass
            
            # Clear state
            self._audio_buffer = None
            self._recording_start_time = None
            
            # Force IDLE
            self._state = PipelineState.IDLE
            
            if self._on_state_change:
                try:
                    self._on_state_change(PipelineState.IDLE)
                except:
                    pass
            
            logger.info("Pipeline reset complete")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.force_reset()
        
        # Unload STT model
        if self._stt:
            try:
                self._stt.unload_model()
            except:
                pass
            self._stt = None
        
        self._capture = None
        
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
