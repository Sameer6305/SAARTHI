"""
STRICT INTENT ROUTER - STEP 1 FIX
==================================

DESIGN: Single source of truth for routing ALL user input.

ROUTING CATEGORIES:
A) CONVERSATIONAL / KNOWLEDGE  → Direct LLM response (NO planner)
B) ACTIONABLE TASK             → Planner → Executor + Permission
C) STUDENT MODE                → Student tools (explanatory mode)
D) INVALID / AMBIGUOUS         → Clarification question

CRITICAL RULE: NEVER mix categories. One input = One route.
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from .intent_engine import IntentType, ParsedIntent

logger = logging.getLogger(__name__)


class RouteCategory(Enum):
    """Strict routing categories - NO OVERLAP."""
    CONVERSATIONAL = "conversational"  # greetings, thanks, chitchat
    KNOWLEDGE = "knowledge"            # questions, explanations (direct answer)
    ACTION = "action"                  # open, search, play (needs executor)
    STUDENT = "student"                # assignment, quiz, concept help
    SYSTEM = "system"                  # status, help, settings
    AMBIGUOUS = "ambiguous"            # unclear, needs clarification
    INVALID = "invalid"                # nonsense, too vague


@dataclass
class RoutingDecision:
    """
    Complete routing decision with justification.
    
    This is the SINGLE SOURCE OF TRUTH for how input is processed.
    """
    category: RouteCategory
    confidence: float  # 0.0 to 1.0
    
    # Original intent classification
    intent_type: IntentType
    intent_confidence: float
    
    # Routing metadata
    requires_planner: bool  # True = send to planner/executor
    requires_permission: bool  # True = needs user confirmation
    requires_online: bool  # True = needs internet
    
    # If ambiguous/invalid
    clarification_question: Optional[str] = None
    suggested_rephrase: Optional[str] = None
    
    # Reasoning (for debugging)
    reasoning: str = ""
    
    def is_actionable(self) -> bool:
        """Returns True if this requires executor."""
        return self.category == RouteCategory.ACTION
    
    def is_conversational(self) -> bool:
        """Returns True if this is conversational (direct response)."""
        return self.category in [RouteCategory.CONVERSATIONAL, RouteCategory.KNOWLEDGE]
    
    def needs_clarification(self) -> bool:
        """Returns True if we need to ask for clarification."""
        return self.category in [RouteCategory.AMBIGUOUS, RouteCategory.INVALID]


class StrictIntentRouter:
    """
    STRICT intent router - prevents misrouting bugs.
    
    PRINCIPLE: Explicit is better than implicit.
    Every routing decision is documented with reasoning.
    """
    
    # Intent type → Route category mapping (EXPLICIT)
    INTENT_TO_ROUTE = {
        # Conversational (NO ACTION)
        IntentType.GREETING: RouteCategory.CONVERSATIONAL,
        IntentType.FAREWELL: RouteCategory.CONVERSATIONAL,
        IntentType.THANKS: RouteCategory.CONVERSATIONAL,
        IntentType.CONFIRMATION_YES: RouteCategory.CONVERSATIONAL,
        IntentType.CONFIRMATION_NO: RouteCategory.CONVERSATIONAL,
        
        # Knowledge (DIRECT ANSWER)
        IntentType.QUESTION: RouteCategory.KNOWLEDGE,
        IntentType.EXPLANATION: RouteCategory.KNOWLEDGE,
        IntentType.DEFINITION: RouteCategory.KNOWLEDGE,
        
        # Action (NEEDS EXECUTOR)
        IntentType.OPEN_WEBSITE: RouteCategory.ACTION,
        IntentType.OPEN_APPLICATION: RouteCategory.ACTION,
        IntentType.SEARCH_WEB: RouteCategory.ACTION,
        IntentType.PLAY_MEDIA: RouteCategory.ACTION,
        IntentType.SYSTEM_COMMAND: RouteCategory.ACTION,
        IntentType.MULTI_STEP: RouteCategory.ACTION,
        
        # System
        IntentType.STATUS: RouteCategory.SYSTEM,
        IntentType.HELP: RouteCategory.SYSTEM,
        IntentType.CANCEL: RouteCategory.SYSTEM,
    }
    
    # Student mode keywords (simple detection for now)
    STUDENT_KEYWORDS = {
        "assignment", "homework", "quiz", "mcq", "question paper",
        "exam", "study", "prepare", "resume", "cv", "gate", "jee",
        "explain step by step", "teach me", "help me understand",
        "algorithm explanation", "data structure explanation",
    }
    
    def route(self, intent: ParsedIntent) -> RoutingDecision:
        """
        Make routing decision for a parsed intent.
        
        This is the CRITICAL function that determines how input is processed.
        """
        # 1. Check for unknown/low confidence
        if intent.intent_type == IntentType.UNKNOWN or intent.confidence < 0.3:
            return self._handle_unknown(intent)
        
        # 2. Check for student mode indicators
        if self._is_student_mode(intent):
            return self._route_to_student(intent)
        
        # 3. Check for knowledge questions (CRITICAL: don't send to planner!)
        if self._is_knowledge_question(intent):
            return self._route_to_knowledge(intent)
        
        # 4. Route based on intent type
        category = self.INTENT_TO_ROUTE.get(intent.intent_type, RouteCategory.AMBIGUOUS)
        
        if category == RouteCategory.ACTION:
            return self._route_to_action(intent)
        elif category == RouteCategory.CONVERSATIONAL:
            return self._route_to_conversational(intent)
        elif category == RouteCategory.SYSTEM:
            return self._route_to_system(intent)
        else:
            return self._handle_ambiguous(intent)
    
    def _is_student_mode(self, intent: ParsedIntent) -> bool:
        """Detect if input is student-related."""
        text = intent.raw_text.lower()
        
        # Check for student keywords
        for keyword in self.STUDENT_KEYWORDS:
            if keyword in text:
                return True
        
        # Check for specific patterns
        if re.search(r'\b(dsa|os|dbms|cn|gate|jee)\b', text, re.I):
            return True
        
        if re.search(r'(step by step|teach|tutor|explain.*concept)', text, re.I):
            return True
        
        return False
    
    def _is_knowledge_question(self, intent: ParsedIntent) -> bool:
        """
        Detect if this is a knowledge question (NOT an action).
        
        CRITICAL: Questions like "Who is Elon Musk?" should NEVER go to planner.
        """
        if intent.intent_type in [IntentType.QUESTION, IntentType.EXPLANATION, IntentType.DEFINITION]:
            return True
        
        text = intent.raw_text.lower()
        
        # Question words at start
        question_starts = ['who is', 'what is', 'when is', 'where is', 'why is', 
                          'how does', 'what are', 'who are', 'explain', 'define',
                          'tell me about', 'describe']
        
        for start in question_starts:
            if text.startswith(start):
                return True
        
        # Contains question mark
        if '?' in text:
            return True
        
        return False
    
    def _route_to_knowledge(self, intent: ParsedIntent) -> RoutingDecision:
        """Route to knowledge system (direct answer, NO planner)."""
        return RoutingDecision(
            category=RouteCategory.KNOWLEDGE,
            confidence=intent.confidence,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,  # CRITICAL: NO PLANNER
            requires_permission=False,
            requires_online=True,  # May need Wikipedia/search
            reasoning=f"Knowledge question detected: {intent.intent_type.value}",
        )
    
    def _route_to_action(self, intent: ParsedIntent) -> RoutingDecision:
        """Route to action executor (WITH planner/permission)."""
        # Determine if permission needed
        risky_actions = {IntentType.SYSTEM_COMMAND}
        needs_permission = intent.intent_type in risky_actions
        
        return RoutingDecision(
            category=RouteCategory.ACTION,
            confidence=intent.confidence,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=True,  # Actions need planning
            requires_permission=needs_permission,
            requires_online=False,
            reasoning=f"Action detected: {intent.intent_type.value}",
        )
    
    def _route_to_conversational(self, intent: ParsedIntent) -> RoutingDecision:
        """Route to conversational handler (simple response)."""
        return RoutingDecision(
            category=RouteCategory.CONVERSATIONAL,
            confidence=intent.confidence,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,
            requires_permission=False,
            requires_online=False,
            reasoning=f"Conversational intent: {intent.intent_type.value}",
        )
    
    def _route_to_student(self, intent: ParsedIntent) -> RoutingDecision:
        """Route to student mode (explanatory, teaching approach)."""
        return RoutingDecision(
            category=RouteCategory.STUDENT,
            confidence=0.8,  # High confidence for student mode
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,
            requires_permission=False,
            requires_online=True,  # May need LLM
            reasoning="Student mode keywords detected",
        )
    
    def _route_to_system(self, intent: ParsedIntent) -> RoutingDecision:
        """Route to system commands (status, help, settings)."""
        return RoutingDecision(
            category=RouteCategory.SYSTEM,
            confidence=intent.confidence,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,
            requires_permission=False,
            requires_online=False,
            reasoning=f"System command: {intent.intent_type.value}",
        )
    
    def _handle_unknown(self, intent: ParsedIntent) -> RoutingDecision:
        """Handle unknown/low-confidence input."""
        # Try to give helpful clarification
        text = intent.raw_text.strip()
        
        if len(text) < 3:
            clarification = "I didn't catch that. Could you say more?"
        elif any(word in text.lower() for word in ['open', 'launch', 'start']):
            clarification = "Did you want me to open something? What should I open?"
        elif '?' in text or text.lower().startswith(('what', 'who', 'when', 'where', 'why', 'how')):
            clarification = "What would you like to know about?"
        else:
            clarification = "I'm not sure what you mean. Could you rephrase that?"
        
        return RoutingDecision(
            category=RouteCategory.INVALID,
            confidence=0.0,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,
            requires_permission=False,
            requires_online=False,
            clarification_question=clarification,
            reasoning=f"Unknown intent or low confidence ({intent.confidence:.2f})",
        )
    
    def _handle_ambiguous(self, intent: ParsedIntent) -> RoutingDecision:
        """Handle ambiguous input."""
        return RoutingDecision(
            category=RouteCategory.AMBIGUOUS,
            confidence=intent.confidence,
            intent_type=intent.intent_type,
            intent_confidence=intent.confidence,
            requires_planner=False,
            requires_permission=False,
            requires_online=False,
            clarification_question="I understood that partially. Can you be more specific?",
            reasoning="Ambiguous or unclear intent",
        )


# =============================================================================
# FACTORY
# =============================================================================

_router_instance: Optional[StrictIntentRouter] = None

def get_router() -> StrictIntentRouter:
    """Get singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = StrictIntentRouter()
    return _router_instance


def route_intent(intent: ParsedIntent) -> RoutingDecision:
    """Convenience function for routing."""
    return get_router().route(intent)
