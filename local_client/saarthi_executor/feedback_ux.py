"""
Production UX Feedback System for SAARTHI
==========================================

Provides comprehensive user feedback including:
- Spoken status updates ("Listening...", "Processing...", etc.)
- Visual feedback via tray notifications
- Error recovery with user guidance
- Accessibility-friendly messages

Author: Principal AI Systems Engineer
Version: 1.0.0
"""

import logging
import time
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)


# =============================================================================
# FEEDBACK STATES
# =============================================================================

class FeedbackState(Enum):
    """User feedback states."""
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()
    SUCCESS = auto()
    CONFIRMING = auto()


@dataclass
class FeedbackMessage:
    """A feedback message to the user."""
    text: str
    speak: bool = True
    show_notification: bool = True
    state: FeedbackState = FeedbackState.IDLE
    duration_ms: int = 3000  # For notifications


# =============================================================================
# FEEDBACK MESSAGES
# =============================================================================

class FeedbackMessages:
    """Pre-defined feedback messages for consistency."""
    
    # Listening feedback
    LISTENING_START = FeedbackMessage(
        text="Listening...",
        speak=True,
        state=FeedbackState.LISTENING,
    )
    
    LISTENING_STOP = FeedbackMessage(
        text="Got it.",
        speak=False,  # Don't speak, it's too quick
        state=FeedbackState.PROCESSING,
    )
    
    # Processing feedback
    PROCESSING = FeedbackMessage(
        text="Processing...",
        speak=False,  # Don't speak, show visually
        state=FeedbackState.PROCESSING,
    )
    
    THINKING = FeedbackMessage(
        text="Let me think about that...",
        speak=True,
        state=FeedbackState.PROCESSING,
    )
    
    # Error feedback
    DIDNT_CATCH = FeedbackMessage(
        text="I didn't catch that. Could you repeat?",
        speak=True,
        state=FeedbackState.ERROR,
    )
    
    TOO_QUIET = FeedbackMessage(
        text="I couldn't hear you. Please speak a bit louder.",
        speak=True,
        state=FeedbackState.ERROR,
    )
    
    TOO_SHORT = FeedbackMessage(
        text="That was too short. Please say more.",
        speak=True,
        state=FeedbackState.ERROR,
    )
    
    AUDIO_ERROR = FeedbackMessage(
        text="There was an audio problem. Let's try again.",
        speak=True,
        state=FeedbackState.ERROR,
    )
    
    STT_ERROR = FeedbackMessage(
        text="I couldn't understand that. Please try again.",
        speak=True,
        state=FeedbackState.ERROR,
    )
    
    # Confirmation feedback
    CONFIRM_PROMPT = FeedbackMessage(
        text="Say 'yes' to confirm or 'no' to cancel.",
        speak=True,
        state=FeedbackState.CONFIRMING,
    )
    
    CONFIRMED = FeedbackMessage(
        text="Done!",
        speak=True,
        state=FeedbackState.SUCCESS,
    )
    
    CANCELLED = FeedbackMessage(
        text="Cancelled.",
        speak=True,
        state=FeedbackState.IDLE,
    )
    
    # Success feedback
    ACTION_COMPLETE = FeedbackMessage(
        text="Done.",
        speak=False,  # Action already visible
        state=FeedbackState.SUCCESS,
    )
    
    # General
    READY = FeedbackMessage(
        text="Ready.",
        speak=False,
        state=FeedbackState.IDLE,
    )
    
    GOODBYE = FeedbackMessage(
        text="Goodbye!",
        speak=True,
        state=FeedbackState.IDLE,
    )


# =============================================================================
# TTS WRAPPER
# =============================================================================

