"""
System Tray Application
=======================

Windows system tray application for SAARTHI local executor.

Features:
- Tray icon with state indication
- Menu for state control
- Action processing integration
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
    """
    
    # Colors for different states
    STATE_COLORS = {
        ExecutorState.SLEEP: "#808080",      # Gray
        ExecutorState.LISTENING: "#00FF00",  # Green  
        ExecutorState.ACTIVE: "#FFD700",     # Gold
    }
    
    def __init__(
        self,
        state_machine: StateMachine,
        on_exit: Callable[[], None],
    ):
        """Initialize tray icon."""
        self._state_machine = state_machine
        self._on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._running = False
        
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
        
        return pystray.Menu(
            pystray.MenuItem(
                f"Status: {current_state.name}",
                None,
                enabled=False,
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
        )
    
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
