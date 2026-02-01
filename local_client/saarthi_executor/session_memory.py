"""
Session Memory System
======================

Contextual memory for natural follow-up conversations.

PRODUCT GOALS:
- Enable "do it again", "tell me more", "why?", "how?"
- Remember last command, topic, action result
- Clean reset per session (no stale context)
- Memory decay for privacy (no persistent conversation logs)

DESIGN DECISIONS:

1. WHY SESSION-SCOPED?
   - Privacy: Users expect voice assistants to forget
   - Predictability: Fresh start on each session
   - Simplicity: No complex memory management

2. WHY RING BUFFER FOR HISTORY?
   - Bounded memory (5-10 entries max)
   - O(1) append and lookup
   - Natural forgetting of old context

3. WHAT WE INTENTIONALLY DON'T STORE:
   - Passwords, credentials, personal info
   - Raw audio (only transcriptions)
   - Cross-session history (use CommandHistory for that)

INTERVIEW TALKING POINTS:
- Slot filling with context: Partial utterances complete from memory
- Referent resolution: "it", "that", "this" → previous target
- Action replay: "again" → repeat last executed action
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Deque
from collections import deque
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of remembered context."""
    COMMAND = "command"          # Last executed command
    QUESTION = "question"        # Last answered question
    TOPIC = "topic"              # Current conversation topic
    TARGET = "target"            # Last referenced entity (website, app)
    SEARCH_QUERY = "search"      # Last search query
    EXPLANATION = "explanation"  # Last explained topic


@dataclass
class ContextEntry:
    """A single memory entry."""
    context_type: ContextType
    value: Any
    timestamp: float = field(default_factory=time.time)
    
    # Original command that created this context
    raw_text: str = ""
    
    # Intent information
    intent_type: str = ""
    confidence: float = 0.0
    
    # Execution result
    success: bool = True
    result_text: str = ""
    
    # Slots from the original intent
    slots: Dict[str, Any] = field(default_factory=dict)
    
    def age_seconds(self) -> float:
        """How old is this context?"""
        return time.time() - self.timestamp
    
    def is_fresh(self, max_age: float = 60.0) -> bool:
        """Is context still fresh (not stale)?"""
        return self.age_seconds() < max_age


