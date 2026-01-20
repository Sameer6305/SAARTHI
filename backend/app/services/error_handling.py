"""
Error Handling Module
=====================

Robust error handling, timeouts, and failure management for SAARTHI backend.

DESIGN PRINCIPLES:
- Fail closed, not open
- No silent failures
- No partial execution
- Clear, user-facing error messages
- All failures logged for audit

ERROR CATEGORIES:
1. Planner Timeout - Planning took too long
2. Invalid Intent - User input cannot be processed
3. Validation Failure - Input doesn't meet constraints
4. Service Error - Internal service failure
"""

import asyncio
import functools
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, ParamSpec
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.logging_config import get_logger

logger = get_logger("error_handling")


# =============================================================================
# ERROR TYPES
# =============================================================================

class ErrorCategory(Enum):
    """Categories of errors for classification."""
    
    TIMEOUT = "timeout"              # Operation exceeded time limit
    INVALID_INPUT = "invalid_input"  # User input is malformed
    AMBIGUOUS_INPUT = "ambiguous"    # Intent unclear
    UNSUPPORTED = "unsupported"      # Request cannot be handled
    VALIDATION = "validation"        # Input validation failed
    SERVICE_ERROR = "service_error"  # Internal service failure
    NETWORK_ERROR = "network"        # Network/connection issue


class ErrorSeverity(Enum):
    """Severity levels for error classification."""
    
    LOW = "low"          # Minor issue, recoverable
    MEDIUM = "medium"    # Significant issue, may need user action
    HIGH = "high"        # Critical issue, operation cannot continue
    CRITICAL = "critical"  # System-level failure


