"""
TTS Policy Layer
=================

STRICT control over what the assistant speaks.
Prevents speaking URLs, file paths, system commands, and other unsafe content.

DESIGN PRINCIPLE: Explicit allowlist - if not explicitly allowed, don't speak.
"""

import re
import logging
from typing import Optional, Set, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SpeechCategory(Enum):
    """Categories of content for TTS policy decisions."""
    GREETING = "greeting"
    THANKS = "thanks"
    EXPLANATION = "explanation"
    ANSWER = "answer"
    ERROR = "error"
    STATUS = "status"
    ACTION_CONFIRM = "action_confirm"  # "Opening YouTube" - but NOT the URL
    ACTION_RESULT = "action_result"
    QUESTION = "question"
    UNKNOWN = "unknown"


@dataclass
class TTSPolicy:
    """TTS Policy configuration."""
    # Categories that are ALLOWED to be spoken
    allowed_categories: Set[SpeechCategory] = None
    
    # Max length for spoken text (prevents reading long content)
    max_spoken_length: int = 500
    
    # Whether to sanitize URLs in allowed text
    sanitize_urls: bool = True
    
    # Whether to sanitize file paths
    sanitize_paths: bool = True
    
    # Whether to sanitize commands
    sanitize_commands: bool = True
    
    def __post_init__(self):
        if self.allowed_categories is None:
            self.allowed_categories = {
                SpeechCategory.GREETING,
                SpeechCategory.THANKS,
                SpeechCategory.EXPLANATION,
                SpeechCategory.ANSWER,
                SpeechCategory.ERROR,
                SpeechCategory.STATUS,
                SpeechCategory.QUESTION,
            }


class TTSPolicyEnforcer:
    """
    Enforces TTS policy - decides what can be spoken and sanitizes content.
    
    SECURITY PATTERNS:
    - Block ALL URLs (http://, https://, www., *.com, etc.)
    - Block ALL file paths (C:\\, /home/, etc.)
    - Block ALL command syntax (cmd, powershell, etc.)
    - Block hex strings, base64, technical garbage
    - Truncate excessively long content
    """
    
    # Patterns that should NEVER be spoken
    BLOCKED_PATTERNS = [
        # URLs
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r'[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|org|net|io|edu|gov|co|uk|dev|app|ai)[^\s]*',
        
        # File paths (Windows)
        r'[A-Z]:\\[^\s]+',
        r'\\\\[^\s]+',  # UNC paths
        
        # File paths (Unix)
        r'/(?:home|usr|var|etc|tmp|opt|mnt|media|root)/[^\s]+',
        
        # Commands/executables
        r'\.exe\b',
        r'\.bat\b',
        r'\.cmd\b',
        r'\.ps1\b',
        r'\.sh\b',
        
        # Technical strings that shouldn't be spoken
        r'[a-fA-F0-9]{32,}',  # Long hex strings (hashes, GUIDs)
        r'[A-Za-z0-9+/]{40,}={0,2}',  # Base64
        r'\{[a-fA-F0-9-]{36}\}',  # GUIDs
        
        # Query strings and parameters
        r'\?[a-zA-Z0-9_]+=[^\s]+',
        r'&[a-zA-Z0-9_]+=[^\s]+',
    ]
    
    # Replacement phrases for blocked content types
    REPLACEMENTS = {
        'url': '',  # Just remove URLs entirely
        'path': 'the file',
        'command': 'the command',
    }
    
    def __init__(self, policy: Optional[TTSPolicy] = None):
        self.policy = policy or TTSPolicy()
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.BLOCKED_PATTERNS]
        
        # Action-related phrases that indicate we shouldn't speak
        self._action_indicators = [
            "opening",
            "launching", 
            "starting",
            "running",
            "executing",
            "searching for",
            "navigating to",
        ]
    
    def should_speak(self, text: str, category: SpeechCategory = SpeechCategory.UNKNOWN) -> bool:
        """
        Determine if the given text should be spoken.
        
        Returns True only if:
        1. Category is in the allowed list
        2. Text doesn't contain blocked patterns
        3. Text isn't an action confirmation with technical details
        """
        if not text or not text.strip():
            return False
        
        # Category check
        if category not in self.policy.allowed_categories:
            logger.debug(f"TTS blocked: category {category} not in allowed list")
            return False
        
        # Check for blocked patterns
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                logger.debug(f"TTS blocked: matched pattern {pattern.pattern}")
                return False
        
        # Check for action confirmations with URLs/paths
        text_lower = text.lower()
        for indicator in self._action_indicators:
            if indicator in text_lower:
                # If it's an action confirmation, check for technical content
                if self._contains_technical_content(text):
                    logger.debug(f"TTS blocked: action confirmation with technical content")
                    return False
        
        return True
    
    def sanitize(self, text: str) -> str:
        """
        Sanitize text for TTS output.
        Removes or replaces blocked content while preserving the message.
        
        Example:
            "Opening youtube at https://www.youtube.com" 
            -> "Opening youtube"
        """
        if not text:
            return ""
        
        result = text
        
        # Remove URLs
        result = re.sub(r'https?://[^\s]+', '', result)
        result = re.sub(r'www\.[^\s]+', '', result)
        result = re.sub(r'at\s+[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|org|net|io)[^\s]*', '', result, flags=re.IGNORECASE)
        
        # Remove file paths
        result = re.sub(r'[A-Z]:\\[^\s]+', 'the file', result)
        result = re.sub(r'/(?:home|usr|var|etc)/[^\s]+', 'the file', result)
        
        # Remove command references
        result = re.sub(r'\b\w+\.exe\b', '', result, flags=re.IGNORECASE)
        
        # Remove query parameters
        result = re.sub(r'\?[^\s]+', '', result)
        
        # Remove parenthetical URLs (e.g., "(https://...)")
        result = re.sub(r'\([^)]*(?:https?://|www\.)[^)]*\)', '', result)
        
        # Clean up extra spaces and punctuation
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'\s+([.,!?])', r'\1', result)
        result = re.sub(r'([.,!?])\s*\1+', r'\1', result)
        result = result.strip()
        
        # Remove trailing prepositions (leftover from URL removal)
        result = re.sub(r'\s+(at|to|from|in|on)\s*[.,!?]?\s*$', '', result, flags=re.IGNORECASE)
        result = result.strip(' .,')
        
        # Truncate if too long
        if len(result) > self.policy.max_spoken_length:
            # Find a good break point
            truncated = result[:self.policy.max_spoken_length]
            last_sentence = max(
                truncated.rfind('. '),
                truncated.rfind('! '),
                truncated.rfind('? ')
            )
            if last_sentence > self.policy.max_spoken_length // 2:
                result = truncated[:last_sentence + 1]
            else:
                result = truncated.rsplit(' ', 1)[0] + '...'
        
        return result
    
    def _contains_technical_content(self, text: str) -> bool:
        """Check if text contains technical content that shouldn't be spoken."""
        # Check for URLs
        if re.search(r'https?://', text) or re.search(r'www\.', text):
            return True
        
        # Check for file paths
        if re.search(r'[A-Z]:\\', text) or re.search(r'/home/', text):
            return True
        
        # Check for extensions
        if re.search(r'\.\w{2,4}\b', text) and re.search(r'\.(?:exe|bat|cmd|dll|py|js|html)', text, re.I):
            return True
        
        return False
    
    def process_for_speech(self, text: str, category: SpeechCategory = SpeechCategory.UNKNOWN) -> Optional[str]:
        """
        Process text for speech output.
        
        Returns:
            - Sanitized text if allowed to speak
            - None if should not speak
        """
        if not self.should_speak(text, category):
            return None
        
        sanitized = self.sanitize(text)
        
        # Final validation - don't speak if only technical garbage remains
        if not sanitized or len(sanitized) < 3:
            return None
        
        # Don't speak if it's just "Opening" or similar with nothing useful
        if sanitized.lower() in ['opening', 'launching', 'starting', 'running']:
            return None
        
        return sanitized


