"""
Intent Classification Engine v2.0
=================================

Interview-grade intent classification with:
- Layered parsing pipeline
- Confidence-based routing
- Slot extraction
- Partial intent recovery
- Extensible command registry

DESIGN PRINCIPLES:
1. Declarative patterns (no procedural if/else chains)
2. Confidence-based decisions
3. Separation of parsing and execution
4. Easy extension without touching core logic

INTERVIEW TALKING POINTS:
- Why layered parsing? Graceful degradation, predictable behavior
- Why confidence scores? Enables threshold-based routing
- Why slot extraction? Separates "what" from "how"
- Why registry pattern? Open/closed principle, hot-reloadable
"""

import re
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import (
    Optional, Dict, Any, List, Tuple, Callable, Pattern, Set, Match
)
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# INTENT TYPES
# =============================================================================

class IntentType(Enum):
    """
    Intent classification categories.
    
    Design: Each intent type maps to exactly one executor.
    """
    # Action intents (execute something)
    OPEN_WEBSITE = "open_website"
    OPEN_APPLICATION = "open_application"
    SEARCH_WEB = "search_web"
    PLAY_MEDIA = "play_media"
    SYSTEM_COMMAND = "system_command"
    
    # Knowledge intents (answer something)
    QUESTION = "question"
    EXPLANATION = "explanation"
    DEFINITION = "definition"
    
    # Conversational intents
    GREETING = "greeting"
    FAREWELL = "farewell"
    THANKS = "thanks"
    CONFIRMATION_YES = "confirmation_yes"
    CONFIRMATION_NO = "confirmation_no"
    
    # System intents
    STATUS = "status"
    HELP = "help"
    CANCEL = "cancel"
    
    # Compound intents
    MULTI_STEP = "multi_step"
    
    # Fallback
    UNKNOWN = "unknown"


# =============================================================================
# SLOT EXTRACTION
# =============================================================================

@dataclass
class Slot:
    """
    Extracted slot from user input.
    
    Slots are the "arguments" to intents:
    - OPEN_WEBSITE: target="youtube"
    - PLAY_MEDIA: query="lofi music", platform="youtube"
    - QUESTION: topic="binary search"
    """
    name: str
    value: Any
    confidence: float = 1.0
    source: str = "pattern"  # pattern, entity, inference
    
    def __repr__(self):
        return f"Slot({self.name}={self.value!r}, conf={self.confidence:.2f})"


@dataclass
class ParsedIntent:
    """
    Complete parsed intent with slots and metadata.
    
    This is the output of the intent classification pipeline.
    """
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    slots: Dict[str, Slot] = field(default_factory=dict)
    
    # Original text
    raw_text: str = ""
    normalized_text: str = ""
    
    # Parsing metadata
    verb: Optional[str] = None
    target: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    
    # Which parsing layer matched
    source: str = "unknown"  # exact, verb_object, fuzzy, question, fallback
    
    # For multi-step intents
    sub_intents: List['ParsedIntent'] = field(default_factory=list)
    
    def get_slot(self, name: str, default: Any = None) -> Any:
        """Get slot value by name."""
        slot = self.slots.get(name)
        return slot.value if slot else default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "intent_type": self.intent_type.value,
            "confidence": round(self.confidence, 3),
            "slots": {k: {"value": v.value, "confidence": v.confidence} 
                      for k, v in self.slots.items()},
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "verb": self.verb,
            "target": self.target,
            "source": self.source,
        }


# =============================================================================
# TEXT NORMALIZER
# =============================================================================

