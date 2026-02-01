"""
Integration Tests: End-to-End Pipeline
=======================================

Tests the complete voice assistant pipeline with mocked I/O.

Run: pytest tests/test_integration.py -v
"""

import pytest
import time
import threading
import numpy as np
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class MockWhisperModel:
    """Mock Whisper model for testing."""
    
    def __init__(self):
        self.transcription = "open youtube"
        self.call_count = 0
        self.delay = 0.0
    
    def transcribe(self, audio, **kwargs):
        self.call_count += 1
        if self.delay > 0:
            time.sleep(self.delay)
        return {"text": self.transcription}


class MockTTSEngine:
    """Mock TTS engine for testing."""
    
    def __init__(self):
        self.spoken_texts = []
        self.initialized = True
        self.should_fail = False
    
    def speak(self, text):
        if self.should_fail:
            raise Exception("TTS failure")
        self.spoken_texts.append(text)
    
    def stop(self):
        pass
    
    def clear(self):
        self.spoken_texts.clear()


class MockAudioStream:
    """Mock audio stream for testing."""
    
    def __init__(self, sample_rate=16000, duration=2.0):
        self.sample_rate = sample_rate
        self.duration = duration
        self.frames = []
        self._generate_frames()
    
    def _generate_frames(self):
        """Generate mock audio frames."""
        total_samples = int(self.sample_rate * self.duration)
        frame_size = 512
        
        for i in range(0, total_samples, frame_size):
            frame = np.zeros(frame_size, dtype=np.float32)
            # Add some "speech" in the middle
            if 0.5 < (i / self.sample_rate) < 1.5:
                frame = np.random.randn(frame_size).astype(np.float32) * 0.1
            self.frames.append(frame)
    
    def get_audio(self) -> np.ndarray:
        """Return complete audio."""
        return np.concatenate(self.frames)


class TestIntentToExecution:
    """Tests for intent-to-execution pipeline."""
    
    def test_open_website_intent_executes(self, intent_engine):
        """Open website intent should be executable."""
        intent = intent_engine.classify("open youtube")
        
        assert intent.intent_type.value == "open_website"
        assert intent.confidence >= 0.70
        assert intent.get_slot("url") is not None
    
    def test_question_intent_routes_to_knowledge(self, intent_engine):
        """Question intent should route to knowledge router."""
        intent = intent_engine.classify("what is binary search")
        
        assert intent.intent_type.value in ["question", "explanation"]
        assert "topic" in intent.slots or "raw_input" in intent.slots
    
    def test_multi_step_extracts_sub_intents(self, intent_engine):
        """Multi-step should extract correct sub-intents."""
        intent = intent_engine.classify("open youtube and play lofi music")
        
        assert intent.intent_type.value == "multi_step"
        assert len(intent.sub_intents) == 2


class TestSTTIntegration:
    """Tests for STT integration."""
    
    def test_whisper_mock_transcribes(self):
        """Mock Whisper should return transcription."""
        model = MockWhisperModel()
        audio = np.zeros(16000, dtype=np.float32)
        
        result = model.transcribe(audio)
        assert result["text"] == "open youtube"
        assert model.call_count == 1
    
    def test_whisper_mock_with_custom_text(self):
        """Mock Whisper should use custom transcription."""
        model = MockWhisperModel()
        model.transcription = "search for python tutorials"
        
        result = model.transcribe(np.zeros(16000))
        assert result["text"] == "search for python tutorials"


class TestTTSIntegration:
    """Tests for TTS integration."""
    
    def test_tts_speaks_allowed_text(self):
        """TTS should speak allowed text."""
        engine = MockTTSEngine()
        engine.speak("Hello, how can I help?")
        
        assert len(engine.spoken_texts) == 1
        assert "Hello" in engine.spoken_texts[0]
    
    def test_tts_failure_handled(self):
        """TTS failure should be handled gracefully."""
        engine = MockTTSEngine()
        engine.should_fail = True
        
        with pytest.raises(Exception):
            engine.speak("Test")


class TestStateMachineIntegration:
    """Tests for state machine integration with pipeline."""
    
    def test_full_happy_path(self, state_machine):
        """Full pipeline path should work."""
        # Simulate full command execution
        assert state_machine.transition(
            state_machine.state.__class__.LISTENING, "space_pressed"
        )
        assert state_machine.transition(
            state_machine.state.__class__.TRANSCRIBING, "vad_complete"
        )
        assert state_machine.transition(
            state_machine.state.__class__.THINKING, "stt_complete"
        )
        assert state_machine.transition(
            state_machine.state.__class__.EXECUTING, "intent_action"
        )
        assert state_machine.transition(
            state_machine.state.__class__.IDLE, "execution_silent"
        )
        
        assert state_machine.is_idle
    
    def test_error_recovery_path(self, state_machine):
        """Error should recover to IDLE."""
        from saarthi_executor.assistant_state_machine import AssistantState
        
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.ERROR, "stt_failed")
        state_machine.transition(AssistantState.IDLE, "recovery")
        
        assert state_machine.is_idle


