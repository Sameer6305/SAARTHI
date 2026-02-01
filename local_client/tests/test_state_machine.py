"""
Unit Tests: State Machine
=========================

Tests for deterministic state machine behavior, transitions, and timeouts.

Run: pytest tests/test_state_machine.py -v
"""

import pytest
import time
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saarthi_executor.assistant_state_machine import (
    AssistantStateMachine,
    AssistantState,
    StateConfig,
    StateTransitionError,
    create_state_machine,
)


class TestStateInitialization:
    """Tests for state machine initialization."""
    
    def test_initial_state_is_idle(self, state_machine):
        """State machine should start in IDLE state."""
        assert state_machine.state == AssistantState.IDLE
    
    def test_is_idle_property(self, state_machine):
        """is_idle property should work correctly."""
        assert state_machine.is_idle
    
    def test_is_busy_property(self, state_machine):
        """is_busy property should work correctly."""
        assert not state_machine.is_busy


class TestValidTransitions:
    """Tests for valid state transitions."""
    
    def test_idle_to_listening(self, state_machine):
        """Should transition from IDLE to LISTENING."""
        assert state_machine.can_transition_to(AssistantState.LISTENING)
        assert state_machine.transition(
            AssistantState.LISTENING,
            "user_pressed_space"
        )
        assert state_machine.state == AssistantState.LISTENING
    
    def test_listening_to_transcribing(self, state_machine):
        """Should transition from LISTENING to TRANSCRIBING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        assert state_machine.transition(
            AssistantState.TRANSCRIBING,
            "vad_complete"
        )
        assert state_machine.state == AssistantState.TRANSCRIBING
    
    def test_transcribing_to_thinking(self, state_machine):
        """Should transition from TRANSCRIBING to THINKING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        assert state_machine.transition(
            AssistantState.THINKING,
            "stt_complete"
        )
        assert state_machine.state == AssistantState.THINKING
    
    def test_thinking_to_executing(self, state_machine):
        """Should transition from THINKING to EXECUTING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        assert state_machine.transition(
            AssistantState.EXECUTING,
            "intent_action"
        )
        assert state_machine.state == AssistantState.EXECUTING
    
    def test_thinking_to_speaking(self, state_machine):
        """Should transition from THINKING to SPEAKING (for Q&A)."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        assert state_machine.transition(
            AssistantState.SPEAKING,
            "intent_question"
        )
        assert state_machine.state == AssistantState.SPEAKING
    
    def test_executing_to_speaking(self, state_machine):
        """Should transition from EXECUTING to SPEAKING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        state_machine.transition(AssistantState.EXECUTING, "action")
        assert state_machine.transition(
            AssistantState.SPEAKING,
            "execution_complete"
        )
        assert state_machine.state == AssistantState.SPEAKING
    
    def test_executing_to_idle(self, state_machine):
        """Should transition from EXECUTING to IDLE (silent execution)."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        state_machine.transition(AssistantState.EXECUTING, "action")
        assert state_machine.transition(
            AssistantState.IDLE,
            "silent_execution"
        )
        assert state_machine.state == AssistantState.IDLE
    
    def test_speaking_to_idle(self, state_machine):
        """Should transition from SPEAKING to IDLE."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        state_machine.transition(AssistantState.SPEAKING, "question")
        assert state_machine.transition(
            AssistantState.IDLE,
            "tts_complete"
        )
        assert state_machine.state == AssistantState.IDLE
    
    def test_error_to_idle(self, state_machine):
        """Should transition from ERROR to IDLE (recovery)."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.ERROR, "test_error")
        assert state_machine.transition(
            AssistantState.IDLE,
            "recovery"
        )
        assert state_machine.state == AssistantState.IDLE


class TestInvalidTransitions:
    """Tests for invalid state transition handling."""
    
    def test_idle_to_transcribing_invalid(self, state_machine):
        """Should not transition directly from IDLE to TRANSCRIBING."""
        assert not state_machine.can_transition_to(AssistantState.TRANSCRIBING)
        assert not state_machine.transition(
            AssistantState.TRANSCRIBING,
            "invalid"
        )
        assert state_machine.state == AssistantState.IDLE
    
    def test_idle_to_executing_invalid(self, state_machine):
        """Should not transition directly from IDLE to EXECUTING."""
        assert not state_machine.can_transition_to(AssistantState.EXECUTING)
    
    def test_listening_to_speaking_invalid(self, state_machine):
        """Should not transition directly from LISTENING to SPEAKING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        assert not state_machine.can_transition_to(AssistantState.SPEAKING)
    
    def test_speaking_to_listening_invalid(self, state_machine):
        """Should not transition from SPEAKING to LISTENING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        state_machine.transition(AssistantState.SPEAKING, "answer")
        assert not state_machine.can_transition_to(AssistantState.LISTENING)


