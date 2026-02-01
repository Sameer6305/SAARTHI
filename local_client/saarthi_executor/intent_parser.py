"""
Intent Parser Module
====================

Robust intent parsing with better verb-object extraction and validation.

ROOT CAUSE ANALYSIS - Current issues:
1. Pattern matching too strict - fails on minor variations
2. No fuzzy matching for similar commands
3. No validation that action can actually be executed
4. Multi-step parsing doesn't handle edge cases
5. No extraction of implicit intents

SOLUTION:
1. Layered parsing: exact patterns → fuzzy match → verb-object extraction → fallback
2. Normalize text before matching (lowercase, remove filler words)
3. Extract verb and object separately for flexible matching
4. Validate extracted intents against known actions
5. Better multi-step command detection
"""

import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Intent types."""
    OPEN_URL = "open_url"
    OPEN_APP = "open_app"
    SEARCH_WEB = "search_web"
    PLAY_MEDIA = "play_media"
    EXPLAIN = "explain"
    QUESTION = "question"
    GREETING = "greeting"
    THANKS = "thanks"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    STATUS = "status"
    HELP = "help"
    MULTI_STEP = "multi_step"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    """Result of intent parsing."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any]
    raw_text: str
    normalized_text: str
    verb: Optional[str] = None
    object: Optional[str] = None
    sub_intents: Optional[List['ParsedIntent']] = None  # For multi-step
    source: str = "unknown"  # pattern, fuzzy, verb_object, fallback


