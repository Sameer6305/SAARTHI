"""
Bug Audit and Test Suite for Voice-Only Refactor
=================================================

Tests for:
1. Race conditions
2. State desync  
3. Voice pipeline deadlocks
4. Permission bypass
5. Hotkey edge cases

Run: python test_voice_only.py
"""

import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add path
sys.path.insert(0, str(Path(__file__).parent))


class TestHotkeyStateMachine(unittest.TestCase):
    """Test hotkey state machine for edge cases."""
    
    def setUp(self):
        from saarthi_executor.hotkey_voice import HoldToTalkHotkey, HotkeyState
        self.HotkeyState = HotkeyState
        
        self.on_start = Mock(return_value=True)
        self.on_stop = Mock(return_value="test transcription")
        self.on_error = Mock()
        
        self.hotkey = HoldToTalkHotkey(
            on_recording_start=self.on_start,
            on_recording_stop=self.on_stop,
            on_error=self.on_error,
            enabled_check=lambda: True,
        )
    
    def tearDown(self):
        if self.hotkey:
            self.hotkey.stop()
    
    def test_initial_state(self):
        """Test initial state is INACTIVE."""
        self.assertEqual(self.hotkey.state, self.HotkeyState.INACTIVE)
    
    def test_state_after_stop(self):
        """Test state returns to INACTIVE after stop."""
        # Simulate start/stop without actual keyboard
        self.hotkey._running = True
        self.hotkey._state = self.HotkeyState.READY
        
        self.hotkey.stop()
        self.assertEqual(self.hotkey.state, self.HotkeyState.INACTIVE)
    
    def test_force_reset(self):
        """Test force reset from any state."""
        self.hotkey._running = True
        self.hotkey._state = self.HotkeyState.KEY_DOWN
        self.hotkey._combo_active = True
        
        self.hotkey.force_reset()
        
        self.assertEqual(self.hotkey.state, self.HotkeyState.READY)
        self.assertFalse(self.hotkey._combo_active)
    
    def test_double_press_prevention(self):
        """Test that rapid presses don't cause double recording."""
        self.hotkey._running = True
        self.hotkey._state = self.HotkeyState.COOLDOWN
        
        # Simulate key press during cooldown
        self.hotkey._on_combo_down()
        
        # Should not start recording
        self.on_start.assert_not_called()
    
    def test_enabled_check_honored(self):
        """Test that disabled assistant blocks recording."""
        self.hotkey._running = True
        self.hotkey._state = self.HotkeyState.READY
        self.hotkey._enabled_check = lambda: False  # Disabled
        
        self.hotkey._on_combo_down()
        
        # Should not start recording
        self.on_start.assert_not_called()
    
    def test_recording_start_failure_handling(self):
        """Test handling when recording start fails."""
        self.on_start.return_value = False  # Simulate failure
        
        self.hotkey._running = True
        self.hotkey._state = self.HotkeyState.READY
        
        self.hotkey._on_combo_down()
        
        # Should call error handler
        self.on_error.assert_called()


class TestPipelineStateMachine(unittest.TestCase):
    """Test voice pipeline state machine."""
    
    def setUp(self):
        from saarthi_executor.hardened_pipeline import HardenedVoicePipeline, PipelineState
        self.PipelineState = PipelineState
        
        self.on_state_change = Mock()
        self.on_result = Mock()
        self.on_error = Mock()
        
        self.pipeline = HardenedVoicePipeline(
            on_state_change=self.on_state_change,
            on_result=self.on_result,
            on_error=self.on_error,
        )
    
    def tearDown(self):
        if self.pipeline:
            self.pipeline.cleanup()
    
    def test_initial_state(self):
        """Test initial state is IDLE."""
        self.assertEqual(self.pipeline.state, self.PipelineState.IDLE)
    
    def test_cannot_stop_when_not_recording(self):
        """Test stop fails gracefully when not recording."""
        result = self.pipeline.stop_recording()
        self.assertFalse(result)
    
    def test_force_reset_from_recording(self):
        """Test force reset while recording."""
        self.pipeline._state = self.PipelineState.RECORDING
        
        self.pipeline.force_reset()
        
        self.assertEqual(self.pipeline.state, self.PipelineState.IDLE)
    
    def test_force_reset_from_processing(self):
        """Test force reset while processing."""
        self.pipeline._state = self.PipelineState.PROCESSING
        
        self.pipeline.force_reset()
        
        self.assertEqual(self.pipeline.state, self.PipelineState.IDLE)
    
    def test_cancel_operation(self):
        """Test cancel from any state."""
        self.pipeline._state = self.PipelineState.RECORDING
        
        self.pipeline.cancel()
        
        self.assertEqual(self.pipeline.state, self.PipelineState.IDLE)
    
    def test_is_busy_during_recording(self):
        """Test is_busy flag during recording."""
        self.pipeline._state = self.PipelineState.RECORDING
        self.assertTrue(self.pipeline.is_busy)
    
    def test_is_busy_during_processing(self):
        """Test is_busy flag during processing."""
        self.pipeline._state = self.PipelineState.PROCESSING
        self.assertTrue(self.pipeline.is_busy)
    
    def test_not_busy_when_idle(self):
        """Test not busy when idle."""
        self.pipeline._state = self.PipelineState.IDLE
        self.assertFalse(self.pipeline.is_busy)


