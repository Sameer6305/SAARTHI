"""
System Tray Application
=======================

Windows system tray application for SAARTHI local executor.

Features:
- Tray icon with state indication
- Menu for state control
- Voice Command (PRIMARY) - push-to-talk voice input
- Send Command dialog for text input
- Action processing integration

VOICE INPUT:
- Push-to-talk ONLY (no background listening)
- Voice is treated as UNTRUSTED input (same as text)
- Goes through same permission flow
"""

import logging
import threading
import time
from typing import Optional, Callable
from pathlib import Path

# pystray for system tray
import pystray
from PIL import Image, ImageDraw

from saarthi_executor.state_machine import StateMachine, ExecutorState

logger = logging.getLogger(__name__)


class TrayIcon:
    """
    System tray icon for SAARTHI executor.
    
    Shows current state and provides control menu.
    Includes "Voice Command" (PRIMARY) and "Send Command" options.
    
    VOICE COMMAND:
    - Push-to-talk only, no background listening
    - Voice input treated as untrusted (same security as text)
    - Goes through same permission enforcement
    """
    
    # Colors for different states
    STATE_COLORS = {
        ExecutorState.SLEEP: "#808080",      # Gray
        ExecutorState.LISTENING: "#00FF00",  # Green  
        ExecutorState.ACTIVE: "#FFD700",     # Gold
    }
    
    # Recording state color
    RECORDING_COLOR = "#FF4444"  # Red when recording voice
    
    def __init__(
        self,
        state_machine: StateMachine,
        on_exit: Callable[[], None],
        on_send_command: Optional[Callable[[], None]] = None,
        on_voice_command: Optional[Callable[[], None]] = None,
        on_voice_settings: Optional[Callable[[], None]] = None,
        is_voice_enabled: Optional[Callable[[], bool]] = None,
    ):
        """
        Initialize tray icon.
        
        Args:
            state_machine: The executor state machine
            on_exit: Callback when user clicks Exit
            on_send_command: Callback when user clicks "Send Command"
            on_voice_command: Callback when user clicks "Voice Command" (PRIMARY)
            on_voice_settings: Callback when user clicks "Voice Settings"
            is_voice_enabled: Callable to check if voice is enabled
        """
        self._state_machine = state_machine
        self._on_exit = on_exit
        self._on_send_command = on_send_command
        self._on_voice_command = on_voice_command
        self._on_voice_settings = on_voice_settings
        self._is_voice_enabled = is_voice_enabled
        self._icon: Optional[pystray.Icon] = None
        self._running = False
        self._is_recording = False  # Track recording state
        
        # Register for state changes
        state_machine.register_state_change_callback(self._on_state_change)
    
    def _create_icon_image(self, color: str) -> Image.Image:
        """Create a simple circular icon with the given color."""
        size = 64
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
        
        return image
    
    def _get_menu(self) -> pystray.Menu:
        """Create the context menu."""
        current_state = self._state_machine.current_state
        
        # Check voice availability
        voice_enabled = self._is_voice_enabled() if self._is_voice_enabled else False
        voice_label = "🎤 Voice Command" if voice_enabled else "🎤 Voice Command (Disabled)"
        
        # Build menu items
        menu_items = [
            pystray.MenuItem(
                f"Status: {current_state.name}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            
            # ═══════════════════════════════════════════════════════════════
            # PRIMARY ACTION: Voice Command (push-to-talk)
            # ═══════════════════════════════════════════════════════════════
            pystray.MenuItem(
                voice_label,
                self._on_voice_command_click,
                enabled=self._on_voice_command is not None and voice_enabled,
                default=True,  # Make it the default (bold) - PRIMARY entry point
            ),
            
            # SECONDARY: Text Command
            pystray.MenuItem(
                "📝 Send Command (Text)",
                self._on_send_command_click,
                enabled=self._on_send_command is not None,
            ),
            pystray.Menu.SEPARATOR,
            
            # Voice Settings submenu
            pystray.MenuItem(
                "🔧 Voice Settings",
                self._on_voice_settings_click,
                enabled=self._on_voice_settings is not None,
            ),
            pystray.Menu.SEPARATOR,
            
            pystray.MenuItem(
                "Wake Up",
                self._on_wake_up,
                enabled=current_state == ExecutorState.SLEEP,
            ),
            pystray.MenuItem(
                "Go to Sleep",
                self._on_sleep,
                enabled=current_state != ExecutorState.SLEEP,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Test Action",
                self._on_test_action,
                enabled=current_state == ExecutorState.LISTENING,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self._on_exit_click,
            ),
        ]
        
        return pystray.Menu(*menu_items)
    
    def _on_state_change(
        self, 
        old_state: ExecutorState, 
        new_state: ExecutorState
    ) -> None:
        """Handle state change - update icon."""
        if self._icon:
            color = self.STATE_COLORS.get(new_state, "#808080")
            self._icon.icon = self._create_icon_image(color)
            self._icon.menu = self._get_menu()
            self._icon.title = f"SAARTHI - {new_state.name}"
    
    def _on_wake_up(self, icon, item) -> None:
        """Handle wake up menu click."""
        self._state_machine.wake_up("User clicked Wake Up")
    
    def _on_sleep(self, icon, item) -> None:
        """Handle sleep menu click."""
        self._state_machine.go_to_sleep("User clicked Sleep")
    
    def _on_send_command_click(self, icon, item) -> None:
        """
        Handle "Send Command" menu click.
        
        Opens the command input dialog in a separate thread
        to avoid blocking the tray icon event loop.
        """
        logger.info("Send Command clicked from tray menu")
        
        if self._on_send_command:
            # Run in thread to avoid blocking tray
            threading.Thread(
                target=self._on_send_command,
                daemon=True,
                name="CommandDialogThread",
            ).start()
        else:
            logger.warning("No send_command callback registered")
    
    def _on_voice_command_click(self, icon, item) -> None:
        """
        Handle "Voice Command" menu click.
        
        Opens the push-to-talk voice input dialog.
        Voice input is treated as UNTRUSTED - same as text input.
        
        SECURITY:
        - Voice goes through same permission flow as text
        - No special trust for voice input
        - Same allowlist, same dialogs, same logging
        """
        logger.info("Voice Command clicked from tray menu (PRIMARY)")
        
        if self._on_voice_command:
            # Run in thread to avoid blocking tray
            threading.Thread(
                target=self._on_voice_command,
                daemon=True,
                name="VoiceCommandThread",
            ).start()
        else:
            logger.warning("No voice_command callback registered")
    
    def _on_voice_settings_click(self, icon, item) -> None:
        """Handle "Voice Settings" menu click."""
        logger.info("Voice Settings clicked from tray menu")
        
        if self._on_voice_settings:
            threading.Thread(
                target=self._on_voice_settings,
                daemon=True,
                name="VoiceSettingsThread",
            ).start()
        else:
            logger.warning("No voice_settings callback registered")
    
    def set_recording_state(self, is_recording: bool) -> None:
        """
        Update tray icon to show recording state.
        
        Shows red icon when recording voice input.
        """
        self._is_recording = is_recording
        
        if self._icon:
            if is_recording:
                self._icon.icon = self._create_icon_image(self.RECORDING_COLOR)
                self._icon.title = "SAARTHI - 🎤 RECORDING"
            else:
                current_state = self._state_machine.current_state
                color = self.STATE_COLORS.get(current_state, "#808080")
                self._icon.icon = self._create_icon_image(color)
                self._icon.title = f"SAARTHI - {current_state.name}"

    def _on_test_action(self, icon, item) -> None:
        """Trigger a test action for demonstration."""
        logger.info("Test action triggered from menu")
        # This would be connected to the executor in the main app
    
    def _on_exit_click(self, icon, item) -> None:
        """Handle exit menu click."""
        logger.info("Exit requested from tray menu")
        self.stop()
        self._on_exit()
    
    def start(self) -> None:
        """Start the tray icon."""
        color = self.STATE_COLORS.get(
            self._state_machine.current_state, 
            "#808080"
        )
        
        self._icon = pystray.Icon(
            name="SAARTHI",
            icon=self._create_icon_image(color),
            title=f"SAARTHI - {self._state_machine.current_state.name}",
            menu=self._get_menu(),
        )
        
        self._running = True
        logger.info("Tray icon started")
        
        # This blocks - run in main thread
        self._icon.run()
    
    def stop(self) -> None:
        """Stop the tray icon."""
        self._running = False
        if self._icon:
            self._icon.stop()
            self._icon = None
            logger.info("Tray icon stopped")
    
    def show_notification(self, title: str, message: str) -> None:
        """Show a system notification."""
        if self._icon:
            self._icon.notify(message, title)