class TextNormalizer:
    """
    Text normalization for consistent intent matching.
    
    Steps:
    1. Lowercase
    2. Remove punctuation
    3. Remove filler words
    4. Normalize whitespace
    5. Handle contractions
    """
    
    # Filler words to remove
    # NOTE: Do NOT remove greeting words (hi, hello, hey) or confirmation words (ok, okay) - they are valid intents!
    FILLER_WORDS: Set[str] = {
        # Politeness
        "please", "kindly", "would", "could", "can",
        # Hedging
        "maybe", "perhaps", "just", "actually", "basically",
        # Discourse markers
        "so", "well", "like", "um", "uh",
        # Self-reference (removing "I want to" etc.)
        "i", "want", "to", "need", "like",
        # Assistant references
        "saarthi", "sarthi", "assistant",
    }
    
    # Contraction expansions
    CONTRACTIONS: Dict[str, str] = {
        "what's": "what is",
        "who's": "who is",
        "where's": "where is",
        "when's": "when is",
        "how's": "how is",
        "that's": "that is",
        "it's": "it is",
        "let's": "let us",
        "i'm": "i am",
        "you're": "you are",
        "we're": "we are",
        "they're": "they are",
        "i've": "i have",
        "you've": "you have",
        "we've": "we have",
        "they've": "they have",
        "i'll": "i will",
        "you'll": "you will",
        "he'll": "he will",
        "she'll": "she will",
        "we'll": "we will",
        "they'll": "they will",
        "i'd": "i would",
        "you'd": "you would",
        "he'd": "he would",
        "she'd": "she would",
        "we'd": "we would",
        "they'd": "they would",
        "isn't": "is not",
        "aren't": "are not",
        "wasn't": "was not",
        "weren't": "were not",
        "haven't": "have not",
        "hasn't": "has not",
        "hadn't": "had not",
        "won't": "will not",
        "wouldn't": "would not",
        "don't": "do not",
        "doesn't": "does not",
        "didn't": "did not",
        "can't": "cannot",
        "couldn't": "could not",
        "shouldn't": "should not",
        "mightn't": "might not",
        "mustn't": "must not",
    }
    
    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Normalize text for intent matching.
        
        Returns normalized text suitable for pattern matching.
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        # Expand contractions
        for contraction, expansion in cls.CONTRACTIONS.items():
            result = result.replace(contraction, expansion)
        
        # Remove punctuation (keep apostrophes for now)
        result = re.sub(r'[,!.?;:"()[\]{}]', ' ', result)
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Remove filler words (careful not to remove parts of words)
        words = result.split()
        words = [w for w in words if w not in cls.FILLER_WORDS]
        result = ' '.join(words)
        
        return result.strip()
    
    @classmethod
    def extract_verb_and_object(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract primary verb and object from normalized text.
        
        Returns (verb, object) tuple.
        Single word input returns (word, None).
        """
        normalized = cls.normalize(text)
        
        if not normalized:
            return None, None
        
        words = normalized.split()
        
        if not words:
            return None, None
        
        verb = words[0]
        obj = ' '.join(words[1:]) if len(words) > 1 else None
        
        return verb, obj


# =============================================================================
# ENTITY DEFINITIONS
# =============================================================================

class EntityRegistry:
    """
    Registry of known entities (websites, applications, etc.)
    
    Design: Entities are declared once and referenced by multiple patterns.
    This prevents duplication and makes updates easy.
    """
    
    # Known websites with their URLs
    WEBSITES: Dict[str, str] = {
        # Video
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "netflix": "https://www.netflix.com",
        "twitch": "https://www.twitch.tv",
        
        # Social
        "twitter": "https://twitter.com",
        "x": "https://twitter.com",
        "facebook": "https://www.facebook.com",
        "fb": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "linkedin": "https://www.linkedin.com",
        "reddit": "https://www.reddit.com",
        
        # Productivity
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "drive": "https://drive.google.com",
        "docs": "https://docs.google.com",
        "sheets": "https://sheets.google.com",
        "calendar": "https://calendar.google.com",
        
        # Development
        "github": "https://github.com",
        "gitlab": "https://gitlab.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        
        # Reference
        "wikipedia": "https://www.wikipedia.org",
        "wiki": "https://www.wikipedia.org",
        
        # Shopping
        "amazon": "https://www.amazon.com",
        "flipkart": "https://www.flipkart.com",
        
        # AI
        "chatgpt": "https://chat.openai.com",
        "chat gpt": "https://chat.openai.com",
        "claude": "https://claude.ai",
        "bard": "https://bard.google.com",
        "gemini": "https://gemini.google.com",
        
        # Music
        "spotify": "https://open.spotify.com",
        
        # Communication
        "whatsapp": "https://web.whatsapp.com",
        "discord": "https://discord.com",
        "slack": "https://slack.com",
        "zoom": "https://zoom.us",
        "teams": "https://teams.microsoft.com",
    }
    
    # Known applications with their executables
    APPLICATIONS: Dict[str, str] = {
        # Windows built-in
        "notepad": "notepad.exe",
        "note pad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "files": "explorer.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "terminal": "wt.exe",
        "windows terminal": "wt.exe",
        "powershell": "powershell.exe",
        "task manager": "taskmgr.exe",
        "control panel": "control.exe",
        "settings": "ms-settings:",
        "snipping tool": "snippingtool.exe",
        "wordpad": "wordpad.exe",
        
        # Browsers
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "brave": "brave",
        
        # Development
        "vscode": "code",
        "vs code": "code",
        "visual studio code": "code",
        "code": "code",
        "visual studio": "devenv",
        "sublime": "sublime_text",
        "atom": "atom",
        "pycharm": "pycharm64",
        "intellij": "idea64",
        
        # Microsoft Office
        "word": "winword",
        "microsoft word": "winword",
        "excel": "excel",
        "microsoft excel": "excel",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
        "onenote": "onenote",
        
        # Media
        "vlc": "vlc",
        "spotify": "spotify",
        
        # Communication
        "discord": "discord",
        "slack": "slack",
        "teams": "teams",
        "zoom": "zoom",
    }
    
    # Verb synonyms for intent detection
    VERB_SYNONYMS: Dict[str, Set[str]] = {
        "open": {"open", "launch", "start", "run", "go", "navigate", "show", "bring"},
        "search": {"search", "find", "look", "lookup", "google", "query"},
        "play": {"play", "stream", "watch", "listen"},
        "close": {"close", "exit", "quit", "stop", "terminate", "kill", "end"},
        "explain": {"explain", "describe", "tell", "elaborate"},
        "define": {"define", "meaning", "definition"},
    }
    
    @classmethod
    def get_website_url(cls, name: str) -> Optional[str]:
        """Get URL for a known website."""
        return cls.WEBSITES.get(name.lower())
    
    @classmethod
    def get_application_executable(cls, name: str) -> Optional[str]:
        """Get executable for a known application."""
        return cls.APPLICATIONS.get(name.lower())
    
    @classmethod
    def is_known_website(cls, name: str) -> bool:
        """Check if name is a known website."""
        return name.lower() in cls.WEBSITES
    
    @classmethod
    def is_known_application(cls, name: str) -> bool:
        """Check if name is a known application."""
        return name.lower() in cls.APPLICATIONS
    
    @classmethod
    def get_canonical_verb(cls, verb: str) -> Optional[str]:
        """Get canonical verb for a synonym."""
        verb = verb.lower()
        for canonical, synonyms in cls.VERB_SYNONYMS.items():
            if verb in synonyms:
                return canonical
        return None


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

@dataclass
class IntentPattern:
    """
    Pattern definition for intent matching.
    
    Supports:
    - Regex patterns with named groups
    - Confidence score
    - Slot extractors
    """
    intent_type: IntentType
    pattern: Pattern
    confidence: float
    slot_extractors: Dict[str, Callable[[Match], Any]] = field(default_factory=dict)
    
    def match(self, text: str) -> Optional[Tuple[Match, Dict[str, Slot]]]:
        """
        Attempt to match text against pattern.
        
        Returns (match, slots) if successful, None otherwise.
        """
        m = self.pattern.search(text)
        if not m:
            return None
        
        slots = {}
        for slot_name, extractor in self.slot_extractors.items():
            try:
                value = extractor(m)
                if value is not None:
                    slots[slot_name] = Slot(
                        name=slot_name,
                        value=value,
                        confidence=self.confidence,
                        source="pattern",
                    )
            except Exception:
                pass
        
        return m, slots


class PatternLibrary:
    """
    Library of intent patterns.
    
    Organized by intent type for efficient lookup.
    """
    
    @staticmethod
    def get_patterns() -> List[IntentPattern]:
        """Get all intent patterns."""
        patterns = []
        
        # -----------------------------------------------------------------
        # GREETING PATTERNS (highest confidence - exact match)
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.GREETING,
                pattern=re.compile(r'^(hi|hello|hey|good morning|good afternoon|good evening|howdy|greetings)$', re.I),
                confidence=0.99,
            ),
        ])
        
        # -----------------------------------------------------------------
        # THANKS PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.THANKS,
                pattern=re.compile(r'^(thanks?|thank you|thx|ty|appreciate|grateful)$', re.I),
                confidence=0.99,
            ),
        ])
        
        # -----------------------------------------------------------------
        # CONFIRMATION PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.CONFIRMATION_YES,
                pattern=re.compile(r'^(yes|yeah|yep|sure|ok|okay|confirm|proceed|do it|go ahead|affirmative|correct)$', re.I),
                confidence=0.99,
            ),
            IntentPattern(
                intent_type=IntentType.CONFIRMATION_NO,
                pattern=re.compile(r'^(no|nope|cancel|stop|don\'t|nevermind|never mind|abort|negative)$', re.I),
                confidence=0.99,
            ),
        ])
        
        # -----------------------------------------------------------------
        # STATUS / HELP PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.STATUS,
                pattern=re.compile(r'^(status|how are you|are you there|you there)$', re.I),
                confidence=0.95,
            ),
            IntentPattern(
                intent_type=IntentType.HELP,
                pattern=re.compile(r'^(help|what can you do|commands|options)$', re.I),
                confidence=0.95,
            ),
        ])
        
        # -----------------------------------------------------------------
        # OPEN WEBSITE PATTERNS
        # -----------------------------------------------------------------
        # Pattern: "open youtube", "go to github", "launch google"
        website_names = '|'.join(re.escape(name) for name in EntityRegistry.WEBSITES.keys())
        patterns.append(IntentPattern(
            intent_type=IntentType.OPEN_WEBSITE,
            pattern=re.compile(
                rf'(?:open|launch|go\s+to|start|show|navigate\s+to)\s+(?P<website>{website_names})',
                re.I
            ),
            confidence=0.95,
            slot_extractors={
                "target": lambda m: m.group("website").lower(),
                "url": lambda m: EntityRegistry.get_website_url(m.group("website")),
            },
        ))
        
        # -----------------------------------------------------------------
        # OPEN APPLICATION PATTERNS
        # -----------------------------------------------------------------
        app_names = '|'.join(re.escape(name) for name in EntityRegistry.APPLICATIONS.keys())
        patterns.append(IntentPattern(
            intent_type=IntentType.OPEN_APPLICATION,
            pattern=re.compile(
                rf'(?:open|launch|start|run)\s+(?P<app>{app_names})',
                re.I
            ),
            confidence=0.95,
            slot_extractors={
                "target": lambda m: m.group("app").lower(),
                "executable": lambda m: EntityRegistry.get_application_executable(m.group("app")),
            },
        ))
        
        # -----------------------------------------------------------------
        # SEARCH PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.SEARCH_WEB,
                pattern=re.compile(r'(?:search|google|look\s+up|find)\s+(?:for\s+)?(?P<query>.+)', re.I),
                confidence=0.90,
                slot_extractors={
                    "query": lambda m: m.group("query").strip(),
                },
            ),
        ])
        
        # -----------------------------------------------------------------
        # PLAY MEDIA PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            # "play lofi on youtube"
            IntentPattern(
                intent_type=IntentType.PLAY_MEDIA,
                pattern=re.compile(r'play\s+(?P<query>.+?)\s+on\s+(?P<platform>youtube|spotify)', re.I),
                confidence=0.92,
                slot_extractors={
                    "query": lambda m: m.group("query").strip(),
                    "platform": lambda m: m.group("platform").lower(),
                },
            ),
            # "play lofi music"
            IntentPattern(
                intent_type=IntentType.PLAY_MEDIA,
                pattern=re.compile(r'play\s+(?P<query>.+)', re.I),
                confidence=0.85,
                slot_extractors={
                    "query": lambda m: m.group("query").strip(),
                    "platform": lambda m: "youtube",  # Default to YouTube
                },
            ),
        ])
        
        # -----------------------------------------------------------------
        # QUESTION PATTERNS (what is, who is, how does, etc.)
        # -----------------------------------------------------------------
        question_patterns = [
            r'what\s+(?:is|are)\s+(?P<topic>.+)',
            r'who\s+(?:is|are|was|were)\s+(?P<topic>.+)',
            r'when\s+(?:is|was|did|will)\s+(?P<topic>.+)',
            r'where\s+(?:is|are|was|were)\s+(?P<topic>.+)',
            r'why\s+(?:is|are|do|does|did)\s+(?P<topic>.+)',
            r'how\s+(?:is|are|do|does|did|to|can|should)\s+(?P<topic>.+)',
        ]
        
        for qp in question_patterns:
            patterns.append(IntentPattern(
                intent_type=IntentType.QUESTION,
                pattern=re.compile(qp, re.I),
                confidence=0.88,
                slot_extractors={
                    "topic": lambda m: m.group("topic").strip(),
                },
            ))
        
        # -----------------------------------------------------------------
        # EXPLANATION PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.EXPLANATION,
                pattern=re.compile(r'(?:explain|describe|elaborate\s+on)\s+(?P<topic>.+)', re.I),
                confidence=0.90,
                slot_extractors={
                    "topic": lambda m: m.group("topic").strip(),
                },
            ),
            IntentPattern(
                intent_type=IntentType.EXPLANATION,
                pattern=re.compile(r'tell\s+me\s+about\s+(?P<topic>.+)', re.I),
                confidence=0.88,
                slot_extractors={
                    "topic": lambda m: m.group("topic").strip(),
                },
            ),
        ])
        
        # -----------------------------------------------------------------
        # DEFINITION PATTERNS
        # -----------------------------------------------------------------
        patterns.extend([
            IntentPattern(
                intent_type=IntentType.DEFINITION,
                pattern=re.compile(r'(?:define|meaning\s+of|definition\s+of)\s+(?P<topic>.+)', re.I),
                confidence=0.90,
                slot_extractors={
                    "topic": lambda m: m.group("topic").strip(),
                },
            ),
        ])
        
        return patterns


# =============================================================================
# PARSING LAYERS
# =============================================================================

class ParsingLayer(ABC):
    """
    Abstract base class for parsing layers.
    
    Each layer tries to parse the input and returns a ParsedIntent
    or None if it cannot parse.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Layer name for logging."""
        pass
    
    @abstractmethod
    def parse(self, text: str, normalized: str) -> Optional[ParsedIntent]:
        """
        Attempt to parse text.
        
        Args:
            text: Original user input
            normalized: Normalized text
        
        Returns:
            ParsedIntent if parsing succeeded, None otherwise
        """
        pass


class ExactPatternLayer(ParsingLayer):
    """
    Layer 1: Exact pattern matching.
    
    Highest confidence, fastest, but most restrictive.
    """
    
    def __init__(self):
        self._patterns = PatternLibrary.get_patterns()
    
    @property
    def name(self) -> str:
        return "exact_pattern"
    
    def parse(self, text: str, normalized: str) -> Optional[ParsedIntent]:
        best_match: Optional[ParsedIntent] = None
        best_confidence = 0.0
        
        for pattern in self._patterns:
            result = pattern.match(normalized)
            if result and pattern.confidence > best_confidence:
                match, slots = result
                best_match = ParsedIntent(
                    intent_type=pattern.intent_type,
                    confidence=pattern.confidence,
                    slots=slots,
                    raw_text=text,
                    normalized_text=normalized,
                    source=self.name,
                )
                best_confidence = pattern.confidence
        
        return best_match


class VerbObjectLayer(ParsingLayer):
    """
    Layer 2: Verb-object extraction.
    
    Extracts verb and object, maps to intent based on verb type
    and entity matching.
    """
    
    @property
    def name(self) -> str:
        return "verb_object"
    
    def parse(self, text: str, normalized: str) -> Optional[ParsedIntent]:
        verb, obj = TextNormalizer.extract_verb_and_object(normalized)
        
        if not verb or not obj:
            return None
        
        canonical_verb = EntityRegistry.get_canonical_verb(verb)
        
        if canonical_verb == "open":
            # Check if object is a known website
            url = EntityRegistry.get_website_url(obj)
            if url:
                return ParsedIntent(
                    intent_type=IntentType.OPEN_WEBSITE,
                    confidence=0.85,
                    slots={
                        "target": Slot("target", obj, 0.85, "verb_object"),
                        "url": Slot("url", url, 0.85, "verb_object"),
                    },
                    raw_text=text,
                    normalized_text=normalized,
                    verb=verb,
                    target=obj,
                    source=self.name,
                )
            
            # Check if object is a known application
            exe = EntityRegistry.get_application_executable(obj)
            if exe:
                return ParsedIntent(
                    intent_type=IntentType.OPEN_APPLICATION,
                    confidence=0.85,
                    slots={
                        "target": Slot("target", obj, 0.85, "verb_object"),
                        "executable": Slot("executable", exe, 0.85, "verb_object"),
                    },
                    raw_text=text,
                    normalized_text=normalized,
                    verb=verb,
                    target=obj,
                    source=self.name,
                )
        
        elif canonical_verb == "search":
            return ParsedIntent(
                intent_type=IntentType.SEARCH_WEB,
                confidence=0.80,
                slots={
                    "query": Slot("query", obj, 0.80, "verb_object"),
                },
                raw_text=text,
                normalized_text=normalized,
                verb=verb,
                target=obj,
                source=self.name,
            )
        
        elif canonical_verb == "play":
            return ParsedIntent(
                intent_type=IntentType.PLAY_MEDIA,
                confidence=0.80,
                slots={
                    "query": Slot("query", obj, 0.80, "verb_object"),
                    "platform": Slot("platform", "youtube", 0.70, "inference"),
                },
                raw_text=text,
                normalized_text=normalized,
                verb=verb,
                target=obj,
                source=self.name,
            )
        
        elif canonical_verb == "explain":
            return ParsedIntent(
                intent_type=IntentType.EXPLANATION,
                confidence=0.82,
                slots={
                    "topic": Slot("topic", obj, 0.82, "verb_object"),
                },
                raw_text=text,
                normalized_text=normalized,
                verb=verb,
                target=obj,
                source=self.name,
            )
        
        elif canonical_verb == "define":
            return ParsedIntent(
                intent_type=IntentType.DEFINITION,
                confidence=0.82,
                slots={
                    "topic": Slot("topic", obj, 0.82, "verb_object"),
                },
                raw_text=text,
                normalized_text=normalized,
                verb=verb,
                target=obj,
                source=self.name,
            )
        
        return None


class QuestionLayer(ParsingLayer):
    """
    Layer 3: Question detection.
    
    Catches question-like inputs that didn't match exact patterns.
    """
    
    QUESTION_STARTERS = {
        "what", "who", "when", "where", "why", "how",
        "is", "are", "was", "were", "do", "does", "did",
        "can", "could", "would", "should", "will",
    }
    
    @property
    def name(self) -> str:
        return "question"
    
    def parse(self, text: str, normalized: str) -> Optional[ParsedIntent]:
        words = normalized.split()
        
        if not words:
            return None
        
        # Check if starts with question word
        if words[0] in self.QUESTION_STARTERS:
            topic = normalized  # Use full text as topic
            return ParsedIntent(
                intent_type=IntentType.QUESTION,
                confidence=0.70,
                slots={
                    "topic": Slot("topic", topic, 0.70, "question_detection"),
                },
                raw_text=text,
                normalized_text=normalized,
                source=self.name,
            )
        
        # Check if ends with question mark
        if text.strip().endswith("?"):
            return ParsedIntent(
                intent_type=IntentType.QUESTION,
                confidence=0.65,
                slots={
                    "topic": Slot("topic", normalized, 0.65, "question_detection"),
                },
                raw_text=text,
                normalized_text=normalized,
                source=self.name,
            )
        
        return None


class FallbackLayer(ParsingLayer):
    """
    Layer 4: Fallback for unknown intents.
    
    Always succeeds but with low confidence.
    """
    
    @property
    def name(self) -> str:
        return "fallback"
    
    def parse(self, text: str, normalized: str) -> Optional[ParsedIntent]:
        return ParsedIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            slots={
                "raw_input": Slot("raw_input", text, 0.0, "fallback"),
            },
            raw_text=text,
            normalized_text=normalized,
            source=self.name,
        )


# =============================================================================
# MULTI-STEP DETECTOR
# =============================================================================

class MultiStepDetector:
    """
    Detects and splits multi-step commands.
    
    Example: "open youtube and play lofi" → [open_website, play_media]
    """
    
    # Conjunctions that indicate multi-step
    CONJUNCTIONS = {" and ", " then ", " after that ", " afterwards "}
    
    # Words that should NOT be split on "and"
    # e.g., "search for bread and butter" should not split
    KEEP_TOGETHER = {"bread", "salt", "pepper", "peanut", "ham"}
    
    @classmethod
    def is_multi_step(cls, text: str) -> bool:
        """Check if text contains multi-step command."""
        text_lower = text.lower()
        
        # Check for conjunctions
        for conj in cls.CONJUNCTIONS:
            if conj in text_lower:
                # Make sure it's not a phrase like "bread and butter"
                parts = text_lower.split(conj)
                if len(parts) >= 2:
                    # Heuristic: if any part starts with a verb, it's multi-step
                    verbs = set()
                    for syn_set in EntityRegistry.VERB_SYNONYMS.values():
                        verbs.update(syn_set)
                    
                    for part in parts[1:]:  # Skip first part
                        first_word = part.strip().split()[0] if part.strip() else ""
                        if first_word in verbs:
                            return True
        
        return False
    
    @classmethod
    def split(cls, text: str) -> List[str]:
        """Split multi-step command into individual commands."""
        text_lower = text.lower()
        
        # Try each conjunction
        for conj in cls.CONJUNCTIONS:
            if conj in text_lower:
                parts = text.split(conj[1:-1])  # Remove spaces from conj
                return [p.strip() for p in parts if p.strip()]
        
        return [text]


# =============================================================================
# MAIN INTENT ENGINE
# =============================================================================

class IntentEngine:
    """
    Main intent classification engine.
    
    Uses layered parsing with confidence-based routing.
    
    USAGE:
        engine = IntentEngine()
        intent = engine.classify("open youtube and play lofi")
        
        if intent.confidence >= 0.7:
            execute(intent)
        else:
            ask_for_clarification(intent)
    """
    
    # Confidence thresholds
    THRESHOLD_EXECUTE = 0.70    # Execute without confirmation
    THRESHOLD_SUGGEST = 0.40    # Suggest interpretation
    THRESHOLD_FALLBACK = 0.20   # Go to knowledge router
    
    def __init__(self):
        # Parsing layers in order of priority
        self._layers: List[ParsingLayer] = [
            ExactPatternLayer(),
            VerbObjectLayer(),
            QuestionLayer(),
            FallbackLayer(),
        ]
        
        self._normalizer = TextNormalizer
        self._multi_step = MultiStepDetector
        
        logger.info(f"Intent engine initialized with {len(self._layers)} layers")
    
    def classify(self, text: str) -> ParsedIntent:
        """
        Classify user input into an intent.
        
        Args:
            text: Raw user input
        
        Returns:
            ParsedIntent with type, slots, and confidence
        """
        if not text or not text.strip():
            return ParsedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                raw_text=text or "",
                normalized_text="",
                source="empty_input",
            )
        
        normalized = self._normalizer.normalize(text)
        
        # Check for multi-step command first
        if self._multi_step.is_multi_step(normalized):
            return self._classify_multi_step(text, normalized)
        
        # Try each layer in order
        for layer in self._layers:
            result = layer.parse(text, normalized)
            if result and result.intent_type != IntentType.UNKNOWN:
                logger.debug(
                    f"Intent classified by {layer.name}: "
                    f"{result.intent_type.value} (conf={result.confidence:.2f})"
                )
                return result
        
        # Fallback layer always returns something
        return self._layers[-1].parse(text, normalized)
    
    def _classify_multi_step(self, text: str, normalized: str) -> ParsedIntent:
        """Classify a multi-step command."""
        parts = self._multi_step.split(text)
        
        sub_intents = []
        total_confidence = 0.0
        
        for part in parts:
            part_normalized = self._normalizer.normalize(part)
            sub_intent = self._classify_single(part, part_normalized)
            sub_intents.append(sub_intent)
            total_confidence += sub_intent.confidence
        
        # Average confidence across all sub-intents
        avg_confidence = total_confidence / len(sub_intents) if sub_intents else 0.0
        
        return ParsedIntent(
            intent_type=IntentType.MULTI_STEP,
            confidence=avg_confidence,
            slots={
                "step_count": Slot("step_count", len(sub_intents), avg_confidence, "multi_step"),
            },
            raw_text=text,
            normalized_text=normalized,
            sub_intents=sub_intents,
            source="multi_step",
        )
    
    def _classify_single(self, text: str, normalized: str) -> ParsedIntent:
        """Classify a single (non-multi-step) command."""
        for layer in self._layers:
            result = layer.parse(text, normalized)
            if result and result.intent_type != IntentType.UNKNOWN:
                return result
        
        return self._layers[-1].parse(text, normalized)
    
    def should_execute(self, intent: ParsedIntent) -> bool:
        """Check if intent confidence is high enough to execute."""
        return intent.confidence >= self.THRESHOLD_EXECUTE
    
    def should_suggest(self, intent: ParsedIntent) -> bool:
        """Check if intent confidence is high enough to suggest."""
        return intent.confidence >= self.THRESHOLD_SUGGEST
    
    def get_clarification_prompt(self, intent: ParsedIntent) -> str:
        """Generate clarification prompt for low-confidence intent."""
        if intent.intent_type == IntentType.UNKNOWN:
            return "I didn't understand that. Could you rephrase?"
        
        return f"Did you mean: {intent.intent_type.value}? (yes/no)"


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_intent_engine() -> IntentEngine:
    """Create a configured intent engine."""
    return IntentEngine()


def classify_intent(text: str) -> ParsedIntent:
    """Convenience function for one-off classification."""
    engine = IntentEngine()
    return engine.classify(text)
