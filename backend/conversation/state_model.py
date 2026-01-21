"""
Conversation State Model
========================

Manages multi-turn dialogue state for the SAARTHI assistant.

DESIGN PRINCIPLES:
1. Context-aware: Maintains recent conversation history
2. Intent-driven: Classifies user input before acting
3. Confirmation-gated: No action without explicit user approval
4. Privacy-first: All state is RAM-only, cleared on session end

STATE MACHINE:
    IDLE → UNDERSTANDING → CLARIFYING → PLANNING → CONFIRMING → EXECUTING → RESPONDING → IDLE
                ↑              │              │           │
                └──────────────┴──────────────┴───────────┘
                        (user clarification / rejection)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any
import uuid


# =============================================================================
# ENUMS
# =============================================================================

class ConversationState(Enum):
    """Current state of the conversation."""
    IDLE = "idle"                       # Waiting for user input
    UNDERSTANDING = "understanding"     # Processing user input
    CLARIFYING = "clarifying"           # Asking clarification question
    PLANNING = "planning"               # LLM is planning actions
    CONFIRMING = "confirming"           # Waiting for user confirmation
    EXECUTING = "executing"             # Action is being executed
    RESPONDING = "responding"           # Generating response
    ERROR = "error"                     # Error state


class IntentType(Enum):
    """Classification of user intent."""
    # Task intents (require planning)
    OPEN_URL = "open_url"               # Open a website
    SEARCH_WEB = "search_web"           # Search for information
    READ_FILE = "read_file"             # Read/summarize a file
    CALCULATE = "calculate"             # Math/engineering calculation
    EXPLAIN = "explain"                 # Explain a concept
    STUDY_PLAN = "study_plan"           # Create study schedule
    QUIZ_HELP = "quiz_help"             # Help with quiz/MCQ
    
    # Conversational intents (no action needed)
    GREETING = "greeting"               # Hello, hi, etc.
    THANKS = "thanks"                   # Thank you
    CLARIFICATION = "clarification"     # User providing more info
    CONFIRMATION = "confirmation"       # Yes, no, approve, reject
    FOLLOWUP = "followup"               # Follow-up question
    CHITCHAT = "chitchat"               # General conversation
    
    # Meta intents
    HELP = "help"                       # What can you do?
    CANCEL = "cancel"                   # Cancel current operation
    UNKNOWN = "unknown"                 # Cannot classify


class ConfirmationStatus(Enum):
    """Status of action confirmation."""
    PENDING = "pending"                 # Waiting for user response
    APPROVED = "approved"               # User approved
    REJECTED = "rejected"               # User rejected
    MODIFIED = "modified"               # User modified the action
    TIMEOUT = "timeout"                 # Confirmation timed out


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Turn:
    """A single conversation turn (user + assistant)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    
    # User input
    user_text: str = ""
    user_intent: IntentType = IntentType.UNKNOWN
    user_entities: Dict[str, Any] = field(default_factory=dict)
    
    # Assistant response
    assistant_text: str = ""
    assistant_action: Optional[str] = None
    
    # Metadata
    confidence: float = 0.0
    required_clarification: bool = False
    action_confirmed: Optional[bool] = None


@dataclass
class PendingAction:
    """An action waiting for user confirmation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""               # Human-readable description
    risk_level: str = "low"             # low, medium, high
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationContext:
    """
    Full conversation context for a session.
    
    PRIVACY: This is RAM-only. Cleared when session ends.
    No persistence, no logging of conversation content.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    
    # Current state
    state: ConversationState = ConversationState.IDLE
    
    # Conversation history (sliding window)
    history: List[Turn] = field(default_factory=list)
    max_history: int = 5                # Keep last N turns only
    
    # Current turn being processed
    current_turn: Optional[Turn] = None
    
    # Pending action (if any)
    pending_action: Optional[PendingAction] = None
    
    # Task context (for multi-turn tasks)
    task_context: Dict[str, Any] = field(default_factory=dict)
    
    # Clarification state
    clarification_question: Optional[str] = None
    clarification_for: Optional[str] = None  # What we're clarifying
    
    def add_turn(self, turn: Turn) -> None:
        """Add a turn to history, maintaining sliding window."""
        self.history.append(turn)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_recent_context(self, n: int = 3) -> List[Turn]:
        """Get last N turns for context."""
        return self.history[-n:] if self.history else []
    
    def clear_pending(self) -> None:
        """Clear pending action and clarification."""
        self.pending_action = None
        self.clarification_question = None
        self.clarification_for = None
    
    def to_prompt_context(self) -> str:
        """
        Convert recent history to a prompt context string.
        Used for feeding context to the LLM.
        """
        if not self.history:
            return ""
        
        lines = ["Recent conversation:"]
        for turn in self.get_recent_context():
            lines.append(f"User: {turn.user_text}")
            if turn.assistant_text:
                lines.append(f"Assistant: {turn.assistant_text}")
        
        return "\n".join(lines)


# =============================================================================
# CONVERSATION MANAGER
# =============================================================================