class TestMinimalTray(unittest.TestCase):
    """Test minimal tray functionality."""
    
    def test_state_transitions(self):
        """Test tray state transitions."""
        from saarthi_executor.minimal_tray import MinimalTray, AssistantState
        
        on_enable = Mock(return_value=True)
        on_disable = Mock()
        on_exit = Mock()
        
        tray = MinimalTray(
            on_enable=on_enable,
            on_disable=on_disable,
            on_exit=on_exit,
            initial_state=AssistantState.DISABLED,
        )
        
        # Test initial state
        self.assertEqual(tray.state, AssistantState.DISABLED)
        
        # Test state change
        tray.set_state(AssistantState.ENABLED)
        self.assertEqual(tray.state, AssistantState.ENABLED)
        
        tray.set_state(AssistantState.RECORDING)
        self.assertEqual(tray.state, AssistantState.RECORDING)


class TestSecurityLogging(unittest.TestCase):
    """Test security logging."""
    
    def test_event_logging(self):
        """Test that events are logged."""
        from saarthi_executor.voice_security import VoiceSecurityLogger, SecurityEventType
        
        logger = VoiceSecurityLogger()
        
        # Log some events
        logger.hotkey_pressed()
        logger.recording_started()
        logger.recording_stopped(2.5)
        logger.transcription_complete(50, 0.95, True)
        
        # Check recent events
        events = logger.get_recent_events(10)
        
        self.assertTrue(len(events) >= 4)
        
        # Verify event types
        event_types = [e.event_type for e in events]
        self.assertIn(SecurityEventType.HOTKEY_PRESSED, event_types)
        self.assertIn(SecurityEventType.RECORDING_STARTED, event_types)
        self.assertIn(SecurityEventType.RECORDING_STOPPED, event_types)


class TestRaceConditions(unittest.TestCase):
    """Test for race conditions."""
    
    def test_concurrent_recording_requests(self):
        """Test that concurrent recording requests are handled safely."""
        from saarthi_executor.hardened_pipeline import HardenedVoicePipeline, PipelineState
        
        pipeline = HardenedVoicePipeline()
        
        # Simulate busy state
        pipeline._state = PipelineState.RECORDING
        
        # Multiple concurrent start attempts
        results = []
        threads = []
        
        def try_start():
            result = pipeline.start_recording()
            results.append(result)
        
        for _ in range(5):
            t = threading.Thread(target=try_start)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should fail (pipeline was busy)
        self.assertTrue(all(r == False for r in results))
        
        pipeline.cleanup()


class TestPermissionBypass(unittest.TestCase):
    """Test that permissions cannot be bypassed."""
    
    def test_disabled_blocks_recording(self):
        """Test that disabled state blocks recording."""
        from saarthi_executor.hotkey_voice import HoldToTalkHotkey, HotkeyState
        
        enabled = [False]  # Use list for mutability in closure
        
        on_start = Mock(return_value=True)
        hotkey = HoldToTalkHotkey(
            on_recording_start=on_start,
            on_recording_stop=Mock(),
            enabled_check=lambda: enabled[0],
        )
        
        hotkey._running = True
        hotkey._state = HotkeyState.READY
        
        # Try to record while disabled
        hotkey._on_combo_down()
        
        # Should not start recording
        on_start.assert_not_called()
        
        hotkey.stop()


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHotkeyStateMachine))
    suite.addTests(loader.loadTestsFromTestCase(TestPipelineStateMachine))
    suite.addTests(loader.loadTestsFromTestCase(TestMinimalTray))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityLogging))
    suite.addTests(loader.loadTestsFromTestCase(TestRaceConditions))
    suite.addTests(loader.loadTestsFromTestCase(TestPermissionBypass))
    
    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("SAARTHI Voice-Only Bug Audit Tests")
    print("=" * 60)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 60)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
