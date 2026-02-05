"""
Minimal System Tray - Voice-Only Mode
=====================================

MINIMAL tray icon for SAARTHI voice-only assistant.

ONLY provides:
- Enable Assistant (green indicator)
- Disable Assistant (gray indicator)
- Status indicator (shows current state)
- Exit

DOES NOT provide:
- Voice command dialog (hotkey only!)
- Text input
- Any command handling

The tray is PURELY for status and enable/disable toggle.
All voice input is via Ctrl+Space hotkey.
"""

import logging
import threading
from enum import Enum
from typing import Optional, Callable

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    """Minimal assistant states."""
    DISABLED = "disabled"      # Gray - not listening to hotkey
    ENABLED = "enabled"        # Green - ready for Ctrl+Space
    RECORDING = "recording"    # Red - currently recording
    PROCESSING = "processing"  # Yellow - processing command


class MinimalTray:
    """
    Minimal system tray for voice-only assistant.
    
    ONLY shows status and enable/disable toggle.
    NO command dialogs, NO text input.
    """
    
    # Colors for states
    STATE_COLORS = {
        AssistantState.DISABLED: "#808080",     # Gray
        AssistantState.ENABLED: "#00FF00",      # Green
        AssistantState.RECORDING: "#FF4444",    # Red
        AssistantState.PROCESSING: "#FFD700",   # Gold/Yellow
    }
    
    STATE_LABELS = {
        AssistantState.DISABLED: "Disabled",
        AssistantState.ENABLED: "Ready (Ctrl+Space)",
        AssistantState.RECORDING: "🎤 Recording...",
        AssistantState.PROCESSING: "Processing...",
    }
    
    def __init__(
        self,
        on_enable: Callable[[], bool],
        on_disable: Callable[[], None],
        on_exit: Callable[[], None],
        initial_state: AssistantState = AssistantState.DISABLED,
    ):
        """
        Initialize minimal tray.
        
        Args:
            on_enable: Callback when user clicks Enable (return True if success)
            on_disable: Callback when user clicks Disable
            on_exit: Callback when user clicks Exit
            initial_state: Starting state
        """
        self._on_enable = on_enable
        self._on_disable = on_disable
        self._on_exit = on_exit
        
        self._state = initial_state
        self._icon: Optional[pystray.Icon] = None
        self._running = False
        self._lock = threading.Lock()
        
        logger.info("MinimalTray created")
    
    @property
    def state(self) -> AssistantState:
        """Current state."""
        return self._state
    
    def set_state(self, new_state: AssistantState) -> None:
        """
        Update tray state.
        
        Thread-safe - can be called from any thread.
        """
        with self._lock:
            if new_state == self._state:
                return
            
            old_state = self._state
            self._state = new_state
            
            logger.info(f"Tray state: {old_state.value} -> {new_state.value}")
            
            # Update icon
            if self._icon:
                self._icon.icon = self._create_icon_image()
                self._icon.title = f"SAARTHI - {self.STATE_LABELS[new_state]}"
                self._icon.menu = self._create_menu()
    
    def _create_icon_image(self) -> Image.Image:
        """Create icon image based on current state."""
        size = 64
        color = self.STATE_COLORS.get(self._state, "#808080")
        
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw circle
        margin = 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color,
            outline="#2c3e50",
            width=2,
        )
        
        # Add indicator for recording state
        if self._state == AssistantState.RECORDING:
            # Add inner pulsing circle
            inner_margin = 16
            draw.ellipse(
                [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
                fill="#FF0000",
            )
        
        return image
    
    def _create_menu(self) -> pystray.Menu:
        """Create context menu."""
        is_enabled = self._state != AssistantState.DISABLED
        
        return pystray.Menu(
            # Status (non-clickable)
            pystray.MenuItem(
                f"Status: {self.STATE_LABELS[self._state]}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            
            # Enable (only if disabled)
            pystray.MenuItem(
                "✓ Enable Assistant",
                self._handle_enable,
                enabled=not is_enabled,
            ),
            
            # Disable (only if enabled)
            pystray.MenuItem(
                "✗ Disable Assistant",
                self._handle_disable,
                enabled=is_enabled and self._state != AssistantState.RECORDING,
            ),
            
            pystray.Menu.SEPARATOR,
            
            # Help text
            pystray.MenuItem(
                "Hold Ctrl+Space to speak",
                None,
                enabled=False,
            ),
            
            pystray.Menu.SEPARATOR,
            
            # Exit
            pystray.MenuItem(
                "Exit",
                self._handle_exit,
            ),
        )
    
    def _handle_enable(self, icon, item) -> None:
        """Handle Enable click."""
        logger.info("Enable clicked")
        
        try:
            if self._on_enable():
                self.set_state(AssistantState.ENABLED)
                self.show_notification("SAARTHI Enabled", "Hold Ctrl+Space to speak")
            else:
                self.show_notification("Enable Failed", "Could not enable assistant")
        except Exception as e:
            logger.error(f"Enable error: {e}")
            self.show_notification("Error", str(e))
    
    def _handle_disable(self, icon, item) -> None:
        """Handle Disable click."""
        logger.info("Disable clicked")
        
        try:
            self._on_disable()
            self.set_state(AssistantState.DISABLED)
            self.show_notification("SAARTHI Disabled", "Assistant is now disabled")
        except Exception as e:
            logger.error(f"Disable error: {e}")
    
    def _handle_exit(self, icon, item) -> None:
        """Handle Exit click."""
        logger.info("Exit clicked")
        self.stop()
        self._on_exit()
    
    def show_notification(self, title: str, message: str) -> None:
        """Show system notification."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Notification failed: {e}")
    
    def start_detached(self) -> None:
        """
        Start tray icon in background thread.
        
        Non-blocking - returns immediately.
        """
        self._icon = pystray.Icon(
            name="SAARTHI",
            icon=self._create_icon_image(),
            title=f"SAARTHI - {self.STATE_LABELS[self._state]}",
            menu=self._create_menu(),
        )
        
        self._running = True
        self._icon.run_detached()
        
        logger.info("MinimalTray started (detached)")
    
    def stop(self) -> None:
        """Stop tray icon."""
        self._running = False
        
        if self._icon:
            try:
                self._icon.stop()
            except:
                pass
            self._icon = None
        
        logger.info("MinimalTray stopped")
