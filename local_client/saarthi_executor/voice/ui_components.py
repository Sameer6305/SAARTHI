"""
Voice UI Components
===================

UI elements for voice interaction:
- Recording indicator overlay
- Push-to-talk button integration
- Voice status in tray menu

PRIVACY:
- Recording indicator is ALWAYS visible when mic is active
- Clear visual distinction between recording states
- User can always see when voice is enabled/disabled
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from enum import Enum

from saarthi_executor.voice.pipeline import VoicePipelineState

logger = logging.getLogger(__name__)


class RecordingIndicator:
    """
    Floating recording indicator.
    
    Shows a visible indicator when microphone is active.
    This ensures the user ALWAYS knows when recording is happening.
    """
    
    # Colors
    COLOR_RECORDING = "#FF4444"      # Red - actively recording
    COLOR_PROCESSING = "#FFB800"     # Orange - processing
    COLOR_READY = "#44FF44"          # Green - ready
    
    def __init__(
        self,
        on_stop_click: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize recording indicator.
        
        Args:
            on_stop_click: Callback when user clicks to stop recording
        """
        self._on_stop_click = on_stop_click
        self._window: Optional[tk.Tk] = None
        self._label: Optional[tk.Label] = None
        self._visible = False
        self._lock = threading.Lock()
    
    def _create_window(self) -> None:
        """Create the indicator window."""
        self._window = tk.Tk()
        self._window.overrideredirect(True)  # No title bar
        self._window.attributes('-topmost', True)  # Always on top
        self._window.attributes('-alpha', 0.9)  # Slightly transparent
        
        # Position in top-right corner
        screen_width = self._window.winfo_screenwidth()
        self._window.geometry(f"+{screen_width - 200}+10")
        
        # Create label
        self._label = tk.Label(
            self._window,
            text="🎤 RECORDING",
            font=("Segoe UI", 14, "bold"),
            fg="white",
            bg=self.COLOR_RECORDING,
            padx=20,
            pady=10,
        )
        self._label.pack()
        
        # Click to stop
        if self._on_stop_click:
            self._label.bind("<Button-1>", lambda e: self._on_stop_click())
            self._label.config(cursor="hand2")
    
    def show_recording(self) -> None:
        """Show recording indicator."""
        with self._lock:
            if self._visible:
                self._update_state("🎤 RECORDING", self.COLOR_RECORDING)
                return
            
            self._visible = True
            
            def create_and_show():
                try:
                    self._create_window()
                    self._window.mainloop()
                except Exception as e:
                    logger.error(f"Recording indicator error: {e}")
            
            threading.Thread(target=create_and_show, daemon=True).start()
    
    def show_processing(self) -> None:
        """Show processing indicator."""
        self._update_state("⏳ PROCESSING", self.COLOR_PROCESSING)
    
    def _update_state(self, text: str, color: str) -> None:
        """Update indicator state."""
        if self._label and self._window:
            try:
                self._label.config(text=text, bg=color)
            except Exception:
                pass
    
    def hide(self) -> None:
        """Hide the indicator."""
        with self._lock:
            if not self._visible:
                return
            
            self._visible = False
            
            if self._window:
                try:
                    self._window.quit()
                    self._window.destroy()
                except Exception:
                    pass
                self._window = None
                self._label = None


class VoiceConfirmationDialog:
    """
    Dialog for confirming ambiguous voice input.
    
    Shows when STT confidence is low and asks user to verify.
    """
    
    def __init__(self):
        self._result: Optional[bool] = None
        self._confirmed_text: Optional[str] = None
    
    def show(
        self,
        transcribed_text: str,
        confidence: float,
    ) -> tuple[bool, str]:
        """
        Show confirmation dialog.
        
        Args:
            transcribed_text: Text from STT
            confidence: Confidence level (0-1)
            
        Returns:
            (confirmed, text) - confirmed is True if user accepted,
            text is the (possibly edited) text
        """
        self._result = None
        self._confirmed_text = transcribed_text
        
        def create_dialog():
            root = tk.Tk()
            root.title("Confirm Voice Input")
            root.attributes('-topmost', True)
            
            # Center on screen
            root.geometry("500x250")
            root.eval('tk::PlaceWindow . center')
            
            # Main frame
            frame = ttk.Frame(root, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Warning label
            confidence_pct = int(confidence * 100)
            warning = ttk.Label(
                frame,
                text=f"⚠️ Voice recognition confidence: {confidence_pct}%",
                font=("Segoe UI", 11),
            )
            warning.pack(pady=(0, 10))
            
            # Instruction
            instruction = ttk.Label(
                frame,
                text="Please verify or edit the recognized text:",
                font=("Segoe UI", 10),
            )
            instruction.pack(pady=(0, 5))
            
            # Text entry
            text_var = tk.StringVar(value=transcribed_text)
            entry = ttk.Entry(frame, textvariable=text_var, font=("Segoe UI", 12), width=50)
            entry.pack(pady=10, fill=tk.X)
            entry.focus()
            entry.select_range(0, tk.END)
            
            # Buttons
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=20)
            
            def on_confirm():
                self._result = True
                self._confirmed_text = text_var.get()
                root.quit()
                root.destroy()
            
            def on_cancel():
                self._result = False
                root.quit()
                root.destroy()
            
            confirm_btn = ttk.Button(
                btn_frame,
                text="✓ Confirm",
                command=on_confirm,
            )
            confirm_btn.pack(side=tk.LEFT, padx=5)
            
            cancel_btn = ttk.Button(
                btn_frame,
                text="✗ Cancel",
                command=on_cancel,
            )
            cancel_btn.pack(side=tk.LEFT, padx=5)
            
            # Enter = confirm, Escape = cancel
            root.bind('<Return>', lambda e: on_confirm())
            root.bind('<Escape>', lambda e: on_cancel())
            
            root.protocol("WM_DELETE_WINDOW", on_cancel)
            root.mainloop()
        
        # Run in thread to not block
        thread = threading.Thread(target=create_dialog)
        thread.start()
        thread.join(timeout=120)  # 2 minute timeout
        
        if self._result is None:
            return (False, "")
        
        return (self._result, self._confirmed_text or "")


