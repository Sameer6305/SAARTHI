"""
Unit Tests: Metrics & Performance Tracking
==========================================

Tests for latency tracking, success rates, and failure categorization.

Run: pytest tests/test_metrics.py -v
"""

import pytest
import time
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saarthi_executor.metrics import (
    MetricsCollector,
    LatencyTracker,
    SuccessRateTracker,
    FailureTracker,
    FailureCategory,
    PerformanceSnapshot,
    get_metrics,
    reset_metrics,
    track_latency,
    track_failure,
)


class TestLatencyTracker:
    """Tests for latency tracking."""
    
    @pytest.fixture
    def tracker(self):
        return LatencyTracker(window_size=100)
    
    def test_record_latency(self, tracker):
        """Should record latency values."""
        tracker.record("stt", 1.5)
        tracker.record("stt", 2.0)
        
        percentiles = tracker.get_percentiles("stt")
        assert percentiles["count"] == 2
    
    def test_measure_context_manager(self, tracker):
        """Context manager should measure elapsed time."""
        with tracker.measure("test_stage"):
            time.sleep(0.1)
        
        percentiles = tracker.get_percentiles("test_stage")
        assert percentiles["count"] == 1
        assert percentiles["p50"] >= 0.1
    
    def test_percentile_calculation(self, tracker):
        """Should calculate percentiles correctly."""
        # Add 100 values: 1, 2, 3, ..., 100
        for i in range(1, 101):
            tracker.record("test", float(i))
        
        percentiles = tracker.get_percentiles("test")
        assert percentiles["p50"] == 50.0
        assert percentiles["p90"] == 90.0
        assert percentiles["min"] == 1.0
        assert percentiles["max"] == 100.0
    
    def test_empty_percentiles(self, tracker):
        """Should handle empty stage gracefully."""
        percentiles = tracker.get_percentiles("nonexistent")
        assert percentiles["count"] == 0
        assert percentiles["p50"] == 0
    
    def test_window_size_respected(self):
        """Should respect window size limit."""
        tracker = LatencyTracker(window_size=10)
        
        for i in range(20):
            tracker.record("test", float(i))
        
        percentiles = tracker.get_percentiles("test")
        assert percentiles["count"] == 10
        # Should have last 10 values (10-19)
        assert percentiles["min"] == 10.0
    
    def test_get_all_stages(self, tracker):
        """Should list all tracked stages."""
        tracker.record("stage1", 1.0)
        tracker.record("stage2", 2.0)
        
        stages = tracker.get_all_stages()
        assert "stage1" in stages
        assert "stage2" in stages
    
    def test_get_summary(self, tracker):
        """Should return summary for all stages."""
        tracker.record("stt", 1.0)
        tracker.record("intent", 0.1)
        
        summary = tracker.get_summary()
        assert "stt" in summary
        assert "intent" in summary


class TestSuccessRateTracker:
    """Tests for success rate tracking."""
    
    @pytest.fixture
    def tracker(self):
        return SuccessRateTracker(window_size=100)
    
    def test_record_success(self, tracker):
        """Should record successful commands."""
        tracker.record("open_website", True)
        tracker.record("open_website", True)
        
        rate = tracker.get_success_rate("open_website")
        assert rate == 1.0
    
    def test_record_failure(self, tracker):
        """Should record failed commands."""
        tracker.record("open_website", True)
        tracker.record("open_website", False)
        
        rate = tracker.get_success_rate("open_website")
        assert rate == 0.5
    
    def test_success_rate_calculation(self, tracker):
        """Should calculate success rate correctly."""
        for _ in range(80):
            tracker.record("test", True)
        for _ in range(20):
            tracker.record("test", False)
        
        rate = tracker.get_success_rate("test")
        assert rate == 0.8
    
    def test_empty_success_rate(self, tracker):
        """Should handle empty intent gracefully."""
        rate = tracker.get_success_rate("nonexistent")
        assert rate == 0.0
    
    def test_get_all_rates(self, tracker):
        """Should return rates for all intent types."""
        tracker.record("open_website", True)
        tracker.record("search", False)
        
        rates = tracker.get_all_rates()
        assert "open_website" in rates
        assert "search" in rates
        assert rates["open_website"]["success_rate"] == 1.0
        assert rates["search"]["success_rate"] == 0.0
    
    def test_get_overall_rate(self, tracker):
        """Should calculate overall success rate."""
        tracker.record("type1", True)
        tracker.record("type1", True)
        tracker.record("type2", False)
        tracker.record("type2", False)
        
        rate = tracker.get_overall_rate()
        assert rate == 0.5


