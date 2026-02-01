"""
Robust Voice Activity Detection (VAD) Module
=============================================

Provides deterministic, reliable speech detection with multiple strategies.

ROOT CAUSE ANALYSIS - Why current VAD fails:
1. Simple RMS threshold doesn't account for ambient noise
2. No adaptive threshold based on environment
3. Silence counter resets improperly
4. No speech onset detection - starts counting silence before speech even starts
5. Frame size (30ms) is too fine-grained for robust detection

SOLUTION:
1. Adaptive threshold with noise floor estimation
2. State machine: WAITING → SPEECH_DETECTED → RECORDING → TRAILING_SILENCE → DONE
3. WebRTC VAD integration (when available) for professional detection
4. Minimum speech duration requirement before considering silence
5. Debouncing to prevent false stops
"""

import numpy as np
import logging
from enum import Enum
from typing import Optional, Tuple, List, Callable
from dataclasses import dataclass, field
from collections import deque
import time

logger = logging.getLogger(__name__)


class VADState(Enum):
    """Voice Activity Detection states."""
    IDLE = "idle"
    WAITING_FOR_SPEECH = "waiting_for_speech"
    SPEECH_DETECTED = "speech_detected"
    RECORDING = "recording"
    TRAILING_SILENCE = "trailing_silence"
    DONE = "done"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class VADConfig:
    """VAD configuration with production-safe defaults."""
    
    # Sample rate (must match audio capture)
    sample_rate: int = 16000
    
    # Frame duration in milliseconds
    frame_duration_ms: int = 30
    
    # --- Threshold settings ---
    
    # Initial silence threshold (RMS)
    initial_threshold: float = 0.01
    
    # Adaptive threshold: multiply noise floor by this factor
    threshold_multiplier: float = 2.5
    
    # Minimum threshold to prevent over-sensitivity
    min_threshold: float = 0.005
    
    # Maximum threshold to ensure detection in noisy environments
    max_threshold: float = 0.1
    
    # --- Timing settings ---
    
    # Seconds of silence to trigger stop AFTER speech is detected
    silence_duration: float = 1.5
    
    # Minimum speech duration before silence detection kicks in
    min_speech_duration: float = 0.3
    
    # Maximum recording duration (hard stop)
    max_recording_duration: float = 30.0
    
    # Timeout waiting for speech to start
    speech_start_timeout: float = 10.0
    
    # --- Noise estimation ---
    
    # Seconds of audio to use for initial noise estimation
    noise_estimation_duration: float = 0.2
    
    # Number of frames to average for noise floor
    noise_average_frames: int = 10
    
    # --- Debouncing ---
    
    # Minimum consecutive speech frames to confirm speech start
    speech_onset_frames: int = 3
    
    # Minimum consecutive silence frames to confirm speech end
    silence_onset_frames: int = 5
    
    # --- WebRTC VAD settings (if available) ---
    
    # WebRTC VAD aggressiveness (0-3, higher = more aggressive filtering)
    webrtc_aggressiveness: int = 2
    
    # Whether to prefer WebRTC VAD when available
    prefer_webrtc: bool = True


