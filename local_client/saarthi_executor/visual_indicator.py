"""
Visual State Indicator
=======================

Lightweight, non-intrusive visual feedback for assistant state.

PRODUCT GOALS:
- Show current state without interrupting workflow
- Minimal screen real estate
- Accessible (color + icon)
- System tray integration for Windows

DESIGN DECISIONS:

1. WHY SYSTEM TRAY?
   - Always visible but non-intrusive
   - Windows-native UX
   - No extra window management
   - Tooltip for detailed status

2. ALTERNATIVES CONSIDERED:
   - Floating window: Intrusive, takes focus
   - Overlay: Complex, may conflict with games/apps
   - Status bar: Requires app window

3. STATE VISUALIZATION:
   - IDLE: Gray/dim icon, "Ready"
   - LISTENING: Pulsing blue, "Listening..."
   - PROCESSING: Yellow/amber, "Thinking..."
   - SPEAKING: Green, "Speaking..."
   - ERROR: Red, "Error"
   - OFFLINE: Orange, "Offline"
   - FOCUS: Purple badge, "Focus Mode"

4. IMPLEMENTATION:
   - pystray for cross-platform tray
   - PIL/Pillow for icon generation
   - Thread-safe state updates
"""

import logging
import threading
import time
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class IndicatorState(Enum):
    """Visual indicator states."""
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()
    OFFLINE = auto()
    FOCUS = auto()


@dataclass
class StateVisuals:
    """Visual properties for a state."""
    color: Tuple[int, int, int]  # RGB
    label: str
    tooltip: str
    icon_char: str  # Fallback character for simple display


# State visual definitions
STATE_VISUALS: Dict[IndicatorState, StateVisuals] = {
    IndicatorState.IDLE: StateVisuals(
        color=(128, 128, 128),
        label="Ready",
        tooltip="SAARTHI - Ready (press SPACE to speak)",
        icon_char="○",
    ),
    IndicatorState.LISTENING: StateVisuals(
        color=(66, 135, 245),
        label="Listening",
        tooltip="SAARTHI - Listening...",
        icon_char="◉",
    ),
    IndicatorState.PROCESSING: StateVisuals(
        color=(245, 180, 66),
        label="Processing",
        tooltip="SAARTHI - Processing your request...",
        icon_char="◐",
    ),
    IndicatorState.SPEAKING: StateVisuals(
        color=(76, 175, 80),
        label="Speaking",
        tooltip="SAARTHI - Speaking...",
        icon_char="◆",
    ),
    IndicatorState.ERROR: StateVisuals(
        color=(244, 67, 54),
        label="Error",
        tooltip="SAARTHI - An error occurred",
        icon_char="✕",
    ),
    IndicatorState.OFFLINE: StateVisuals(
        color=(255, 152, 0),
        label="Offline",
        tooltip="SAARTHI - Offline mode (limited features)",
        icon_char="◇",
    ),
    IndicatorState.FOCUS: StateVisuals(
        color=(156, 39, 176),
        label="Focus",
        tooltip="SAARTHI - Focus mode active",
        icon_char="●",
    ),
}


class ConsoleIndicator:
    """
    Simple console-based state indicator.
    
    For when system tray is not available or during development.
    Uses ANSI colors where supported.
    """
    
    # ANSI color codes
    COLORS = {
        IndicatorState.IDLE: "\033[90m",       # Gray
        IndicatorState.LISTENING: "\033[94m",   # Blue
        IndicatorState.PROCESSING: "\033[93m",  # Yellow
        IndicatorState.SPEAKING: "\033[92m",    # Green
        IndicatorState.ERROR: "\033[91m",       # Red
        IndicatorState.OFFLINE: "\033[33m",     # Orange
        IndicatorState.FOCUS: "\033[95m",       # Purple
    }
    RESET = "\033[0m"
    
    def __init__(self):
        self._state = IndicatorState.IDLE
        self._focus_mode = False
    
    def set_state(self, state: IndicatorState):
        """Update the displayed state."""
        self._state = state
        self._print_state()
    
    def set_focus_mode(self, enabled: bool):
        """Update focus mode indicator."""
        self._focus_mode = enabled
    
    def _print_state(self):
        """Print current state to console."""
        visuals = STATE_VISUALS[self._state]
        color = self.COLORS.get(self._state, "")
        
        focus_badge = " [FOCUS]" if self._focus_mode else ""
        
        # Clear line and print state
        print(f"\r{color}{visuals.icon_char} {visuals.label}{focus_badge}{self.RESET}", end="", flush=True)
    
    def get_status_line(self) -> str:
        """Get status line for embedding in other output."""
        visuals = STATE_VISUALS[self._state]
        focus_badge = " [FOCUS]" if self._focus_mode else ""
        return f"{visuals.icon_char} {visuals.label}{focus_badge}"