class TestErrorTransitions:
    """Tests for error state transitions."""
    
    def test_listening_to_error(self, state_machine):
        """Should transition from LISTENING to ERROR on failure."""
        state_machine.transition(AssistantState.LISTENING, "start")
        assert state_machine.transition(
            AssistantState.ERROR,
            "audio_failure"
        )
        assert state_machine.state == AssistantState.ERROR
    
    def test_transcribing_to_error(self, state_machine):
        """Should transition from TRANSCRIBING to ERROR on failure."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        assert state_machine.transition(
            AssistantState.ERROR,
            "stt_failure"
        )
        assert state_machine.state == AssistantState.ERROR
    
    def test_error_always_recovers_to_idle(self, state_machine):
        """ERROR state should always be able to transition to IDLE."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.ERROR, "failure")
        
        # Can only go to IDLE from ERROR
        assert state_machine.can_transition_to(AssistantState.IDLE)
        assert not state_machine.can_transition_to(AssistantState.LISTENING)


class TestForceIdle:
    """Tests for force_idle recovery mechanism."""
    
    def test_force_idle_from_listening(self, state_machine):
        """Should force IDLE from LISTENING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.force_idle("forced_reset")
        assert state_machine.state == AssistantState.IDLE
    
    def test_force_idle_from_executing(self, state_machine):
        """Should force IDLE from EXECUTING."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        state_machine.transition(AssistantState.THINKING, "stt")
        state_machine.transition(AssistantState.EXECUTING, "action")
        state_machine.force_idle("stuck_execution")
        assert state_machine.state == AssistantState.IDLE
    
    def test_force_idle_from_idle_is_noop(self, state_machine):
        """Force IDLE from IDLE should be no-op."""
        state_machine.force_idle("test")
        assert state_machine.state == AssistantState.IDLE


class TestStateDuration:
    """Tests for state duration tracking."""
    
    def test_state_duration_tracked(self, state_machine):
        """State duration should be tracked."""
        state_machine.transition(AssistantState.LISTENING, "start")
        time.sleep(0.1)
        assert state_machine.state_duration >= 0.1
    
    def test_state_duration_resets_on_transition(self, state_machine):
        """State duration should reset on transition."""
        state_machine.transition(AssistantState.LISTENING, "start")
        time.sleep(0.1)
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        assert state_machine.state_duration < 0.05


class TestObservers:
    """Tests for state change observers."""
    
    def test_observer_called_on_transition(self, state_machine):
        """Observer should be called on state transition."""
        transitions = []
        
        def observer(old, new, reason):
            transitions.append((old, new, reason))
        
        state_machine.add_observer(observer)
        state_machine.transition(AssistantState.LISTENING, "test")
        
        assert len(transitions) == 1
        assert transitions[0][0] == AssistantState.IDLE
        assert transitions[0][1] == AssistantState.LISTENING
        assert transitions[0][2] == "test"
    
    def test_multiple_observers(self, state_machine):
        """Multiple observers should all be called."""
        counts = [0, 0]
        
        def observer1(old, new, reason):
            counts[0] += 1
        
        def observer2(old, new, reason):
            counts[1] += 1
        
        state_machine.add_observer(observer1)
        state_machine.add_observer(observer2)
        state_machine.transition(AssistantState.LISTENING, "test")
        
        assert counts[0] == 1
        assert counts[1] == 1
    
    def test_remove_observer(self, state_machine):
        """Removed observer should not be called."""
        count = [0]
        
        def observer(old, new, reason):
            count[0] += 1
        
        state_machine.add_observer(observer)
        state_machine.transition(AssistantState.LISTENING, "test")
        assert count[0] == 1
        
        state_machine.remove_observer(observer)
        state_machine.transition(AssistantState.TRANSCRIBING, "test2")
        assert count[0] == 1  # Still 1, not called again