@dataclass
class SafeError:
    """
    Safe, user-facing error representation.
    
    SECURITY: Never exposes:
    - Stack traces
    - Internal paths
    - System information
    - Raw exception details
    """
    
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str       # Safe message for user
    internal_code: str      # Internal error code for logs
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recoverable: bool = False
    retry_after_seconds: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to API response format."""
        return {
            "error": True,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.user_message,
            "code": self.internal_code,
            "recoverable": self.recoverable,
            "retry_after": self.retry_after_seconds,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# TIMEOUT CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class TimeoutConfig:
    """
    Timeout settings for various operations.
    
    All timeouts are HARD limits - no extensions.
    """
    
    # Planning phase timeouts
    intent_analysis_seconds: float = 5.0
    plan_generation_seconds: float = 10.0
    total_planning_seconds: float = 15.0  # Hard cap for entire planning
    
    # Validation timeouts
    input_validation_seconds: float = 2.0
    
    # Response timeouts
    response_generation_seconds: float = 3.0


# Default timeout configuration
DEFAULT_TIMEOUTS = TimeoutConfig()


# =============================================================================
# TIMEOUT ENFORCEMENT
# =============================================================================

P = ParamSpec('P')
T = TypeVar('T')


class PlanningTimeoutError(Exception):
    """Raised when planning exceeds the allowed time."""
    
    def __init__(
        self,
        phase: str,
        timeout_seconds: float,
        elapsed_seconds: float,
    ):
        self.phase = phase
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"Planning timeout in {phase}: "
            f"{elapsed_seconds:.2f}s exceeded {timeout_seconds:.2f}s limit"
        )


def with_timeout(
    timeout_seconds: float,
    phase_name: str = "operation",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to enforce timeout on synchronous functions.
    
    Uses ThreadPoolExecutor for non-blocking timeout.
    
    Args:
        timeout_seconds: Maximum allowed execution time
        phase_name: Name of the phase (for error messages)
    
    BEHAVIOR ON TIMEOUT:
    - Function execution is cancelled
    - PlanningTimeoutError is raised
    - Error is logged
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.monotonic()
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                
                try:
                    result = future.result(timeout=timeout_seconds)
                    elapsed = time.monotonic() - start_time
                    
                    logger.debug(
                        f"{phase_name}_completed",
                        elapsed_seconds=round(elapsed, 3),
                        timeout_seconds=timeout_seconds,
                    )
                    
                    return result
                    
                except FuturesTimeoutError:
                    elapsed = time.monotonic() - start_time
                    
                    logger.error(
                        f"{phase_name}_timeout",
                        phase=phase_name,
                        timeout_seconds=timeout_seconds,
                        elapsed_seconds=round(elapsed, 3),
                    )
                    
                    raise PlanningTimeoutError(
                        phase=phase_name,
                        timeout_seconds=timeout_seconds,
                        elapsed_seconds=elapsed,
                    )
        
        return wrapper
    return decorator


async def async_with_timeout(
    coro,
    timeout_seconds: float,
    phase_name: str = "operation",
):
    """
    Execute async coroutine with timeout.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Maximum allowed time
        phase_name: Name of the phase
        
    Returns:
        Coroutine result
        
    Raises:
        PlanningTimeoutError on timeout
    """
    start_time = time.monotonic()
    
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        elapsed = time.monotonic() - start_time
        
        logger.debug(
            f"{phase_name}_completed",
            elapsed_seconds=round(elapsed, 3),
        )
        
        return result
        
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start_time
        
        logger.error(
            f"{phase_name}_timeout",
            phase=phase_name,
            timeout_seconds=timeout_seconds,
            elapsed_seconds=round(elapsed, 3),
        )
        
        raise PlanningTimeoutError(
            phase=phase_name,
            timeout_seconds=timeout_seconds,
            elapsed_seconds=elapsed,
        )


# =============================================================================
# INPUT VALIDATION
# =============================================================================

@dataclass
class InputValidationResult:
    """Result of input validation."""
    
    is_valid: bool
    sanitized_input: Optional[str] = None
    error: Optional[SafeError] = None
    rejection_reason: Optional[str] = None


class InputValidator:
    """
    Validates user input before processing.
    
    VALIDATION RULES:
    1. Not empty
    2. Not too short (min 2 chars)
    3. Not too long (max 10000 chars)
    4. Not pure symbols/numbers
    5. Contains actual words
    6. Not known gibberish patterns
    """
    
    # Constraints
    MIN_INPUT_LENGTH = 2
    MAX_INPUT_LENGTH = 10000
    MIN_WORD_LENGTH = 2
    
    # Patterns indicating invalid input
    GIBBERISH_PATTERNS = [
        r'^[^a-zA-Z]*$',           # No letters at all
        r'^(.)\1{5,}$',            # Repeated single character (aaaaaa)
        r'^[\W\d]+$',              # Only symbols and numbers
        r'^[a-z]{1,2}$',           # Too short to be meaningful
    ]
    
    # Keywords that indicate unsupported requests
    UNSUPPORTED_KEYWORDS = [
        "hack", "crack", "exploit", "ddos", "malware",
        "steal", "password", "credentials",
        "bypass", "admin access", "root access",
    ]
    
    def __init__(self):
        """Initialize the validator."""
        import re
        self._gibberish_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.GIBBERISH_PATTERNS
        ]
        logger.info("input_validator_initialized")
    
    def validate(self, input_text: Optional[str]) -> InputValidationResult:
        """
        Validate user input.
        
        Returns InputValidationResult with validation status.
        
        NEVER raises exceptions - always returns a result.
        """
        # Check for None/empty
        if input_text is None:
            return self._reject(
                ErrorCategory.INVALID_INPUT,
                "Please provide a command or question.",
                "INPUT_NULL",
            )
        
        # Strip whitespace
        text = input_text.strip()
        
        # Check empty after strip
        if not text:
            return self._reject(
                ErrorCategory.INVALID_INPUT,
                "Please enter a command or question.",
                "INPUT_EMPTY",
            )
        
        # Check minimum length
        if len(text) < self.MIN_INPUT_LENGTH:
            return self._reject(
                ErrorCategory.INVALID_INPUT,
                "Your input is too short. Please provide more details.",
                "INPUT_TOO_SHORT",
            )
        
        # Check maximum length
        if len(text) > self.MAX_INPUT_LENGTH:
            return self._reject(
                ErrorCategory.INVALID_INPUT,
                "Your input is too long. Please shorten your request.",
                "INPUT_TOO_LONG",
            )
        
        # Check for gibberish patterns
        for pattern in self._gibberish_patterns:
            if pattern.match(text):
                return self._reject(
                    ErrorCategory.INVALID_INPUT,
                    "I couldn't understand your request. Please try rephrasing.",
                    "INPUT_GIBBERISH",
                )
        
        # Check for unsupported keywords
        text_lower = text.lower()
        for keyword in self.UNSUPPORTED_KEYWORDS:
            if keyword in text_lower:
                return self._reject(
                    ErrorCategory.UNSUPPORTED,
                    "I'm not able to help with that type of request.",
                    "INPUT_UNSUPPORTED",
                )
        
        # Check for actual words
        words = [w for w in text.split() if len(w) >= self.MIN_WORD_LENGTH]
        if len(words) == 0:
            return self._reject(
                ErrorCategory.AMBIGUOUS_INPUT,
                "I need more context. Please describe what you'd like to do.",
                "INPUT_NO_WORDS",
            )
        
        # Sanitize: remove control characters
        sanitized = "".join(
            char for char in text
            if char in ("\n", "\t", " ") or (ord(char) >= 32 and ord(char) < 127)
        ).strip()
        
        # Valid input
        return InputValidationResult(
            is_valid=True,
            sanitized_input=sanitized,
        )
    
    def _reject(
        self,
        category: ErrorCategory,
        user_message: str,
        internal_code: str,
    ) -> InputValidationResult:
        """Create a rejection result."""
        return InputValidationResult(
            is_valid=False,
            error=SafeError(
                category=category,
                severity=ErrorSeverity.MEDIUM,
                user_message=user_message,
                internal_code=internal_code,
                recoverable=True,
            ),
            rejection_reason=internal_code,
        )


# =============================================================================
# INTENT VALIDATION
# =============================================================================

@dataclass
class IntentValidationResult:
    """Result of intent validation."""
    
    is_valid: bool
    error: Optional[SafeError] = None
    rejection_reason: Optional[str] = None


def validate_intent_confidence(
    confidence_score: float,
    intent_category: str,
    min_confidence: float = 0.3,
) -> IntentValidationResult:
    """
    Validate that intent analysis produced a confident result.
    
    LOW CONFIDENCE means we should NOT proceed.
    """
    if confidence_score < min_confidence:
        return IntentValidationResult(
            is_valid=False,
            error=SafeError(
                category=ErrorCategory.AMBIGUOUS_INPUT,
                severity=ErrorSeverity.MEDIUM,
                user_message=(
                    "I'm not sure what you're asking for. "
                    "Could you please rephrase your request?"
                ),
                internal_code="INTENT_LOW_CONFIDENCE",
                recoverable=True,
            ),
            rejection_reason=f"Confidence {confidence_score:.2f} below threshold {min_confidence}",
        )
    
    return IntentValidationResult(is_valid=True)


def validate_intent_is_actionable(
    intent_category: str,
    requires_tools: list[str],
) -> IntentValidationResult:
    """
    Validate that the intent can be acted upon.
    
    Information-only intents with no tools should be handled differently.
    """
    # Information requests without tools are valid but informational
    if intent_category == "information_request" and not requires_tools:
        return IntentValidationResult(
            is_valid=False,
            error=SafeError(
                category=ErrorCategory.UNSUPPORTED,
                severity=ErrorSeverity.LOW,
                user_message=(
                    "I understand you're asking a question, but I can only "
                    "help with actions like opening websites or playing media. "
                    "Please ask me to do something specific."
                ),
                internal_code="INTENT_NOT_ACTIONABLE",
                recoverable=True,
            ),
            rejection_reason="Information request with no tools",
        )
    
    return IntentValidationResult(is_valid=True)


# =============================================================================
# ERROR FACTORY
# =============================================================================

def create_timeout_error(
    phase: str,
    timeout_seconds: float,
    elapsed_seconds: float,
) -> SafeError:
    """Create a user-safe timeout error."""
    return SafeError(
        category=ErrorCategory.TIMEOUT,
        severity=ErrorSeverity.HIGH,
        user_message=(
            "Your request took too long to process. "
            "Please try again with a simpler request."
        ),
        internal_code=f"TIMEOUT_{phase.upper()}",
        recoverable=True,
        retry_after_seconds=5,
    )


def create_planning_failed_error(reason: str) -> SafeError:
    """Create a user-safe planning failure error."""
    return SafeError(
        category=ErrorCategory.SERVICE_ERROR,
        severity=ErrorSeverity.HIGH,
        user_message=(
            "I wasn't able to plan how to complete your request. "
            "Please try rephrasing or simplifying your command."
        ),
        internal_code="PLANNING_FAILED",
        recoverable=True,
    )


def create_service_error(internal_message: str) -> SafeError:
    """Create a generic service error (hides internal details)."""
    logger.error(
        "service_error_occurred",
        internal_message=internal_message,
    )
    
    return SafeError(
        category=ErrorCategory.SERVICE_ERROR,
        severity=ErrorSeverity.HIGH,
        user_message=(
            "Something went wrong on my end. "
            "Please try again in a moment."
        ),
        internal_code="SERVICE_ERROR",
        recoverable=True,
        retry_after_seconds=10,
    )


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_input_validator: Optional[InputValidator] = None


def get_input_validator() -> InputValidator:
    """Get the singleton input validator."""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
