"""
Unit Tests: Intent Engine
=========================

Tests for intent classification, slot extraction, and confidence scoring.

Run: pytest tests/test_intent_engine.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saarthi_executor.intent_engine import (
    IntentEngine,
    IntentType,
    ParsedIntent,
    TextNormalizer,
    EntityRegistry,
    MultiStepDetector,
    classify_intent,
)


class TestTextNormalizer:
    """Tests for text normalization."""
    
    def test_lowercase(self):
        """Text should be lowercased."""
        result = TextNormalizer.normalize("HELLO WORLD")
        assert result.islower() or result == ""
    
    def test_remove_punctuation(self):
        """Punctuation should be removed."""
        result = TextNormalizer.normalize("Hello, world!")
        assert "," not in result
        assert "!" not in result
    
    def test_remove_filler_words(self):
        """Filler words should be removed."""
        result = TextNormalizer.normalize("please just open youtube")
        assert "please" not in result
        assert "just" not in result
        assert "open" in result
        assert "youtube" in result
    
    def test_expand_contractions(self):
        """Contractions should be expanded."""
        result = TextNormalizer.normalize("what's the time")
        assert "what is" in result
    
    def test_normalize_whitespace(self):
        """Multiple spaces should become single space."""
        result = TextNormalizer.normalize("hello    world")
        assert "  " not in result
    
    def test_empty_input(self):
        """Empty input should return empty string."""
        assert TextNormalizer.normalize("") == ""
        assert TextNormalizer.normalize(None) == ""
    
    def test_extract_verb_object(self):
        """Should extract verb and object correctly."""
        verb, obj = TextNormalizer.extract_verb_and_object("open youtube")
        assert verb == "open"
        assert obj == "youtube"
    
    def test_extract_verb_only(self):
        """Single word should have no object."""
        verb, obj = TextNormalizer.extract_verb_and_object("hello")
        assert verb == "hello"
        assert obj is None


class TestEntityRegistry:
    """Tests for entity registry."""
    
    def test_known_websites(self):
        """Should recognize known websites."""
        assert EntityRegistry.is_known_website("youtube")
        assert EntityRegistry.is_known_website("YouTube")  # Case insensitive
        assert EntityRegistry.is_known_website("github")
        assert not EntityRegistry.is_known_website("unknownsite")
    
    def test_website_urls(self):
        """Should return correct URLs."""
        assert EntityRegistry.get_website_url("youtube") == "https://www.youtube.com"
        assert EntityRegistry.get_website_url("github") == "https://github.com"
        assert EntityRegistry.get_website_url("unknownsite") is None
    
    def test_known_applications(self):
        """Should recognize known applications."""
        assert EntityRegistry.is_known_application("notepad")
        assert EntityRegistry.is_known_application("calculator")
        assert EntityRegistry.is_known_application("vscode")
        assert not EntityRegistry.is_known_application("unknownapp")
    
    def test_application_executables(self):
        """Should return correct executables."""
        assert EntityRegistry.get_application_executable("notepad") == "notepad.exe"
        assert EntityRegistry.get_application_executable("vscode") == "code"
    
    def test_verb_synonyms(self):
        """Should map verb synonyms to canonical verbs."""
        assert EntityRegistry.get_canonical_verb("open") == "open"
        assert EntityRegistry.get_canonical_verb("launch") == "open"
        assert EntityRegistry.get_canonical_verb("start") == "open"
        assert EntityRegistry.get_canonical_verb("google") == "search"
        assert EntityRegistry.get_canonical_verb("unknownverb") is None


class TestMultiStepDetector:
    """Tests for multi-step command detection."""
    
    def test_detect_multi_step_with_and(self):
        """Should detect 'and' as multi-step."""
        assert MultiStepDetector.is_multi_step("open youtube and play lofi")
    
    def test_detect_multi_step_with_then(self):
        """Should detect 'then' as multi-step."""
        assert MultiStepDetector.is_multi_step("open notepad then open calculator")
    
    def test_single_step_command(self):
        """Single step commands should not be multi-step."""
        assert not MultiStepDetector.is_multi_step("open youtube")
        assert not MultiStepDetector.is_multi_step("play lofi music")
    
    def test_split_multi_step(self):
        """Should correctly split multi-step commands."""
        parts = MultiStepDetector.split("open youtube and play lofi")
        assert len(parts) == 2
        assert "youtube" in parts[0].lower()
        assert "lofi" in parts[1].lower()


class TestIntentClassification:
    """Tests for intent classification."""
    
    def test_open_website(self, intent_engine):
        """Should classify website opening."""
        intent = intent_engine.classify("open youtube")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
        assert intent.confidence >= 0.90
        assert intent.get_slot("target") == "youtube"
        assert intent.get_slot("url") is not None
    
    def test_open_website_variations(self, intent_engine):
        """Should handle variations of open website."""
        for text in ["launch youtube", "go to youtube", "start youtube"]:
            intent = intent_engine.classify(text)
            assert intent.intent_type == IntentType.OPEN_WEBSITE, f"Failed for: {text}"
    
    def test_open_application(self, intent_engine):
        """Should classify application opening."""
        intent = intent_engine.classify("open notepad")
        assert intent.intent_type == IntentType.OPEN_APPLICATION
        assert intent.confidence >= 0.90
        assert intent.get_slot("target") == "notepad"
        assert intent.get_slot("executable") == "notepad.exe"
    
    def test_search_web(self, intent_engine):
        """Should classify web search."""
        intent = intent_engine.classify("search for python tutorials")
        assert intent.intent_type == IntentType.SEARCH_WEB
        assert intent.confidence >= 0.85
        assert "python" in intent.get_slot("query", "").lower()
    
    def test_play_media(self, intent_engine):
        """Should classify media playback."""
        intent = intent_engine.classify("play lofi music")
        assert intent.intent_type == IntentType.PLAY_MEDIA
        assert intent.confidence >= 0.80
        assert "lofi" in intent.get_slot("query", "").lower()
    
    def test_question(self, intent_engine):
        """Should classify questions."""
        intent = intent_engine.classify("what is binary search")
        assert intent.intent_type in [IntentType.QUESTION, IntentType.EXPLANATION]
        assert intent.confidence >= 0.70
    
    def test_explanation(self, intent_engine):
        """Should classify explanation requests."""
        intent = intent_engine.classify("explain machine learning")
        assert intent.intent_type == IntentType.EXPLANATION
        assert intent.confidence >= 0.80
    
    def test_greeting(self, intent_engine):
        """Should classify greetings."""
        for greeting in ["hello", "hi", "hey", "good morning"]:
            intent = intent_engine.classify(greeting)
            assert intent.intent_type == IntentType.GREETING, f"Failed for: {greeting}"
            assert intent.confidence >= 0.95
    
    def test_thanks(self, intent_engine):
        """Should classify thanks."""
        for thanks in ["thanks", "thank you", "thx"]:
            intent = intent_engine.classify(thanks)
            assert intent.intent_type == IntentType.THANKS, f"Failed for: {thanks}"
            assert intent.confidence >= 0.95
    
    def test_confirmation_yes(self, intent_engine):
        """Should classify positive confirmations."""
        for yes in ["yes", "yeah", "sure", "ok", "confirm"]:
            intent = intent_engine.classify(yes)
            assert intent.intent_type == IntentType.CONFIRMATION_YES, f"Failed for: {yes}"
    
    def test_confirmation_no(self, intent_engine):
        """Should classify negative confirmations."""
        for no in ["no", "nope", "cancel", "stop"]:
            intent = intent_engine.classify(no)
            assert intent.intent_type == IntentType.CONFIRMATION_NO, f"Failed for: {no}"
    
    def test_unknown_intent(self, intent_engine):
        """Should classify unknown inputs with low confidence."""
        intent = intent_engine.classify("xyz abc gibberish")
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence < 0.20
    
    def test_empty_input(self, intent_engine):
        """Should handle empty input gracefully."""
        intent = intent_engine.classify("")
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0
    
    def test_none_input(self, intent_engine):
        """Should handle None input gracefully."""
        # Note: This depends on implementation - may need try/except
        try:
            intent = intent_engine.classify(None)
            assert intent.intent_type == IntentType.UNKNOWN
        except (TypeError, AttributeError):
            pass  # Acceptable to raise on None


class TestMultiStepClassification:
    """Tests for multi-step command classification."""
    
    def test_multi_step_detection(self, intent_engine):
        """Should detect multi-step commands."""
        intent = intent_engine.classify("open youtube and play lofi")
        assert intent.intent_type == IntentType.MULTI_STEP
    
    def test_multi_step_sub_intents(self, intent_engine):
        """Should extract sub-intents correctly."""
        intent = intent_engine.classify("open youtube and play lofi")
        assert len(intent.sub_intents) == 2
        assert intent.sub_intents[0].intent_type == IntentType.OPEN_WEBSITE
        assert intent.sub_intents[1].intent_type == IntentType.PLAY_MEDIA
    
    def test_multi_step_confidence(self, intent_engine):
        """Multi-step confidence should be average of sub-intents."""
        intent = intent_engine.classify("open youtube and play music")
        expected_avg = sum(s.confidence for s in intent.sub_intents) / len(intent.sub_intents)
        assert abs(intent.confidence - expected_avg) < 0.01


class TestSlotExtraction:
    """Tests for slot extraction."""
    
    def test_website_slots(self, intent_engine):
        """Should extract website slots correctly."""
        intent = intent_engine.classify("open github")
        assert intent.get_slot("target") == "github"
        assert intent.get_slot("url") == "https://github.com"
    
    def test_application_slots(self, intent_engine):
        """Should extract application slots correctly."""
        intent = intent_engine.classify("open calculator")
        assert intent.get_slot("target") == "calculator"
        assert intent.get_slot("executable") == "calc.exe"
    
    def test_search_query_slot(self, intent_engine):
        """Should extract search query correctly."""
        intent = intent_engine.classify("search for machine learning tutorials")
        query = intent.get_slot("query", "")
        assert "machine learning" in query.lower()
    
    def test_play_media_slots(self, intent_engine):
        """Should extract play media slots correctly."""
        intent = intent_engine.classify("play jazz music on spotify")
        assert "jazz" in intent.get_slot("query", "").lower()
        # Platform may or may not be extracted depending on pattern


class TestConfidenceThresholds:
    """Tests for confidence-based decision making."""
    
    def test_should_execute_high_confidence(self, intent_engine):
        """High confidence intents should be executed."""
        intent = intent_engine.classify("open youtube")
        assert intent_engine.should_execute(intent)
    
    def test_should_not_execute_low_confidence(self, intent_engine):
        """Low confidence intents should not be executed."""
        intent = intent_engine.classify("xyz abc random")
        assert not intent_engine.should_execute(intent)
    
    def test_should_suggest_medium_confidence(self, intent_engine):
        """Medium confidence intents should be suggested."""
        # Create a mock intent with medium confidence
        intent = ParsedIntent(
            intent_type=IntentType.OPEN_WEBSITE,
            confidence=0.55,
            raw_text="",
            normalized_text="",
        )
        assert intent_engine.should_suggest(intent)
        assert not intent_engine.should_execute(intent)


class TestEdgeCases:
    """Tests for edge cases and robustness."""
    
    def test_punctuation_handling(self, intent_engine):
        """Should handle punctuation correctly."""
        intent = intent_engine.classify("Open YouTube!")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
    
    def test_extra_whitespace(self, intent_engine):
        """Should handle extra whitespace."""
        intent = intent_engine.classify("  open   youtube  ")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
    
    def test_mixed_case(self, intent_engine):
        """Should handle mixed case."""
        intent = intent_engine.classify("OpEn YoUtUbE")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
    
    def test_filler_words(self, intent_engine):
        """Should handle filler words."""
        intent = intent_engine.classify("please kindly open youtube")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
    
    def test_assistant_prefix(self, intent_engine):
        """Should handle assistant name prefix."""
        intent = intent_engine.classify("hey saarthi open youtube")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
    
    def test_very_long_input(self, intent_engine):
        """Should handle very long input."""
        long_text = "open youtube " + "and do something " * 50
        intent = intent_engine.classify(long_text)
        # Should not crash, may be multi-step or unknown
        assert intent is not None


class TestConvenienceFunction:
    """Tests for the convenience classify_intent function."""
    
    def test_classify_intent_function(self):
        """Should work as standalone function."""
        intent = classify_intent("open youtube")
        assert intent.intent_type == IntentType.OPEN_WEBSITE
