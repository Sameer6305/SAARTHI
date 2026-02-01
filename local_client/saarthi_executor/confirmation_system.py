"""
Risk-Aware Confirmation System
===============================

Smart confirmation logic that only asks for dangerous actions.

PRODUCT GOALS:
- NEVER ask for confirmation on safe actions (open website, answer question)
- ALWAYS confirm destructive actions (delete, shutdown, terminate)
- Clear risk categories with explicit rules
- Fast path for common, safe operations

DESIGN DECISIONS:

1. WHY RISK-BASED CONFIRMATION?
   - Voice UX is slow: every confirmation adds 2-3 seconds
   - Most commands are safe: confirming "open youtube" is annoying
   - Dangerous commands are rare: worth the friction for safety
   - User trust: predictable behavior builds confidence

2. RISK CATEGORIES:
   - SAFE: Execute immediately, no confirmation (open, search, play, ask)
   - MODERATE: Confirm if uncertain (app with similar name, ambiguous target)
   - DESTRUCTIVE: Always confirm (delete, shutdown, terminate, close all)
   - IRREVERSIBLE: Double confirm (format, system changes)

3. WHAT WE CONFIRM:
   - File deletion
   - Application termination
   - System commands (shutdown, restart)
   - Bulk operations (close all windows)
   - Commands with low confidence

4. WHAT WE DON'T CONFIRM:
   - Opening websites
   - Opening applications
   - Web searches
   - Playing media
   - Questions / explanations
   - Greetings / small talk
"""

