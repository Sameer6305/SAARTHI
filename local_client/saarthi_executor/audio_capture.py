"""
Audio Capture Module
====================

Robust audio capture with proper lifecycle management.

ROOT CAUSE ANALYSIS - Current issues:
1. Stream not properly closed on errors
2. No proper handling of device disconnection
3. Buffer accumulation without size limits
4. Callback exceptions can crash the stream
5. No audio level monitoring

SOLUTION:
1. Context manager for stream lifecycle
2. Ring buffer with size limits
3. Exception handling in callback
4. Device availability checking
5. Level monitoring for debugging
"""

import numpy as np
import sounddevice as sd
import threading
import time
import logging
from typing import Optional, Callable, List
from dataclasses import dataclass
from collections import deque
from contextlib import contextmanager

from .robust_vad import RobustVAD, VADConfig, VADState

logger = logging.getLogger(__name__)


@dataclass
class AudioCaptureConfig:
    """Audio capture configuration."""
    
    # Sample rate (Whisper works best at 16kHz)
    sample_rate: int = 16000
    
    # Number of channels (mono for speech)
    channels: int = 1
    
    # Frame duration in milliseconds
    frame_duration_ms: int = 30
    
    # Maximum buffer size in seconds
    max_buffer_seconds: float = 60.0
    
    # Device index (None = default)
    device_index: Optional[int] = None
    
    # Audio dtype
    dtype: str = 'float32'
    
    # Enable audio level monitoring
    monitor_levels: bool = True
    
    # Callback for audio level updates
    level_callback: Optional[Callable[[float], None]] = None


class AudioBuffer:
    """
    Thread-safe audio buffer with size limits.
    
    Uses a deque internally for O(1) append/popleft.
    Provides numpy array output for processing.
    """
    
    def __init__(self, max_frames: int = 100000):
        self._buffer: deque = deque(maxlen=max_frames)
        self._lock = threading.Lock()
        self._total_samples = 0
    
    def append(self, frame: np.ndarray):
        """Append audio frame to buffer."""
        with self._lock:
            self._buffer.append(frame.copy())
            self._total_samples += len(frame)
    
    def get_all(self) -> Optional[np.ndarray]:
        """Get all buffered audio as a single numpy array."""
        with self._lock:
            if not self._buffer:
                return None
            return np.concatenate(list(self._buffer))
    
    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()
            self._total_samples = 0
    
    def __len__(self):
        """Return number of frames in buffer."""
        with self._lock:
            return len(self._buffer)
    
    @property
    def total_samples(self) -> int:
        """Total samples currently in buffer."""
        with self._lock:
            return self._total_samples


class AudioCaptureError(Exception):
    """Audio capture error."""
    pass