class VoiceSettingsDialog:
    """
    Dialog for voice settings.
    
    Allows user to:
    - Enable/disable voice
    - Select TTS voice
    - Adjust volume/rate
    - Configure hotkey
    """
    
    def __init__(self, config):
        self._config = config
        self._result = None
    
    def show(self) -> Optional[dict]:
        """
        Show settings dialog.
        
        Returns updated settings dict or None if cancelled.
        """
        self._result = None
        
        def create_dialog():
            root = tk.Tk()
            root.title("Voice Settings")
            root.attributes('-topmost', True)
            root.geometry("400x350")
            root.eval('tk::PlaceWindow . center')
            
            # Main frame
            frame = ttk.Frame(root, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title = ttk.Label(
                frame,
                text="🎤 Voice Settings",
                font=("Segoe UI", 14, "bold"),
            )
            title.pack(pady=(0, 20))
            
            # Enable checkbox
            enabled_var = tk.BooleanVar(value=self._config.enabled)
            enable_check = ttk.Checkbutton(
                frame,
                text="Enable voice features",
                variable=enabled_var,
            )
            enable_check.pack(anchor=tk.W, pady=5)
            
            # Volume slider
            vol_frame = ttk.Frame(frame)
            vol_frame.pack(fill=tk.X, pady=10)
            ttk.Label(vol_frame, text="TTS Volume:").pack(side=tk.LEFT)
            vol_var = tk.IntVar(value=self._config.tts_volume)
            vol_slider = ttk.Scale(
                vol_frame,
                from_=0,
                to=100,
                variable=vol_var,
                orient=tk.HORIZONTAL,
            )
            vol_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            vol_label = ttk.Label(vol_frame, textvariable=vol_var, width=4)
            vol_label.pack(side=tk.LEFT)
            
            # Confirmation checkbox
            confirm_var = tk.BooleanVar(value=self._config.confirm_ambiguous)
            confirm_check = ttk.Checkbutton(
                frame,
                text="Confirm low-confidence transcriptions",
                variable=confirm_var,
            )
            confirm_check.pack(anchor=tk.W, pady=5)
            
            # Recording indicator checkbox
            indicator_var = tk.BooleanVar(value=self._config.show_recording_indicator)
            indicator_check = ttk.Checkbutton(
                frame,
                text="Show recording indicator",
                variable=indicator_var,
            )
            indicator_check.pack(anchor=tk.W, pady=5)
            
            # Buttons
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=20)
            
            def on_save():
                self._result = {
                    'enabled': enabled_var.get(),
                    'tts_volume': vol_var.get(),
                    'confirm_ambiguous': confirm_var.get(),
                    'show_recording_indicator': indicator_var.get(),
                }
                root.quit()
                root.destroy()
            
            def on_cancel():
                self._result = None
                root.quit()
                root.destroy()
            
            save_btn = ttk.Button(btn_frame, text="Save", command=on_save)
            save_btn.pack(side=tk.LEFT, padx=5)
            
            cancel_btn = ttk.Button(btn_frame, text="Cancel", command=on_cancel)
            cancel_btn.pack(side=tk.LEFT, padx=5)
            
            root.protocol("WM_DELETE_WINDOW", on_cancel)
            root.mainloop()
        
        thread = threading.Thread(target=create_dialog)
        thread.start()
        thread.join()
        
        return self._result
