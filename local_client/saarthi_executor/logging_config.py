"""
Logging Configuration
=====================

Structured logging for the SAARTHI local executor.
All security events are logged for audit.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
) -> None:
    """
    Configure logging for the executor.
    
    Logs are written to both console and file (if specified).
    Security events are always logged.
    """
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, handlers filter
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


class SecurityLogger:
    """
    Dedicated logger for security events.
    
    All security-relevant events should use this logger.
    """
    
    def __init__(self):
        """Initialize security logger."""
        self._logger = logging.getLogger("security")
    
    def action_validated(self, action_id: str, action_type: str) -> None:
        """Log successful action validation."""
        self._logger.info(
            f"ACTION_VALIDATED | {action_id} | {action_type}"
        )
    
    def action_rejected(
        self, 
        action_id: str, 
        reason: str, 
        rule: str
    ) -> None:
        """Log action rejection (security event)."""
        self._logger.warning(
            f"ACTION_REJECTED | {action_id} | {rule} | {reason}"
        )
    
    def permission_granted(self, action_id: str, action_type: str) -> None:
        """Log user granting permission."""
        self._logger.info(
            f"PERMISSION_GRANTED | {action_id} | {action_type}"
        )
    
    def permission_denied(self, action_id: str, action_type: str) -> None:
        """Log user denying permission."""
        self._logger.info(
            f"PERMISSION_DENIED | {action_id} | {action_type}"
        )
    
    def action_executed(
        self, 
        action_id: str, 
        action_type: str, 
        success: bool
    ) -> None:
        """Log action execution."""
        status = "SUCCESS" if success else "FAILURE"
        self._logger.info(
            f"ACTION_EXECUTED | {action_id} | {action_type} | {status}"
        )
    
    def forbidden_action_attempted(
        self, 
        action_type: str, 
        details: str
    ) -> None:
        """Log attempt to execute forbidden action (critical)."""
        self._logger.error(
            f"FORBIDDEN_ACTION | {action_type} | {details}"
        )
    
    def state_transition(
        self, 
        from_state: str, 
        to_state: str, 
        reason: str
    ) -> None:
        """Log state machine transition."""
        self._logger.info(
            f"STATE_TRANSITION | {from_state} -> {to_state} | {reason}"
        )
    
    # =========================================================================
    # BACKEND COMMUNICATION LOGGING (NEW)
    # =========================================================================
    
    def backend_connected(self, url: str) -> None:
        """Log successful backend connection."""
        self._logger.info(
            f"BACKEND_CONNECTED | {url}"
        )
    
    def backend_disconnected(self, url: str) -> None:
        """Log backend disconnection."""
        self._logger.info(
            f"BACKEND_DISCONNECTED | {url}"
        )
    
    def backend_connection_failed(self, url: str, error: str) -> None:
        """Log failed backend connection."""
        self._logger.error(
            f"BACKEND_CONNECTION_FAILED | {url} | {error}"
        )
    
    def command_sent(
        self, 
        task_id: str, 
        input_length: int
    ) -> None:
        """Log command sent to backend."""
        self._logger.info(
            f"COMMAND_SENT | {task_id} | input_length={input_length}"
        )
    
    def command_failed(self, error: str) -> None:
        """Log failed command."""
        self._logger.warning(
            f"COMMAND_FAILED | {error}"
        )
    
    def actions_received(
        self, 
        task_id: str, 
        action_count: int, 
        action_types: list[str]
    ) -> None:
        """Log actions received from backend."""
        types_str = ", ".join(action_types)
        self._logger.info(
            f"ACTIONS_RECEIVED | {task_id} | count={action_count} | types=[{types_str}]"
        )
    
    def actions_fetch_failed(self, task_id: str, error: str) -> None:
        """Log failed action fetch."""
        self._logger.warning(
            f"ACTIONS_FETCH_FAILED | {task_id} | {error}"
        )


# Global security logger instance
security_logger = SecurityLogger()