@dataclass
class SessionContext:
    """
    Complete session context for follow-up handling.
    
    This is what gets passed to the intent engine to resolve
    partial utterances like "why?", "again", "more".
    """
    # Most recent entries by type
    last_command: Optional[ContextEntry] = None
    last_question: Optional[ContextEntry] = None
    last_topic: Optional[str] = None
    last_target: Optional[str] = None
    
    # Current mode
    focus_mode: bool = False
    
    # Session metadata
    session_start: float = field(default_factory=time.time)
    command_count: int = 0
    
    def is_empty(self) -> bool:
        """No context available yet."""
        return (
            self.last_command is None and
            self.last_question is None and
            self.last_topic is None
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for debugging."""
        return {
            "last_command": self.last_command.raw_text if self.last_command else None,
            "last_question": self.last_question.raw_text if self.last_question else None,
            "last_topic": self.last_topic,
            "last_target": self.last_target,
            "focus_mode": self.focus_mode,
            "command_count": self.command_count,
            "session_age_seconds": time.time() - self.session_start,
        }


class SessionMemory:
    """
    Manages conversational context within a session.
    
    MEMORY STRUCTURE:
    - Ring buffer of last N interactions (default: 10)
    - Quick lookup by context type
    - Automatic staleness detection
    
    USAGE:
        memory = SessionMemory()
        
        # Record a command
        memory.record_command(intent, result)
        
        # Get context for follow-up resolution
        ctx = memory.get_context()
        if ctx.last_topic:
            # Can answer "tell me more about it"
            pass
        
        # Reset on new session
        memory.reset()
    """
    
    # Max entries in history ring buffer
    MAX_HISTORY = 10
    
    # Context staleness thresholds (seconds)
    COMMAND_STALE_AFTER = 120.0   # 2 minutes
    QUESTION_STALE_AFTER = 180.0  # 3 minutes
    TOPIC_STALE_AFTER = 300.0     # 5 minutes
    
    def __init__(self):
        self._history: Deque[ContextEntry] = deque(maxlen=self.MAX_HISTORY)
        self._by_type: Dict[ContextType, ContextEntry] = {}
        self._session_start = time.time()
        self._command_count = 0
        self._focus_mode = False
        
        # Repeatable action (for "do it again")
        self._last_repeatable: Optional[ContextEntry] = None
    
    def record(
        self,
        context_type: ContextType,
        value: Any,
        raw_text: str = "",
        intent_type: str = "",
        confidence: float = 0.0,
        success: bool = True,
        result_text: str = "",
        slots: Optional[Dict[str, Any]] = None,
    ) -> ContextEntry:
        """
        Record a new context entry.
        
        Returns the created entry.
        """
        entry = ContextEntry(
            context_type=context_type,
            value=value,
            raw_text=raw_text,
            intent_type=intent_type,
            confidence=confidence,
            success=success,
            result_text=result_text,
            slots=slots or {},
        )
        
        self._history.append(entry)
        self._by_type[context_type] = entry
        self._command_count += 1
        
        # Track repeatable actions
        if context_type == ContextType.COMMAND and success:
            self._last_repeatable = entry
        
        logger.debug(f"Recorded context: {context_type.value}={value}")
        
        return entry
    
    def record_command(
        self,
        raw_text: str,
        intent_type: str,
        target: Optional[str] = None,
        slots: Optional[Dict[str, Any]] = None,
        success: bool = True,
        result_text: str = "",
    ):
        """
        Convenience method to record a command execution.
        
        Also updates last_target if present.
        """
        self.record(
            context_type=ContextType.COMMAND,
            value=raw_text,
            raw_text=raw_text,
            intent_type=intent_type,
            success=success,
            result_text=result_text,
            slots=slots,
        )
        
        if target:
            self.record(
                context_type=ContextType.TARGET,
                value=target,
                raw_text=raw_text,
            )
    
    def record_question(
        self,
        raw_text: str,
        topic: str,
        answer: str,
        source: str = "",
    ):
        """
        Convenience method to record a Q&A interaction.
        """
        self.record(
            context_type=ContextType.QUESTION,
            value=topic,
            raw_text=raw_text,
            intent_type="question",
            success=True,
            result_text=answer,
        )
        
        self.record(
            context_type=ContextType.TOPIC,
            value=topic,
            raw_text=raw_text,
        )
    
    def get_last(self, context_type: ContextType) -> Optional[ContextEntry]:
        """Get most recent entry of a specific type."""
        entry = self._by_type.get(context_type)
        
        if entry is None:
            return None
        
        # Check staleness
        max_age = {
            ContextType.COMMAND: self.COMMAND_STALE_AFTER,
            ContextType.QUESTION: self.QUESTION_STALE_AFTER,
            ContextType.TOPIC: self.TOPIC_STALE_AFTER,
            ContextType.TARGET: self.COMMAND_STALE_AFTER,
            ContextType.SEARCH_QUERY: self.COMMAND_STALE_AFTER,
            ContextType.EXPLANATION: self.QUESTION_STALE_AFTER,
        }.get(context_type, 60.0)
        
        if not entry.is_fresh(max_age):
            return None
        
        return entry
    
    def get_context(self) -> SessionContext:
        """
        Get current session context for follow-up resolution.
        
        Returns a snapshot of the current memory state.
        """
        last_command = self.get_last(ContextType.COMMAND)
        last_question = self.get_last(ContextType.QUESTION)
        last_topic_entry = self.get_last(ContextType.TOPIC)
        last_target_entry = self.get_last(ContextType.TARGET)
        
        return SessionContext(
            last_command=last_command,
            last_question=last_question,
            last_topic=last_topic_entry.value if last_topic_entry else None,
            last_target=last_target_entry.value if last_target_entry else None,
            focus_mode=self._focus_mode,
            session_start=self._session_start,
            command_count=self._command_count,
        )
    
    def get_repeatable_action(self) -> Optional[ContextEntry]:
        """
        Get the last action that can be repeated with "do it again".
        
        Only returns successful, non-stale commands.
        """
        if self._last_repeatable is None:
            return None
        
        if not self._last_repeatable.is_fresh(self.COMMAND_STALE_AFTER):
            return None
        
        return self._last_repeatable
    
    def get_topic_for_follow_up(self) -> Optional[str]:
        """
        Get topic for "tell me more", "why?", etc.
        
        Prioritizes question topic over command target.
        """
        # First try question topic
        question = self.get_last(ContextType.QUESTION)
        if question and question.value:
            return question.value
        
        # Then try topic
        topic = self.get_last(ContextType.TOPIC)
        if topic and topic.value:
            return topic.value
        
        # Finally try target
        target = self.get_last(ContextType.TARGET)
        if target and target.value:
            return target.value
        
        return None
    
    def set_focus_mode(self, enabled: bool):
        """Enable or disable focus mode."""
        self._focus_mode = enabled
        logger.info(f"Focus mode: {'enabled' if enabled else 'disabled'}")
    
    def is_focus_mode(self) -> bool:
        """Check if focus mode is active."""
        return self._focus_mode
    
    def get_history(self, n: int = 5) -> List[ContextEntry]:
        """Get last N entries (most recent first)."""
        return list(reversed(list(self._history)))[:n]
    
    def reset(self):
        """
        Clear all session memory.
        
        Called on explicit session end or timeout.
        """
        self._history.clear()
        self._by_type.clear()
        self._session_start = time.time()
        self._command_count = 0
        self._focus_mode = False
        self._last_repeatable = None
        
        logger.info("Session memory reset")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session for debugging."""
        return {
            "session_age": time.time() - self._session_start,
            "command_count": self._command_count,
            "history_size": len(self._history),
            "focus_mode": self._focus_mode,
            "has_repeatable": self._last_repeatable is not None,
            "context": self.get_context().to_dict(),
        }


# =============================================================================
# FOLLOW-UP PATTERNS
# =============================================================================

class FollowUpType(Enum):
    """Types of follow-up utterances."""
    REPEAT = "repeat"           # "again", "do it again", "repeat"
    ELABORATE = "elaborate"     # "tell me more", "continue", "more"
    EXPLAIN_WHY = "why"         # "why?", "why is that?"
    EXPLAIN_HOW = "how"         # "how?", "how does that work?"
    SIMPLIFY = "simplify"       # "simpler", "in simple terms"
    EXAMPLE = "example"         # "give me an example", "example?"
    RELATED = "related"         # "what about...", "and..."
    CONFIRM = "confirm"         # "yes", "do it", "go ahead"
    CANCEL = "cancel"           # "no", "cancel", "never mind"
    NOT_FOLLOW_UP = "none"      # Not a follow-up


@dataclass
class FollowUpMatch:
    """Result of follow-up detection."""
    follow_up_type: FollowUpType
    confidence: float
    requires_context: bool = True
    modifier: Optional[str] = None  # e.g., "in Python" for "how in Python?"


class FollowUpDetector:
    """
    Detects if an utterance is a follow-up to previous context.
    
    DESIGN DECISION: Pattern matching over ML
    - Faster (no model loading)
    - Predictable (exact patterns)
    - Maintainable (easy to add patterns)
    - No false positives on unrelated commands
    """
    
    # Patterns for each follow-up type
    PATTERNS = {
        FollowUpType.REPEAT: [
            r"^(do it )?again$",
            r"^repeat( that)?$",
            r"^one more time$",
            r"^same( thing)?$",
            r"^replay$",
        ],
        FollowUpType.ELABORATE: [
            r"^(tell me )?more$",
            r"^(go on|continue|elaborate)$",
            r"^(can you )?explain (more|further)$",
            r"^what else$",
            r"^and( then)?(\?)?$",
        ],
        FollowUpType.EXPLAIN_WHY: [
            r"^why(\?)?$",
            r"^why (is|does|did|was|would) (that|it|this)(\?)?$",
            r"^(but )?why though(\?)?$",
            r"^reason(\?)?$",
        ],
        FollowUpType.EXPLAIN_HOW: [
            r"^how(\?)?$",
            r"^how (does|do|did|would) (that|it|this) work(\?)?$",
            r"^how (exactly|specifically)(\?)?$",
            r"^in what way(\?)?$",
        ],
        FollowUpType.SIMPLIFY: [
            r"^(in )?simple(r)?( terms)?$",
            r"^(make it |explain )?simpler$",
            r"^eli5$",
            r"^for (a )?beginner(s)?$",
            r"^dumb it down$",
            r"^in (layman|plain) terms$",
        ],
        FollowUpType.EXAMPLE: [
            r"^(give me (an )?)?example(s)?(\?)?$",
            r"^for example(\?)?$",
            r"^show me( an example)?$",
            r"^like what(\?)?$",
        ],
        FollowUpType.CONFIRM: [
            r"^yes$",
            r"^yeah$",
            r"^yep$",
            r"^sure$",
            r"^do it$",
            r"^go ahead$",
            r"^confirm$",
            r"^okay$",
            r"^ok$",
        ],
        FollowUpType.CANCEL: [
            r"^no$",
            r"^nope$",
            r"^cancel$",
            r"^never ?mind$",
            r"^stop$",
            r"^forget it$",
            r"^abort$",
        ],
    }
    
    def __init__(self):
        import re
        # Compile patterns for efficiency
        self._compiled = {
            ftype: [re.compile(p, re.IGNORECASE) for p in patterns]
            for ftype, patterns in self.PATTERNS.items()
        }
    
    def detect(self, text: str, context: SessionContext) -> FollowUpMatch:
        """
        Detect if text is a follow-up utterance.
        
        Returns FollowUpMatch with type and confidence.
        """
        normalized = text.lower().strip()
        
        # Check each follow-up type
        for ftype, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.match(normalized):
                    # Check if context supports this follow-up
                    requires_context = ftype not in {
                        FollowUpType.CONFIRM,
                        FollowUpType.CANCEL,
                    }
                    
                    if requires_context and context.is_empty():
                        # No context to follow up on
                        continue
                    
                    return FollowUpMatch(
                        follow_up_type=ftype,
                        confidence=0.95,
                        requires_context=requires_context,
                    )
        
        return FollowUpMatch(
            follow_up_type=FollowUpType.NOT_FOLLOW_UP,
            confidence=1.0,
            requires_context=False,
        )
    
    def is_follow_up(self, text: str, context: SessionContext) -> bool:
        """Quick check if text is any kind of follow-up."""
        match = self.detect(text, context)
        return match.follow_up_type != FollowUpType.NOT_FOLLOW_UP


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_session_memory: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """Get the global session memory instance."""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory


def reset_session_memory():
    """Reset the global session memory."""
    global _session_memory
    if _session_memory is not None:
        _session_memory.reset()
