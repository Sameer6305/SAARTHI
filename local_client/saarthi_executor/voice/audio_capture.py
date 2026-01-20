"""
Audio Capture Module
====================

Push-to-talk audio capture with strict privacy guarantees.

PRIVACY INVARIANTS:
- Recording ONLY while button/key is pressed
- Audio exists ONLY in memory (never written to disk)
- Recording state is ALWAYS visible to user
- Capture stops IMMEDIATELY on release
- No background threads that record audio

SECURITY:
- Audio buffer is cleared after use
- No raw audio persistence
- Maximum recording duration enforced
"""

import logging
import threading
import time
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CaptureState(Enum):
    """Audio capture state machine."""
    IDLE = "idle"           # Not recording, mic not accessed
    PREPARING = "preparing" # Initializing mic (brief)
    RECORDING = "recording" # Actively recording (user holding button)
    PROCESSING = "processing" # Recording done, processing audio
    ERROR = "error"         # Error state


@dataclass
class AudioBuffer:
    """
    In-memory audio buffer.
    
    SECURITY: Audio data is cleared after use.
    """
    data: np.ndarray
    sample_rate: int
    duration_seconds: float
    
    def clear(self) -> None:
        """Securely clear audio data from memory."""
        if self.data is not None:
            # Overwrite with zeros before releasing
            self.data.fill(0)
            self.data = np.array([], dtype=np.float32)
        self.duration_seconds = 0.0
        logger.debug("Audio buffer cleared")


@dataclass
class CaptureResult:
    """Result of an audio capture session."""
    success: bool
    audio: Optional[AudioBuffer]
    error: Optional[str]
    duration_seconds: float
    
    def clear(self) -> None:
        """Clear any audio data."""
        if self.audio:
            self.audio.clear()