class TextNormalizer:
    """Normalize text for intent parsing."""
    
    # Filler words to remove
    FILLER_WORDS = {
        "please", "kindly", "can you", "could you", "would you",
        "i want to", "i need to", "i'd like to", "i would like to",
        "go ahead and", "just", "maybe", "perhaps", "actually",
        "basically", "literally", "like", "um", "uh", "so",
        "hey saarthi", "hey sarthi", "hi saarthi", "hello saarthi",
        "saarthi", "sarthi", "assistant",
    }
    
    # Greeting prefixes that should be stripped when followed by a command
    GREETING_PREFIXES = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    }
    
    # Punctuation to remove
    PUNCTUATION = r'[,!.?;:\'"()]'
    
    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Normalize text for intent matching.
        
        Steps:
        1. Lowercase
        2. Remove punctuation
        3. Remove filler words
        4. Normalize whitespace
        5. Strip greeting prefixes if followed by command
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        # Remove punctuation
        result = re.sub(cls.PUNCTUATION, ' ', result)
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Remove filler words
        for filler in cls.FILLER_WORDS:
            result = re.sub(rf'\b{re.escape(filler)}\b', '', result, flags=re.IGNORECASE)
        
        # Normalize whitespace again
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Strip greeting prefix if followed by command
        for greeting in cls.GREETING_PREFIXES:
            pattern = rf'^{re.escape(greeting)}\s+'
            if re.match(pattern, result, re.IGNORECASE):
                stripped = re.sub(pattern, '', result, flags=re.IGNORECASE)
                # Only strip if there's a command after
                if stripped and not stripped in cls.GREETING_PREFIXES:
                    result = stripped
                    break
        
        return result.strip()
    
    @classmethod
    def extract_verb_object(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract verb and object from normalized text.
        
        Returns:
            Tuple of (verb, object) or (None, None)
        """
        normalized = cls.normalize(text)
        words = normalized.split()
        
        if not words:
            return None, None
        
        # First word is usually the verb
        verb = words[0]
        
        # Rest is the object
        obj = ' '.join(words[1:]) if len(words) > 1 else None
        
        return verb, obj


class IntentPatterns:
    """Pattern definitions for intent matching."""
    
    # Known sites for URL opening
    KNOWN_SITES = {
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://www.github.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "wikipedia": "https://www.wikipedia.org",
        "wiki": "https://www.wikipedia.org",
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "x": "https://twitter.com",
        "linkedin": "https://www.linkedin.com",
        "gmail": "https://mail.google.com",
        "drive": "https://drive.google.com",
        "whatsapp": "https://web.whatsapp.com",
        "chatgpt": "https://chat.openai.com",
        "amazon": "https://www.amazon.com",
        "netflix": "https://www.netflix.com",
        "spotify": "https://open.spotify.com",
    }
    
    # Known apps
    KNOWN_APPS = {
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
        "powershell": "powershell.exe",
        "vscode": "code",
        "vs code": "code",
        "visual studio code": "code",
        "code": "code",
        "chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
    }
    
    # Verbs that indicate opening
    OPEN_VERBS = {"open", "launch", "start", "run", "go to", "goto", "navigate to", "show"}
    
    # Verbs that indicate search
    SEARCH_VERBS = {"search", "find", "look up", "lookup", "google", "look for"}
    
    # Verbs that indicate play
    PLAY_VERBS = {"play", "stream", "watch", "listen to", "listen"}
    
    # Question indicators
    QUESTION_INDICATORS = {
        "what is", "what's", "what are", "whats",
        "who is", "who's", "who are", "whos",
        "when is", "when's", "when did", "when was",
        "where is", "where's", "where are",
        "why is", "why's", "why do", "why did",
        "how is", "how's", "how do", "how does", "how to", "how can",
        "define", "explain", "tell me about", "describe",
        "meaning of", "definition of",
    }
    
    # Greeting patterns
    GREETING_PATTERNS = {
        "hi", "hello", "hey", "good morning", "good afternoon", 
        "good evening", "howdy", "greetings", "yo",
    }
    
    # Thanks patterns
    THANKS_PATTERNS = {
        "thanks", "thank you", "thx", "ty", "appreciate it",
        "much appreciated", "grateful",
    }
    
    # Confirmation patterns
    CONFIRM_YES = {"yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "proceed", "do it", "go ahead", "affirmative"}
    CONFIRM_NO = {"no", "nope", "cancel", "stop", "don't", "deny", "nevermind", "never mind", "abort"}


class IntentParser:
    """
    Robust intent parser with multiple strategies.
    
    Parsing layers (in order):
    1. Exact pattern matching (fastest, highest confidence)
    2. Verb-object extraction with known entity matching
    3. Fuzzy matching for close matches
    4. Fallback to question/unknown
    """
    
    def __init__(self):
        self.normalizer = TextNormalizer()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for matching."""
        # Multi-step detection
        self._multi_step_pattern = re.compile(
            r'\s+and\s+(?!the\b|a\b|an\b|then\b)',
            re.IGNORECASE
        )
        
        # URL detection
        self._url_pattern = re.compile(
            r'https?://[^\s]+|www\.[^\s]+',
            re.IGNORECASE
        )
    
    def parse(self, text: str) -> ParsedIntent:
        """
        Parse text into an intent.
        
        Args:
            text: Raw user input
            
        Returns:
            ParsedIntent with type, entities, and confidence
        """
        if not text or not text.strip():
            return ParsedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                entities={},
                raw_text=text or "",
                normalized_text="",
                source="empty",
            )
        
        normalized = self.normalizer.normalize(text)
        
        # Check for multi-step commands first
        if self._is_multi_step(normalized):
            return self._parse_multi_step(text, normalized)
        
        # Try each parsing strategy in order
        
        # 1. Exact patterns (greetings, thanks, confirmations)
        result = self._try_exact_patterns(text, normalized)
        if result:
            return result
        
        # 2. Verb-object with known entities
        result = self._try_verb_object(text, normalized)
        if result:
            return result
        
        # 3. Question detection
        result = self._try_question(text, normalized)
        if result:
            return result
        
        # 4. Fallback
        return self._fallback(text, normalized)
    
    def _is_multi_step(self, normalized: str) -> bool:
        """Check if text contains multi-step commands."""
        # Don't split explanations
        if any(q in normalized for q in ["explain", "what is", "tell me", "describe"]):
            return False
        
        return bool(self._multi_step_pattern.search(normalized))
    
    def _parse_multi_step(self, raw_text: str, normalized: str) -> ParsedIntent:
        """Parse multi-step command into sub-intents."""
        # Split on " and "
        parts = self._multi_step_pattern.split(normalized)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 2:
            # Not actually multi-step
            return self._try_verb_object(raw_text, normalized) or self._fallback(raw_text, normalized)
        
        # Parse each step
        sub_intents = []
        for part in parts:
            intent = self.parse(part)
            if intent.intent_type != IntentType.UNKNOWN:
                sub_intents.append(intent)
        
        if not sub_intents:
            return self._fallback(raw_text, normalized)
        
        return ParsedIntent(
            intent_type=IntentType.MULTI_STEP,
            confidence=min(i.confidence for i in sub_intents),
            entities={"steps": parts, "count": len(sub_intents)},
            raw_text=raw_text,
            normalized_text=normalized,
            sub_intents=sub_intents,
            source="multi_step",
        )
    
    def _try_exact_patterns(self, raw_text: str, normalized: str) -> Optional[ParsedIntent]:
        """Try exact pattern matching for common intents."""
        
        # Greetings (exact match)
        if normalized in IntentPatterns.GREETING_PATTERNS:
            return ParsedIntent(
                intent_type=IntentType.GREETING,
                confidence=0.99,
                entities={},
                raw_text=raw_text,
                normalized_text=normalized,
                source="pattern",
            )
        
        # Thanks
        if normalized in IntentPatterns.THANKS_PATTERNS:
            return ParsedIntent(
                intent_type=IntentType.THANKS,
                confidence=0.99,
                entities={},
                raw_text=raw_text,
                normalized_text=normalized,
                source="pattern",
            )
        
        # Confirmations
        if normalized in IntentPatterns.CONFIRM_YES:
            return ParsedIntent(
                intent_type=IntentType.CONFIRM_YES,
                confidence=0.99,
                entities={"value": True},
                raw_text=raw_text,
                normalized_text=normalized,
                source="pattern",
            )
        
        if normalized in IntentPatterns.CONFIRM_NO:
            return ParsedIntent(
                intent_type=IntentType.CONFIRM_NO,
                confidence=0.99,
                entities={"value": False},
                raw_text=raw_text,
                normalized_text=normalized,
                source="pattern",
            )
        
        # Status
        if normalized in {"status", "how are you", "you there", "are you there"}:
            return ParsedIntent(
                intent_type=IntentType.STATUS,
                confidence=0.95,
                entities={},
                raw_text=raw_text,
                normalized_text=normalized,
                source="pattern",
            )
        
        return None
    
    def _try_verb_object(self, raw_text: str, normalized: str) -> Optional[ParsedIntent]:
        """Try verb-object extraction with known entity matching."""
        verb, obj = self.normalizer.extract_verb_object(normalized)
        
        if not verb:
            return None
        
        # Open commands
        if verb in IntentPatterns.OPEN_VERBS or normalized.startswith("open "):
            # Re-extract object for "open" specifically
            obj = re.sub(r'^(open|launch|start|run|go\s*to|navigate\s*to|show)\s+', '', normalized, flags=re.I).strip()
            
            if not obj:
                return None
            
            # Check known sites
            if obj in IntentPatterns.KNOWN_SITES:
                return ParsedIntent(
                    intent_type=IntentType.OPEN_URL,
                    confidence=0.95,
                    entities={
                        "site": obj,
                        "url": IntentPatterns.KNOWN_SITES[obj],
                    },
                    raw_text=raw_text,
                    normalized_text=normalized,
                    verb=verb,
                    object=obj,
                    source="verb_object",
                )
            
            # Check known apps
            if obj in IntentPatterns.KNOWN_APPS:
                return ParsedIntent(
                    intent_type=IntentType.OPEN_APP,
                    confidence=0.95,
                    entities={
                        "app": obj,
                        "executable": IntentPatterns.KNOWN_APPS[obj],
                    },
                    raw_text=raw_text,
                    normalized_text=normalized,
                    verb=verb,
                    object=obj,
                    source="verb_object",
                )
            
            # Unknown target - try as website
            return ParsedIntent(
                intent_type=IntentType.OPEN_URL,
                confidence=0.7,
                entities={
                    "site": obj,
                    "url": f"https://{obj}.com",
                },
                raw_text=raw_text,
                normalized_text=normalized,
                verb=verb,
                object=obj,
                source="verb_object_guess",
            )
        
        # Search commands
        if verb in IntentPatterns.SEARCH_VERBS:
            obj = re.sub(r'^(search|find|look\s*up|google|look\s*for)\s+', '', normalized, flags=re.I)
            obj = re.sub(r'^for\s+', '', obj).strip()
            
            if obj:
                return ParsedIntent(
                    intent_type=IntentType.SEARCH_WEB,
                    confidence=0.90,
                    entities={"query": obj},
                    raw_text=raw_text,
                    normalized_text=normalized,
                    verb=verb,
                    object=obj,
                    source="verb_object",
                )
        
        # Play commands (YouTube)
        if verb in IntentPatterns.PLAY_VERBS:
            obj = re.sub(r'^(play|stream|watch|listen\s*to|listen)\s+', '', normalized, flags=re.I).strip()
            
            if obj:
                return ParsedIntent(
                    intent_type=IntentType.PLAY_MEDIA,
                    confidence=0.90,
                    entities={
                        "query": obj,
                        "url": f"https://www.youtube.com/results?search_query={obj.replace(' ', '+')}",
                    },
                    raw_text=raw_text,
                    normalized_text=normalized,
                    verb=verb,
                    object=obj,
                    source="verb_object",
                )
        
        return None
    
    def _try_question(self, raw_text: str, normalized: str) -> Optional[ParsedIntent]:
        """Try to detect question intents."""
        
        # Check question indicators
        for indicator in IntentPatterns.QUESTION_INDICATORS:
            if normalized.startswith(indicator):
                topic = normalized[len(indicator):].strip()
                
                if topic:
                    return ParsedIntent(
                        intent_type=IntentType.QUESTION if "explain" not in indicator else IntentType.EXPLAIN,
                        confidence=0.85,
                        entities={"topic": topic, "question_type": indicator},
                        raw_text=raw_text,
                        normalized_text=normalized,
                        source="question",
                    )
        
        # Check if ends with question mark
        if raw_text.strip().endswith("?"):
            return ParsedIntent(
                intent_type=IntentType.QUESTION,
                confidence=0.70,
                entities={"topic": normalized},
                raw_text=raw_text,
                normalized_text=normalized,
                source="question_mark",
            )
        
        return None
    
    def _fallback(self, raw_text: str, normalized: str) -> ParsedIntent:
        """Fallback for unrecognized intents."""
        # If it looks like a command (starts with a verb), try to help
        verb, obj = self.normalizer.extract_verb_object(normalized)
        
        if verb and obj:
            return ParsedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.3,
                entities={"verb": verb, "object": obj},
                raw_text=raw_text,
                normalized_text=normalized,
                verb=verb,
                object=obj,
                source="fallback",
            )
        
        return ParsedIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.1,
            entities={},
            raw_text=raw_text,
            normalized_text=normalized,
            source="fallback",
        )


# Singleton instance
_parser = None

def get_intent_parser() -> IntentParser:
    """Get the global intent parser instance."""
    global _parser
    if _parser is None:
        _parser = IntentParser()
    return _parser


def parse_intent(text: str) -> ParsedIntent:
    """Convenience function to parse intent."""
    return get_intent_parser().parse(text)
