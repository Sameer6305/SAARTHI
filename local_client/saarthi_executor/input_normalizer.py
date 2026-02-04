"""
INPUT NORMALIZER - STEP 5 FIX
=============================

IMPROVES handling of:
- Broken English
- Short commands  
- Mixed language (basic Hinglish)
- Typos and misspellings

SAFETY: Never guess unsafe actions from unclear input.
"""

import re
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NormalizedInput:
    """Normalized and cleaned user input."""
    original: str
    normalized: str
    confidence: float  # How confident we are in normalization (0.0-1.0)
    corrections_made: List[str]  # What we fixed
    language_detected: str  # en, hinglish, mixed
    is_safe_to_process: bool  # False if too unclear for safety


class InputNormalizer:
    """
    Normalizes messy input before intent classification.
    
    PIPELINE:
    1. Language detection
    2. Spelling correction
    3. Grammar fixes (simple)
    4. Hinglish → English
    5. Abbreviation expansion
    """
    
    # Common Hinglish patterns → English
    HINGLISH_MAPPINGS = {
        # Verbs
        r'\bkhol\w*\b': 'open',
        r'\bband\w*\b': 'close',
        r'\bchala\w*\b': 'start',
        r'\bdekh\w*\b': 'show',
        r'\bbaja\w*\b': 'play',
        r'\bdhund\w*\b': 'search',
        r'\bbtaa\w*\b': 'tell',
        r'\bsamjha\w*\b': 'explain',
        
        # Common words
        r'\bgaana\b': 'song',
        r'\bvideo\b': 'video',
        r'\bwebsite\b': 'website',
        r'\bapp\b': 'application',
        r'\bfile\b': 'file',
        r'\bkya\b': 'what',
        r'\bkaise\b': 'how',
        r'\bkaun\b': 'who',
    }
    
    # Common typos / abbreviations
    ABBREVIATION_EXPANSIONS = {
        'yt': 'youtube',
        'ytube': 'youtube',
        'fb': 'facebook',
        'ig': 'instagram',
        'insta': 'instagram',
        'twtr': 'twitter',
        'ggl': 'google',
        'calc': 'calculator',
        'notepad': 'notepad',
        'ppt': 'powerpoint',
        'docs': 'documents',
        'msg': 'message',
        'pic': 'picture',
        'vid': 'video',
        'plz': 'please',
        'pls': 'please',
        'thx': 'thanks',
        'ty': 'thank you',
    }
    
    # Common misspellings
    COMMON_MISSPELLINGS = {
        'opne': 'open',
        'palsy': 'play',
        'serach': 'search',
        'srach': 'search',
        'youtub': 'youtube',
        'youtbe': 'youtube',
        'gogle': 'google',
        'goggle': 'google',
        'calcluator': 'calculator',
        'claculator': 'calculator',
    }
    
    # Filler words to remove
    FILLER_WORDS = {
        'um', 'uh', 'like', 'you know', 'basically', 'actually',
        'kind of', 'sort of', 'i mean', 'well', 'so', 'yeah',
    }
    
    # Action safety: these MUST be clear to execute
    SAFETY_CRITICAL_ACTIONS = {
        'delete', 'remove', 'uninstall', 'shutdown', 'restart',
        'format', 'wipe', 'erase', 'kill', 'terminate',
    }
    
    def normalize(self, text: str) -> NormalizedInput:
        """
        Normalize input for better intent classification.
        
        Args:
            text: Raw user input
        
        Returns:
            NormalizedInput with cleaned text and metadata
        """
        if not text or not text.strip():
            return NormalizedInput(
                original="",
                normalized="",
                confidence=0.0,
                corrections_made=[],
                language_detected="unknown",
                is_safe_to_process=False,
            )
        
        original = text.strip()
        normalized = original.lower()
        corrections = []
        
        # 1. Detect language
        language = self._detect_language(normalized)
        
        # 2. Handle Hinglish
        if language == "hinglish":
            normalized, hinglish_corrections = self._normalize_hinglish(normalized)
            corrections.extend(hinglish_corrections)
        
        # 3. Fix common misspellings
        normalized, spelling_corrections = self._fix_misspellings(normalized)
        corrections.extend(spelling_corrections)
        
        # 4. Expand abbreviations
        normalized, abbrev_corrections = self._expand_abbreviations(normalized)
        corrections.extend(abbrev_corrections)
        
        # 5. Remove filler words
        normalized = self._remove_fillers(normalized)
        
        # 6. Clean punctuation / whitespace
        normalized = self._clean_punctuation(normalized)
        
        # 7. Safety check
        is_safe = self._safety_check(normalized, original)
        
        # 8. Calculate confidence
        confidence = self._calculate_confidence(
            original, normalized, corrections, language
        )
        
        logger.info(f"Normalized: '{original}' → '{normalized}' (conf: {confidence:.2f})")
        if corrections:
            logger.debug(f"Corrections: {corrections}")
        
        return NormalizedInput(
            original=original,
            normalized=normalized,
            confidence=confidence,
            corrections_made=corrections,
            language_detected=language,
            is_safe_to_process=is_safe,
        )
    
    def _detect_language(self, text: str) -> str:
        """Detect if input is English, Hinglish, or mixed."""
        # Simple heuristic: count Hinglish words
        hinglish_count = sum(
            1 for pattern in self.HINGLISH_MAPPINGS.keys()
            if re.search(pattern, text, re.I)
        )
        
        if hinglish_count >= 2:
            return "hinglish"
        elif hinglish_count == 1:
            return "mixed"
        else:
            return "en"
    
    def _normalize_hinglish(self, text: str) -> Tuple[str, List[str]]:
        """Convert Hinglish to English."""
        normalized = text
        corrections = []
        
        for hinglish_pattern, english_word in self.HINGLISH_MAPPINGS.items():
            if re.search(hinglish_pattern, normalized, re.I):
                before = normalized
                normalized = re.sub(hinglish_pattern, english_word, normalized, flags=re.I)
                if before != normalized:
                    corrections.append(f"hinglish:{hinglish_pattern}→{english_word}")
        
        return normalized, corrections
    
    def _fix_misspellings(self, text: str) -> Tuple[str, List[str]]:
        """Fix common misspellings."""
        words = text.split()
        corrections = []
        
        for i, word in enumerate(words):
            if word in self.COMMON_MISSPELLINGS:
                correct = self.COMMON_MISSPELLINGS[word]
                words[i] = correct
                corrections.append(f"spelling:{word}→{correct}")
        
        return ' '.join(words), corrections
    
    def _expand_abbreviations(self, text: str) -> Tuple[str, List[str]]:
        """Expand common abbreviations."""
        words = text.split()
        corrections = []
        
        for i, word in enumerate(words):
            # Remove punctuation for matching
            clean_word = word.strip('.,!?;:')
            
            if clean_word in self.ABBREVIATION_EXPANSIONS:
                expanded = self.ABBREVIATION_EXPANSIONS[clean_word]
                words[i] = expanded
                corrections.append(f"abbrev:{clean_word}→{expanded}")
        
        return ' '.join(words), corrections
    
    def _remove_fillers(self, text: str) -> str:
        """Remove filler words."""
        for filler in self.FILLER_WORDS:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(filler) + r'\b'
            text = re.sub(pattern, '', text, flags=re.I)
        
        # Clean up extra spaces
        text = ' '.join(text.split())
        
        return text
    
    def _clean_punctuation(self, text: str) -> str:
        """Clean up punctuation and whitespace."""
        # Remove multiple spaces
        text = ' '.join(text.split())
        
        # Remove leading/trailing punctuation from words (but keep internal)
        # e.g., "open!" → "open", but "don't" → "don't"
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.,!?;:])\s*([.,!?;:])', r'\1', text)  # Remove duplicate punctuation
        
        return text.strip()
    
    def _safety_check(self, normalized: str, original: str) -> bool:
        """
        Check if normalized text is safe to process.
        
        CRITICAL: Don't execute dangerous actions if input is unclear.
        """
        # Check for safety-critical actions
        has_critical_action = any(
            action in normalized.lower()
            for action in self.SAFETY_CRITICAL_ACTIONS
        )
        
        if has_critical_action:
            # If critical action, input must be very clear
            # (original should be similar to normalized)
            similarity = self._text_similarity(original.lower(), normalized)
            
            if similarity < 0.7:
                logger.warning(
                    f"Safety check failed: critical action in unclear input "
                    f"(similarity: {similarity:.2f})"
                )
                return False
        
        # Too short to be safe
        if len(normalized.split()) < 2 and has_critical_action:
            logger.warning("Safety check failed: critical action too short")
            return False
        
        return True
    
    def _calculate_confidence(
        self,
        original: str,
        normalized: str,
        corrections: List[str],
        language: str,
    ) -> float:
        """
        Calculate confidence in normalization.
        
        Higher confidence = more likely normalization is correct.
        """
        # Start with base confidence
        confidence = 0.8
        
        # Penalty for each correction (more corrections = less certain)
        confidence -= len(corrections) * 0.1
        
        # Bonus for English (most reliable)
        if language == "en":
            confidence += 0.1
        
        # Penalty for Hinglish (less reliable normalization)
        if language == "hinglish":
            confidence -= 0.15
        
        # Very short input is less confident
        word_count = len(normalized.split())
        if word_count == 1:
            confidence -= 0.2
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Simple text similarity (0.0 to 1.0).
        
        Used for safety checks.
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0


# =============================================================================
# FACTORY
# =============================================================================

_normalizer_instance: Optional[InputNormalizer] = None

def get_normalizer() -> InputNormalizer:
    """Get singleton normalizer."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = InputNormalizer()
    return _normalizer_instance


def normalize_input(text: str) -> NormalizedInput:
    """Convenience function for normalization."""
    return get_normalizer().normalize(text)
