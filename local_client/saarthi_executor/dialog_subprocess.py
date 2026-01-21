#!/usr/bin/env python3
"""
Dialog Subprocess Script
========================

This script is run as a separate Python process to handle Tkinter dialogs.
It receives dialog configuration via stdin and outputs result via stdout.

IMPORTANT: This runs in its own process where Tkinter is in the main thread.

Input (JSON via stdin):
    {
        "dialog_type": "simple_command" | "simple_voice",
        "data": { ... optional initial data ... }
    }

Output (JSON via stdout):
    {
        "success": true/false,
        "data": { ... result data ... },
        "error": "error message if failed"
    }
"""

import json
import sys
import tkinter as tk
from tkinter import ttk


def create_simple_command_dialog(root: tk.Tk, initial_data: dict) -> dict:
    """Create a simple command input dialog."""
    result = {"command_text": None, "cancelled": True}
    
    # Configure window
    root.title("SAARTHI - Send Command")
    root.geometry("500x200")
    root.resizable(False, False)
    
    # Center on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"+{x}+{y}")
    
    # Make topmost
    root.attributes("-topmost", True)
    
    # Main frame
    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title_label = ttk.Label(
        main_frame,
        text="📝 Enter Your Command",
        font=("Segoe UI", 12, "bold"),
    )
    title_label.pack(pady=(0, 10))
    
    # Instruction
    instruction_label = ttk.Label(
        main_frame,
        text="Type your command below and click Send",
        font=("Segoe UI", 9),
        foreground="#666666",
    )
    instruction_label.pack(pady=(0, 10))
    
    # Entry field
    entry_var = tk.StringVar()
    entry = ttk.Entry(
        main_frame,
        textvariable=entry_var,
        font=("Segoe UI", 11),
    )
    entry.pack(fill=tk.X, pady=(0, 15))
    entry.focus_set()
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X)
    
    def on_send():
        text = entry_var.get().strip()
        if text:
            result["command_text"] = text
            result["cancelled"] = False
            root.quit()
    
    def on_cancel():
        result["cancelled"] = True
        root.quit()
    
    send_btn = ttk.Button(
        button_frame,
        text="Send",
        command=on_send,
    )
    send_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    cancel_btn = ttk.Button(
        button_frame,
        text="Cancel",
        command=on_cancel,
    )
    cancel_btn.pack(side=tk.RIGHT)
    
    # Bind Enter key
    entry.bind("<Return>", lambda e: on_send())
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    
    return result


def create_simple_voice_dialog(root: tk.Tk, initial_data: dict) -> dict:
    """Create a simple voice command dialog (text-based for now)."""
    result = {"command_text": None, "cancelled": True, "is_voice": True}
    
    # Configure window
    root.title("SAARTHI - Voice Command")
    root.geometry("500x250")
    root.resizable(False, False)
    
    # Center on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"+{x}+{y}")
    
    # Make topmost
    root.attributes("-topmost", True)
    
    # Main frame
    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title with voice icon
    title_label = ttk.Label(
        main_frame,
        text="🎤 Voice Command",
        font=("Segoe UI", 14, "bold"),
    )
    title_label.pack(pady=(0, 5))
    
    # Voice note
    note_label = ttk.Label(
        main_frame,
        text="Voice recording will be available in a future update.\nFor now, please type your command below.",
        font=("Segoe UI", 9),
        foreground="#666666",
        justify=tk.CENTER,
    )
    note_label.pack(pady=(0, 15))
    
    # Privacy note
    privacy_label = ttk.Label(
        main_frame,
        text="🔒 Push-to-talk only • Audio stays on device • Local transcription",
        font=("Segoe UI", 8),
        foreground="#888888",
    )
    privacy_label.pack(pady=(0, 10))
    
    # Entry field
    entry_var = tk.StringVar()
    entry = ttk.Entry(
        main_frame,
        textvariable=entry_var,
        font=("Segoe UI", 11),
    )
    entry.pack(fill=tk.X, pady=(0, 15))
    entry.focus_set()
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X)
    
    def on_send():
        text = entry_var.get().strip()
        if text:
            result["command_text"] = text
            result["cancelled"] = False
            root.quit()
    
    def on_cancel():
        result["cancelled"] = True
        root.quit()
    
    send_btn = ttk.Button(
        button_frame,
        text="Send Command",
        command=on_send,
    )
    send_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    cancel_btn = ttk.Button(
        button_frame,
        text="Cancel",
        command=on_cancel,
    )
    cancel_btn.pack(side=tk.RIGHT)
    
    # Bind Enter key
    entry.bind("<Return>", lambda e: on_send())
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    
    return result


def main():
    """Main entry point for dialog subprocess."""
    try:
        # Read input from stdin
        input_text = sys.stdin.read()
        input_data = json.loads(input_text)
        
        dialog_type = input_data.get("dialog_type", "simple_command")
        data = input_data.get("data", {})
        
        # Create Tkinter root
        root = tk.Tk()
        
        # Create appropriate dialog
        if dialog_type == "simple_command":
            result = create_simple_command_dialog(root, data)
        elif dialog_type == "simple_voice":
            result = create_simple_voice_dialog(root, data)
        else:
            output = {
                "success": False,
                "error": f"Unknown dialog type: {dialog_type}",
                "data": {},
            }
            print(json.dumps(output))
            return
        
        # Run dialog
        root.mainloop()
        
        # Cleanup
        try:
            root.destroy()
        except:
            pass
        
        # Output result
        output = {
            "success": not result.get("cancelled", True),
            "data": result,
            "error": None,
        }
        print(json.dumps(output))
        
    except Exception as e:
        output = {
            "success": False,
            "error": str(e),
            "data": {},
        }
        print(json.dumps(output))


if __name__ == "__main__":
    main()
