"""
Focus Mode System
==================

Explicit task/focus mode for reduced chatter and concise interactions.

PRODUCT GOALS:
- Users can say "start focus mode" when they need minimal distraction
- Responses become shorter, fewer confirmations
- Clear activation/deactivation vocabulary
- Visual indicator of mode (if visual system enabled)

DESIGN DECISIONS:

1. WHY EXPLICIT ACTIVATION?
   - No ambient guessing about user's state
   - User maintains control
   - Predictable behavior

2. WHAT CHANGES IN FOCUS MODE:
   - Shorter TTS responses (summaries, not full explanations)
   - No greeting/farewell spoken
   - No "I'll do that for you" chatter
   - Success/failure indicated by sound, not speech
   - Questions get bullet-point answers

3. WHAT STAYS THE SAME:
   - Full command recognition
   - Error messages (important to speak)
   - Confirmations for destructive actions (safety first)

INTERVIEW TALKING POINTS:
- Mode as state: Separate from the execution state machine
- Behavior modification: Strategy pattern for response generation
- User control: No AI inference, explicit commands only
"""

import logging
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class FocusModeLevel(Enum):
    """
    Levels of focus mode intensity.
    
    DEFAULT: Normal operation with full responses
    MINIMAL: Shorter responses, essential speech only
    SILENT: No speech except errors, sound feedback only
    """
    DEFAULT = auto()
    MINIMAL = auto()
    SILENT = auto()


@dataclass
class FocusModeConfig:
    """Configuration for focus mode behavior."""
    
    # TTS behavior
    speak_greetings: bool = True
    speak_confirmations: bool = True
    speak_answers: bool = True
    speak_errors: bool = True  # Always true in all modes
    
    # Response length
    max_answer_sentences: int = 10  # 0 = unlimited
    summarize_long_answers: bool = False
    
    # Confirmation behavior
    confirm_all_actions: bool = False
    sound_only_confirmations: bool = False
    
    # Chatter control
    use_filler_phrases: bool = True  # "Sure!", "Got it!"
    announce_intent: bool = True     # "Opening YouTube..."
    
    @classmethod
    def for_level(cls, level: FocusModeLevel) -> 'FocusModeConfig':
        """Get config for a focus mode level."""
        if level == FocusModeLevel.DEFAULT:
            return cls(
                speak_greetings=True,
                speak_confirmations=True,
                speak_answers=True,
                speak_errors=True,
                max_answer_sentences=10,
                summarize_long_answers=False,
                confirm_all_actions=False,
                sound_only_confirmations=False,
                use_filler_phrases=True,
                announce_intent=True,
            )
        elif level == FocusModeLevel.MINIMAL:
            return cls(
                speak_greetings=False,
                speak_confirmations=False,
                speak_answers=True,
                speak_errors=True,
                max_answer_sentences=3,
                summarize_long_answers=True,
                confirm_all_actions=False,
                sound_only_confirmations=True,
                use_filler_phrases=False,
                announce_intent=False,
            )
        elif level == FocusModeLevel.SILENT:
            return cls(
                speak_greetings=False,
                speak_confirmations=False,
                speak_answers=False,
                speak_errors=True,  # Safety: always speak errors
                max_answer_sentences=0,
                summarize_long_answers=True,
                confirm_all_actions=False,
                sound_only_confirmations=True,
                use_filler_phrases=False,
                announce_intent=False,
            )
        else:
            return cls()  # Default


@dataclass
class FocusModeState:
    """Current state of focus mode."""
    enabled: bool = False
    level: FocusModeLevel = FocusModeLevel.DEFAULT
    activated_at: Optional[float] = None
    auto_disable_after: Optional[float] = None  # Seconds, None = manual only
    
    def is_active(self) -> bool:
        """Check if focus mode is currently active."""
        if not self.enabled:
            return False
        
        # Check auto-disable
        if self.auto_disable_after and self.activated_at:
            elapsed = time.time() - self.activated_at
            if elapsed > self.auto_disable_after:
                return False
        
        return True


