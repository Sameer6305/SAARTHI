"""
Error Handling Module for Local Executor
=========================================

Robust error handling, timeouts, and failure management for SAARTHI local client.

DESIGN PRINCIPLES:
- Fail closed, not open
- No silent failures
- Maximum ONE retry per failure type
- Clear, user-facing error messages
- All failures logged for audit
- Safe idle state on unrecoverable errors

ERROR CATEGORIES:
1. Network Failure - Cannot reach backend
2. Execution Timeout - Action took too long
3. Browser/Media Failure - Could not open resource
4. Permission Failure - User denied or timeout
"""

import functools
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, ParamSpec

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR TYPES
# =============================================================================

class ErrorCategory(Enum):
    """Categories of errors for classification."""
    
    NETWORK_UNREACHABLE = "network_unreachable"   # Backend not reachable
    NETWORK_TIMEOUT = "network_timeout"           # Request timed out
    NETWORK_ERROR = "network_error"               # Other network issues
    EXECUTION_TIMEOUT = "execution_timeout"       # Action execution timeout
    BROWSER_FAILURE = "browser_failure"           # Failed to open browser
    MEDIA_FAILURE = "media_failure"               # Failed to play media
    PERMISSION_DENIED = "permission_denied"       # User denied permission
    PERMISSION_TIMEOUT = "permission_timeout"     # Permission dialog timeout
    VALIDATION_FAILURE = "validation_failure"     # Action validation failed
    INTERNAL_ERROR = "internal_error"             # Unexpected error


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    
    INFO = "info"          # Informational only
    WARNING = "warning"    # Minor issue
    ERROR = "error"        # Significant issue
    CRITICAL = "critical"  # System cannot continue