class PushToTalkCapture:
    """
    Push-to-talk audio capture.
    
    Recording happens ONLY while user holds the button.
    Audio exists ONLY in memory.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        max_duration: float = 30.0,
        min_duration: float = 0.5,
        on_state_change: Optional[Callable[[CaptureState], None]] = None,
    ):
        """
        Initialize capture.
        
        Args:
            sample_rate: Audio sample rate (Whisper needs 16kHz)
            max_duration: Maximum recording duration (seconds)
            min_duration: Minimum valid recording duration (seconds)
            on_state_change: Callback when capture state changes
        """
        self._sample_rate = sample_rate
        self._max_duration = max_duration
        self._min_duration = min_duration
        self._on_state_change = on_state_change
        
        # State
        self._state = CaptureState.IDLE
        self._recording = False
        self._lock = threading.Lock()
        
        # Audio data (in-memory only)
        self._audio_chunks: List[np.ndarray] = []
        self._stream = None
        
        # Check for audio library
        self._audio_available = self._check_audio_available()
    
    def _check_audio_available(self) -> bool:
        """Check if audio capture is available."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            # Check for input device
            for d in devices:
                if d.get('max_input_channels', 0) > 0:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Audio not available: {e}")
            return False
    
    @property
    def state(self) -> CaptureState:
        """Current capture state."""
        return self._state
    
    @property
    def is_available(self) -> bool:
        """Whether audio capture is available."""
        return self._audio_available
    
    @property
    def is_recording(self) -> bool:
        """Whether currently recording."""
        return self._state == CaptureState.RECORDING
    
    def _set_state(self, new_state: CaptureState) -> None:
        """Update state and notify callback."""
        old_state = self._state
        self._state = new_state
        
        if self._on_state_change and old_state != new_state:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def start_recording(self) -> bool:
        """
        Start recording (called when user PRESSES button).
        
        Returns True if recording started successfully.
        """
        if not self._audio_available:
            logger.error("Audio not available")
            return False
        
        with self._lock:
            if self._recording:
                logger.warning("Already recording")
                return True
            
            try:
                import sounddevice as sd
                
                self._set_state(CaptureState.PREPARING)
                
                # Clear any previous audio
                self._audio_chunks = []
                
                # Start input stream
                self._stream = sd.InputStream(
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype=np.float32,
                    callback=self._audio_callback,
                    blocksize=1024,
                )
                self._stream.start()
                self._recording = True
                self._record_start_time = time.time()
                
                self._set_state(CaptureState.RECORDING)
                
                logger.info("Recording started (push-to-talk)")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start recording: {e}")
                self._set_state(CaptureState.ERROR)
                return False
    
    def stop_recording(self) -> CaptureResult:
        """
        Stop recording (called when user RELEASES button).
        
        Returns the captured audio.
        """
        with self._lock:
            if not self._recording:
                return CaptureResult(
                    success=False,
                    audio=None,
                    error="Not recording",
                    duration_seconds=0.0,
                )
            
            try:
                self._set_state(CaptureState.PROCESSING)
                
                # Stop stream
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                
                self._recording = False
                duration = time.time() - self._record_start_time
                
                # Check minimum duration
                if duration < self._min_duration:
                    self._clear_audio_chunks()
                    self._set_state(CaptureState.IDLE)
                    return CaptureResult(
                        success=False,
                        audio=None,
                        error=f"Recording too short ({duration:.1f}s < {self._min_duration}s)",
                        duration_seconds=duration,
                    )
                
                # Combine audio chunks
                if not self._audio_chunks:
                    self._set_state(CaptureState.IDLE)
                    return CaptureResult(
                        success=False,
                        audio=None,
                        error="No audio captured",
                        duration_seconds=0.0,
                    )
                
                audio_data = np.concatenate(self._audio_chunks)
                
                # Clear chunks immediately
                self._clear_audio_chunks()
                
                # Create audio buffer
                audio_buffer = AudioBuffer(
                    data=audio_data,
                    sample_rate=self._sample_rate,
                    duration_seconds=len(audio_data) / self._sample_rate,
                )
                
                self._set_state(CaptureState.IDLE)
                
                logger.info(f"Recording stopped: {audio_buffer.duration_seconds:.1f}s captured")
                
                return CaptureResult(
                    success=True,
                    audio=audio_buffer,
                    error=None,
                    duration_seconds=audio_buffer.duration_seconds,
                )
                
            except Exception as e:
                logger.error(f"Failed to stop recording: {e}")
                self._clear_audio_chunks()
                self._set_state(CaptureState.ERROR)
                return CaptureResult(
                    success=False,
                    audio=None,
                    error=str(e),
                    duration_seconds=0.0,
                )
    
    def cancel_recording(self) -> None:
        """Cancel recording and discard all audio."""
        with self._lock:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            
            self._recording = False
            self._clear_audio_chunks()
            self._set_state(CaptureState.IDLE)
            
            logger.info("Recording cancelled")
    
    def _audio_callback(
        self, 
        indata: np.ndarray, 
        frames: int, 
        time_info, 
        status
    ) -> None:
        """Callback for audio stream - stores chunks in memory."""
        if status:
            logger.warning(f"Audio status: {status}")
        
        # Check max duration
        if hasattr(self, '_record_start_time'):
            elapsed = time.time() - self._record_start_time
            if elapsed > self._max_duration:
                # Will be handled on stop
                return
        
        # Store chunk (copy to avoid reference issues)
        self._audio_chunks.append(indata.copy().flatten())
    
    def _clear_audio_chunks(self) -> None:
        """Securely clear audio chunks from memory."""
        for chunk in self._audio_chunks:
            chunk.fill(0)
        self._audio_chunks = []


@contextmanager
def push_to_talk_session(
    sample_rate: int = 16000,
    max_duration: float = 30.0,
):
    """
    Context manager for push-to-talk recording.
    
    Ensures audio is always cleaned up.
    
    Usage:
        with push_to_talk_session() as capture:
            capture.start_recording()
            # User holds button...
            result = capture.stop_recording()
            # Process result.audio
            result.clear()  # Always clear audio when done
    """
    capture = PushToTalkCapture(
        sample_rate=sample_rate,
        max_duration=max_duration,
    )
    try:
        yield capture
    finally:
        capture.cancel_recording()