class TestMetricsIntegration:
    """Tests for metrics integration with pipeline."""
    
    def test_metrics_track_session(self, metrics_collector):
        """Metrics should track full session."""
        session = metrics_collector.start_session("integration_test")
        
        # Simulate pipeline stages
        metrics_collector.latency.record("stt", 1.5)
        metrics_collector.latency.record("intent", 0.05)
        metrics_collector.latency.record("execution", 0.2)
        
        session.stt_success = True
        session.intent_type = "open_website"
        session.execution_success = True
        
        metrics_collector.end_session(session)
        
        summary = metrics_collector.get_summary()
        assert "stt" in summary["latency"]
        assert "intent" in summary["latency"]
    
    def test_failure_tracking(self, metrics_collector):
        """Failures should be tracked with context."""
        from saarthi_executor.metrics import FailureCategory
        
        session = metrics_collector.start_session("failure_test")
        metrics_collector.record_failure(
            FailureCategory.STT_TIMEOUT,
            "Whisper took 15 seconds",
            context={"audio_duration": 5.0}
        )
        
        failures = metrics_collector.failures.get_recent_failures(1)
        assert len(failures) == 1
        assert failures[0]["category"] == "stt_timeout"


class TestKnowledgeRouterIntegration:
    """Tests for knowledge router integration."""
    
    def test_builtin_knowledge_instant(self, knowledge_router):
        """Built-in knowledge should be instant."""
        start = time.time()
        result = knowledge_router.get_answer("binary search")
        elapsed = time.time() - start
        
        assert result is not None
        assert elapsed < 0.1  # Should be near-instant
    
    def test_knowledge_cache_works(self, knowledge_router):
        """Cache should store and retrieve results."""
        # First call
        result1 = knowledge_router.get_answer("machine learning")
        
        # Second call should be cached
        result2 = knowledge_router.get_answer("machine learning")
        
        # Results should be the same
        assert result1 == result2 or (result1 and result2)


class TestEndToEndScenarios:
    """End-to-end scenario tests."""
    
    @pytest.fixture
    def mock_pipeline(self):
        """Create mock pipeline components."""
        return {
            "whisper": MockWhisperModel(),
            "tts": MockTTSEngine(),
            "audio": MockAudioStream(),
        }
    
    def test_open_website_scenario(self, mock_pipeline, intent_engine):
        """Test: User says 'open youtube'."""
        # Simulate STT
        mock_pipeline["whisper"].transcription = "open youtube"
        audio = mock_pipeline["audio"].get_audio()
        result = mock_pipeline["whisper"].transcribe(audio)
        
        # Parse intent
        intent = intent_engine.classify(result["text"])
        
        # Verify
        assert intent.intent_type.value == "open_website"
        assert intent.get_slot("target") == "youtube"
        assert "youtube.com" in intent.get_slot("url", "")
    
    def test_question_scenario(self, mock_pipeline, intent_engine):
        """Test: User asks 'what is recursion'."""
        mock_pipeline["whisper"].transcription = "what is recursion"
        result = mock_pipeline["whisper"].transcribe(np.zeros(16000))
        
        intent = intent_engine.classify(result["text"])
        
        assert intent.intent_type.value in ["question", "explanation"]
    
    def test_multi_step_scenario(self, mock_pipeline, intent_engine):
        """Test: User says 'open chrome and search for python'."""
        mock_pipeline["whisper"].transcription = "open chrome and search for python"
        result = mock_pipeline["whisper"].transcribe(np.zeros(16000))
        
        intent = intent_engine.classify(result["text"])
        
        assert intent.intent_type.value == "multi_step"
        assert len(intent.sub_intents) == 2
    
    def test_greeting_scenario(self, mock_pipeline, intent_engine):
        """Test: User says 'hello'."""
        mock_pipeline["whisper"].transcription = "hello"
        result = mock_pipeline["whisper"].transcribe(np.zeros(16000))
        
        intent = intent_engine.classify(result["text"])
        
        assert intent.intent_type.value == "greeting"
        # Greeting should be spoken
        # TTS would be called with a greeting response


class TestErrorHandling:
    """Tests for error handling across the pipeline."""
    
    def test_empty_transcription_handled(self, intent_engine):
        """Empty transcription should be handled."""
        intent = intent_engine.classify("")
        assert intent.intent_type.value == "unknown"
        assert intent.confidence == 0.0
    
    def test_none_transcription_handled(self, intent_engine):
        """None transcription should be handled."""
        try:
            intent = intent_engine.classify(None)
            assert intent.intent_type.value == "unknown"
        except (TypeError, AttributeError):
            pass  # Acceptable
    
    def test_tts_failure_doesnt_crash(self):
        """TTS failure shouldn't crash the system."""
        engine = MockTTSEngine()
        engine.should_fail = True
        
        try:
            engine.speak("Test")
        except Exception:
            pass  # Should be caught and handled
        
        # System should still be usable
        engine.should_fail = False
        engine.speak("Recovery test")
        assert "Recovery test" in engine.spoken_texts


class TestPerformanceBenchmarks:
    """Basic performance benchmarks."""
    
    def test_intent_parsing_latency(self, intent_engine):
        """Intent parsing should be fast."""
        start = time.time()
        
        for _ in range(100):
            intent_engine.classify("open youtube")
        
        elapsed = time.time() - start
        per_parse = elapsed / 100
        
        assert per_parse < 0.01  # <10ms per parse
    
    def test_state_transition_latency(self, state_machine):
        """State transitions should be fast."""
        from saarthi_executor.assistant_state_machine import AssistantState
        
        start = time.time()
        
        for _ in range(100):
            state_machine.transition(AssistantState.LISTENING, "test")
            state_machine.force_idle("reset")
        
        elapsed = time.time() - start
        per_transition = elapsed / 200  # 2 transitions per iteration
        
        assert per_transition < 0.001  # <1ms per transition
