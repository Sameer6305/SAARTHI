"""
Unit Tests: TTS Policy
======================

Tests for TTS content filtering and URL/path blocking.

Run: pytest tests/test_tts_policy.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saarthi_executor.tts_policy import (
    TTSPolicy,
    TTSPolicyEnforcer,
    SpeechCategory,
    SafeTTS,
)


class TestSpeechCategories:
    """Tests for speech category definitions."""
    
    def test_allowed_categories_exist(self):
        """Default allowed categories should be defined."""
        policy = TTSPolicy()
        assert SpeechCategory.GREETING in policy.allowed_categories
        assert SpeechCategory.ANSWER in policy.allowed_categories
        assert SpeechCategory.EXPLANATION in policy.allowed_categories
        assert SpeechCategory.ERROR in policy.allowed_categories
    
    def test_action_confirm_not_allowed(self):
        """ACTION_CONFIRM should not be in default allowed categories."""
        policy = TTSPolicy()
        assert SpeechCategory.ACTION_CONFIRM not in policy.allowed_categories


class TestURLBlocking:
    """Tests for URL blocking in TTS."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_block_https_urls(self, enforcer):
        """Should block HTTPS URLs."""
        assert not enforcer.should_speak(
            "Opening https://www.youtube.com",
            SpeechCategory.ANSWER
        )
    
    def test_block_http_urls(self, enforcer):
        """Should block HTTP URLs."""
        assert not enforcer.should_speak(
            "Opening http://example.com/path",
            SpeechCategory.ANSWER
        )
    
    def test_block_www_urls(self, enforcer):
        """Should block www URLs."""
        assert not enforcer.should_speak(
            "Opening www.google.com",
            SpeechCategory.ANSWER
        )
    
    def test_block_domain_urls(self, enforcer):
        """Should block domain-like URLs."""
        assert not enforcer.should_speak(
            "Go to youtube.com",
            SpeechCategory.ANSWER
        )
    
    def test_block_complex_urls(self, enforcer):
        """Should block URLs with paths and query strings."""
        assert not enforcer.should_speak(
            "Opening https://www.youtube.com/watch?v=abc123&list=xyz",
            SpeechCategory.ANSWER
        )
    
    def test_allow_text_without_urls(self, enforcer):
        """Should allow text without URLs."""
        assert enforcer.should_speak(
            "Binary search is an efficient algorithm",
            SpeechCategory.ANSWER
        )


class TestPathBlocking:
    """Tests for file path blocking in TTS."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_block_windows_paths(self, enforcer):
        """Should block Windows file paths."""
        assert not enforcer.should_speak(
            "Opening C:\\Users\\test\\file.exe",
            SpeechCategory.ANSWER
        )
    
    def test_block_unc_paths(self, enforcer):
        """Should block UNC paths."""
        assert not enforcer.should_speak(
            "Opening \\\\server\\share\\file.txt",
            SpeechCategory.ANSWER
        )
    
    def test_block_unix_paths(self, enforcer):
        """Should block Unix file paths."""
        assert not enforcer.should_speak(
            "Opening /home/user/documents/file.txt",
            SpeechCategory.ANSWER
        )
    
    def test_block_exe_files(self, enforcer):
        """Should block .exe files."""
        assert not enforcer.should_speak(
            "Running notepad.exe",
            SpeechCategory.ANSWER
        )
    
    def test_block_batch_files(self, enforcer):
        """Should block .bat files."""
        assert not enforcer.should_speak(
            "Running script.bat",
            SpeechCategory.ANSWER
        )
    
    def test_block_shell_scripts(self, enforcer):
        """Should block .sh files."""
        assert not enforcer.should_speak(
            "Running script.sh",
            SpeechCategory.ANSWER
        )


class TestTechnicalStringBlocking:
    """Tests for technical string blocking."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_block_hex_hashes(self, enforcer):
        """Should block long hex strings (hashes)."""
        assert not enforcer.should_speak(
            "Hash: a1b2c3d4e5f6789012345678901234567890abcd",
            SpeechCategory.ANSWER
        )
    
    def test_block_guids(self, enforcer):
        """Should block GUIDs."""
        assert not enforcer.should_speak(
            "ID: {12345678-1234-1234-1234-123456789012}",
            SpeechCategory.ANSWER
        )
    
    def test_block_query_parameters(self, enforcer):
        """Should block query parameter strings."""
        assert not enforcer.should_speak(
            "Link: ?id=123&token=abc&session=xyz",
            SpeechCategory.ANSWER
        )