class FeedbackTTS:
    """
    Thread-safe TTS for feedback.
    Uses Windows SAPI for reliability.
    """
    
    def __init__(self):
        self._engine = None
        self._lock = Lock()
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize TTS engine."""
        with self._lock:
            if self._initialized:
                return True
            
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', 180)  # Slightly faster
                self._engine.setProperty('volume', 1.0)
                self._initialized = True
                logger.info("FeedbackTTS initialized with pyttsx3")
                return True
            except Exception as e:
                logger.warning(f"pyttsx3 init failed: {e}, trying SAPI")
                
            try:
                import win32com.client
                self._engine = win32com.client.Dispatch("SAPI.SpVoice")
                self._initialized = True
                logger.info("FeedbackTTS initialized with SAPI")
                return True
            except Exception as e:
                logger.error(f"SAPI init failed: {e}")
            
            return False
    
    def speak(self, text: str, async_mode: bool = True):
        """Speak text."""
        if not self._initialized or not self._engine:
            return
        
        with self._lock:
            try:
                if hasattr(self._engine, 'say'):
                    # pyttsx3
                    self._engine.say(text)
                    if not async_mode:
                        self._engine.runAndWait()
                    else:
                        # Start and don't wait
                        import threading
                        def speak_thread():
                            try:
                                self._engine.runAndWait()
                            except:
                                pass
                        threading.Thread(target=speak_thread, daemon=True).start()
                else:
                    # SAPI
                    flags = 1 if async_mode else 0  # 1 = async
                    self._engine.Speak(text, flags)
            except Exception as e:
                logger.error(f"TTS speak error: {e}")
    
    def stop(self):
        """Stop speaking."""
        if not self._initialized or not self._engine:
            return
        
        with self._lock:
            try:
                if hasattr(self._engine, 'stop'):
                    self._engine.stop()
            except:
                pass
    
    def cleanup(self):
        """Cleanup TTS resources."""
        self.stop()
        self._engine = None
        self._initialized = False


# =============================================================================
# NOTIFICATION MANAGER
# =============================================================================

class NotificationManager:
    """
    Manage system tray notifications.
    Falls back gracefully if tray not available.
    """
    
    def __init__(self, tray_callback: Optional[Callable] = None):
        self._tray_callback = tray_callback
        self._last_notification: Optional[str] = None
        self._last_notification_time: float = 0
        self._min_interval = 0.5  # Min seconds between notifications
    
    def notify(self, title: str, message: str, duration_ms: int = 3000):
        """Show a notification."""
        # Rate limit
        now = time.time()
        if now - self._last_notification_time < self._min_interval:
            return
        
        self._last_notification = message
        self._last_notification_time = now
        
        if self._tray_callback:
            try:
                self._tray_callback(title, message, duration_ms)
            except Exception as e:
                logger.warning(f"Tray notification failed: {e}")
        else:
            # Fallback: just log
            logger.info(f"[{title}] {message}")
    
    def set_tray_callback(self, callback: Callable):
        """Set the tray notification callback."""
        self._tray_callback = callback


# =============================================================================
# FEEDBACK MANAGER
# =============================================================================

class FeedbackManager:
    """
    Central feedback manager coordinating TTS and notifications.
    
    USAGE:
    ```python
    feedback = FeedbackManager()
    feedback.initialize()
    
    feedback.listening_started()  # Says "Listening..."
    feedback.processing()         # Shows "Processing..."
    feedback.speak("Hello!")      # Says custom text
    feedback.error_didnt_catch()  # Says "I didn't catch that..."
    ```
    """
    
    def __init__(
        self,
        enable_tts: bool = True,
        enable_notifications: bool = True,
        tray_callback: Optional[Callable] = None,
    ):
        self._enable_tts = enable_tts
        self._enable_notifications = enable_notifications
        
        self._tts = FeedbackTTS() if enable_tts else None
        self._notifications = NotificationManager(tray_callback)
        
        self._current_state = FeedbackState.IDLE
        self._state_history: list = []
        self._max_history = 100
    
    def initialize(self) -> bool:
        """Initialize feedback systems."""
        success = True
        
        if self._tts:
            if not self._tts.initialize():
                logger.warning("TTS initialization failed, continuing without speech")
                success = False
        
        logger.info("FeedbackManager initialized")
        return success
    
    # ===================
    # STATE TRANSITIONS
    # ===================
    
    def _set_state(self, state: FeedbackState):
        """Set current state and log transition."""
        old_state = self._current_state
        self._current_state = state
        
        self._state_history.append({
            "time": time.time(),
            "from": old_state.name,
            "to": state.name,
        })
        
        if len(self._state_history) > self._max_history:
            self._state_history = self._state_history[-self._max_history:]
    
    # ===================
    # FEEDBACK METHODS
    # ===================
    
    def deliver(self, message: FeedbackMessage):
        """Deliver a feedback message."""
        self._set_state(message.state)
        
        if message.speak and self._tts:
            self._tts.speak(message.text, async_mode=True)
        
        if message.show_notification and self._enable_notifications:
            self._notifications.notify("SAARTHI", message.text, message.duration_ms)
    
    def speak(self, text: str, async_mode: bool = True):
        """Speak custom text."""
        if self._tts:
            self._tts.speak(text, async_mode)
    
    def notify(self, title: str, message: str, duration_ms: int = 3000):
        """Show a notification."""
        if self._enable_notifications:
            self._notifications.notify(title, message, duration_ms)
    
    # ===================
    # CONVENIENCE METHODS
    # ===================
    
    def listening_started(self):
        """Call when listening starts."""
        self.deliver(FeedbackMessages.LISTENING_START)
    
    def listening_stopped(self):
        """Call when listening stops."""
        self.deliver(FeedbackMessages.LISTENING_STOP)
    
    def processing(self):
        """Call when processing starts."""
        self.deliver(FeedbackMessages.PROCESSING)
    
    def thinking(self):
        """Call for complex queries requiring LLM."""
        self.deliver(FeedbackMessages.THINKING)
    
    def error_didnt_catch(self):
        """Call when input wasn't understood."""
        self.deliver(FeedbackMessages.DIDNT_CATCH)
    
    def error_too_quiet(self):
        """Call when audio was too quiet."""
        self.deliver(FeedbackMessages.TOO_QUIET)
    
    def error_too_short(self):
        """Call when audio was too short."""
        self.deliver(FeedbackMessages.TOO_SHORT)
    
    def error_audio(self):
        """Call on audio capture error."""
        self.deliver(FeedbackMessages.AUDIO_ERROR)
    
    def error_stt(self):
        """Call on STT error."""
        self.deliver(FeedbackMessages.STT_ERROR)
    
    def confirm_prompt(self, action_description: str = ""):
        """Call when awaiting confirmation."""
        if action_description:
            self.speak(f"{action_description}. Say yes to confirm or no to cancel.")
        else:
            self.deliver(FeedbackMessages.CONFIRM_PROMPT)
    
    def confirmed(self):
        """Call when action confirmed."""
        self.deliver(FeedbackMessages.CONFIRMED)
    
    def cancelled(self):
        """Call when action cancelled."""
        self.deliver(FeedbackMessages.CANCELLED)
    
    def action_complete(self, description: str = ""):
        """Call when action completed."""
        if description:
            self.notify("SAARTHI", description, 2000)
        self.deliver(FeedbackMessages.ACTION_COMPLETE)
    
    def ready(self):
        """Call when ready for input."""
        self.deliver(FeedbackMessages.READY)
    
    def goodbye(self):
        """Call when shutting down."""
        self.deliver(FeedbackMessages.GOODBYE)
    
    def custom(self, text: str, speak: bool = True, notify: bool = True):
        """Deliver custom feedback."""
        self.deliver(FeedbackMessage(
            text=text,
            speak=speak,
            show_notification=notify,
            state=self._current_state,
        ))
    
    # ===================
    # ACCESSORS
    # ===================
    
    def get_current_state(self) -> FeedbackState:
        """Get current feedback state."""
        return self._current_state
    
    def get_state_history(self) -> list:
        """Get state transition history."""
        return self._state_history.copy()
    
    def set_tray_callback(self, callback: Callable):
        """Set tray notification callback."""
        self._notifications.set_tray_callback(callback)
    
    # ===================
    # CLEANUP
    # ===================
    
    def stop_speaking(self):
        """Stop current speech."""
        if self._tts:
            self._tts.stop()
    
    def cleanup(self):
        """Cleanup resources."""
        self.stop_speaking()
        if self._tts:
            self._tts.cleanup()
        logger.info("FeedbackManager cleaned up")


# =============================================================================
# FACTORY
# =============================================================================

_feedback_instance: Optional[FeedbackManager] = None


def get_feedback_manager(
    enable_tts: bool = True,
    enable_notifications: bool = True,
    tray_callback: Optional[Callable] = None,
) -> FeedbackManager:
    """Get or create the feedback manager singleton."""
    global _feedback_instance
    
    if _feedback_instance is None:
        _feedback_instance = FeedbackManager(
            enable_tts=enable_tts,
            enable_notifications=enable_notifications,
            tray_callback=tray_callback,
        )
        _feedback_instance.initialize()
    
    return _feedback_instance


def reset_feedback_manager():
    """Reset the feedback manager (for testing)."""
    global _feedback_instance
    if _feedback_instance:
        _feedback_instance.cleanup()
        _feedback_instance = None
