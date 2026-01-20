"""
Voice Command Dialog
====================

Push-to-talk dialog for voice input.

PRIVACY GUARANTEES:
- Push-to-talk ONLY - no background listening
- Recording ONLY while button is held
- Audio exists ONLY in memory
- Audio discarded immediately after transcription
- Clear visual indicator when recording

SECURITY:
- Voice input is treated IDENTICALLY to text input
- Same permission flow, same allowlist, same logging
- Voice is a convenience layer, NOT a controller
- No special trust for voice input
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES
# =============================================================================

class VoiceCommandResult(Enum):
    """Result of voice command interaction."""
    SUCCESS = "success"           # Voice transcribed and sent
    CANCELLED = "cancelled"       # User cancelled
    NO_SPEECH = "no_speech"       # No speech detected
    LOW_CONFIDENCE = "low_confidence"  # Low confidence, user cancelled confirmation
    TRANSCRIPTION_ERROR = "transcription_error"  # STT failed
    BACKEND_ERROR = "backend_error"  # Backend communication failed
    VOICE_DISABLED = "voice_disabled"  # Voice not enabled


@dataclass
class VoiceDialogResult:
    """Result from the voice command dialog."""
    
    result: VoiceCommandResult
    transcribed_text: Optional[str] = None
    confidence: Optional[float] = None
    task_id: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# VOICE COMMAND DIALOG
# =============================================================================

class VoiceCommandDialog:
    """
    Push-to-talk dialog for voice input.
    
    USAGE:
        dialog = VoiceCommandDialog(
            on_start_recording=start_func,
            on_stop_recording=stop_func,
            on_send_text=send_func,
        )
        result = dialog.show()
    
    USER FLOW:
    1. Dialog opens with "Hold to Talk" button
    2. User presses and HOLDS the button
    3. Recording starts, indicator shows red "🎤 RECORDING"
    4. User speaks their command
    5. User releases button
    6. Transcription happens
    7. User confirms or edits transcribed text
    8. Text is sent (same as typed text)
    
    SECURITY:
    - Voice input treated as UNTRUSTED
    - Same permission flow as text
    - No special privileges
    """
    
    # Dialog dimensions
    WIDTH = 500
    HEIGHT = 350
    
    # Colors
    COLOR_IDLE = "#2196F3"       # Blue - ready to record
    COLOR_RECORDING = "#F44336"  # Red - recording
    COLOR_PROCESSING = "#FF9800" # Orange - processing
    COLOR_SUCCESS = "#4CAF50"    # Green - success
    
    def __init__(
        self,
        on_start_recording: Callable[[], bool],
        on_stop_recording: Callable[[], Optional[tuple[str, float]]],
        on_send_text: Callable[[str], Optional[str]],
        on_cancel_recording: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize voice command dialog.
        
        Args:
            on_start_recording: Called when user presses button. Returns True if started.
            on_stop_recording: Called when user releases button. Returns (text, confidence) or None.
            on_send_text: Called with final text. Returns task_id or None on error.
            on_cancel_recording: Called when recording is cancelled.
        """
        self._on_start_recording = on_start_recording
        self._on_stop_recording = on_stop_recording
        self._on_send_text = on_send_text
        self._on_cancel_recording = on_cancel_recording
        
        self._result: Optional[VoiceDialogResult] = None
        self._root: Optional[tk.Tk] = None
        
        # State
        self._is_recording = False
        self._transcribed_text: Optional[str] = None
        self._confidence: Optional[float] = None
        
        # UI elements (set during creation)
        self._talk_button: Optional[tk.Button] = None
        self._status_label: Optional[tk.Label] = None
        self._text_entry: Optional[tk.Entry] = None
        self._send_button: Optional[tk.Button] = None
    
    def show(self) -> Optional[VoiceDialogResult]:
        """
        Show the dialog and wait for user interaction.
        
        Returns:
            VoiceDialogResult with outcome, or None if dialog failed
        """
        try:
            self._create_dialog()
            self._root.mainloop()
            return self._result
        except Exception as e:
            logger.error(f"Failed to show voice command dialog: {e}")
            return VoiceDialogResult(
                result=VoiceCommandResult.BACKEND_ERROR,
                error=f"Failed to open dialog: {e}"
            )
    
    def _create_dialog(self) -> None:
        """Create the dialog window and widgets."""
        # Create root window
        self._root = tk.Tk()
        self._root.title("SAARTHI - Voice Command")
        self._root.resizable(False, False)
        
        # Center on screen
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = (screen_width - self.WIDTH) // 2
        y = (screen_height - self.HEIGHT) // 2
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        
        # Make modal
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Main frame
        main_frame = ttk.Frame(self._root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="🎤 Voice Command",
            font=("Segoe UI", 14, "bold"),
        )
        title_label.pack(pady=(0, 5))
        
        # Instructions
        instruction_label = ttk.Label(
            main_frame,
            text="Press and HOLD the button below while speaking your command.",
            font=("Segoe UI", 10),
            foreground="#666666",
        )
        instruction_label.pack(pady=(0, 5))
        
        # Privacy note
        privacy_label = ttk.Label(
            main_frame,
            text="🔒 Push-to-talk only • Audio stays on device • Local transcription",
            font=("Segoe UI", 9),
            foreground="#888888",
        )
        privacy_label.pack(pady=(0, 20))
        
        # Talk button
        self._talk_button = tk.Button(
            main_frame,
            text="🎤 Hold to Talk",
            font=("Segoe UI", 14, "bold"),
            bg=self.COLOR_IDLE,
            fg="white",
            activebackground=self.COLOR_RECORDING,
            activeforeground="white",
            width=20,
            height=2,
            cursor="hand2",
            relief=tk.RAISED,
            borderwidth=3,
        )
        self._talk_button.pack(pady=10)
        
        # Bind press and release events
        self._talk_button.bind("<ButtonPress-1>", self._on_button_press)
        self._talk_button.bind("<ButtonRelease-1>", self._on_button_release)
        
        # Status label
        self._status_label = tk.Label(
            main_frame,
            text="Press and hold to record",
            font=("Segoe UI", 11),
            fg="#666666",
        )
        self._status_label.pack(pady=10)
        
        # Separator
        ttk.Separator(main_frame).pack(fill=tk.X, pady=10)
        
        # Transcription section (initially hidden)
        self._transcription_frame = ttk.Frame(main_frame)
        self._transcription_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(
            self._transcription_frame,
            text="Transcribed text (edit if needed):",
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W)
        
        text_var = tk.StringVar()
        self._text_entry = ttk.Entry(
            self._transcription_frame,
            textvariable=text_var,
            font=("Segoe UI", 11),
            width=50,
        )
        self._text_entry.pack(fill=tk.X, pady=5)
        self._text_entry.config(state=tk.DISABLED)
        
        # Confidence label
        self._confidence_label = ttk.Label(
            self._transcription_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="#888888",
        )
        self._confidence_label.pack(anchor=tk.W)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
        )
        cancel_btn.pack(side=tk.LEFT)
        
        # Send button (initially disabled)
        self._send_button = ttk.Button(
            button_frame,
            text="Send Command",
            command=self._on_send,
            state=tk.DISABLED,
        )
        self._send_button.pack(side=tk.RIGHT)
    
    def _on_button_press(self, event) -> None:
        """Handle talk button press - start recording."""
        if self._is_recording:
            return
        
        logger.info("Voice button pressed - starting recording")
        
        # Update UI immediately
        self._talk_button.config(
            text="🎤 RECORDING...",
            bg=self.COLOR_RECORDING,
        )
        self._status_label.config(
            text="🔴 Recording... Release button when done",
            fg=self.COLOR_RECORDING,
        )
        
        # Start recording
        try:
            if self._on_start_recording():
                self._is_recording = True
            else:
                self._update_status("❌ Failed to start recording", "#F44336")
                self._reset_button()
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self._update_status(f"❌ Error: {e}", "#F44336")
            self._reset_button()
    
    def _on_button_release(self, event) -> None:
        """Handle talk button release - stop recording and transcribe."""
        if not self._is_recording:
            return
        
        logger.info("Voice button released - stopping recording")
        self._is_recording = False
        
        # Update UI
        self._talk_button.config(
            text="⏳ Processing...",
            bg=self.COLOR_PROCESSING,
            state=tk.DISABLED,
        )
        self._status_label.config(
            text="⏳ Transcribing speech...",
            fg=self.COLOR_PROCESSING,
        )
        
        # Stop recording in background thread
        def process():
            try:
                result = self._on_stop_recording()
                
                if result:
                    text, confidence = result
                    self._root.after(0, lambda: self._show_transcription(text, confidence))
                else:
                    self._root.after(0, lambda: self._handle_no_speech())
            except Exception as e:
                logger.error(f"Error processing recording: {e}")
                self._root.after(0, lambda: self._handle_error(str(e)))
        
        threading.Thread(target=process, daemon=True).start()
    
    def _show_transcription(self, text: str, confidence: float) -> None:
        """Show transcription result and enable editing/sending."""
        self._transcribed_text = text
        self._confidence = confidence
        
        # Update text entry
        self._text_entry.config(state=tk.NORMAL)
        self._text_entry.delete(0, tk.END)
        self._text_entry.insert(0, text)
        self._text_entry.focus()
        self._text_entry.select_range(0, tk.END)
        
        # Update confidence display
        confidence_pct = int(confidence * 100)
        if confidence >= 0.8:
            conf_color = "#4CAF50"  # Green
            conf_text = f"✓ High confidence: {confidence_pct}%"
        elif confidence >= 0.6:
            conf_color = "#FF9800"  # Orange
            conf_text = f"⚠️ Medium confidence: {confidence_pct}% - Please verify"
        else:
            conf_color = "#F44336"  # Red
            conf_text = f"⚠️ Low confidence: {confidence_pct}% - Please verify or re-record"
        
        self._confidence_label.config(text=conf_text, foreground=conf_color)
        
        # Reset button
        self._reset_button()
        
        # Enable send button
        self._send_button.config(state=tk.NORMAL)
        
        # Update status
        self._update_status(f"✓ Transcribed: \"{text[:30]}...\"" if len(text) > 30 else f"✓ Transcribed: \"{text}\"", "#4CAF50")
    
    def _handle_no_speech(self) -> None:
        """Handle case where no speech was detected."""
        self._reset_button()
        self._update_status("❌ No speech detected. Try again.", "#F44336")
        
        # Clear any previous transcription
        self._text_entry.config(state=tk.NORMAL)
        self._text_entry.delete(0, tk.END)
        self._text_entry.config(state=tk.DISABLED)
        self._confidence_label.config(text="")
        self._send_button.config(state=tk.DISABLED)
    
    def _handle_error(self, error: str) -> None:
        """Handle transcription error."""
        self._reset_button()
        self._update_status(f"❌ Error: {error}", "#F44336")
        self._send_button.config(state=tk.DISABLED)
    
    def _reset_button(self) -> None:
        """Reset talk button to idle state."""
        self._talk_button.config(
            text="🎤 Hold to Talk",
            bg=self.COLOR_IDLE,
            state=tk.NORMAL,
        )
    
    def _update_status(self, text: str, color: str) -> None:
        """Update status label."""
        self._status_label.config(text=text, fg=color)
    
    def _on_send(self) -> None:
        """Send the transcribed/edited text."""
        # Get text from entry (may have been edited)
        text = self._text_entry.get().strip()
        
        if not text:
            self._update_status("❌ Please enter a command", "#F44336")
            return
        
        logger.info(f"Sending voice command: '{text[:50]}...'")
        
        # Disable UI during send
        self._send_button.config(state=tk.DISABLED)
        self._text_entry.config(state=tk.DISABLED)
        self._update_status("⏳ Sending command...", self.COLOR_PROCESSING)
        
        def send():
            try:
                task_id = self._on_send_text(text)
                
                if task_id:
                    self._result = VoiceDialogResult(
                        result=VoiceCommandResult.SUCCESS,
                        transcribed_text=text,
                        confidence=self._confidence,
                        task_id=task_id,
                    )
                    self._root.after(0, self._close_success)
                else:
                    self._root.after(0, lambda: self._handle_send_error("Failed to send command"))
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                self._root.after(0, lambda: self._handle_send_error(str(e)))
        
        threading.Thread(target=send, daemon=True).start()
    
    def _close_success(self) -> None:
        """Close dialog after successful send."""
        self._update_status("✓ Command sent!", self.COLOR_SUCCESS)
        self._root.after(500, self._close)
    
    def _handle_send_error(self, error: str) -> None:
        """Handle send error."""
        self._update_status(f"❌ {error}", "#F44336")
        self._send_button.config(state=tk.NORMAL)
        self._text_entry.config(state=tk.NORMAL)
    
    def _on_cancel(self) -> None:
        """Handle cancel button."""
        if self._is_recording and self._on_cancel_recording:
            self._on_cancel_recording()
        
        self._result = VoiceDialogResult(
            result=VoiceCommandResult.CANCELLED,
        )
        self._close()
    
    def _on_close(self) -> None:
        """Handle window close."""
        if self._is_recording and self._on_cancel_recording:
            self._on_cancel_recording()
        
        if not self._result:
            self._result = VoiceDialogResult(
                result=VoiceCommandResult.CANCELLED,
            )
        self._close()
    
    def _close(self) -> None:
        """Close the dialog."""
        if self._root:
            self._root.quit()
            self._root.destroy()
            self._root = None


# =============================================================================
# HELPER FUNCTION
# =============================================================================

def show_voice_command_dialog(
    on_start_recording: Callable[[], bool],
    on_stop_recording: Callable[[], Optional[tuple[str, float]]],
    on_send_text: Callable[[str], Optional[str]],
    on_cancel_recording: Optional[Callable[[], None]] = None,
) -> Optional[VoiceDialogResult]:
    """
    Show the voice command dialog and wait for result.
    
    Convenience function for one-shot usage.
    
    Args:
        on_start_recording: Start recording callback
        on_stop_recording: Stop recording callback  
        on_send_text: Send text callback
        on_cancel_recording: Cancel recording callback
        
    Returns:
        VoiceDialogResult or None
    """
    dialog = VoiceCommandDialog(
        on_start_recording=on_start_recording,
        on_stop_recording=on_stop_recording,
        on_send_text=on_send_text,
        on_cancel_recording=on_cancel_recording,
    )
    return dialog.show()