class TestCategoryFiltering:
    """Tests for category-based filtering."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_allow_greeting(self, enforcer):
        """Should allow greetings."""
        assert enforcer.should_speak("Hello!", SpeechCategory.GREETING)
    
    def test_allow_answer(self, enforcer):
        """Should allow answers."""
        assert enforcer.should_speak(
            "Binary search has O(log n) time complexity.",
            SpeechCategory.ANSWER
        )
    
    def test_allow_explanation(self, enforcer):
        """Should allow explanations."""
        assert enforcer.should_speak(
            "Machine learning is a subset of artificial intelligence.",
            SpeechCategory.EXPLANATION
        )
    
    def test_allow_error(self, enforcer):
        """Should allow error messages."""
        assert enforcer.should_speak(
            "Sorry, I couldn't find that.",
            SpeechCategory.ERROR
        )
    
    def test_block_action_confirm(self, enforcer):
        """Should block action confirmations."""
        assert not enforcer.should_speak(
            "Opening YouTube",
            SpeechCategory.ACTION_CONFIRM
        )
    
    def test_block_unknown_category(self, enforcer):
        """Should block unknown category."""
        assert not enforcer.should_speak(
            "Some text",
            SpeechCategory.UNKNOWN
        )


class TestTextSanitization:
    """Tests for text sanitization."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_sanitize_removes_urls(self, enforcer):
        """Sanitize should remove URLs from text."""
        text = "Check out https://www.example.com for more info"
        sanitized = enforcer.sanitize(text)
        assert "https://" not in sanitized
        assert "example.com" not in sanitized
        assert "Check out" in sanitized
        assert "for more info" in sanitized
    
    def test_sanitize_removes_paths(self, enforcer):
        """Sanitize should remove paths from text."""
        text = "File saved to C:\\Users\\test\\file.txt successfully"
        sanitized = enforcer.sanitize(text)
        assert "C:\\" not in sanitized
        # Should have replacement text
    
    def test_sanitize_preserves_clean_text(self, enforcer):
        """Sanitize should preserve text without problematic content."""
        text = "Binary search is an algorithm"
        sanitized = enforcer.sanitize(text)
        assert sanitized == text
    
    def test_sanitize_truncates_long_text(self, enforcer):
        """Sanitize should truncate very long text."""
        long_text = "word " * 200
        sanitized = enforcer.sanitize(long_text)
        assert len(sanitized) <= enforcer.policy.max_spoken_length + 50  # Some buffer


class TestEmptyAndEdgeCases:
    """Tests for empty and edge case inputs."""
    
    @pytest.fixture
    def enforcer(self):
        return TTSPolicyEnforcer()
    
    def test_empty_text(self, enforcer):
        """Should reject empty text."""
        assert not enforcer.should_speak("", SpeechCategory.ANSWER)
    
    def test_whitespace_only(self, enforcer):
        """Should reject whitespace-only text."""
        assert not enforcer.should_speak("   ", SpeechCategory.ANSWER)
    
    def test_none_text(self, enforcer):
        """Should handle None gracefully."""
        assert not enforcer.should_speak(None, SpeechCategory.ANSWER)
    
    def test_very_short_text(self, enforcer):
        """Should allow very short valid text."""
        assert enforcer.should_speak("OK", SpeechCategory.ANSWER)
    
    def test_unicode_text(self, enforcer):
        """Should handle unicode text."""
        assert enforcer.should_speak(
            "Hello 世界 🌍",
            SpeechCategory.GREETING
        )


class TestCustomPolicy:
    """Tests for custom TTS policies."""
    
    def test_custom_allowed_categories(self):
        """Should respect custom allowed categories."""
        policy = TTSPolicy(
            allowed_categories={SpeechCategory.GREETING}
        )
        enforcer = TTSPolicyEnforcer(policy)
        
        assert enforcer.should_speak("Hello", SpeechCategory.GREETING)
        assert not enforcer.should_speak("Hello", SpeechCategory.ANSWER)
    
    def test_custom_max_length(self):
        """Should respect custom max length."""
        policy = TTSPolicy(max_spoken_length=50)
        enforcer = TTSPolicyEnforcer(policy)
        
        long_text = "word " * 100
        sanitized = enforcer.sanitize(long_text)
        assert len(sanitized) <= 100  # Some buffer for truncation marker


class TestSafeTTS:
    """Tests for SafeTTS wrapper."""
    
    def test_safe_tts_blocks_urls(self):
        """SafeTTS should block URLs."""
        class MockEngine:
            spoken = []
            def speak(self, text):
                self.spoken.append(text)
        
        engine = MockEngine()
        safe_tts = SafeTTS(engine)
        
        result = safe_tts.speak(
            "Opening https://youtube.com",
            category=SpeechCategory.ACTION_CONFIRM
        )
        
        assert not result  # Should not speak
        assert len(engine.spoken) == 0
    
    def test_safe_tts_allows_valid_text(self):
        """SafeTTS should allow valid text."""
        class MockEngine:
            spoken = []
            def speak(self, text):
                self.spoken.append(text)
        
        engine = MockEngine()
        safe_tts = SafeTTS(engine)
        
        result = safe_tts.speak(
            "Hello, how can I help?",
            category=SpeechCategory.GREETING
        )
        
        assert result  # Should speak
        assert len(engine.spoken) == 1
        assert "Hello" in engine.spoken[0]