class RobustVAD:
    """
    Robust Voice Activity Detection with state machine and adaptive threshold.
    
    DESIGN PRINCIPLES:
    1. State machine ensures deterministic behavior
    2. Adaptive threshold handles different environments
    3. Debouncing prevents false triggers
    4. Multiple detection strategies (RMS, WebRTC, energy)
    5. Clear start/stop guarantees
    """
    
    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()
        
        # State
        self._state = VADState.IDLE
        self._state_start_time: float = 0
        
        # Counters
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._total_frame_count = 0
        
        # Threshold
        self._current_threshold = self.config.initial_threshold
        self._noise_floor = 0.0
        self._noise_samples: deque = deque(maxlen=self.config.noise_average_frames)
        
        # Timing
        self._recording_start_time: float = 0
        self._last_speech_time: float = 0
        
        # Frame size
        self._frame_size = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        
        # WebRTC VAD (optional)
        self._webrtc_vad = None
        self._init_webrtc_vad()
        
        # Statistics for debugging
        self._stats = {
            "frames_processed": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "threshold_adjustments": 0,
            "false_starts": 0,
        }
    
    def _init_webrtc_vad(self):
        """Initialize WebRTC VAD if available."""
        if not self.config.prefer_webrtc:
            return
        
        try:
            import webrtcvad
            self._webrtc_vad = webrtcvad.Vad(self.config.webrtc_aggressiveness)
            logger.info(f"WebRTC VAD initialized (aggressiveness={self.config.webrtc_aggressiveness})")
        except ImportError:
            logger.info("WebRTC VAD not available, using RMS-based detection")
        except Exception as e:
            logger.warning(f"WebRTC VAD init failed: {e}")
    
    def reset(self):
        """Reset VAD to initial state."""
        self._state = VADState.IDLE
        self._state_start_time = 0
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._total_frame_count = 0
        self._recording_start_time = 0
        self._last_speech_time = 0
        self._noise_samples.clear()
        self._current_threshold = self.config.initial_threshold
    
    def start(self):
        """Start VAD detection. Call before processing frames."""
        self.reset()
        self._state = VADState.WAITING_FOR_SPEECH
        self._state_start_time = time.time()
        self._recording_start_time = time.time()
        logger.debug("VAD started, waiting for speech")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[VADState, bool]:
        """
        Process a single audio frame.
        
        Args:
            frame: Audio frame as numpy array (float32, -1 to 1)
            
        Returns:
            Tuple of (current_state, is_speech_in_frame)
        """
        self._total_frame_count += 1
        self._stats["frames_processed"] += 1
        
        # Ensure correct shape
        if frame.ndim > 1:
            frame = frame.flatten()
        
        # Calculate frame energy/RMS
        rms = np.sqrt(np.mean(frame ** 2))
        
        # Detect speech in this frame
        is_speech = self._detect_speech(frame, rms)
        
        if is_speech:
            self._stats["speech_frames"] += 1
        else:
            self._stats["silence_frames"] += 1
        
        # Update noise floor during initial period
        if self._state == VADState.WAITING_FOR_SPEECH:
            self._update_noise_floor(rms)
        
        # State machine
        self._update_state(is_speech, rms)
        
        return self._state, is_speech
    
    def _detect_speech(self, frame: np.ndarray, rms: float) -> bool:
        """
        Detect if frame contains speech using multiple strategies.
        
        Priority:
        1. WebRTC VAD (if available and frame is valid)
        2. RMS threshold with adaptive adjustment
        """
        # Try WebRTC VAD first
        if self._webrtc_vad:
            try:
                # WebRTC VAD expects 16-bit PCM
                pcm = (frame * 32767).astype(np.int16).tobytes()
                if len(pcm) == self._frame_size * 2:  # 2 bytes per sample
                    return self._webrtc_vad.is_speech(pcm, self.config.sample_rate)
            except Exception as e:
                logger.debug(f"WebRTC VAD failed, falling back to RMS: {e}")
        
        # Fall back to RMS threshold
        return rms > self._current_threshold
    
    def _update_noise_floor(self, rms: float):
        """Update noise floor estimate during initial period."""
        elapsed = time.time() - self._state_start_time
        
        if elapsed < self.config.noise_estimation_duration:
            self._noise_samples.append(rms)
            
            if len(self._noise_samples) >= 3:
                # Use median to be robust against speech during estimation
                self._noise_floor = np.median(list(self._noise_samples))
                
                # Update threshold adaptively
                new_threshold = self._noise_floor * self.config.threshold_multiplier
                new_threshold = max(self.config.min_threshold, min(self.config.max_threshold, new_threshold))
                
                if abs(new_threshold - self._current_threshold) > 0.001:
                    self._current_threshold = new_threshold
                    self._stats["threshold_adjustments"] += 1
                    logger.debug(f"Adaptive threshold: {self._current_threshold:.4f} (noise floor: {self._noise_floor:.4f})")
    
    def _update_state(self, is_speech: bool, rms: float):
        """Update state machine based on speech detection."""
        current_time = time.time()
        elapsed = current_time - self._state_start_time
        total_elapsed = current_time - self._recording_start_time
        
        # Hard timeout check
        if total_elapsed > self.config.max_recording_duration:
            self._state = VADState.TIMEOUT
            logger.info("VAD: max recording duration reached")
            return
        
        if self._state == VADState.WAITING_FOR_SPEECH:
            # Check for speech start timeout
            if elapsed > self.config.speech_start_timeout:
                self._state = VADState.TIMEOUT
                logger.info("VAD: speech start timeout")
                return
            
            if is_speech:
                self._speech_frame_count += 1
                self._silence_frame_count = 0
                
                # Debounce: require consecutive speech frames
                if self._speech_frame_count >= self.config.speech_onset_frames:
                    self._state = VADState.SPEECH_DETECTED
                    self._state_start_time = current_time
                    self._last_speech_time = current_time
                    logger.debug("VAD: speech detected")
            else:
                self._speech_frame_count = 0
        
        elif self._state == VADState.SPEECH_DETECTED:
            # Transition to recording after speech confirmed
            self._state = VADState.RECORDING
            self._state_start_time = current_time
            logger.debug("VAD: recording started")
            self._update_state(is_speech, rms)  # Process this frame in new state
        
        elif self._state == VADState.RECORDING:
            if is_speech:
                self._speech_frame_count += 1
                self._silence_frame_count = 0
                self._last_speech_time = current_time
            else:
                self._silence_frame_count += 1
                
                # Check if enough speech has been recorded
                speech_duration = self._last_speech_time - self._recording_start_time
                if speech_duration >= self.config.min_speech_duration:
                    # Check for silence onset
                    if self._silence_frame_count >= self.config.silence_onset_frames:
                        self._state = VADState.TRAILING_SILENCE
                        self._state_start_time = current_time
                        logger.debug("VAD: trailing silence started")
        
        elif self._state == VADState.TRAILING_SILENCE:
            if is_speech:
                # Speech resumed, go back to recording
                self._state = VADState.RECORDING
                self._state_start_time = current_time
                self._silence_frame_count = 0
                self._speech_frame_count = 1
                self._last_speech_time = current_time
                self._stats["false_starts"] += 1
                logger.debug("VAD: speech resumed, back to recording")
            else:
                self._silence_frame_count += 1
                
                # Check if silence duration exceeded
                silence_time = current_time - self._state_start_time
                if silence_time >= self.config.silence_duration:
                    self._state = VADState.DONE
                    logger.debug(f"VAD: done (silence duration: {silence_time:.2f}s)")
    
    def is_done(self) -> bool:
        """Check if VAD detection is complete."""
        return self._state in (VADState.DONE, VADState.TIMEOUT, VADState.ERROR)
    
    def should_stop(self) -> bool:
        """Check if recording should stop."""
        return self.is_done()
    
    def get_state(self) -> VADState:
        """Get current VAD state."""
        return self._state
    
    def get_stats(self) -> dict:
        """Get VAD statistics for debugging."""
        return {
            **self._stats,
            "state": self._state.value,
            "current_threshold": self._current_threshold,
            "noise_floor": self._noise_floor,
            "speech_frames": self._speech_frame_count,
            "silence_frames": self._silence_frame_count,
        }
    
    def get_recording_duration(self) -> float:
        """Get total recording duration so far."""
        if self._recording_start_time == 0:
            return 0
        return time.time() - self._recording_start_time