@dataclass
class UserError:
    """
    User-facing error representation.
    
    SECURITY: Never exposes:
    - Stack traces
    - Internal paths
    - System information
    """
    
    category: ErrorCategory
    severity: ErrorSeverity
    title: str              # Short title for notification
    message: str            # Detailed user message
    internal_code: str      # Code for logs
    action_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_attempted: bool = False
    is_recoverable: bool = False
    
    def to_notification(self) -> tuple[str, str]:
        """Get (title, message) for tray notification."""
        return (self.title, self.message)
    
    def to_dict(self) -> dict:
        """Convert to dict for logging."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "internal_code": self.internal_code,
            "action_id": self.action_id,
            "timestamp": self.timestamp.isoformat(),
            "retry_attempted": self.retry_attempted,
        }


# =============================================================================
# TIMEOUT CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class TimeoutConfig:
    """
    Timeout settings for the local executor.
    
    All timeouts are HARD limits.
    """
    
    # Network timeouts
    connect_timeout_seconds: float = 5.0
    request_timeout_seconds: float = 30.0
    
    # Execution timeouts
    action_execution_seconds: float = 30.0
    browser_open_seconds: float = 10.0
    media_open_seconds: float = 10.0
    
    # Permission dialog
    permission_dialog_seconds: float = 60.0
    
    # Retry configuration
    max_retry_attempts: int = 1  # MAXIMUM ONE RETRY
    retry_delay_seconds: float = 2.0


DEFAULT_TIMEOUTS = TimeoutConfig()


# =============================================================================
# EXECUTION TIMEOUT ENFORCEMENT
# =============================================================================

P = ParamSpec('P')
T = TypeVar('T')


class ExecutionTimeoutError(Exception):
    """Raised when action execution exceeds time limit."""
    
    def __init__(
        self,
        action_type: str,
        action_id: str,
        timeout_seconds: float,
        elapsed_seconds: float,
    ):
        self.action_type = action_type
        self.action_id = action_id
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"Execution timeout for {action_type} ({action_id}): "
            f"{elapsed_seconds:.2f}s exceeded {timeout_seconds:.2f}s limit"
        )


def with_execution_timeout(
    timeout_seconds: float,
    action_type: str = "action",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to enforce timeout on action execution.
    
    Args:
        timeout_seconds: Maximum allowed execution time
        action_type: Name of the action type
        
    ON TIMEOUT:
    - Execution is cancelled
    - ExecutionTimeoutError is raised
    - Error is logged
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.monotonic()
            action_id = kwargs.get("action_id", "unknown")
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                
                try:
                    result = future.result(timeout=timeout_seconds)
                    elapsed = time.monotonic() - start_time
                    
                    logger.debug(
                        f"Action execution completed",
                        extra={
                            "action_type": action_type,
                            "action_id": action_id,
                            "elapsed_seconds": round(elapsed, 3),
                        }
                    )
                    
                    return result
                    
                except FuturesTimeoutError:
                    elapsed = time.monotonic() - start_time
                    
                    logger.error(
                        f"Action execution timeout",
                        extra={
                            "action_type": action_type,
                            "action_id": action_id,
                            "timeout_seconds": timeout_seconds,
                            "elapsed_seconds": round(elapsed, 3),
                        }
                    )
                    
                    raise ExecutionTimeoutError(
                        action_type=action_type,
                        action_id=str(action_id),
                        timeout_seconds=timeout_seconds,
                        elapsed_seconds=elapsed,
                    )
        
        return wrapper
    return decorator


# =============================================================================
# RETRY LOGIC
# =============================================================================

@dataclass
class RetryState:
    """Tracks retry attempts for a specific operation."""
    
    operation_type: str
    max_attempts: int = 1
    attempts: int = 0
    last_error: Optional[str] = None
    
    @property
    def can_retry(self) -> bool:
        """Whether another retry is allowed."""
        return self.attempts < self.max_attempts
    
    def record_attempt(self, error: Optional[str] = None) -> None:
        """Record a retry attempt."""
        self.attempts += 1
        self.last_error = error
        
        logger.info(
            f"Retry attempt recorded",
            extra={
                "operation": self.operation_type,
                "attempt": self.attempts,
                "max_attempts": self.max_attempts,
                "can_retry": self.can_retry,
            }
        )


class RetryManager:
    """
    Manages retry state for the executor.
    
    CONSTRAINT: Maximum ONE retry per failure type per action.
    """
    
    def __init__(self, max_retries: int = 1):
        self._max_retries = max_retries
        self._retry_states: dict[str, RetryState] = {}
        self._lock = threading.Lock()
    
    def get_state(self, operation_key: str) -> RetryState:
        """Get or create retry state for an operation."""
        with self._lock:
            if operation_key not in self._retry_states:
                self._retry_states[operation_key] = RetryState(
                    operation_type=operation_key,
                    max_attempts=self._max_retries,
                )
            return self._retry_states[operation_key]
    
    def clear_state(self, operation_key: str) -> None:
        """Clear retry state after success."""
        with self._lock:
            if operation_key in self._retry_states:
                del self._retry_states[operation_key]
    
    def clear_all(self) -> None:
        """Clear all retry states."""
        with self._lock:
            self._retry_states.clear()


# =============================================================================
# ERROR FACTORIES
# =============================================================================

def create_network_unreachable_error(
    backend_url: str,
    retry_attempted: bool = False,
) -> UserError:
    """Create error for when backend is not reachable."""
    return UserError(
        category=ErrorCategory.NETWORK_UNREACHABLE,
        severity=ErrorSeverity.ERROR,
        title="Cannot Connect",
        message=(
            f"Unable to reach the SAARTHI backend. "
            f"Please check that the server is running."
        ),
        internal_code="NETWORK_UNREACHABLE",
        retry_attempted=retry_attempted,
        is_recoverable=True,
    )


def create_network_timeout_error(
    timeout_seconds: float,
    retry_attempted: bool = False,
) -> UserError:
    """Create error for network request timeout."""
    return UserError(
        category=ErrorCategory.NETWORK_TIMEOUT,
        severity=ErrorSeverity.ERROR,
        title="Request Timed Out",
        message=(
            f"The request took too long to complete. "
            f"Please try again."
        ),
        internal_code="NETWORK_TIMEOUT",
        retry_attempted=retry_attempted,
        is_recoverable=True,
    )


def create_execution_timeout_error(
    action_type: str,
    action_id: str,
    timeout_seconds: float,
) -> UserError:
    """Create error for action execution timeout."""
    action_name = action_type.replace("_", " ").title()
    
    return UserError(
        category=ErrorCategory.EXECUTION_TIMEOUT,
        severity=ErrorSeverity.ERROR,
        title="Action Timed Out",
        message=(
            f"The action '{action_name}' took too long to complete "
            f"and was cancelled for safety."
        ),
        internal_code="EXECUTION_TIMEOUT",
        action_id=action_id,
        is_recoverable=False,
    )


def create_browser_failure_error(
    url: str,
    action_id: str,
    reason: Optional[str] = None,
) -> UserError:
    """Create error for browser open failure."""
    # Truncate URL for display
    display_url = url[:50] + "..." if len(url) > 50 else url
    
    message = f"Failed to open '{display_url}' in your browser."
    if reason:
        message += f" Reason: {reason}"
    
    return UserError(
        category=ErrorCategory.BROWSER_FAILURE,
        severity=ErrorSeverity.ERROR,
        title="Browser Error",
        message=message,
        internal_code="BROWSER_OPEN_FAILED",
        action_id=action_id,
        is_recoverable=False,
    )


def create_media_failure_error(
    media_type: str,
    action_id: str,
    reason: Optional[str] = None,
) -> UserError:
    """Create error for media playback failure."""
    message = f"Failed to play {media_type} file."
    if reason:
        message += f" Reason: {reason}"
    
    return UserError(
        category=ErrorCategory.MEDIA_FAILURE,
        severity=ErrorSeverity.ERROR,
        title="Media Error",
        message=message,
        internal_code="MEDIA_PLAY_FAILED",
        action_id=action_id,
        is_recoverable=False,
    )


def create_permission_denied_error(
    action_type: str,
    action_id: str,
    reason: str = "User denied permission",
) -> UserError:
    """Create error for permission denial."""
    action_name = action_type.replace("_", " ").title()
    
    return UserError(
        category=ErrorCategory.PERMISSION_DENIED,
        severity=ErrorSeverity.INFO,
        title="Permission Denied",
        message=f"'{action_name}' was denied: {reason}",
        internal_code="PERMISSION_DENIED",
        action_id=action_id,
        is_recoverable=False,
    )


def create_validation_failure_error(
    action_type: str,
    action_id: str,
    reason: str,
) -> UserError:
    """Create error for action validation failure."""
    return UserError(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.WARNING,
        title="Action Rejected",
        message=f"Action could not be validated: {reason}",
        internal_code="VALIDATION_FAILED",
        action_id=action_id,
        is_recoverable=False,
    )


def create_internal_error(
    internal_message: str,
    action_id: Optional[str] = None,
) -> UserError:
    """Create error for unexpected internal errors (hides details)."""
    logger.error(
        "Internal error occurred",
        extra={
            "internal_message": internal_message,
            "action_id": action_id,
        }
    )
    
    return UserError(
        category=ErrorCategory.INTERNAL_ERROR,
        severity=ErrorSeverity.ERROR,
        title="Unexpected Error",
        message=(
            "Something unexpected happened. "
            "Please try again. If the problem persists, restart the application."
        ),
        internal_code="INTERNAL_ERROR",
        action_id=action_id,
        is_recoverable=True,
    )


# =============================================================================
# ERROR LOGGER
# =============================================================================

class ErrorLogger:
    """
    Centralized error logging for audit trail.
    
    All errors are logged with consistent format.
    """
    
    def __init__(self, log_name: str = "error_audit"):
        self._logger = logging.getLogger(log_name)
    
    def log_error(self, error: UserError) -> None:
        """Log an error for audit."""
        log_data = error.to_dict()
        
        if error.severity == ErrorSeverity.CRITICAL:
            self._logger.critical(
                f"CRITICAL_ERROR: {error.internal_code}",
                extra=log_data,
            )
        elif error.severity == ErrorSeverity.ERROR:
            self._logger.error(
                f"ERROR: {error.internal_code}",
                extra=log_data,
            )
        elif error.severity == ErrorSeverity.WARNING:
            self._logger.warning(
                f"WARNING: {error.internal_code}",
                extra=log_data,
            )
        else:
            self._logger.info(
                f"INFO: {error.internal_code}",
                extra=log_data,
            )
    
    def log_retry(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        reason: str,
    ) -> None:
        """Log a retry attempt."""
        self._logger.info(
            f"RETRY: {operation} (attempt {attempt}/{max_attempts})",
            extra={
                "operation": operation,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "reason": reason,
            }
        )
    
    def log_final_failure(
        self,
        operation: str,
        attempts: int,
        error: UserError,
    ) -> None:
        """Log when all retries are exhausted."""
        self._logger.error(
            f"FINAL_FAILURE: {operation} after {attempts} attempts",
            extra={
                "operation": operation,
                "attempts": attempts,
                "error": error.to_dict(),
            }
        )


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_retry_manager: Optional[RetryManager] = None
_error_logger: Optional[ErrorLogger] = None


def get_retry_manager() -> RetryManager:
    """Get the singleton retry manager."""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager(max_retries=1)
    return _retry_manager


def get_error_logger() -> ErrorLogger:
    """Get the singleton error logger."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger
