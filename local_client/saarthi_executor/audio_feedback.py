"""
Audio Feedback Module
=====================

Provides non-intrusive audio feedback for state transitions.

DESIGN PRINCIPLES:
1. Non-blocking beeps (background thread)
2. No interference with STT/VAD (plays after audio capture stops)
3. Configurable and mockable for tests
4. Native Windows API only (winsound)

BEEP FREQUENCIES:
- Start listening: 1000 Hz (high, attention-grabbing)
- Stop listening: 800 Hz (lower, confirmation)
- Success: 1200 Hz (bright, positive)
- Error: 400 Hz (low, warning)
"""

import logging
import threading
import time
from typing import Optional, Callable
from enum import Enum, auto

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of audio feedback."""
    LISTENING_START = auto()    # SPACE pressed, starting to listen
    LISTENING_STOP = auto()     # VAD complete, processing speech
    SUCCESS = auto()             # Action completed successfully
    ERROR = auto()               # Unrecoverable error
    WARNING = auto()             # Recoverable issue


class AudioFeedback:
    """
    Manages audio feedback (beeps) for state transitions.
    
    Uses winsound on Windows for native beeps.
    Beeps are non-blocking and run in background threads.
    
    INTERVIEW TALKING POINTS:
    - Why background threads? Don't block main loop or audio capture
    - Why winsound? Native, no dependencies, works on all Windows
    - Why configurable? Tests must not play sounds, users may disable
    - Why different frequencies? Distinct audio signatures for each event
    """
    
    # Beep configurations: (frequency_hz, duration_ms)
    BEEP_CONFIGS = {
        FeedbackType.LISTENING_START: (1000, 100),   # High pitch, short
        FeedbackType.LISTENING_STOP: (800, 80),      # Lower pitch, shorter
        FeedbackType.SUCCESS: (1200, 120),            # Bright, positive
        FeedbackType.ERROR: (400, 200),               # Low, warning
        FeedbackType.WARNING: (600, 150),             # Medium, caution
    }
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: Whether to actually play beeps (False for tests)
        """
        self._enabled = enabled
        self._beep_func: Optional[Callable[[int, int], None]] = None
        
        # Try to import winsound (Windows only)
        if enabled:
            try:
                import winsound
                self._beep_func = winsound.Beep
                logger.info("Audio feedback enabled (winsound)")
            except ImportError:
                logger.warning("winsound not available, audio feedback disabled")
                self._enabled = False
        else:
            logger.info("Audio feedback disabled (test mode or user preference)")
    
    def play(self, feedback_type: FeedbackType, async_mode: bool = True):
        """
        Play audio feedback for a state transition.
        
        Args:
            feedback_type: Type of feedback to play
            async_mode: If True, play in background thread (default)
        """
        if not self._enabled or self._beep_func is None:
            return
        
        frequency, duration = self.BEEP_CONFIGS.get(
            feedback_type,
            (1000, 100)  # Default
        )
        
        if async_mode:
            # Play in background thread to avoid blocking
            threading.Thread(
                target=self._beep_safe,
                args=(frequency, duration),
                daemon=True,
                name=f"beep_{feedback_type.name}"
            ).start()
        else:
            self._beep_safe(frequency, duration)
    
    def _beep_safe(self, frequency: int, duration: int):
        """
        Safely play a beep with error handling.
        
        Args:
            frequency: Beep frequency in Hz
            duration: Beep duration in milliseconds
        """
        try:
            self._beep_func(frequency, duration)
            logger.debug(f"Played beep: {frequency}Hz for {duration}ms")
        except Exception as e:
            logger.warning(f"Beep failed: {e}")
    
    def play_listening_start(self):
        """Play beep for starting to listen."""
        self.play(FeedbackType.LISTENING_START)
    
    def play_listening_stop(self):
        """Play beep for stopping listening."""
        self.play(FeedbackType.LISTENING_STOP)
    
    def play_success(self):
        """Play beep for successful action."""
        self.play(FeedbackType.SUCCESS)
    
    def play_error(self):
        """Play beep for error."""
        # Double beep for errors
        if self._enabled and self._beep_func:
            threading.Thread(
                target=self._double_beep_error,
                daemon=True,
                name="beep_error_double"
            ).start()
    
    def _double_beep_error(self):
        """Play double beep for errors."""
        try:
            freq, dur = self.BEEP_CONFIGS[FeedbackType.ERROR]
            self._beep_func(freq, dur)
            time.sleep(0.15)  # Short pause between beeps
            self._beep_func(freq, dur)
            logger.debug("Played double error beep")
        except Exception as e:
            logger.warning(f"Error beep failed: {e}")
    
    def enable(self):
        """Enable audio feedback."""
        if self._beep_func is not None:
            self._enabled = True
            logger.info("Audio feedback enabled")
    
    def disable(self):
        """Disable audio feedback."""
        self._enabled = False
        logger.info("Audio feedback disabled")
    
    @property
    def is_enabled(self) -> bool:
        """Check if audio feedback is enabled."""
        return self._enabled


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_audio_feedback(enabled: bool = True) -> AudioFeedback:
    """
    Create an audio feedback instance.
    
    Args:
        enabled: Whether to play sounds (False for tests)
    
    Returns:
        AudioFeedback instance
    """
    return AudioFeedback(enabled=enabled)


# =============================================================================
# MOCK FOR TESTING
# =============================================================================

class MockAudioFeedback(AudioFeedback):
    """
    Mock audio feedback for testing.
    
    Records what beeps were played without making actual sounds.
    """
    
    def __init__(self):
        # Don't call super().__init__() to avoid winsound import
        self._enabled = True
        self._beep_func = None
        self.played_beeps = []  # Track what was played
    
    def play(self, feedback_type: FeedbackType, async_mode: bool = True):
        """Record beep instead of playing it."""
        self.played_beeps.append(feedback_type)
        logger.debug(f"Mock beep: {feedback_type.name}")
    
    def play_error(self):
        """Record double error beep synchronously for testing."""
        self.played_beeps.append(FeedbackType.ERROR)
        self.played_beeps.append(FeedbackType.ERROR)
    
    def _beep_safe(self, frequency: int, duration: int):
        """No-op for mock."""
        pass
    
    def _double_beep_error(self):
        """Record double beep."""
        self.played_beeps.append(FeedbackType.ERROR)
        self.played_beeps.append(FeedbackType.ERROR)
    
    def reset(self):
        """Clear recorded beeps."""
        self.played_beeps.clear()
