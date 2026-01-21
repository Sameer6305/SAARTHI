"""
Dialog Runner Module
=====================

Runs Tkinter dialogs in a separate process to avoid threading issues.

PROBLEM:
- pystray runs callbacks in worker threads
- Tkinter MUST run in the main thread
- This causes "main thread is not in main loop" errors

SOLUTION:
- Spawn dialog as a subprocess
- Communicate via JSON over pipes
- Dialog runs in its own Python process where Tkinter is in main thread

USAGE:
    result = run_dialog_in_subprocess("voice_command", callbacks_dict)
"""

import json
import logging
import subprocess
import sys
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class DialogProcessResult:
    """Result from a dialog subprocess."""
    success: bool
    dialog_type: str
    data: Dict[str, Any]
    error: Optional[str] = None


# =============================================================================
# SUBPROCESS DIALOG RUNNER
# =============================================================================

def run_dialog_subprocess(
    dialog_type: str,
    dialog_data: Dict[str, Any] = None,
) -> Optional[DialogProcessResult]:
    """
    Run a dialog in a separate subprocess.
    
    Args:
        dialog_type: Type of dialog ("command", "voice_command", "voice_settings")
        dialog_data: Initial data to pass to dialog
        
    Returns:
        DialogProcessResult with outcome
    """
    try:
        # Get path to dialog subprocess script
        script_path = Path(__file__).parent / "dialog_subprocess.py"
        
        if not script_path.exists():
            logger.error(f"Dialog subprocess script not found: {script_path}")
            return DialogProcessResult(
                success=False,
                dialog_type=dialog_type,
                data={},
                error="Dialog script not found"
            )
        
        # Prepare input data
        input_data = json.dumps({
            "dialog_type": dialog_type,
            "data": dialog_data or {},
        })
        
        # Run subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Dialog subprocess failed: {result.stderr}")
            return DialogProcessResult(
                success=False,
                dialog_type=dialog_type,
                data={},
                error=result.stderr[:500] if result.stderr else "Unknown error"
            )
        
        # Parse output
        try:
            output_data = json.loads(result.stdout)
            return DialogProcessResult(
                success=output_data.get("success", False),
                dialog_type=dialog_type,
                data=output_data.get("data", {}),
                error=output_data.get("error"),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse dialog output: {e}")
            return DialogProcessResult(
                success=False,
                dialog_type=dialog_type,
                data={},
                error=f"Invalid dialog response: {result.stdout[:200]}"
            )
            
    except subprocess.TimeoutExpired:
        logger.error("Dialog subprocess timed out")
        return DialogProcessResult(
            success=False,
            dialog_type=dialog_type,
            data={},
            error="Dialog timed out"
        )
    except Exception as e:
        logger.error(f"Error running dialog subprocess: {e}")
        return DialogProcessResult(
            success=False,
            dialog_type=dialog_type,
            data={},
            error=str(e)
        )


# =============================================================================
# SIMPLE TEXT COMMAND DIALOG
# =============================================================================

def run_simple_command_dialog() -> Optional[str]:
    """
    Run a simple text command dialog in subprocess.
    
    Returns:
        The entered command text, or None if cancelled
    """
    result = run_dialog_subprocess("simple_command")
    
    if result and result.success:
        return result.data.get("command_text")
    return None


def run_simple_voice_dialog() -> Optional[Dict[str, Any]]:
    """
    Run a simple voice command dialog in subprocess.
    
    For now, this opens a simple text dialog with voice styling.
    Full voice integration requires inter-process communication.
    
    Returns:
        Dict with command_text and other metadata, or None if cancelled
    """
    result = run_dialog_subprocess("simple_voice")
    
    if result and result.success:
        return result.data
    return None