class ConversationManager:
    """
    Manages conversation state and transitions.
    
    RESPONSIBILITIES:
    1. Maintain conversation context
    2. Classify user intents
    3. Manage state transitions
    4. Generate clarification questions
    5. Handle confirmations
    
    DOES NOT:
    - Execute actions (that's the Executor's job)
    - Call LLMs directly (that's the Planner's job)
    - Store conversations persistently (privacy)
    """
    
    # Intent keywords for fast classification
    INTENT_KEYWORDS = {
        IntentType.OPEN_URL: ["open", "go to", "visit", "browse", "launch"],
        IntentType.SEARCH_WEB: ["search", "find", "look up", "google", "what is"],
        IntentType.READ_FILE: ["read", "summarize", "open file", "show", "pdf"],
        IntentType.CALCULATE: ["calculate", "solve", "compute", "what's", "how much"],
        IntentType.EXPLAIN: ["explain", "how does", "what does", "tell me about"],
        IntentType.STUDY_PLAN: ["study plan", "schedule", "timetable", "plan for"],
        IntentType.QUIZ_HELP: ["quiz", "mcq", "question", "answer this", "solve this"],
        IntentType.GREETING: ["hello", "hi", "hey", "good morning", "good evening"],
        IntentType.THANKS: ["thanks", "thank you", "thx", "appreciate"],
        IntentType.HELP: ["help", "what can you do", "commands", "abilities"],
        IntentType.CANCEL: ["cancel", "stop", "nevermind", "forget it"],
        IntentType.CONFIRMATION: ["yes", "no", "okay", "confirm", "approve", "reject", "deny"],
    }
    
    # Clarification templates
    CLARIFICATION_TEMPLATES = {
        "url_ambiguous": "Which website would you like me to open? For example, 'YouTube' or 'Google'.",
        "file_not_found": "I couldn't find that file. Could you provide the full path or filename?",
        "search_vague": "What specifically would you like me to search for?",
        "action_unclear": "I'm not sure what you'd like me to do. Could you rephrase that?",
        "confirm_action": "I'm about to {action}. Should I proceed? (Yes/No)",
    }
    
    def __init__(self):
        self._context = ConversationContext()
    
    @property
    def context(self) -> ConversationContext:
        return self._context
    
    @property
    def state(self) -> ConversationState:
        return self._context.state
    
    def new_session(self) -> str:
        """Start a new conversation session. Returns session ID."""
        self._context = ConversationContext()
        return self._context.session_id
    
    def classify_intent(self, text: str) -> tuple[IntentType, float]:
        """
        Classify user intent from text.
        
        Returns (intent, confidence).
        
        NOTE: This is a simple keyword-based classifier.
        In production, use the LLM for better classification.
        """
        text_lower = text.lower().strip()
        
        # Check for confirmation first (state-dependent)
        if self._context.state == ConversationState.CONFIRMING:
            if any(w in text_lower for w in ["yes", "okay", "sure", "do it", "proceed", "confirm"]):
                return IntentType.CONFIRMATION, 0.95
            if any(w in text_lower for w in ["no", "cancel", "stop", "don't", "reject"]):
                return IntentType.CANCEL, 0.95
        
        # Check for clarification response
        if self._context.state == ConversationState.CLARIFYING:
            return IntentType.CLARIFICATION, 0.8
        
        # Keyword matching for other intents
        best_intent = IntentType.UNKNOWN
        best_score = 0.0
        
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    score = len(keyword) / len(text_lower) + 0.5
                    if score > best_score:
                        best_score = min(score, 0.9)
                        best_intent = intent
        
        return best_intent, best_score
    
    def extract_entities(self, text: str, intent: IntentType) -> Dict[str, Any]:
        """
        Extract relevant entities from text based on intent.
        
        NOTE: Simple extraction. LLM does better job.
        """
        entities = {}
        text_lower = text.lower()
        
        if intent == IntentType.OPEN_URL:
            # Extract website names
            sites = ["youtube", "google", "github", "stackoverflow", "wikipedia"]
            for site in sites:
                if site in text_lower:
                    entities["site"] = site
                    entities["url"] = f"https://www.{site}.com"
                    break
        
        elif intent == IntentType.SEARCH_WEB:
            # Extract search query (everything after "search for" or "find")
            for prefix in ["search for", "search", "find", "look up"]:
                if prefix in text_lower:
                    idx = text_lower.index(prefix) + len(prefix)
                    entities["query"] = text[idx:].strip()
                    break
        
        return entities
    
    def needs_clarification(self, intent: IntentType, entities: Dict, confidence: float) -> Optional[str]:
        """
        Check if we need to ask for clarification.
        
        Returns clarification question or None.
        """
        if confidence < 0.5:
            return self.CLARIFICATION_TEMPLATES["action_unclear"]
        
        if intent == IntentType.OPEN_URL and "url" not in entities:
            return self.CLARIFICATION_TEMPLATES["url_ambiguous"]
        
        if intent == IntentType.SEARCH_WEB and not entities.get("query"):
            return self.CLARIFICATION_TEMPLATES["search_vague"]
        
        return None
    
    def create_confirmation_request(
        self, 
        action_type: str, 
        parameters: Dict[str, Any],
        description: str
    ) -> PendingAction:
        """
        Create a pending action that needs user confirmation.
        """
        action = PendingAction(
            action_type=action_type,
            parameters=parameters,
            description=description,
            risk_level="low",
        )
        self._context.pending_action = action
        self._context.state = ConversationState.CONFIRMING
        return action
    
    def handle_confirmation(self, approved: bool) -> Optional[PendingAction]:
        """
        Handle user's confirmation response.
        
        Returns the action if approved, None if rejected.
        """
        if not self._context.pending_action:
            return None
        
        action = self._context.pending_action
        
        if approved:
            action.status = ConfirmationStatus.APPROVED
            self._context.state = ConversationState.EXECUTING
            return action
        else:
            action.status = ConfirmationStatus.REJECTED
            self._context.clear_pending()
            self._context.state = ConversationState.IDLE
            return None
    
    def transition_to(self, new_state: ConversationState) -> None:
        """Transition to a new state."""
        old_state = self._context.state
        self._context.state = new_state
        # Could add logging/callbacks here
    
    def process_input(self, user_text: str) -> Dict[str, Any]:
        """
        Process user input and determine next action.
        
        Returns a dict with:
        - intent: classified intent
        - entities: extracted entities
        - needs_clarification: bool
        - clarification_question: str or None
        - needs_confirmation: bool
        - pending_action: action details or None
        - is_conversational: bool (no action needed)
        
        This does NOT execute actions. It prepares them for the planner.
        """
        # Classify intent
        intent, confidence = self.classify_intent(user_text)
        
        # Extract entities
        entities = self.extract_entities(user_text, intent)
        
        # Create turn record
        turn = Turn(
            user_text=user_text,
            user_intent=intent,
            user_entities=entities,
            confidence=confidence,
        )
        self._context.current_turn = turn
        
        # Check for clarification need
        clarification = self.needs_clarification(intent, entities, confidence)
        
        # Determine if this is a conversational intent (no action)
        conversational_intents = {
            IntentType.GREETING, IntentType.THANKS, IntentType.CHITCHAT,
            IntentType.HELP, IntentType.FOLLOWUP
        }
        is_conversational = intent in conversational_intents
        
        # Handle confirmation responses
        if intent == IntentType.CONFIRMATION:
            action = self.handle_confirmation(approved=True)
            return {
                "intent": intent,
                "entities": entities,
                "needs_clarification": False,
                "clarification_question": None,
                "needs_confirmation": False,
                "pending_action": action,
                "is_conversational": False,
                "execute_now": action is not None,
            }
        
        if intent == IntentType.CANCEL:
            self.handle_confirmation(approved=False)
            return {
                "intent": intent,
                "entities": entities,
                "needs_clarification": False,
                "clarification_question": None,
                "needs_confirmation": False,
                "pending_action": None,
                "is_conversational": True,
                "execute_now": False,
            }
        
        # If clarification needed
        if clarification:
            self._context.clarification_question = clarification
            self._context.clarification_for = intent.value
            self.transition_to(ConversationState.CLARIFYING)
            
            return {
                "intent": intent,
                "entities": entities,
                "needs_clarification": True,
                "clarification_question": clarification,
                "needs_confirmation": False,
                "pending_action": None,
                "is_conversational": False,
                "execute_now": False,
            }
        
        # If action intent, create pending action
        if not is_conversational and intent != IntentType.UNKNOWN:
            action = self.create_confirmation_request(
                action_type=intent.value,
                parameters=entities,
                description=self._create_action_description(intent, entities),
            )
            
            return {
                "intent": intent,
                "entities": entities,
                "needs_clarification": False,
                "clarification_question": None,
                "needs_confirmation": True,
                "pending_action": action,
                "is_conversational": False,
                "execute_now": False,
            }
        
        # Conversational or unknown
        return {
            "intent": intent,
            "entities": entities,
            "needs_clarification": False,
            "clarification_question": None,
            "needs_confirmation": False,
            "pending_action": None,
            "is_conversational": is_conversational,
            "execute_now": False,
        }
    
    def _create_action_description(self, intent: IntentType, entities: Dict) -> str:
        """Create human-readable description of the action."""
        if intent == IntentType.OPEN_URL:
            site = entities.get("site", entities.get("url", "website"))
            return f"Open {site} in your browser"
        
        if intent == IntentType.SEARCH_WEB:
            query = entities.get("query", "your query")
            return f"Search the web for '{query}'"
        
        if intent == IntentType.READ_FILE:
            file = entities.get("file", "the file")
            return f"Read and summarize {file}"
        
        if intent == IntentType.CALCULATE:
            expr = entities.get("expression", "the expression")
            return f"Calculate {expr}"
        
        return f"Perform {intent.value}"
    
    def complete_turn(self, assistant_response: str, action_taken: Optional[str] = None) -> None:
        """
        Complete the current turn with assistant's response.
        """
        if self._context.current_turn:
            self._context.current_turn.assistant_text = assistant_response
            self._context.current_turn.assistant_action = action_taken
            self._context.add_turn(self._context.current_turn)
            self._context.current_turn = None
        
        self._context.clear_pending()
        self.transition_to(ConversationState.IDLE)