import logging
import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for actions."""
    SAFE = auto()           # No confirmation needed
    MODERATE = auto()       # Confirm if confidence < threshold
    DESTRUCTIVE = auto()    # Always confirm
    IRREVERSIBLE = auto()   # Double confirm with explicit phrase


@dataclass
class RiskAssessment:
    """Result of risk assessment for an action."""
    level: RiskLevel
    requires_confirmation: bool
    reason: str = ""
    suggested_confirmation: str = ""  # What to ask user
    
    # For low-confidence situations
    confidence_triggered: bool = False
    original_confidence: float = 1.0


class RiskAssessor:
    """
    Assesses action risk and determines confirmation requirements.
    
    RULES:
    1. Intent type determines base risk level
    2. Specific keywords can elevate risk
    3. Low confidence can require confirmation
    4. Destructive keywords always trigger confirmation
    """
    
    # Intent types and their default risk levels
    INTENT_RISK_MAP: Dict[str, RiskLevel] = {
        # Safe - execute immediately
        "open_website": RiskLevel.SAFE,
        "open_application": RiskLevel.SAFE,
        "search_web": RiskLevel.SAFE,
        "play_media": RiskLevel.SAFE,
        "question": RiskLevel.SAFE,
        "explanation": RiskLevel.SAFE,
        "definition": RiskLevel.SAFE,
        "greeting": RiskLevel.SAFE,
        "farewell": RiskLevel.SAFE,
        "thanks": RiskLevel.SAFE,
        "status": RiskLevel.SAFE,
        "help": RiskLevel.SAFE,
        "confirmation_yes": RiskLevel.SAFE,
        "confirmation_no": RiskLevel.SAFE,
        
        # Moderate - confirm if low confidence
        "system_command": RiskLevel.MODERATE,
        "multi_step": RiskLevel.MODERATE,
        "unknown": RiskLevel.MODERATE,
        
        # These would be destructive if we had them
        "terminate_app": RiskLevel.DESTRUCTIVE,
        "delete_file": RiskLevel.DESTRUCTIVE,
        "system_shutdown": RiskLevel.IRREVERSIBLE,
    }
    
    # Keywords that elevate risk
    DESTRUCTIVE_KEYWORDS: Set[str] = {
        # Process control
        "kill", "terminate", "end", "stop", "close all", "quit all",
        "force quit", "force close", "task kill",
        
        # File operations
        "delete", "remove", "erase", "clear", "wipe", "empty",
        "trash", "recycle",
        
        # System commands
        "shutdown", "restart", "reboot", "sleep", "hibernate",
        "log off", "sign out", "lock",
        
        # Bulk operations
        "all windows", "all tabs", "all apps", "everything",
    }
    
    # Keywords that indicate safety
    SAFE_KEYWORDS: Set[str] = {
        "open", "launch", "start", "show", "display",
        "search", "find", "look up", "google",
        "play", "watch", "listen",
        "what", "why", "how", "explain", "tell me",
    }
    
    # Minimum confidence threshold for auto-execution
    CONFIDENCE_THRESHOLD: float = 0.50  # Below this, ask for confirmation
    
    def __init__(self, confidence_threshold: float = 0.50):
        self.confidence_threshold = confidence_threshold
    
    def assess(
        self,
        intent_type: str,
        raw_text: str,
        confidence: float,
        slots: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Assess the risk of an action.
        
        Args:
            intent_type: The classified intent type
            raw_text: Original user text
            confidence: Intent classification confidence
            slots: Extracted slots (target, query, etc.)
            
        Returns:
            RiskAssessment with confirmation requirements
        """
        text_lower = raw_text.lower()
        
        # 1. Check for destructive keywords first (overrides everything)
        for keyword in self.DESTRUCTIVE_KEYWORDS:
            if keyword in text_lower:
                return RiskAssessment(
                    level=RiskLevel.DESTRUCTIVE,
                    requires_confirmation=True,
                    reason=f"Contains destructive keyword: '{keyword}'",
                    suggested_confirmation=self._generate_confirmation(
                        raw_text, keyword
                    ),
                )
        
        # 2. Get base risk from intent type
        base_risk = self.INTENT_RISK_MAP.get(intent_type, RiskLevel.MODERATE)
        
        # 3. Check confidence for moderate/unknown intents
        if base_risk in {RiskLevel.MODERATE, RiskLevel.DESTRUCTIVE}:
            if confidence < self.confidence_threshold:
                return RiskAssessment(
                    level=RiskLevel.MODERATE,
                    requires_confirmation=True,
                    reason=f"Low confidence ({confidence:.0%})",
                    suggested_confirmation=f"Did you mean: {raw_text}?",
                    confidence_triggered=True,
                    original_confidence=confidence,
                )
        
        # 4. SAFE and high-confidence MODERATE don't need confirmation
        if base_risk == RiskLevel.SAFE:
            return RiskAssessment(
                level=RiskLevel.SAFE,
                requires_confirmation=False,
                reason="Safe intent type",
            )
        
        if base_risk == RiskLevel.MODERATE and confidence >= self.confidence_threshold:
            return RiskAssessment(
                level=RiskLevel.MODERATE,
                requires_confirmation=False,
                reason="Moderate intent with high confidence",
            )
        
        # 5. Destructive/irreversible always confirm
        if base_risk in {RiskLevel.DESTRUCTIVE, RiskLevel.IRREVERSIBLE}:
            return RiskAssessment(
                level=base_risk,
                requires_confirmation=True,
                reason=f"Intent type {intent_type} requires confirmation",
                suggested_confirmation=self._generate_confirmation(raw_text),
            )
        
        # Default: safe
        return RiskAssessment(
            level=RiskLevel.SAFE,
            requires_confirmation=False,
        )
    
    def _generate_confirmation(
        self,
        raw_text: str,
        trigger_keyword: Optional[str] = None,
    ) -> str:
        """Generate a confirmation prompt."""
        if trigger_keyword:
            return f"This will {trigger_keyword}. Are you sure?"
        return f"Should I proceed with: {raw_text}?"
    
    def is_safe_intent(self, intent_type: str) -> bool:
        """Quick check if intent type is always safe."""
        return self.INTENT_RISK_MAP.get(intent_type, RiskLevel.MODERATE) == RiskLevel.SAFE


class PendingConfirmation:
    """
    Tracks an action waiting for user confirmation.
    
    LIFECYCLE:
    1. User says "delete all temp files"
    2. System creates PendingConfirmation
    3. System asks "Delete all temp files. Are you sure?"
    4. User says "yes" → execute
    5. User says "no" or timeout → cancel
    """
    
    # How long to wait for confirmation (seconds)
    TIMEOUT = 30.0
    
    def __init__(
        self,
        raw_text: str,
        intent_type: str,
        slots: Dict[str, Any],
        assessment: RiskAssessment,
        executor_callback: Any = None,  # Function to call if confirmed
    ):
        self.raw_text = raw_text
        self.intent_type = intent_type
        self.slots = slots
        self.assessment = assessment
        self.executor_callback = executor_callback
        self.created_at = __import__('time').time()
        self.resolved = False
        self.confirmed: Optional[bool] = None
    
    def is_expired(self) -> bool:
        """Check if confirmation timed out."""
        import time
        return time.time() - self.created_at > self.TIMEOUT
    
    def confirm(self):
        """User confirmed the action."""
        self.resolved = True
        self.confirmed = True
        logger.info(f"Action confirmed: {self.raw_text}")
    
    def cancel(self):
        """User cancelled the action."""
        self.resolved = True
        self.confirmed = False
        logger.info(f"Action cancelled: {self.raw_text}")