class SimpleRMSDetector:
    """
    Simple RMS-based speech detector for fallback.
    More lenient than full VAD, suitable for short commands.
    """
    
    def __init__(self, threshold: float = 0.01, silence_duration: float = 1.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.sample_rate = sample_rate
        
        self._speech_detected = False
        self._silence_start: Optional[float] = None
        self._frame_size = int(sample_rate * 0.03)  # 30ms
    
    def reset(self):
        """Reset detector state."""
        self._speech_detected = False
        self._silence_start = None
    
    def process_frame(self, frame: np.ndarray) -> Tuple[bool, bool]:
        """
        Process frame and return (is_speech, should_stop).
        """
        if frame.ndim > 1:
            frame = frame.flatten()
        
        rms = np.sqrt(np.mean(frame ** 2))
        is_speech = rms > self.threshold
        
        if is_speech:
            self._speech_detected = True
            self._silence_start = None
        elif self._speech_detected:
            if self._silence_start is None:
                self._silence_start = time.time()
            elif time.time() - self._silence_start >= self.silence_duration:
                return False, True  # Not speech, should stop
        
        return is_speech, False


def create_vad(config: Optional[VADConfig] = None) -> RobustVAD:
    """Create a VAD instance with production defaults."""
    return RobustVAD(config or VADConfig())