class AudioCapture:
    """
    Robust audio capture with VAD integration.
    
    USAGE:
    ```python
    config = AudioCaptureConfig()
    vad_config = VADConfig()
    
    capture = AudioCapture(config, vad_config)
    
    # Record with automatic VAD stop
    audio = capture.record_with_vad()
    
    # Or record for fixed duration
    audio = capture.record_fixed(duration=5.0)
    ```
    """
    
    def __init__(self, config: Optional[AudioCaptureConfig] = None, vad_config: Optional[VADConfig] = None):
        self.config = config or AudioCaptureConfig()
        
        # VAD
        self._vad = RobustVAD(vad_config)
        
        # Buffer
        max_frames = int(self.config.max_buffer_seconds * self.config.sample_rate / 
                        (self.config.sample_rate * self.config.frame_duration_ms / 1000))
        self._buffer = AudioBuffer(max_frames=max_frames)
        
        # Frame size
        self._frame_size = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        
        # Stream state
        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._should_stop = threading.Event()
        self._error: Optional[Exception] = None
        
        # Level monitoring
        self._current_level: float = 0.0
        self._peak_level: float = 0.0
        
        # Callbacks
        self._on_speech_start: Optional[Callable] = None
        self._on_speech_end: Optional[Callable] = None
        self._on_level_update: Optional[Callable[[float], None]] = None
    
    def _check_device(self) -> bool:
        """Check if audio device is available."""
        try:
            devices = sd.query_devices()
            if self.config.device_index is not None:
                device = sd.query_devices(self.config.device_index)
                if device['max_input_channels'] < self.config.channels:
                    logger.error(f"Device {self.config.device_index} doesn't support {self.config.channels} channels")
                    return False
            return True
        except Exception as e:
            logger.error(f"Device check failed: {e}")
            return False
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Audio stream callback. Called from audio thread."""
        try:
            if status:
                logger.warning(f"Audio status: {status}")
            
            if not self._is_recording:
                return
            
            # Copy frame data
            frame = indata.copy().flatten()
            
            # Add to buffer
            self._buffer.append(frame)
            
            # Level monitoring
            if self.config.monitor_levels:
                rms = np.sqrt(np.mean(frame ** 2))
                self._current_level = rms
                self._peak_level = max(self._peak_level, rms)
                
                if self._on_level_update:
                    try:
                        self._on_level_update(rms)
                    except:
                        pass
            
            # VAD processing
            state, is_speech = self._vad.process_frame(frame)
            
            # Check for speech start
            if state == VADState.SPEECH_DETECTED and self._on_speech_start:
                try:
                    self._on_speech_start()
                except:
                    pass
            
            # Check if VAD says to stop
            if self._vad.should_stop():
                self._should_stop.set()
                if self._on_speech_end:
                    try:
                        self._on_speech_end()
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Audio callback error: {e}")
            self._error = e
            self._should_stop.set()
    
    @contextmanager
    def _stream_context(self):
        """Context manager for audio stream lifecycle."""
        stream = None
        try:
            stream = sd.InputStream(
                callback=self._audio_callback,
                channels=self.config.channels,
                samplerate=self.config.sample_rate,
                dtype=self.config.dtype,
                blocksize=self._frame_size,
                device=self.config.device_index,
            )
            stream.start()
            yield stream
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except:
                    pass
    
    def record_with_vad(
        self,
        timeout: Optional[float] = None,
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
        on_level_update: Optional[Callable[[float], None]] = None,
    ) -> Optional[np.ndarray]:
        """
        Record audio with automatic VAD-based stop.
        
        Args:
            timeout: Maximum recording time (overrides config)
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends
            on_level_update: Callback for audio level updates
            
        Returns:
            Audio data as numpy array, or None if no speech detected
        """
        if not self._check_device():
            raise AudioCaptureError("Audio device not available")
        
        # Reset state
        self._buffer.clear()
        self._vad.reset()
        self._vad.start()
        self._should_stop.clear()
        self._error = None
        self._peak_level = 0.0
        
        # Set callbacks
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end
        self._on_level_update = on_level_update
        
        # Calculate timeout
        max_duration = timeout or self._vad.config.max_recording_duration
        
        self._is_recording = True
        start_time = time.time()
        
        try:
            with self._stream_context():
                while not self._should_stop.is_set():
                    # Check timeout
                    if time.time() - start_time > max_duration:
                        logger.info("Recording timeout reached")
                        break
                    
                    # Check for errors
                    if self._error:
                        raise AudioCaptureError(f"Recording error: {self._error}")
                    
                    # Small sleep to prevent busy waiting
                    time.sleep(0.01)
        
        finally:
            self._is_recording = False
            self._on_speech_start = None
            self._on_speech_end = None
            self._on_level_update = None
        
        # Get recorded audio
        audio = self._buffer.get_all()
        
        if audio is None or len(audio) < self.config.sample_rate * 0.3:
            logger.info("No significant audio captured")
            return None
        
        duration = len(audio) / self.config.sample_rate
        logger.info(f"Recorded {duration:.2f}s of audio (VAD state: {self._vad.get_state().value})")
        
        return audio
    
    def record_fixed(self, duration: float) -> Optional[np.ndarray]:
        """
        Record audio for a fixed duration.
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            Audio data as numpy array
        """
        if not self._check_device():
            raise AudioCaptureError("Audio device not available")
        
        # Reset state
        self._buffer.clear()
        self._should_stop.clear()
        self._error = None
        
        self._is_recording = True
        start_time = time.time()
        
        try:
            with self._stream_context():
                while time.time() - start_time < duration:
                    if self._error:
                        raise AudioCaptureError(f"Recording error: {self._error}")
                    time.sleep(0.01)
        
        finally:
            self._is_recording = False
        
        return self._buffer.get_all()
    
    def stop(self):
        """Stop current recording."""
        self._should_stop.set()
    
    def get_vad_stats(self) -> dict:
        """Get VAD statistics."""
        return self._vad.get_stats()
    
    def get_audio_level(self) -> float:
        """Get current audio level (RMS)."""
        return self._current_level
    
    def get_peak_level(self) -> float:
        """Get peak audio level since recording started."""
        return self._peak_level


def create_audio_capture(
    sample_rate: int = 16000,
    silence_duration: float = 1.5,
    max_recording: float = 30.0,
) -> AudioCapture:
    """Create an AudioCapture instance with common settings."""
    audio_config = AudioCaptureConfig(
        sample_rate=sample_rate,
    )
    
    vad_config = VADConfig(
        sample_rate=sample_rate,
        silence_duration=silence_duration,
        max_recording_duration=max_recording,
    )
    
    return AudioCapture(audio_config, vad_config)
