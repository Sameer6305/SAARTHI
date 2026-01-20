"""
Voice Pipeline Orchestrator
============================

Coordinates the complete voice flow:
mic → buffer → STT → text → agent pipeline → TTS → speaker

PRIVACY GUARANTEES:
- Push-to-talk only (no always-on listening)
- Audio exists only in memory during processing
- Audio is cleared immediately after transcription
- Voice input treated identically to text input

SAFETY GUARANTEES:
- Voice never bypasses permissions
- Ambiguous input requires text confirmation
- Silence or failure never triggers actions
- Voice is a convenience layer, not a controller
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any
from pathlib import Path

from saarthi_executor.voice.config import VoiceConfig, TTSEngine
from saarthi_executor.voice.audio_capture import PushToTalkCapture, CaptureState, CaptureResult
from saarthi_executor.voice.stt_whisper import LocalWhisperSTT, TranscriptionResult, STTStatus
from saarthi_executor.voice.tts_local import LocalTTS, create_tts_engine, SpeakResult

logger = logging.getLogger(__name__)


class VoicePipelineState(Enum):
    """Voice pipeline state machine."""
    DISABLED = "disabled"       # Voice features off
    READY = "ready"            # Ready for push-to-talk
    RECORDING = "recording"    # User is holding button
    TRANSCRIBING = "transcribing"  # Processing speech
    CONFIRMING = "confirming"  # Waiting for text confirmation
    SPEAKING = "speaking"      # TTS output
    ERROR = "error"           # Error state


@dataclass
class VoiceInputResult:
    """
    Result of voice input processing.
    
    This is what gets passed to the main agent pipeline.
    It is treated IDENTICALLY to typed text input.
    """
    success: bool
    text: str                      # Transcribed text
    confidence: float              # STT confidence
    needs_confirmation: bool       # True if user should verify
    source: str = "voice"          # Always "voice" for voice input
    error: Optional[str] = None
    
    def to_text_input(self) -> str:
        """
        Convert to standard text input for the agent pipeline.
        
        Voice input has NO special treatment - same as typed text.
        """
        return self.text


class VoicePipeline:
    """
    Voice pipeline orchestrator.
    
    Coordinates:
    1. Push-to-talk audio capture
    2. Local Whisper STT
    3. Text confirmation (if needed)
    4. Local TTS output
    
    CRITICAL: Voice input is passed to the agent pipeline
    as PLAIN TEXT with NO special privileges.
    """
    
    def __init__(
        self,
        config: VoiceConfig,
        on_state_change: Optional[Callable[[VoicePipelineState], None]] = None,
        on_recording_state: Optional[Callable[[bool], None]] = None,
    ):
        """
        Initialize voice pipeline.
        
        Args:
            config: Voice configuration
            on_state_change: Callback for pipeline state changes
            on_recording_state: Callback for recording start/stop (for UI)
        """
        self._config = config
        self._on_state_change = on_state_change
        self._on_recording_state = on_recording_state
        
        # State
        self._state = VoicePipelineState.DISABLED
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        
        # Components (lazy initialized)
        self._capture: Optional[PushToTalkCapture] = None
        self._stt: Optional[LocalWhisperSTT] = None
        self._tts: Optional[LocalTTS] = None
        
        # Initialize if enabled
        if config.enabled:
            self._initialize_components()
    
    def _set_state(self, new_state: VoicePipelineState) -> None:
        """Update state and notify callback."""
        old_state = self._state
        self._state = new_state
        
        if self._on_state_change and old_state != new_state:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def _initialize_components(self) -> bool:
        """Initialize voice components."""
        try:
            # Audio capture
            self._capture = PushToTalkCapture(
                sample_rate=self._config.sample_rate,
                max_duration=self._config.max_recording_seconds,
                min_duration=self._config.min_recording_seconds,
                on_state_change=self._on_capture_state_change,
            )
            
            # STT
            self._stt = LocalWhisperSTT(
                model_name=self._config.whisper_model,
                model_path=self._config.whisper_model_path,
                device="cpu",  # CPU for privacy/compatibility
                timeout_seconds=self._config.stt_timeout_seconds,
                min_confidence=self._config.min_confidence,
                ambiguous_confidence=self._config.ambiguous_confidence,
            )
            
            # TTS
            self._tts = create_tts_engine(
                self._config.tts_engine,
                voice_name=self._config.tts_voice_name,
                rate=self._config.tts_rate,
                volume=self._config.tts_volume,
            )
            
            self._set_state(VoicePipelineState.READY)
            logger.info("Voice pipeline initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize voice pipeline: {e}")
            self._set_state(VoicePipelineState.ERROR)
            return False
    
    def _on_capture_state_change(self, capture_state: CaptureState) -> None:
        """Handle audio capture state changes."""
        if capture_state == CaptureState.RECORDING:
            if self._on_recording_state:
                self._on_recording_state(True)
        elif capture_state in (CaptureState.IDLE, CaptureState.ERROR):
            if self._on_recording_state:
                self._on_recording_state(False)
    
    # ==================== PUBLIC API ====================
    
    @property
    def state(self) -> VoicePipelineState:
        """Current pipeline state."""
        return self._state
    
    @property
    def is_enabled(self) -> bool:
        """Whether voice features are enabled."""
        return self._state != VoicePipelineState.DISABLED
    
    @property
    def is_ready(self) -> bool:
        """Whether ready for push-to-talk."""
        return self._state == VoicePipelineState.READY
    
    @property
    def is_recording(self) -> bool:
        """Whether currently recording."""
        return self._state == VoicePipelineState.RECORDING
    
    def enable(self) -> bool:
        """
        Enable voice features.
        
        Requires explicit user action.
        Returns True if successful.
        """
        if self.is_enabled:
            return True
        
        self._config.enabled = True
        success = self._initialize_components()
        
        if success:
            logger.info("Voice features enabled")
        
        return success
    
    def disable(self) -> None:
        """
        Disable voice features.
        
        Stops any in-progress operations and releases resources.
        """
        # Cancel any recording
        if self._capture:
            self._capture.cancel_recording()
        
        # Stop TTS
        if self._tts:
            self._tts.stop()
        
        # Unload STT model
        if self._stt:
            self._stt.unload_model()
        
        self._config.enabled = False
        self._set_state(VoicePipelineState.DISABLED)
        
        logger.info("Voice features disabled")
    
    def start_listening(self) -> bool:
        """
        Start push-to-talk recording.
        
        Called when user PRESSES the talk button.
        Returns True if recording started.
        """
        if not self.is_enabled:
            logger.warning("Voice not enabled")
            return False
        
        if not self._state == VoicePipelineState.READY:
            logger.warning(f"Cannot start recording in state: {self._state}")
            return False
        
        if not self._capture or not self._capture.is_available:
            logger.error("Audio capture not available")
            self._handle_failure("Microphone not available")
            return False
        
        success = self._capture.start_recording()
        
        if success:
            self._set_state(VoicePipelineState.RECORDING)
            logger.info("Push-to-talk: recording started")
        else:
            self._handle_failure("Failed to start recording")
        
        return success
    
    def stop_listening(self) -> VoiceInputResult:
        """
        Stop push-to-talk recording and transcribe.
        
        Called when user RELEASES the talk button.
        Returns transcribed text (or error).
        """
        if self._state != VoicePipelineState.RECORDING:
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error="Not recording",
            )
        
        if not self._capture:
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error="Capture not initialized",
            )
        
        # Stop recording
        capture_result = self._capture.stop_recording()
        
        if not capture_result.success:
            self._handle_failure(capture_result.error or "Recording failed")
            self._set_state(VoicePipelineState.READY)
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error=capture_result.error,
            )
        
        # Transcribe
        self._set_state(VoicePipelineState.TRANSCRIBING)
        
        if not self._stt:
            capture_result.clear()
            self._handle_failure("STT not initialized")
            self._set_state(VoicePipelineState.READY)
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error="Speech recognition not available",
            )
        
        # Transcribe and clear audio (audio is discarded here)
        transcription = self._stt.transcribe_and_clear(capture_result.audio)
        
        # Process result
        if transcription.status == STTStatus.NO_SPEECH:
            self._set_state(VoicePipelineState.READY)
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error="No speech detected",
            )
        
        if transcription.status in (STTStatus.TIMEOUT, STTStatus.MODEL_ERROR, STTStatus.AUDIO_ERROR):
            self._handle_failure(transcription.error or "Transcription failed")
            self._set_state(VoicePipelineState.READY)
            return VoiceInputResult(
                success=False,
                text="",
                confidence=0.0,
                needs_confirmation=False,
                error=transcription.error,
            )
        
        # Success (possibly with low confidence)
        self._consecutive_failures = 0
        self._set_state(VoicePipelineState.READY)
        
        needs_confirmation = transcription.needs_confirmation and self._config.confirm_ambiguous
        
        logger.info(f"Voice input: '{transcription.text}' (confidence: {transcription.confidence:.2f})")
        
        return VoiceInputResult(
            success=True,
            text=transcription.text,
            confidence=transcription.confidence,
            needs_confirmation=needs_confirmation,
            error=None,
        )
    
    def cancel_listening(self) -> None:
        """
        Cancel recording in progress.
        
        Discards all audio without transcription.
        """
        if self._capture:
            self._capture.cancel_recording()
        
        self._set_state(VoicePipelineState.READY)
        logger.info("Recording cancelled")
    
    def speak(self, text: str) -> SpeakResult:
        """
        Speak approved text using TTS.
        
        CRITICAL: Only call this with text that has been:
        1. Generated by the Planner
        2. Approved by the Executor
        3. Shown to the user
        
        NEVER speak arbitrary or unverified content.
        """
        if not self.is_enabled:
            return SpeakResult(
                status="disabled",
                duration_seconds=0.0,
                error="Voice not enabled",
            )
        
        if not self._tts:
            return SpeakResult(
                status="error",
                duration_seconds=0.0,
                error="TTS not initialized",
            )
        
        if not text or not text.strip():
            return SpeakResult(
                status="success",
                duration_seconds=0.0,
                error=None,
            )
        
        self._set_state(VoicePipelineState.SPEAKING)
        
        try:
            result = self._tts.speak(text)
            return result
        finally:
            self._set_state(VoicePipelineState.READY)
    
    def stop_speaking(self) -> None:
        """Stop TTS output immediately."""
        if self._tts:
            self._tts.stop()
        
        if self._state == VoicePipelineState.SPEAKING:
            self._set_state(VoicePipelineState.READY)
    
    def _handle_failure(self, error: str) -> None:
        """Handle a failure and potentially auto-disable."""
        logger.warning(f"Voice failure: {error}")
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= self._config.max_consecutive_failures:
            logger.error(f"Too many consecutive failures ({self._consecutive_failures}), disabling voice")
            self.disable()
    
    def load_stt_model(self) -> bool:
        """
        Pre-load the STT model.
        
        Can be called to avoid first-use delay.
        """
        if not self._stt:
            return False
        
        return self._stt.load_model()
    
    def get_status(self) -> dict:
        """Get current pipeline status for UI."""
        return {
            "enabled": self.is_enabled,
            "state": self._state.value,
            "stt_loaded": self._stt.is_loaded if self._stt else False,
            "capture_available": self._capture.is_available if self._capture else False,
            "tts_available": self._tts.is_available if self._tts else False,
            "consecutive_failures": self._consecutive_failures,
        }


# ==================== FACTORY ====================

def create_voice_pipeline(
    config: Optional[VoiceConfig] = None,
    **kwargs
) -> VoicePipeline:
    """
    Create a voice pipeline with the given configuration.
    
    Voice is DISABLED by default - must be explicitly enabled.
    """
    if config is None:
        config = VoiceConfig(**kwargs)
    
    return VoicePipeline(config)