class TestFailureTracker:
    """Tests for failure tracking."""
    
    @pytest.fixture
    def tracker(self):
        return FailureTracker(max_records=100)
    
    def test_record_failure(self, tracker):
        """Should record failures."""
        tracker.record(
            FailureCategory.STT_TIMEOUT,
            "Whisper took too long",
            context={"duration": 10.5}
        )
        
        assert tracker.get_total_failures() == 1
    
    def test_failure_categorization(self, tracker):
        """Should categorize failures correctly."""
        tracker.record(FailureCategory.STT_TIMEOUT, "timeout1")
        tracker.record(FailureCategory.STT_TIMEOUT, "timeout2")
        tracker.record(FailureCategory.INTENT_UNKNOWN, "unknown1")
        
        top = tracker.get_top_failures(3)
        assert len(top) == 2
        assert top[0][0] == "stt_timeout"
        assert top[0][1] == 2
    
    def test_get_recent_failures(self, tracker):
        """Should return recent failures."""
        tracker.record(FailureCategory.AUDIO_DEVICE_ERROR, "error1")
        tracker.record(FailureCategory.VAD_TIMEOUT, "error2")
        
        recent = tracker.get_recent_failures(10)
        assert len(recent) == 2
    
    def test_get_failures_by_category(self, tracker):
        """Should filter failures by category."""
        tracker.record(FailureCategory.STT_TIMEOUT, "stt1")
        tracker.record(FailureCategory.INTENT_UNKNOWN, "intent1")
        tracker.record(FailureCategory.STT_TIMEOUT, "stt2")
        
        stt_failures = tracker.get_failures_by_category(
            FailureCategory.STT_TIMEOUT, 10
        )
        assert len(stt_failures) == 2
    
    def test_failure_count(self, tracker):
        """Should track failure count by category."""
        tracker.record(FailureCategory.STT_TIMEOUT, "error1")
        tracker.record(FailureCategory.STT_TIMEOUT, "error2")
        
        count = tracker.get_failure_count(FailureCategory.STT_TIMEOUT)
        assert count == 2


class TestMetricsCollector:
    """Tests for unified metrics collector."""
    
    @pytest.fixture
    def collector(self):
        reset_metrics()
        return MetricsCollector()
    
    def test_singleton_pattern(self, collector):
        """Should return same instance."""
        another = MetricsCollector()
        assert collector is another
    
    def test_start_session(self, collector):
        """Should create performance snapshot."""
        session = collector.start_session("test_session")
        assert session.session_id == "test_session"
    
    def test_end_session(self, collector):
        """Should complete and store session."""
        session = collector.start_session()
        session.stt_success = True
        session.intent_type = "open_website"
        session.execution_success = True
        
        time.sleep(0.1)
        collector.end_session(session)
        
        assert session.total_time >= 0.1
    
    def test_record_failure(self, collector):
        """Should record failure with current session."""
        session = collector.start_session("test")
        collector.record_failure(
            FailureCategory.STT_TIMEOUT,
            "Test failure",
            context={"key": "value"}
        )
        
        failures = collector.failures.get_recent_failures(1)
        assert len(failures) == 1
        assert failures[0]["session_id"] == "test"
    
    def test_get_summary(self, collector):
        """Should return comprehensive summary."""
        collector.latency.record("stt", 1.5)
        collector.success.record("open_website", True)
        collector.failures.record(FailureCategory.STT_TIMEOUT, "test")
        
        summary = collector.get_summary()
        assert "latency" in summary
        assert "success_rates" in summary
        assert "top_failures" in summary
    
    def test_get_health_check(self, collector):
        """Should return health status."""
        # Record all successes
        for _ in range(10):
            collector.success.record("test", True)
        
        health = collector.get_health_check()
        assert health["status"] == "healthy"
        assert health["success_rate"] == 1.0
    
    def test_health_degraded(self, collector):
        """Should report degraded health."""
        for _ in range(85):
            collector.success.record("test", True)
        for _ in range(15):
            collector.success.record("test", False)
        
        health = collector.get_health_check()
        assert health["status"] == "degraded"
    
    def test_health_unhealthy(self, collector):
        """Should report unhealthy."""
        for _ in range(70):
            collector.success.record("test", True)
        for _ in range(30):
            collector.success.record("test", False)
        
        health = collector.get_health_check()
        assert health["status"] == "unhealthy"


