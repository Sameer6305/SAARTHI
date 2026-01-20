"""
Command Dialog Test
===================

Quick test for the command input dialog.

USAGE:
    python test_command_dialog.py

This will:
1. Open the command dialog
2. Send a test command to the backend
3. Display the result
"""

import sys
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from saarthi_executor.backend_client import create_backend_client
from saarthi_executor.command_dialog import (
    CommandDialog,
    DialogResult,
    CommandResult,
    show_command_dialog,
)


def setup_logging():
    """Setup logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%H:%M:%S"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Create backend client
backend_client = None


def send_to_backend(input_text: str) -> DialogResult:
    """Send command to backend and return dialog result."""
    global backend_client
    
    if backend_client is None:
        backend_client = create_backend_client()
    
    if not backend_client.is_connected:
        if not backend_client.connect():
            return DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error="Cannot connect to backend at localhost:8000"
            )
    
    try:
        result = backend_client.send_command(input_text)
        
        if result.success:
            return DialogResult(
                result=CommandResult.SUCCESS,
                task_id=result.task_id,
                status=result.status,
                message=f"Intent: {result.intent_summary}" if result.intent_summary else None
            )
        else:
            return DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error=result.error
            )
    except Exception as e:
        return DialogResult(
            result=CommandResult.BACKEND_ERROR,
            error=str(e)
        )


def main():
    """Run the command dialog test."""
    setup_logging()
    
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║              SAARTHI Command Dialog Test                         ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print("Opening command dialog...")
    print("Try commands like: 'open youtube', 'search google for python'")
    print()
    
    result = show_command_dialog(on_send=send_to_backend)
    
    print()
    print("-" * 60)
    
    if result:
        print(f"Result: {result.result.value}")
        if result.task_id:
            print(f"Task ID: {result.task_id}")
        if result.status:
            print(f"Status: {result.status}")
        if result.message:
            print(f"Message: {result.message}")
        if result.error:
            print(f"Error: {result.error}")
    else:
        print("No result returned")
    
    # Cleanup
    if backend_client:
        backend_client.disconnect()
    
    print()


if __name__ == "__main__":
    main()