class ConfirmationManager:
    """
    Manages pending confirmations and integrates with session flow.
    
    USAGE:
        manager = ConfirmationManager()
        
        # Check if action needs confirmation
        assessment = manager.assess_action(intent, text, confidence)
        
        if assessment.requires_confirmation:
            # Create pending confirmation
            pending = manager.create_pending(intent, text, slots, assessment)
            # Ask user
            tts.speak(assessment.suggested_confirmation)
            # Wait for next input...
        
        # Later, when user responds:
        if manager.has_pending():
            if manager.is_confirmation_response(user_text):
                if manager.is_positive_confirmation(user_text):
                    manager.confirm_pending()
                    # Execute the action
                else:
                    manager.cancel_pending()
    """
    
    def __init__(self, confidence_threshold: float = 0.50):
        self._assessor = RiskAssessor(confidence_threshold)
        self._pending: Optional[PendingConfirmation] = None
    
    def assess_action(
        self,
        intent_type: str,
        raw_text: str,
        confidence: float,
        slots: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Assess if an action needs confirmation."""
        return self._assessor.assess(intent_type, raw_text, confidence, slots)
    
    def create_pending(
        self,
        intent_type: str,
        raw_text: str,
        slots: Dict[str, Any],
        assessment: RiskAssessment,
        executor_callback: Any = None,
    ) -> PendingConfirmation:
        """Create a pending confirmation."""
        # Clear any expired pending
        self._clear_expired()
        
        self._pending = PendingConfirmation(
            raw_text=raw_text,
            intent_type=intent_type,
            slots=slots,
            assessment=assessment,
            executor_callback=executor_callback,
        )
        
        logger.info(f"Created pending confirmation: {raw_text}")
        return self._pending
    
    def has_pending(self) -> bool:
        """Check if there's a pending confirmation."""
        self._clear_expired()
        return self._pending is not None and not self._pending.resolved
    
    def get_pending(self) -> Optional[PendingConfirmation]:
        """Get the current pending confirmation."""
        self._clear_expired()
        if self._pending and not self._pending.resolved:
            return self._pending
        return None
    
    def confirm_pending(self) -> Optional[PendingConfirmation]:
        """Confirm the pending action."""
        if self._pending and not self._pending.resolved:
            self._pending.confirm()
            result = self._pending
            self._pending = None
            return result
        return None
    
    def cancel_pending(self) -> Optional[PendingConfirmation]:
        """Cancel the pending action."""
        if self._pending and not self._pending.resolved:
            self._pending.cancel()
            result = self._pending
            self._pending = None
            return result
        return None
    
    def _clear_expired(self):
        """Clear expired pending confirmations."""
        if self._pending and self._pending.is_expired():
            logger.info(f"Pending confirmation expired: {self._pending.raw_text}")
            self._pending = None
    
    def is_confirmation_response(self, text: str) -> bool:
        """Check if text is a yes/no response to pending confirmation."""
        if not self.has_pending():
            return False
        
        normalized = text.lower().strip()
        
        # Check for yes/no patterns
        yes_patterns = ["yes", "yeah", "yep", "sure", "ok", "okay", "do it", 
                        "go ahead", "confirm", "proceed", "affirmative"]
        no_patterns = ["no", "nope", "cancel", "stop", "nevermind", "never mind",
                       "abort", "don't", "negative"]
        
        for pattern in yes_patterns + no_patterns:
            if pattern in normalized:
                return True
        
        return False
    
    def is_positive_confirmation(self, text: str) -> bool:
        """Check if text is a positive (yes) confirmation."""
        normalized = text.lower().strip()
        
        yes_patterns = ["yes", "yeah", "yep", "sure", "ok", "okay", "do it",
                        "go ahead", "confirm", "proceed", "affirmative"]
        
        for pattern in yes_patterns:
            if pattern in normalized:
                return True
        
        return False


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_confirmation_manager: Optional[ConfirmationManager] = None


def get_confirmation_manager() -> ConfirmationManager:
    """Get the global confirmation manager."""
    global _confirmation_manager
    if _confirmation_manager is None:
        _confirmation_manager = ConfirmationManager()
    return _confirmation_manager
