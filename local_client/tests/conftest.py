"""
Pytest Configuration and Shared Fixtures
=========================================

Provides reusable fixtures for testing SAARTHI components.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_tts():
    """Mock TTS engine that records what was spoken."""
    class MockTTS:
        def __init__(self):
            self.spoken: List[str] = []
            self.initialized = True
        
        def speak(self, text: str):
            self.spoken.append(text)
        
        def stop(self):
            pass
        
        def clear(self):
            self.spoken.clear()
    
    return MockTTS()


@pytest.fixture
def mock_audio_capture():
    """Mock audio capture that returns pre-recorded audio."""
    import numpy as np
    
    class MockAudioCapture:
        def __init__(self, duration: float = 2.0, sample_rate: int = 16000):
            self.duration = duration
            self.sample_rate = sample_rate
            self.started = False
            self.stopped = False
        
        def start(self):
            self.started = True
        
        def stop(self):
            self.stopped = True
        
        def get_audio(self) -> np.ndarray:
            """Return silent audio."""
            return np.zeros(int(self.duration * self.sample_rate), dtype=np.float32)
    
    return MockAudioCapture()


@pytest.fixture
def mock_whisper():
    """Mock Whisper STT that returns pre-defined transcriptions."""
    class MockWhisper:
        def __init__(self):
            self.transcriptions: Dict[str, str] = {}
            self.default_transcription = "hello world"
            self.call_count = 0
        
        def transcribe(self, audio, **kwargs) -> Dict[str, Any]:
            self.call_count += 1
            return {"text": self.default_transcription}
        
        def set_transcription(self, text: str):
            self.default_transcription = text
    
    return MockWhisper()


@pytest.fixture
def sample_intents():
    """Sample intent test cases."""
    return [
        # (input_text, expected_intent_type, expected_confidence_min)
        ("open youtube", "open_website", 0.90),
        ("launch notepad", "open_application", 0.90),
        ("search for python tutorials", "search_web", 0.85),
        ("play lofi music", "play_media", 0.80),
        ("what is binary search", "question", 0.70),
        ("explain machine learning", "explanation", 0.80),
        ("hello", "greeting", 0.95),
        ("thanks", "thanks", 0.95),
        ("yes", "confirmation_yes", 0.95),
        ("no", "confirmation_no", 0.95),
        ("gibberish xyz abc", "unknown", 0.0),
    ]


@pytest.fixture
def sample_multi_step_intents():
    """Sample multi-step intent test cases."""
    return [
        # (input_text, expected_step_count)
        ("open youtube and play lofi", 2),
        ("open notepad and then open calculator", 2),
        ("search for python then open github", 2),
    ]


@pytest.fixture
def url_test_cases():
    """Test cases for URL blocking."""
    return [
        # (text, should_be_blocked)
        ("https://www.youtube.com", True),
        ("http://example.com/path", True),
        ("www.google.com", True),
        ("C:\\Users\\test\\file.exe", True),
        ("/home/user/file.sh", True),
        ("Hello world", False),
        ("Opening YouTube", False),
        ("Binary search is an algorithm", False),
    ]


# =============================================================================
# STATE MACHINE FIXTURES
# =============================================================================

@pytest.fixture
def state_machine():
    """Create a fresh state machine for testing."""
    from saarthi_executor.assistant_state_machine import (
        AssistantStateMachine,
        StateConfig,
    )
    
    config = StateConfig(enable_timeout_monitoring=False)
    sm = AssistantStateMachine(config)
    yield sm
    sm.shutdown()


@pytest.fixture
def state_machine_with_timeouts():
    """Create state machine with timeout monitoring."""
    from saarthi_executor.assistant_state_machine import (
        AssistantStateMachine,
        StateConfig,
        AssistantState,
    )
    
    config = StateConfig(
        enable_timeout_monitoring=True,
        timeout_check_interval=0.1,
        timeouts={
            AssistantState.IDLE: float('inf'),
            AssistantState.LISTENING: 1.0,  # Short for testing
            AssistantState.TRANSCRIBING: 1.0,
            AssistantState.THINKING: 1.0,
            AssistantState.EXECUTING: 1.0,
            AssistantState.SPEAKING: 1.0,
            AssistantState.ERROR: 0.5,
        },
    )
    sm = AssistantStateMachine(config)
    yield sm
    sm.shutdown()


# =============================================================================
# METRICS FIXTURES
# =============================================================================

@pytest.fixture
def metrics_collector():
    """Fresh metrics collector for testing."""
    from saarthi_executor.metrics import MetricsCollector, reset_metrics
    reset_metrics()
    return MetricsCollector()


# =============================================================================
# INTENT ENGINE FIXTURES
# =============================================================================

@pytest.fixture
def intent_engine():
    """Create intent engine for testing."""
    from saarthi_executor.intent_engine import IntentEngine
    return IntentEngine()


# =============================================================================
# KNOWLEDGE ROUTER FIXTURES
# =============================================================================

@pytest.fixture
def knowledge_router():
    """Create knowledge router for testing."""
    from saarthi_executor.knowledge_router import KnowledgeRouter
    return KnowledgeRouter()


@pytest.fixture
def mock_wikipedia():
    """Mock Wikipedia API responses."""
    class MockWikipedia:
        def __init__(self):
            self.responses: Dict[str, str] = {
                "binary search": "Binary search is a search algorithm.",
                "python": "Python is a programming language.",
            }
            self.call_count = 0
            self.should_timeout = False
            self.should_fail = False
        
        def get_summary(self, topic: str) -> str:
            self.call_count += 1
            
            if self.should_timeout:
                import time
                time.sleep(10)  # Simulate timeout
            
            if self.should_fail:
                raise Exception("Wikipedia error")
            
            return self.responses.get(topic.lower(), "")
    
    return MockWikipedia()


# =============================================================================
# TEST UTILITIES
# =============================================================================

def assert_intent_matches(intent, expected_type: str, min_confidence: float):
    """Assert that intent matches expected type and confidence."""
    assert intent.intent_type.value == expected_type, \
        f"Expected {expected_type}, got {intent.intent_type.value}"
    assert intent.confidence >= min_confidence, \
        f"Expected confidence >= {min_confidence}, got {intent.confidence}"


def assert_no_urls_in_text(text: str):
    """Assert that text contains no URLs."""
    import re
    url_pattern = r'https?://[^\s]+|www\.[^\s]+'
    matches = re.findall(url_pattern, text, re.IGNORECASE)
    assert not matches, f"Found URLs in text: {matches}"


def assert_no_paths_in_text(text: str):
    """Assert that text contains no file paths."""
    import re
    path_patterns = [
        r'[A-Z]:\\[^\s]+',  # Windows paths
        r'/(?:home|usr|var|etc)/[^\s]+',  # Unix paths
    ]
    for pattern in path_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        assert not matches, f"Found paths in text: {matches}"