class TestDecorators:
    """Tests for instrumentation decorators."""
    
    def test_track_latency_decorator(self):
        """@track_latency should record function latency."""
        reset_metrics()
        
        @track_latency("test_function")
        def slow_function():
            time.sleep(0.1)
            return "result"
        
        result = slow_function()
        assert result == "result"
        
        collector = get_metrics()
        percentiles = collector.latency.get_percentiles("test_function")
        assert percentiles["count"] == 1
        assert percentiles["p50"] >= 0.1
    
    def test_track_failure_decorator(self):
        """@track_failure should record exceptions."""
        reset_metrics()
        
        @track_failure(FailureCategory.EXECUTION_EXCEPTION)
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        collector = get_metrics()
        count = collector.failures.get_failure_count(
            FailureCategory.EXECUTION_EXCEPTION
        )
        assert count == 1


class TestPerformanceSnapshot:
    """Tests for performance snapshot data class."""
    
    def test_default_values(self):
        """Should have sensible defaults."""
        snapshot = PerformanceSnapshot()
        assert snapshot.stt_time == 0.0
        assert snapshot.execution_success == False
    
    def test_to_dict(self):
        """Should convert to dictionary."""
        snapshot = PerformanceSnapshot(
            session_id="test",
            stt_time=1.5,
            intent_type="open_website",
            execution_success=True,
        )
        
        d = snapshot.to_dict()
        assert d["session_id"] == "test"
        assert d["stt_time"] == 1.5
        assert d["intent_type"] == "open_website"
        assert d["execution_success"] == True


class TestThreadSafety:
    """Tests for thread safety of metrics collection."""
    
    def test_concurrent_latency_recording(self):
        """Concurrent latency recording should be thread-safe."""
        tracker = LatencyTracker()
        
        def record_latencies():
            for i in range(100):
                tracker.record("test", float(i))
        
        threads = [threading.Thread(target=record_latencies) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        percentiles = tracker.get_percentiles("test")
        assert percentiles["count"] == 500  # 5 threads * 100 records
    
    def test_concurrent_success_recording(self):
        """Concurrent success recording should be thread-safe."""
        tracker = SuccessRateTracker()
        
        def record_results():
            for _ in range(100):
                tracker.record("test", True)
        
        threads = [threading.Thread(target=record_results) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        rates = tracker.get_all_rates()
        assert rates["test"]["total_count"] == 500


class TestGetMetrics:
    """Tests for get_metrics convenience function."""
    
    def test_get_metrics_returns_singleton(self):
        """get_metrics should return singleton."""
        reset_metrics()
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2
    
    def test_reset_metrics(self):
        """reset_metrics should clear all data."""
        collector = get_metrics()
        collector.latency.record("test", 1.0)
        collector.success.record("test", True)
        
        reset_metrics()
        
        collector = get_metrics()
        assert len(collector.latency.get_all_stages()) == 0
