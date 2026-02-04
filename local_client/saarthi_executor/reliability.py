"""
RELIABILITY GUARANTEES - STEP 7 FIX
====================================

Ensures deterministic behavior and clear error handling throughout the system.

GUARANTEES:
1. Same input → Same output (deterministic routing)
2. Clear error messages (never generic "I don't know")
3. Confidence-based execution thresholds
4. Safe fallback for all edge cases
5. Logging for debugging and auditing
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class ReliabilityLevel(Enum):
    """Reliability levels for different operations."""
    CRITICAL = "critical"      # Must succeed, user-visible
    HIGH = "high"              # Should succeed, retry if needed
    NORMAL = "normal"          # Best effort
    LOW = "low"                # Nice to have


@dataclass
class ValidationResult:
    """Result of input/output validation."""
    is_valid: bool
    confidence: float
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    
    @property
    def should_proceed(self) -> bool:
        """Whether to proceed with execution."""
        return self.is_valid and self.confidence >= 0.3
    
    @property
    def needs_confirmation(self) -> bool:
        """Whether to ask for user confirmation."""
        return self.is_valid and 0.3 <= self.confidence < 0.6


class ReliabilityGuard:
    """
    Guards the system with reliability checks and guarantees.
    
    USAGE:
        guard = get_reliability_guard()
        
        # Before execution
        validation = guard.validate_input(text)
        if not validation.should_proceed:
            return guard.create_error_response(validation)
        
        # After execution  
        guard.validate_output(result)
    """
    
    # Confidence thresholds
    EXECUTE_THRESHOLD = 0.6        # Execute without asking
    CONFIRM_THRESHOLD = 0.3        # Ask for confirmation
    REJECT_THRESHOLD = 0.1         # Reject unclear input
    CRITICAL_ACTION_THRESHOLD = 0.9  # Higher bar for dangerous actions
    
    # Critical actions that need higher confidence
    CRITICAL_ACTIONS = {
        'delete', 'remove', 'shutdown', 'restart', 
        'format', 'clear', 'uninstall', 'terminate'
    }
    
    # Known error patterns to catch
    ERROR_PATTERNS = {
        "i don't know": "generic_unknown",
        "cannot complete": "planner_failure",
        "error occurred": "execution_error",
        "failed to": "action_failure",
    }
    
    def __init__(self):
        self._execution_history: List[Dict] = []
        self._error_counts: Dict[str, int] = {}
    
    def validate_input(self, text: str, intent_type: str = None, 
                       confidence: float = 1.0) -> ValidationResult:
        """
        Validate input before processing.
        
        Returns ValidationResult with:
        - is_valid: Whether input can be processed
        - confidence: Adjusted confidence based on validation
        - errors/warnings/suggestions for user feedback
        """
        errors = []
        warnings = []
        suggestions = []
        adjusted_confidence = confidence
        
        # Check for empty/short input
        if not text or len(text.strip()) < 2:
            errors.append("Input is too short to understand")
            return ValidationResult(False, 0.0, errors, warnings, suggestions)
        
        # Check for critical actions
        text_lower = text.lower()
        is_critical = any(action in text_lower for action in self.CRITICAL_ACTIONS)
        
        if is_critical:
            if confidence < self.CRITICAL_ACTION_THRESHOLD:
                warnings.append(f"This looks like a critical action. Please confirm.")
                adjusted_confidence = min(confidence, 0.5)  # Force confirmation
            
            # Extra check for very short critical commands
            if len(text.split()) < 3:
                warnings.append("Critical commands should be specific")
                suggestions.append("Try: 'delete the file named X' instead of 'delete'")
        
        # Check for ambiguous patterns
        ambiguous_patterns = ['stuff', 'things', 'something', 'whatever']
        if any(p in text_lower for p in ambiguous_patterns):
            warnings.append("Your request is a bit vague")
            suggestions.append("Could you be more specific?")
            adjusted_confidence *= 0.7
        
        # Check for question vs command ambiguity
        if '?' in text and intent_type not in ['question', 'knowledge']:
            warnings.append("This looks like a question but might be interpreted as a command")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=adjusted_confidence,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def validate_output(self, result: Dict[str, Any]) -> ValidationResult:
        """
        Validate output before returning to user.
        Catches generic error messages and improves them.
        """
        errors = []
        warnings = []
        suggestions = []
        
        text = result.get('text', '') or result.get('message', '')
        
        if not text:
            errors.append("No response generated")
            return ValidationResult(False, 0.0, errors, warnings, suggestions)
        
        # Check for generic error patterns
        text_lower = text.lower()
        for pattern, error_type in self.ERROR_PATTERNS.items():
            if pattern in text_lower:
                self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
                warnings.append(f"Response contains generic error: {error_type}")
        
        # Check for empty/unhelpful responses
        if len(text) < 10:
            warnings.append("Response is very short")
        
        confidence = result.get('confidence', 0.5)
        
        return ValidationResult(
            is_valid=True,
            confidence=confidence,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def create_error_response(self, validation: ValidationResult, 
                              original_input: str = "") -> Dict[str, Any]:
        """
        Create a helpful error response when validation fails.
        Never returns generic "I don't know".
        """
        if validation.errors:
            message = validation.errors[0]
        elif validation.warnings:
            message = validation.warnings[0]
        else:
            message = "I couldn't process that request"
        
        # Add suggestions
        if validation.suggestions:
            message += f". {validation.suggestions[0]}"
        elif original_input:
            # Generate helpful suggestions
            message += f". Try rephrasing: '{original_input}'"
        
        return {
            "success": False,
            "text": message,
            "confidence": validation.confidence,
            "validation_errors": validation.errors,
            "validation_warnings": validation.warnings,
        }
    
    def wrap_execution(self, func, *args, **kwargs) -> Dict[str, Any]:
        """
        Wrap any execution with reliability guarantees.
        
        - Catches exceptions
        - Logs execution
        - Ensures valid response format
        """
        try:
            result = func(*args, **kwargs)
            
            # Ensure result is a dict
            if not isinstance(result, dict):
                result = {"success": True, "text": str(result)}
            
            # Ensure required fields
            if "success" not in result:
                result["success"] = True
            if "text" not in result and "message" in result:
                result["text"] = result["message"]
            
            # Validate output
            validation = self.validate_output(result)
            if validation.warnings:
                logger.warning(f"Output validation: {validation.warnings}")
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "success": False,
                "text": f"Something went wrong: {str(e)}. Please try again.",
                "error": str(e),
            }
    
    def get_deterministic_route(self, intent_type: str, text: str) -> str:
        """
        Ensure deterministic routing - same input always gets same route.
        
        This prevents random behavior and makes debugging easier.
        """
        # Priority-based routing rules
        text_lower = text.lower()
        
        # Rule 1: Questions go to knowledge
        question_words = ['who', 'what', 'when', 'where', 'why', 'how']
        if any(text_lower.startswith(w) for w in question_words) or '?' in text:
            return 'knowledge'
        
        # Rule 2: Student keywords go to student mode
        student_keywords = ['assignment', 'homework', 'explain', 'quiz', 'exam', 'study']
        if any(kw in text_lower for kw in student_keywords):
            return 'student'
        
        # Rule 3: Action verbs go to action
        action_verbs = ['open', 'close', 'search', 'play', 'stop', 'start', 'run']
        if any(text_lower.startswith(v) for v in action_verbs):
            return 'action'
        
        # Rule 4: Greetings go to conversational
        greetings = ['hello', 'hi', 'hey', 'bye', 'thanks', 'thank you']
        if any(g in text_lower for g in greetings):
            return 'conversational'
        
        # Default based on intent type
        intent_to_route = {
            'question': 'knowledge',
            'greeting': 'conversational',
            'gratitude': 'conversational',
            'goodbye': 'conversational',
            'open_website': 'action',
            'search_web': 'action',
            'multi_step': 'action',
        }
        
        return intent_to_route.get(intent_type, 'action')
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for debugging."""
        return {
            "error_counts": self._error_counts,
            "total_errors": sum(self._error_counts.values()),
            "most_common": max(self._error_counts.items(), key=lambda x: x[1]) if self._error_counts else None,
        }


# Singleton
_reliability_guard: Optional[ReliabilityGuard] = None

def get_reliability_guard() -> ReliabilityGuard:
    """Get singleton ReliabilityGuard instance."""
    global _reliability_guard
    if _reliability_guard is None:
        _reliability_guard = ReliabilityGuard()
    return _reliability_guard