class SafeTTS:
    """
    Safe TTS wrapper that enforces policy before speaking.
    
    This wraps the actual TTS engine and ensures nothing unsafe is spoken.
    """
    
    def __init__(self, tts_engine, policy: Optional[TTSPolicy] = None):
        """
        Args:
            tts_engine: The actual TTS engine (SimpleTTS or TTSManager)
            policy: TTS policy configuration
        """
        self._engine = tts_engine
        self._policy_enforcer = TTSPolicyEnforcer(policy)
        self._last_spoken = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the underlying TTS engine."""
        if hasattr(self._engine, 'initialize'):
            result = self._engine.initialize()
            self._initialized = result
            return result
        self._initialized = True
        return True
    
    def speak(self, text: str, category: SpeechCategory = SpeechCategory.UNKNOWN, async_mode: bool = True) -> bool:
        """
        Speak text if allowed by policy.
        
        Args:
            text: Text to speak
            category: Category of the speech content
            async_mode: Whether to speak asynchronously
            
        Returns:
            True if text was spoken, False if blocked by policy
        """
        # Lazy initialization on first speak
        if not self._initialized:
            logger.info("SafeTTS auto-initializing on first speak")
            if not self.initialize():
                logger.error("SafeTTS initialization failed")
                return False
        
        # Process through policy
        safe_text = self._policy_enforcer.process_for_speech(text, category)
        
        if safe_text is None:
            logger.debug(f"TTS blocked by policy: {text[:50]}...")
            return False
        
        # Actually speak
        self._last_spoken = safe_text
        
        try:
            if hasattr(self._engine, 'speak'):
                # Try calling with async_mode parameter
                try:
                    self._engine.speak(safe_text, async_mode)
                except TypeError:
                    # Engine doesn't support async_mode, call with just text
                    self._engine.speak(safe_text)
            elif hasattr(self._engine, '_speak_sync'):
                if async_mode:
                    import threading
                    threading.Thread(
                        target=self._engine._speak_sync,
                        args=(safe_text,),
                        daemon=True
                    ).start()
                else:
                    self._engine._speak_sync(safe_text)
            
            logger.debug(f"TTS spoke: {safe_text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"TTS engine failed: {e}")
            return False
    
    def speak_if_allowed(self, text: str, speak_flag: bool, category: SpeechCategory = SpeechCategory.UNKNOWN) -> bool:
        """
        Convenience method: only speak if speak_flag is True AND policy allows.
        
        This is the main entry point for the assistant.
        """
        if not speak_flag:
            return False
        
        return self.speak(text, category)
    
    def stop(self):
        """Stop speaking."""
        if hasattr(self._engine, 'stop'):
            self._engine.stop()
    
    def get_last_spoken(self) -> Optional[str]:
        """Get the last text that was actually spoken."""
        return self._last_spoken


# Convenience function to create SafeTTS with default policy
def create_safe_tts(tts_engine) -> SafeTTS:
    """Create a SafeTTS wrapper with production-safe defaults."""
    policy = TTSPolicy(
        allowed_categories={
            SpeechCategory.GREETING,
            SpeechCategory.THANKS,
            SpeechCategory.EXPLANATION,
            SpeechCategory.ANSWER,
            SpeechCategory.ERROR,
            SpeechCategory.STATUS,
            SpeechCategory.QUESTION,
        },
        max_spoken_length=500,
        sanitize_urls=True,
        sanitize_paths=True,
        sanitize_commands=True,
    )
    return SafeTTS(tts_engine, policy)
