"""
Command Input Dialog
====================

Simple modal dialog for entering text commands.

This is the PRIMARY user interface for sending commands to SAARTHI.

DESIGN PRINCIPLES:
- Minimal, obvious UI
- User must explicitly initiate
- Clear feedback on success/failure
- No hidden behavior

UI FLOW:
1. User clicks "Send Command" in tray menu
2. Dialog opens with text input
3. User types command and clicks Send
4. Dialog shows result and closes
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum
import threading

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES
# =============================================================================

class CommandResult(Enum):
    """Result of a command dialog interaction."""
    SUCCESS = "success"           # Command sent and accepted
    CANCELLED = "cancelled"       # User cancelled
    INVALID_INPUT = "invalid"     # Input validation failed
    BACKEND_ERROR = "error"       # Backend communication failed


@dataclass
class DialogResult:
    """Result from the command dialog."""
    
    result: CommandResult
    task_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_command_input(text: str) -> tuple[bool, str]:
    """
    Validate command input before sending.
    
    Args:
        text: Raw user input
        
    Returns:
        (is_valid, error_message)
    """
    if text is None:
        return False, "Input cannot be empty"
    
    # Strip whitespace
    stripped = text.strip()
    
    if not stripped:
        return False, "Please enter a command (cannot be empty or whitespace)"
    
    if len(stripped) < 2:
        return False, "Command is too short (minimum 2 characters)"
    
    if len(stripped) > 10000:
        return False, "Command is too long (maximum 10,000 characters)"
    
    # Check for only control characters
    printable = "".join(
        char for char in stripped
        if char in ("\n", "\t") or (ord(char) >= 32 and ord(char) != 127)
    )
    
    if not printable.strip():
        return False, "Command contains only invalid characters"
    
    return True, ""


# =============================================================================
# COMMAND DIALOG
# =============================================================================

class CommandDialog:
    """
    Modal dialog for entering and sending text commands.
    
    USAGE:
        dialog = CommandDialog(on_send_callback)
        result = dialog.show()
    
    The dialog:
    - Opens centered on screen
    - Has a text input field
    - Has Send and Cancel buttons
    - Validates input before sending
    - Shows result via callback
    """
    
    # Dialog dimensions
    WIDTH = 500
    HEIGHT = 250
    
    # Input constraints
    MAX_CHARS = 10000
    
    def __init__(
        self,
        on_send: Callable[[str], DialogResult],
        title: str = "SAARTHI - Send Command",
    ):
        """
        Initialize the command dialog.
        
        Args:
            on_send: Callback function that sends the command and returns result
            title: Dialog window title
        """
        self._on_send = on_send
        self._title = title
        self._result: Optional[DialogResult] = None
        self._root: Optional[tk.Tk] = None
        
    def show(self) -> Optional[DialogResult]:
        """
        Show the dialog and wait for user interaction.
        
        Returns:
            DialogResult with outcome, or None if dialog failed to open
        """
        try:
            self._create_dialog()
            self._root.mainloop()
            return self._result
        except Exception as e:
            logger.error(f"Failed to show command dialog: {e}")
            return DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error=f"Failed to open dialog: {e}"
            )
    
    def _create_dialog(self) -> None:
        """Create the dialog window and widgets."""
        # Create root window
        self._root = tk.Tk()
        self._root.title(self._title)
        self._root.resizable(False, False)
        
        # Center on screen
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = (screen_width - self.WIDTH) // 2
        y = (screen_height - self.HEIGHT) // 2
        self._root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        
        # Set icon and styling
        self._root.configure(bg="#f0f0f0")
        
        # Make it modal-like (always on top, grab focus)
        self._root.attributes("-topmost", True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Create main frame with padding
        main_frame = ttk.Frame(self._root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame,
            text="Enter your command:",
            font=("Segoe UI", 11, "bold"),
        )
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Hint label
        hint_label = ttk.Label(
            main_frame,
            text="Examples: 'open youtube', 'search google for python', 'open github'",
            font=("Segoe UI", 9),
            foreground="#666666",
        )
        hint_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Text input field
        self._text_input = tk.Text(
            main_frame,
            height=4,
            width=50,
            font=("Consolas", 10),
            wrap=tk.WORD,
            relief=tk.SOLID,
            borderwidth=1,
        )
        self._text_input.pack(fill=tk.X, pady=(0, 10))
        self._text_input.focus_set()
        
        # Character counter
        self._char_label = ttk.Label(
            main_frame,
            text=f"0 / {self.MAX_CHARS} characters",
            font=("Segoe UI", 8),
            foreground="#888888",
        )
        self._char_label.pack(anchor=tk.E, pady=(0, 10))
        
        # Bind character count update
        self._text_input.bind("<KeyRelease>", self._update_char_count)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=12,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Send button
        self._send_btn = ttk.Button(
            button_frame,
            text="Send",
            command=self._on_send_click,
            width=12,
        )
        self._send_btn.pack(side=tk.RIGHT)
        
        # Status label (hidden initially)
        self._status_label = ttk.Label(
            main_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="#0066cc",
        )
        self._status_label.pack(anchor=tk.W, pady=(10, 0))
        
        # Bind Enter key to send
        self._root.bind("<Return>", lambda e: self._on_send_click())
        self._root.bind("<Escape>", lambda e: self._on_cancel())
        
        logger.info("Command dialog created")
    
    def _update_char_count(self, event=None) -> None:
        """Update the character count label."""
        text = self._text_input.get("1.0", tk.END).strip()
        count = len(text)
        color = "#888888" if count <= self.MAX_CHARS else "#cc0000"
        self._char_label.configure(
            text=f"{count} / {self.MAX_CHARS} characters",
            foreground=color,
        )
    
    def _on_send_click(self) -> None:
        """Handle Send button click."""
        # Get input text
        text = self._text_input.get("1.0", tk.END).strip()
        
        logger.info(
            "Send button clicked",
            extra={"input_length": len(text)}
        )
        
        # Validate input
        is_valid, error_msg = validate_command_input(text)
        
        if not is_valid:
            logger.warning(
                "Input validation failed",
                extra={"error": error_msg}
            )
            self._result = DialogResult(
                result=CommandResult.INVALID_INPUT,
                error=error_msg,
            )
            messagebox.showwarning("Invalid Input", error_msg)
            return
        
        # Show sending status
        self._set_sending_state(True)
        
        # Send command in background to keep UI responsive
        threading.Thread(
            target=self._send_command_async,
            args=(text,),
            daemon=True,
        ).start()
    
    def _send_command_async(self, text: str) -> None:
        """Send command asynchronously."""
        try:
            # Call the send callback
            result = self._on_send(text)
            
            # Update UI from main thread
            self._root.after(0, lambda: self._handle_send_result(result))
            
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            error_result = DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error=str(e),
            )
            self._root.after(0, lambda: self._handle_send_result(error_result))
    
    def _handle_send_result(self, result: DialogResult) -> None:
        """Handle the result of sending a command."""
        self._result = result
        self._set_sending_state(False)
        
        if result.result == CommandResult.SUCCESS:
            logger.info(
                "Command sent successfully",
                extra={"task_id": result.task_id, "status": result.status}
            )
            
            # Show success message
            success_msg = f"Plan received!\n\nTask ID: {result.task_id}\nStatus: {result.status}"
            if result.message:
                success_msg += f"\n\n{result.message}"
            
            messagebox.showinfo("Command Sent", success_msg)
            self._close()
            
        else:
            logger.warning(
                "Command failed",
                extra={"result": result.result.value, "error": result.error}
            )
            
            # Show error message
            error_msg = result.error or "An unknown error occurred"
            messagebox.showerror("Command Failed", error_msg)
            
            # Don't close - let user try again or cancel
    
    def _set_sending_state(self, sending: bool) -> None:
        """Update UI to show sending state."""
        if sending:
            self._send_btn.configure(state=tk.DISABLED)
            self._text_input.configure(state=tk.DISABLED)
            self._status_label.configure(
                text="Sending command...",
                foreground="#0066cc",
            )
        else:
            self._send_btn.configure(state=tk.NORMAL)
            self._text_input.configure(state=tk.NORMAL)
            self._status_label.configure(text="")
    
    def _on_cancel(self) -> None:
        """Handle Cancel button click or window close."""
        logger.info("Command dialog cancelled")
        self._result = DialogResult(result=CommandResult.CANCELLED)
        self._close()
    
    def _close(self) -> None:
        """Close the dialog."""
        if self._root:
            self._root.quit()
            self._root.destroy()
            self._root = None
            logger.info("Command dialog closed")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def show_command_dialog(
    on_send: Callable[[str], DialogResult],
) -> Optional[DialogResult]:
    """
    Show the command dialog and return result.
    
    Args:
        on_send: Callback that sends the command to backend
        
    Returns:
        DialogResult with outcome
    """
    dialog = CommandDialog(on_send)
    return dialog.show()