class FocusModeManager:
    """
    Manages focus mode state and behavior modifications.
    
    USAGE:
        manager = FocusModeManager()
        
        # Activate
        manager.activate(FocusModeLevel.MINIMAL)
        
        # Check behavior
        if manager.should_speak_greeting():
            tts.speak("Hello!")
        
        # Get current config
        config = manager.get_config()
        
        # Deactivate
        manager.deactivate()
    """
    
    # Activation phrases
    ACTIVATE_PHRASES = {
        # Minimal mode
        "start focus mode": FocusModeLevel.MINIMAL,
        "focus mode": FocusModeLevel.MINIMAL,
        "enable focus mode": FocusModeLevel.MINIMAL,
        "focus mode on": FocusModeLevel.MINIMAL,
        "be concise": FocusModeLevel.MINIMAL,
        "brief mode": FocusModeLevel.MINIMAL,
        "quiet mode": FocusModeLevel.MINIMAL,
        
        # Silent mode
        "silent mode": FocusModeLevel.SILENT,
        "mute mode": FocusModeLevel.SILENT,
        "no speech": FocusModeLevel.SILENT,
        "sounds only": FocusModeLevel.SILENT,
    }
    
    DEACTIVATE_PHRASES = [
        "stop focus mode",
        "end focus mode",
        "disable focus mode",
        "focus mode off",
        "normal mode",
        "verbose mode",
        "unmute",
    ]
    
    def __init__(self, on_change: Optional[Callable[[FocusModeState], None]] = None):
        self._state = FocusModeState()
        self._config = FocusModeConfig()
        self._on_change = on_change
    
    def activate(
        self,
        level: FocusModeLevel = FocusModeLevel.MINIMAL,
        duration: Optional[float] = None,
    ):
        """
        Activate focus mode.
        
        Args:
            level: Focus mode intensity
            duration: Auto-disable after this many seconds (None = manual)
        """
        self._state = FocusModeState(
            enabled=True,
            level=level,
            activated_at=time.time(),
            auto_disable_after=duration,
        )
        self._config = FocusModeConfig.for_level(level)
        
        logger.info(f"Focus mode activated: {level.name}")
        
        if self._on_change:
            self._on_change(self._state)
    
    def deactivate(self):
        """Deactivate focus mode, return to normal."""
        was_enabled = self._state.enabled
        
        self._state = FocusModeState()
        self._config = FocusModeConfig.for_level(FocusModeLevel.DEFAULT)
        
        if was_enabled:
            logger.info("Focus mode deactivated")
            
            if self._on_change:
                self._on_change(self._state)
    
    def is_active(self) -> bool:
        """Check if focus mode is currently active."""
        if not self._state.is_active():
            # Auto-expired, clean up
            if self._state.enabled:
                self.deactivate()
            return False
        return True
    
    def get_level(self) -> FocusModeLevel:
        """Get current focus mode level."""
        return self._state.level if self.is_active() else FocusModeLevel.DEFAULT
    
    def get_config(self) -> FocusModeConfig:
        """Get current behavior config."""
        if not self.is_active():
            return FocusModeConfig.for_level(FocusModeLevel.DEFAULT)
        return self._config
    
    def get_state(self) -> FocusModeState:
        """Get full state for debugging/display."""
        return self._state
    
    # Convenience methods for behavior checks
    
    def should_speak_greeting(self) -> bool:
        return self.get_config().speak_greetings
    
    def should_speak_confirmation(self) -> bool:
        return self.get_config().speak_confirmations
    
    def should_speak_answer(self) -> bool:
        return self.get_config().speak_answers
    
    def should_speak_error(self) -> bool:
        return True  # Always speak errors
    
    def should_use_filler(self) -> bool:
        return self.get_config().use_filler_phrases
    
    def should_announce_intent(self) -> bool:
        return self.get_config().announce_intent
    
    def get_max_sentences(self) -> int:
        """Get max sentences for answers. 0 = unlimited."""
        return self.get_config().max_answer_sentences
    
    def detect_activation(self, text: str) -> Optional[FocusModeLevel]:
        """
        Check if text is a focus mode activation command.
        
        Returns the level to activate, or None if not an activation command.
        """
        normalized = text.lower().strip()
        return self.ACTIVATE_PHRASES.get(normalized)
    
    def detect_deactivation(self, text: str) -> bool:
        """Check if text is a focus mode deactivation command."""
        normalized = text.lower().strip()
        return normalized in self.DEACTIVATE_PHRASES


def truncate_to_sentences(text: str, max_sentences: int) -> str:
    """
    Truncate text to max_sentences.
    
    Preserves complete sentences. Adds "..." if truncated.
    """
    if max_sentences <= 0:
        return text
    
    import re
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    if len(sentences) <= max_sentences:
        return text
    
    truncated = ' '.join(sentences[:max_sentences])
    
    # Add ellipsis if we truncated
    if not truncated.endswith(('...', '…')):
        truncated = truncated.rstrip('.!?') + '...'
    
    return truncated


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_focus_manager: Optional[FocusModeManager] = None


def get_focus_manager() -> FocusModeManager:
    """Get the global focus mode manager."""
    global _focus_manager
    if _focus_manager is None:
        _focus_manager = FocusModeManager()
    return _focus_manager
