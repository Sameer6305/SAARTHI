"""
Global Hotkey Voice System
==========================

Ctrl+Space HOLD-TO-TALK voice activation.

BEHAVIOR:
- Hotkey DOWN → start recording
- Hotkey UP → stop recording and process
- User HOLDS the key while speaking

CRITICAL SAFETY:
- Mic access ONLY while key is held
- Mic released IMMEDIATELY on key release
- No toggle mode (prevents stuck recording)
- No always-on listening

SECURITY LOGGING:
- HOTKEY_PRESSED
- RECORDING_STARTED
- RECORDING_STOPPED
- PIPELINE_RESET
"""

import logging
import threading
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class HotkeyState(Enum):
    """Hotkey state machine."""
    INACTIVE = "inactive"       # Hotkey system not running
    READY = "ready"             # Waiting for hotkey press
    KEY_DOWN = "key_down"       # Key is being held, recording
    KEY_UP = "key_up"           # Key released, processing
    COOLDOWN = "cooldown"       # Brief cooldown to prevent double-triggers


@dataclass
class HotkeyEvent:
    """Logged hotkey event."""
    event_type: str
    timestamp: float
    state_before: str
    state_after: str
    details: Optional[str] = None


class HoldToTalkHotkey:
    """
    Ctrl+Space HOLD-TO-TALK system.
    
    ARCHITECTURE:
    - Uses pynput for reliable key detection
    - Falls back to keyboard library if pynput unavailable
    - Thread-safe state machine
    - Automatic timeout protection (max 15 seconds)
    
    USAGE:
    1. User HOLDS Ctrl+Space
    2. Recording starts immediately
    3. User RELEASES Ctrl+Space
    4. Recording stops, audio processed
    """
    
    # Max recording time (safety limit)
    MAX_RECORDING_SECONDS = 15.0
    
    # Cooldown between recordings (prevents double-triggers)
    COOLDOWN_SECONDS = 0.3
    
    def __init__(
        self,
        on_recording_start: Callable[[], bool],
        on_recording_stop: Callable[[], Optional[str]],
        on_error: Optional[Callable[[str], None]] = None,
        enabled_check: Optional[Callable[[], bool]] = None,
    ):
        """
        Initialize hold-to-talk hotkey.
        
        Args:
            on_recording_start: Called when key is pressed (return True to confirm start)
            on_recording_stop: Called when key is released (return transcribed text)
            on_error: Called on errors
            enabled_check: Called to check if assistant is enabled (optional)
        """
        self._on_recording_start = on_recording_start
        self._on_recording_stop = on_recording_stop
        self._on_error = on_error
        self._enabled_check = enabled_check
        
        self._state = HotkeyState.INACTIVE
        self._lock = threading.RLock()
        self._running = False
        
        # Key tracking
        self._ctrl_pressed = False
        self._space_pressed = False
        self._combo_active = False
        
        # Timeout protection
        self._recording_start_time: Optional[float] = None
        self._timeout_timer: Optional[threading.Timer] = None
        
        # Event log (for debugging)
        self._event_log: list[HotkeyEvent] = []
        self._max_events = 100
        
        # Listener reference
        self._listener = None
        self._keyboard_hook = None
        
        logger.info("HoldToTalkHotkey created")
    
    def _log_event(
        self, 
        event_type: str, 
        state_before: str, 
        state_after: str,
        details: Optional[str] = None
    ) -> None:
        """Log a hotkey event."""
        event = HotkeyEvent(
            event_type=event_type,
            timestamp=time.time(),
            state_before=state_before,
            state_after=state_after,
            details=details,
        )
        
        self._event_log.append(event)
        
        # Trim old events
        if len(self._event_log) > self._max_events:
            self._event_log = self._event_log[-self._max_events:]
        
        # Security log
        logger.info(f"HOTKEY_EVENT: {event_type} ({state_before} -> {state_after})" + 
                   (f" [{details}]" if details else ""))
    
    def _set_state(self, new_state: HotkeyState, details: str = None) -> None:
        """Thread-safe state transition."""
        with self._lock:
            old_state = self._state
            self._state = new_state
            self._log_event(
                f"STATE_CHANGE",
                old_state.value,
                new_state.value,
                details
            )
    
    def start(self) -> bool:
        """
        Start listening for Ctrl+Space hotkey.
        
        Returns True if started successfully.
        """
        if self._running:
            return True
        
        # Try pynput first (more reliable)
        try:
            from pynput import keyboard
            
            def on_press(key):
                self._handle_key_press(key)
            
            def on_release(key):
                self._handle_key_release(key)
            
            self._listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
            )
            self._listener.start()
            
            self._running = True
            self._set_state(HotkeyState.READY, "pynput listener started")
            logger.info("Hotkey system started (pynput)")
            logger.info("Hold Ctrl+Space to speak")
            return True
            
        except ImportError:
            logger.info("pynput not available, trying keyboard library")
        
        # Fallback to keyboard library
        try:
            import keyboard
            
            # Use on_press_key and on_release_key for more control
            keyboard.on_press_key('ctrl', lambda _: self._on_ctrl_change(True))
            keyboard.on_release_key('ctrl', lambda _: self._on_ctrl_change(False))
            keyboard.on_press_key('space', lambda _: self._on_space_change(True))
            keyboard.on_release_key('space', lambda _: self._on_space_change(False))
            
            self._keyboard_hook = keyboard
            self._running = True
            self._set_state(HotkeyState.READY, "keyboard library started")
            logger.info("Hotkey system started (keyboard library)")
            logger.info("Hold Ctrl+Space to speak")
            return True
            
        except ImportError:
            logger.error("Neither pynput nor keyboard library available!")
            logger.error("Install with: pip install pynput")
            return False
        except Exception as e:
            logger.error(f"Hotkey setup failed: {e}")
            return False
    
    def stop(self) -> None:
        """Stop hotkey listening."""
        self._running = False
        
        # Cancel any pending timeout
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None
        
        # Stop pynput listener
        if self._listener:
            try:
                self._listener.stop()
            except:
                pass
            self._listener = None
        
        # Unhook keyboard library
        if self._keyboard_hook:
            try:
                self._keyboard_hook.unhook_all()
            except:
                pass
            self._keyboard_hook = None
        
        self._set_state(HotkeyState.INACTIVE, "stopped")
        logger.info("Hotkey system stopped")
    
    def _handle_key_press(self, key) -> None:
        """Handle pynput key press."""
        try:
            from pynput.keyboard import Key
            
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self._on_ctrl_change(True)
            elif key == Key.space:
                self._on_space_change(True)
        except Exception as e:
            logger.debug(f"Key press handling error: {e}")
    
    def _handle_key_release(self, key) -> None:
        """Handle pynput key release."""
        try:
            from pynput.keyboard import Key
            
            if key == Key.ctrl_l or key == Key.ctrl_r:
                self._on_ctrl_change(False)
            elif key == Key.space:
                self._on_space_change(False)
        except Exception as e:
            logger.debug(f"Key release handling error: {e}")
    
    def _on_ctrl_change(self, pressed: bool) -> None:
        """Handle Ctrl key state change."""
        self._ctrl_pressed = pressed
        self._check_combo()
    
    def _on_space_change(self, pressed: bool) -> None:
        """Handle Space key state change."""
        self._space_pressed = pressed
        self._check_combo()
    
    def _check_combo(self) -> None:
        """Check if Ctrl+Space combo is active."""
        combo_now = self._ctrl_pressed and self._space_pressed
        
        if combo_now and not self._combo_active:
            # Combo just activated (key down)
            self._combo_active = True
            self._on_combo_down()
        elif not combo_now and self._combo_active:
            # Combo just deactivated (key up)
            self._combo_active = False
            self._on_combo_up()
    
    def _on_combo_down(self) -> None:
        """Handle Ctrl+Space pressed (start recording)."""
        with self._lock:
            # Check if enabled
            if self._enabled_check and not self._enabled_check():
                logger.debug("Hotkey ignored - assistant disabled")
                return
            
            # Check state
            if self._state == HotkeyState.COOLDOWN:
                logger.debug("Hotkey ignored - in cooldown")
                return
            
            if self._state != HotkeyState.READY:
                logger.warning(f"Hotkey ignored - not ready (state: {self._state.value})")
                return
            
            self._log_event("HOTKEY_PRESSED", self._state.value, "key_down")
            
            # Start recording
            try:
                self._log_event("RECORDING_STARTED", self._state.value, "recording")
                
                success = self._on_recording_start()
                
                if success:
                    self._set_state(HotkeyState.KEY_DOWN, "recording started")
                    self._recording_start_time = time.time()
                    
                    # Start timeout timer
                    self._timeout_timer = threading.Timer(
                        self.MAX_RECORDING_SECONDS,
                        self._on_timeout
                    )
                    self._timeout_timer.start()
                else:
                    logger.warning("Recording start returned False")
                    if self._on_error:
                        self._on_error("Failed to start recording")
                        
            except Exception as e:
                logger.error(f"Recording start error: {e}")
                if self._on_error:
                    self._on_error(f"Recording error: {e}")
    
    def _on_combo_up(self) -> None:
        """Handle Ctrl+Space released (stop recording)."""
        with self._lock:
            # Cancel timeout timer
            if self._timeout_timer:
                self._timeout_timer.cancel()
                self._timeout_timer = None
            
            if self._state != HotkeyState.KEY_DOWN:
                # Not recording, ignore
                return
            
            # Calculate recording duration
            duration = 0.0
            if self._recording_start_time:
                duration = time.time() - self._recording_start_time
                self._recording_start_time = None
            
            self._log_event("RECORDING_STOPPED", self._state.value, "processing", 
                          f"duration={duration:.1f}s")
            
            # Stop recording and process
            self._set_state(HotkeyState.KEY_UP, "processing")
            
            try:
                result = self._on_recording_stop()
                
                if result:
                    logger.info(f"Transcription: \"{result[:50]}...\"" if len(result) > 50 else f"Transcription: \"{result}\"")
                else:
                    logger.info("No transcription (too short or silent)")
                    
            except Exception as e:
                logger.error(f"Recording stop error: {e}")
                if self._on_error:
                    self._on_error(f"Processing error: {e}")
            
            finally:
                # Enter cooldown
                self._set_state(HotkeyState.COOLDOWN, "cooldown")
                
                # Exit cooldown after delay
                threading.Timer(
                    self.COOLDOWN_SECONDS,
                    self._exit_cooldown
                ).start()
    
    def _exit_cooldown(self) -> None:
        """Exit cooldown and return to ready state."""
        with self._lock:
            if self._state == HotkeyState.COOLDOWN:
                self._set_state(HotkeyState.READY, "cooldown complete")
    
    def _on_timeout(self) -> None:
        """Handle recording timeout (safety limit)."""
        with self._lock:
            if self._state == HotkeyState.KEY_DOWN:
                logger.warning(f"Recording timeout ({self.MAX_RECORDING_SECONDS}s) - forcing stop")
                self._log_event("RECORDING_TIMEOUT", self._state.value, "forcing stop")
                
                # Force stop
                self._combo_active = False
                self._on_combo_up()
    
    def force_reset(self) -> None:
        """
        Force reset the hotkey state.
        
        Use if stuck in bad state.
        """
        with self._lock:
            # Cancel any timers
            if self._timeout_timer:
                self._timeout_timer.cancel()
                self._timeout_timer = None
            
            # Reset tracking
            self._ctrl_pressed = False
            self._space_pressed = False
            self._combo_active = False
            self._recording_start_time = None
            
            # Reset state
            old_state = self._state
            self._state = HotkeyState.READY if self._running else HotkeyState.INACTIVE
            
            self._log_event("PIPELINE_RESET", old_state.value, self._state.value, "forced")
            logger.info("Hotkey state force reset")
    
    @property
    def state(self) -> HotkeyState:
        """Current hotkey state."""
        return self._state
    
    @property
    def is_recording(self) -> bool:
        """Whether currently recording."""
        return self._state == HotkeyState.KEY_DOWN
    
    def get_recent_events(self, count: int = 10) -> list[HotkeyEvent]:
        """Get recent hotkey events for debugging."""
        return self._event_log[-count:]