class TestHistory:
    """Tests for transition history."""
    
    def test_history_recorded(self, state_machine):
        """Transitions should be recorded in history."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.TRANSCRIBING, "vad")
        
        history = state_machine.get_history(10)
        assert len(history) == 2
        assert history[0]["from"] == "IDLE"
        assert history[0]["to"] == "LISTENING"
        assert history[1]["from"] == "LISTENING"
        assert history[1]["to"] == "TRANSCRIBING"
    
    def test_history_includes_reason(self, state_machine):
        """History should include transition reason."""
        state_machine.transition(AssistantState.LISTENING, "user_pressed_space")
        
        history = state_machine.get_history(1)
        assert history[0]["reason"] == "user_pressed_space"
    
    def test_history_includes_duration(self, state_machine):
        """History should include duration in previous state."""
        time.sleep(0.05)
        state_machine.transition(AssistantState.LISTENING, "start")
        
        history = state_machine.get_history(1)
        assert "duration" in history[0]
        assert history[0]["duration"] >= 0.05


class TestStatistics:
    """Tests for state machine statistics."""
    
    def test_stats_transition_count(self, state_machine):
        """Should track transition count."""
        state_machine.transition(AssistantState.LISTENING, "test1")
        state_machine.transition(AssistantState.TRANSCRIBING, "test2")
        
        stats = state_machine.get_stats()
        assert stats["transitions"] == 2
    
    def test_stats_error_count(self, state_machine):
        """Should track error count."""
        state_machine.transition(AssistantState.LISTENING, "start")
        state_machine.transition(AssistantState.ERROR, "failure")
        
        stats = state_machine.get_stats()
        assert stats["errors"] == 1
    
    def test_stats_invalid_transition_count(self, state_machine):
        """Should track invalid transition attempts."""
        state_machine.transition(AssistantState.EXECUTING, "invalid")
        
        stats = state_machine.get_stats()
        assert stats["invalid_transitions_attempted"] == 1


class TestContextManager:
    """Tests for state context manager."""
    
    def test_in_state_success(self, state_machine):
        """Context manager should transition to target state."""
        with state_machine.in_state(AssistantState.LISTENING, "test"):
            assert state_machine.state == AssistantState.LISTENING
    
    def test_in_state_exception_goes_to_error(self, state_machine):
        """Exception in context should transition to ERROR."""
        try:
            with state_machine.in_state(AssistantState.LISTENING, "test"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert state_machine.state == AssistantState.ERROR
    
    def test_in_state_invalid_raises(self, state_machine):
        """Invalid state transition in context should raise."""
        with pytest.raises(StateTransitionError):
            with state_machine.in_state(AssistantState.EXECUTING, "invalid"):
                pass


class TestThreadSafety:
    """Tests for thread safety."""
    
    def test_concurrent_transitions(self, state_machine):
        """Concurrent transition attempts should be thread-safe."""
        results = []
        
        def try_transition():
            for _ in range(10):
                if state_machine.state == AssistantState.IDLE:
                    result = state_machine.transition(
                        AssistantState.LISTENING,
                        "concurrent"
                    )
                    results.append(result)
                    if result:
                        state_machine.force_idle("reset")
        
        threads = [threading.Thread(target=try_transition) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # At least some transitions should have succeeded
        assert any(results)
        # State should be consistent (IDLE after all force_idle calls)
        assert state_machine.state in {AssistantState.IDLE, AssistantState.LISTENING}


class TestTimeoutMonitoring:
    """Tests for state timeout monitoring."""
    
    def test_timeout_transitions_to_error(self, state_machine_with_timeouts):
        """State timeout should transition to ERROR."""
        sm = state_machine_with_timeouts
        sm.transition(AssistantState.LISTENING, "start")
        
        # Wait for timeout (1 second + buffer)
        time.sleep(1.5)
        
        # Should have timed out and transitioned to ERROR, then maybe to IDLE
        assert sm.state in {AssistantState.ERROR, AssistantState.IDLE}
    
    def test_stats_track_timeouts(self, state_machine_with_timeouts):
        """Timeouts should be tracked in stats."""
        sm = state_machine_with_timeouts
        sm.transition(AssistantState.LISTENING, "start")
        
        time.sleep(1.5)
        
        stats = sm.get_stats()
        assert stats["timeouts"] >= 1


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_state_machine(self):
        """Factory should create working state machine."""
        sm = create_state_machine(enable_timeouts=False)
        assert sm.state == AssistantState.IDLE
        sm.shutdown()
    
    def test_create_with_custom_timeouts(self):
        """Factory should accept custom timeouts."""
        custom = {AssistantState.LISTENING: 5.0}
        sm = create_state_machine(custom_timeouts=custom)
        assert sm._config.timeouts[AssistantState.LISTENING] == 5.0
        sm.shutdown()