class TrayIndicator:
    """
    System tray indicator using pystray.
    
    Creates a small icon in the Windows system tray that reflects
    the current assistant state.
    
    REQUIRES: pystray, Pillow (optional dependencies)
    """
    
    ICON_SIZE = 64
    
    def __init__(self, on_quit: Optional[Callable] = None):
        self._state = IndicatorState.IDLE
        self._focus_mode = False
        self._on_quit = on_quit
        
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Check if pystray is available
        try:
            import pystray
            from PIL import Image, ImageDraw
            self._pystray = pystray
            self._Image = Image
            self._ImageDraw = ImageDraw
            self._available = True
        except ImportError:
            self._available = False
            logger.warning("pystray or Pillow not installed. Tray indicator disabled.")
    
    def is_available(self) -> bool:
        """Check if tray indicator can be used."""
        return self._available
    
    def start(self):
        """Start the tray indicator."""
        if not self._available:
            return
        
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_tray,
            daemon=True,
            name="TrayIndicator",
        )
        self._thread.start()
        logger.info("Tray indicator started")
    
    def stop(self):
        """Stop the tray indicator."""
        if not self._running:
            return
        
        self._running = False
        if self._icon:
            self._icon.stop()
        logger.info("Tray indicator stopped")
    
    def set_state(self, state: IndicatorState):
        """Update the tray icon state."""
        self._state = state
        self._update_icon()
    
    def set_focus_mode(self, enabled: bool):
        """Update focus mode indicator."""
        self._focus_mode = enabled
        self._update_icon()
    
    def _run_tray(self):
        """Run the tray icon (blocking, runs in thread)."""
        if not self._available:
            return
        
        icon_image = self._create_icon(IndicatorState.IDLE)
        visuals = STATE_VISUALS[IndicatorState.IDLE]
        
        # Create menu
        menu = self._pystray.Menu(
            self._pystray.MenuItem("Status", self._on_status, enabled=False),
            self._pystray.MenuItem("Quit SAARTHI", self._on_quit_clicked),
        )
        
        self._icon = self._pystray.Icon(
            name="SAARTHI",
            icon=icon_image,
            title=visuals.tooltip,
            menu=menu,
        )
        
        self._icon.run()
    
    def _create_icon(self, state: IndicatorState) -> 'Image':
        """Create icon image for a state."""
        if not self._available:
            return None
        
        visuals = STATE_VISUALS[state]
        size = self.ICON_SIZE
        
        # Create image with transparency
        image = self._Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = self._ImageDraw.Draw(image)
        
        # Draw filled circle
        margin = 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=visuals.color + (255,),  # Add alpha
            outline=(255, 255, 255, 128),
            width=2,
        )
        
        # Add focus mode badge (small dot)
        if self._focus_mode:
            badge_size = 16
            badge_pos = size - badge_size - 4
            draw.ellipse(
                [badge_pos, badge_pos, size - 4, size - 4],
                fill=(156, 39, 176, 255),  # Purple
                outline=(255, 255, 255, 255),
                width=1,
            )
        
        return image
    
    def _update_icon(self):
        """Update the tray icon."""
        if not self._icon or not self._available:
            return
        
        try:
            new_icon = self._create_icon(self._state)
            visuals = STATE_VISUALS[self._state]
            
            self._icon.icon = new_icon
            self._icon.title = visuals.tooltip
            
        except Exception as e:
            logger.warning(f"Failed to update tray icon: {e}")
    
    def _on_status(self, icon, item):
        """Handle status menu click."""
        pass  # Status is display-only
    
    def _on_quit_clicked(self, icon, item):
        """Handle quit menu click."""
        if self._on_quit:
            self._on_quit()
        self.stop()


class StateIndicatorManager:
    """
    Manages visual state indication across different display methods.
    
    Automatically uses the best available method:
    1. System tray (if pystray available)
    2. Console fallback (always available)
    
    USAGE:
        manager = StateIndicatorManager()
        manager.start()
        
        # Update state
        manager.set_state(IndicatorState.LISTENING)
        
        # Update focus mode
        manager.set_focus_mode(True)
        
        manager.stop()
    """
    
    def __init__(self, on_quit: Optional[Callable] = None):
        self._tray = TrayIndicator(on_quit=on_quit)
        self._console = ConsoleIndicator()
        self._state = IndicatorState.IDLE
        self._focus_mode = False
    
    def start(self):
        """Start the indicator."""
        if self._tray.is_available():
            self._tray.start()
    
    def stop(self):
        """Stop the indicator."""
        if self._tray.is_available():
            self._tray.stop()
    
    def set_state(self, state: IndicatorState):
        """Update the displayed state."""
        self._state = state
        
        if self._tray.is_available():
            self._tray.set_state(state)
        
        self._console.set_state(state)
    
    def set_focus_mode(self, enabled: bool):
        """Update focus mode indicator."""
        self._focus_mode = enabled
        
        if self._tray.is_available():
            self._tray.set_focus_mode(enabled)
        
        self._console.set_focus_mode(enabled)
    
    def get_status_line(self) -> str:
        """Get status line for console display."""
        return self._console.get_status_line()
    
    def is_tray_available(self) -> bool:
        """Check if system tray is available."""
        return self._tray.is_available()


# =============================================================================
# INTEGRATION WITH STATE MACHINE
# =============================================================================

def map_assistant_state_to_indicator(
    assistant_state: str,
    is_offline: bool = False,
    is_focus_mode: bool = False,
) -> IndicatorState:
    """
    Map AssistantState to IndicatorState.
    
    Args:
        assistant_state: Name of the AssistantState enum
        is_offline: Whether currently offline
        is_focus_mode: Whether focus mode is active
    """
    if is_offline:
        return IndicatorState.OFFLINE
    
    if is_focus_mode and assistant_state == "IDLE":
        return IndicatorState.FOCUS
    
    mapping = {
        "IDLE": IndicatorState.IDLE,
        "LISTENING": IndicatorState.LISTENING,
        "TRANSCRIBING": IndicatorState.PROCESSING,
        "THINKING": IndicatorState.PROCESSING,
        "EXECUTING": IndicatorState.PROCESSING,
        "SPEAKING": IndicatorState.SPEAKING,
        "ERROR": IndicatorState.ERROR,
    }
    
    return mapping.get(assistant_state, IndicatorState.IDLE)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_indicator_manager: Optional[StateIndicatorManager] = None


def get_indicator_manager(on_quit: Optional[Callable] = None) -> StateIndicatorManager:
    """Get the global indicator manager."""
    global _indicator_manager
    if _indicator_manager is None:
        _indicator_manager = StateIndicatorManager(on_quit=on_quit)
    return _indicator_manager
