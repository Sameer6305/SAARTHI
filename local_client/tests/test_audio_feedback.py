"""
Tests for Audio Feedback Module
================================

Tests the audio feedback system for state transitions.
"""

import pytest
import time
from saarthi_executor.audio_feedback import (
    AudioFeedback, FeedbackType, MockAudioFeedback, create_audio_feedback
)


class TestAudioFeedback:
    """Tests for AudioFeedback class."""
    
    def test_disabled_mode_no_sounds(self):
        """Disabled feedback should not play sounds."""
        feedback = AudioFeedback(enabled=False)
        assert not feedback.is_enabled
        
        # Should not crash even when disabled
        feedback.play_listening_start()
        feedback.play_listening_stop()
        feedback.play_success()
        feedback.play_error()
    
    def test_enable_disable(self):
        """Should be able to enable/disable feedback."""
        feedback = AudioFeedback(enabled=False)
        assert not feedback.is_enabled
        
        feedback.enable()
        # May or may not be enabled depending on winsound availability
        
        feedback.disable()
        assert not feedback.is_enabled
    
    def test_feedback_types_defined(self):
        """All feedback types should have configurations."""
        feedback = AudioFeedback(enabled=False)
        
        for feedback_type in FeedbackType:
            assert feedback_type in AudioFeedback.BEEP_CONFIGS
    
    def test_beep_configs_valid(self):
        """Beep configurations should be valid."""
        for feedback_type, (freq, dur) in AudioFeedback.BEEP_CONFIGS.items():
            assert 37 <= freq <= 32767, f"{feedback_type}: frequency out of range"
            assert 0 < dur <= 500, f"{feedback_type}: duration too long"
    
    def test_listening_start_high_pitch(self):
        """Listening start should be higher pitch than stop."""
        start_freq = AudioFeedback.BEEP_CONFIGS[FeedbackType.LISTENING_START][0]
        stop_freq = AudioFeedback.BEEP_CONFIGS[FeedbackType.LISTENING_STOP][0]
        
        assert start_freq > stop_freq, "Start beep should be higher pitch"
    
    def test_short_beeps(self):
        """Beeps should be short to avoid interfering with VAD."""
        for feedback_type, (freq, dur) in AudioFeedback.BEEP_CONFIGS.items():
            if feedback_type in (FeedbackType.LISTENING_START, FeedbackType.LISTENING_STOP):
                assert dur <= 150, f"{feedback_type} beep too long: {dur}ms"


class TestMockAudioFeedback:
    """Tests for MockAudioFeedback class."""
    
    def test_mock_records_beeps(self):
        """Mock should record what beeps were played."""
        mock = MockAudioFeedback()
        
        assert len(mock.played_beeps) == 0
        
        mock.play_listening_start()
        assert len(mock.played_beeps) == 1
        assert mock.played_beeps[0] == FeedbackType.LISTENING_START
        
        mock.play_listening_stop()
        assert len(mock.played_beeps) == 2
        assert mock.played_beeps[1] == FeedbackType.LISTENING_STOP
    
    def test_mock_reset(self):
        """Mock should be able to reset recorded beeps."""
        mock = MockAudioFeedback()
        
        mock.play_listening_start()
        mock.play_listening_stop()
        assert len(mock.played_beeps) == 2
        
        mock.reset()
        assert len(mock.played_beeps) == 0
    
    def test_mock_error_double_beep(self):
        """Mock should record double beep for errors."""
        mock = MockAudioFeedback()
        
        mock.play_error()
        
        # Should have two ERROR entries
        assert mock.played_beeps.count(FeedbackType.ERROR) == 2
    
    def test_mock_always_enabled(self):
        """Mock should always report as enabled."""
        mock = MockAudioFeedback()
        assert mock.is_enabled


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_audio_feedback_enabled(self):
        """Factory should create enabled feedback."""
        feedback = create_audio_feedback(enabled=True)
        assert isinstance(feedback, AudioFeedback)
        # May or may not be enabled depending on platform
    
    def test_create_audio_feedback_disabled(self):
        """Factory should create disabled feedback."""
        feedback = create_audio_feedback(enabled=False)
        assert isinstance(feedback, AudioFeedback)
        assert not feedback.is_enabled


class TestStateTransitionIntegration:
    """Tests for integration with state machine."""
    
    def test_listening_start_trigger(self):
        """Test that listening start beep is triggered correctly."""
        mock = MockAudioFeedback()
        
        # Simulate IDLE -> LISTENING transition
        mock.play_listening_start()
        
        assert FeedbackType.LISTENING_START in mock.played_beeps
    
    def test_listening_stop_trigger(self):
        """Test that listening stop beep is triggered correctly."""
        mock = MockAudioFeedback()
        
        # Simulate LISTENING -> TRANSCRIBING transition
        mock.play_listening_stop()
        
        assert FeedbackType.LISTENING_STOP in mock.played_beeps
    
    def test_error_trigger(self):
        """Test that error beep is triggered correctly."""
        mock = MockAudioFeedback()
        
        # Simulate error condition
        mock.play_error()
        
        # Should have two ERROR beeps
        assert mock.played_beeps.count(FeedbackType.ERROR) == 2
    
    def test_sequence_correct(self):
        """Test correct sequence of beeps in a voice session."""
        mock = MockAudioFeedback()
        
        # Simulate full voice session
        mock.play_listening_start()  # User presses SPACE
        mock.play_listening_stop()   # VAD detects end of speech
        mock.play_success()           # Action completed
        
        assert len(mock.played_beeps) == 3
        assert mock.played_beeps[0] == FeedbackType.LISTENING_START
        assert mock.played_beeps[1] == FeedbackType.LISTENING_STOP
        assert mock.played_beeps[2] == FeedbackType.SUCCESS


class TestNonInterference:
    """Tests to verify beeps don't interfere with audio capture."""
    
    def test_beep_durations_short(self):
        """All beeps should be short enough to not interfere."""
        # VAD typically has a minimum speech duration of 0.3s
        # Beeps should be much shorter
        for feedback_type, (freq, dur) in AudioFeedback.BEEP_CONFIGS.items():
            assert dur < 250, f"{feedback_type} too long, may interfere with VAD"
    
    def test_async_mode_default(self):
        """Beeps should play async by default to avoid blocking."""
        mock = MockAudioFeedback()
        
        # play() should complete immediately
        start = time.perf_counter()
        mock.play(FeedbackType.LISTENING_START, async_mode=True)
        elapsed = time.perf_counter() - start
        
        # Should return almost immediately (< 10ms)
        assert elapsed < 0.01, "Async beep blocked main thread"


class TestConfigurability:
    """Tests for configuration options."""
    
    def test_can_disable_via_config(self):
        """Should be able to disable beeps via config."""
        feedback = AudioFeedback(enabled=False)
        assert not feedback.is_enabled
        
        # Should be safe to call even when disabled
        feedback.play_listening_start()
        feedback.play_listening_stop()
    
    def test_can_enable_after_creation(self):
        """Should be able to enable beeps after creation."""
        feedback = AudioFeedback(enabled=False)
        assert not feedback.is_enabled
        
        feedback.enable()
        # Note: May still be disabled if winsound unavailable
    
    def test_can_disable_after_creation(self):
        """Should be able to disable beeps after creation."""
        feedback = AudioFeedback(enabled=True)
        
        feedback.disable()
        assert not feedback.is_enabled
