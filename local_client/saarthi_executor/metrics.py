"""
Performance & Reliability Engineering Module
=============================================

Production-grade metrics, failure tracking, and debugging infrastructure.

DESIGN PRINCIPLES:
1. Zero overhead when not needed (lazy initialization)
2. Thread-safe metric collection
3. Rolling statistics (no unbounded memory)
4. Structured failure categorization
5. Production debugging utilities

INTERVIEW TALKING POINTS:
- Why percentiles? Mean is misleading with outliers
- Why rolling windows? Bounded memory, recent data most relevant
- Why categorized failures? Enables targeted fixes
"""

import logging
import threading
import time
import json
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from collections import deque, Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class MetricType(Enum):
    """Types of metrics tracked."""
    LATENCY = "latency"
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class FailureCategory(Enum):
    """
    Categorization of failures for targeted debugging.
    
    Hierarchy:
    - Pipeline stage (Audio, STT, Intent, Execution, TTS)
    - Failure type (Timeout, Error, Empty, etc.)
    """
    # Audio pipeline
    AUDIO_DEVICE_ERROR = "audio_device_error"
    AUDIO_PERMISSION_DENIED = "audio_permission_denied"
    VAD_TIMEOUT = "vad_timeout"
    VAD_NO_SPEECH = "vad_no_speech"
    AUDIO_TOO_SHORT = "audio_too_short"
    AUDIO_TOO_LONG = "audio_too_long"
    
    # STT pipeline
    STT_MODEL_LOAD_FAILURE = "stt_model_load_failure"
    STT_EMPTY_RESULT = "stt_empty_result"
    STT_TIMEOUT = "stt_timeout"
    STT_EXCEPTION = "stt_exception"
    STT_LOW_QUALITY = "stt_low_quality"
    
    # Intent pipeline
    INTENT_UNKNOWN = "intent_unknown"
    INTENT_LOW_CONFIDENCE = "intent_low_confidence"
    INTENT_PARSE_ERROR = "intent_parse_error"
    INTENT_AMBIGUOUS = "intent_ambiguous"
    
    # Execution pipeline
    EXECUTION_EXCEPTION = "execution_exception"
    EXECUTION_TIMEOUT = "execution_timeout"
    RESOURCE_NOT_FOUND = "resource_not_found"
    PERMISSION_DENIED = "permission_denied"
    PROCESS_SPAWN_FAILURE = "process_spawn_failure"
    
    # Knowledge pipeline
    KNOWLEDGE_NOT_FOUND = "knowledge_not_found"
    WIKIPEDIA_TIMEOUT = "wikipedia_timeout"
    WIKIPEDIA_ERROR = "wikipedia_error"
    
    # TTS pipeline
    TTS_ENGINE_ERROR = "tts_engine_error"
    TTS_INIT_FAILURE = "tts_init_failure"
    TTS_BLOCKED_CONTENT = "tts_blocked_content"
    
    # Network
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    
    # State machine
    STATE_TIMEOUT = "state_timeout"
    INVALID_TRANSITION = "invalid_transition"
    
    # Unknown
    UNKNOWN = "unknown"


@dataclass
class PerformanceSnapshot:
    """
    Point-in-time performance metrics for a single operation.
    
    Captures all timing data for one voice command cycle.
    """
    # Unique identifier
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Timing metrics (seconds)
    audio_capture_time: float = 0.0
    vad_processing_time: float = 0.0
    stt_time: float = 0.0
    intent_parsing_time: float = 0.0
    knowledge_lookup_time: float = 0.0
    execution_time: float = 0.0
    tts_time: float = 0.0
    total_time: float = 0.0
    
    # Success metrics
    audio_captured: bool = False
    stt_success: bool = False
    intent_type: str = "unknown"
    intent_confidence: float = 0.0
    execution_success: bool = False
    tts_success: bool = False
    
    # Additional context
    audio_duration: float = 0.0
    transcription_length: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class FailureRecord:
    """Record of a single failure for debugging."""
    timestamp: datetime
    category: FailureCategory
    message: str
    context: Dict[str, Any]
    stack_trace: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "message": self.message,
            "context": self.context,
            "stack_trace": self.stack_trace,
            "session_id": self.session_id,
        }


# =============================================================================
# LATENCY TRACKER
# =============================================================================

class LatencyTracker:
    """
    Tracks latency metrics with percentile calculation.
    
    Uses a rolling window to bound memory and focus on recent data.
    """
    
    def __init__(self, window_size: int = 1000):
        self._window_size = window_size
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._lock = threading.Lock()
    
    def record(self, stage: str, latency: float):
        """Record a latency measurement for a stage."""
        with self._lock:
            self._data[stage].append(latency)
    
    @contextmanager
    def measure(self, stage: str):
        """Context manager for measuring stage latency."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record(stage, elapsed)
    
    def get_percentiles(self, stage: str) -> Dict[str, float]:
        """Get p50, p90, p95, p99 latencies for a stage."""
        with self._lock:
            values = list(self._data.get(stage, []))
        
        if not values:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0, "count": 0}
        
        values.sort()
        n = len(values)
        
        # Percentile calculation: for n=100, p50 should be at index 49 (50th element)
        # Use max(0, index-1) to handle the off-by-one correctly
        return {
            "p50": values[max(0, int(n * 0.50) - 1)] if n > 0 else 0,
            "p90": values[max(0, int(n * 0.90) - 1)] if n > 0 else 0,
            "p95": values[max(0, int(n * 0.95) - 1)] if n > 0 else 0,
            "p99": values[max(0, min(int(n * 0.99), n - 1))] if n > 0 else 0,
            "count": n,
            "min": values[0],
            "max": values[-1],
            "mean": sum(values) / n,
        }
    
    def get_all_stages(self) -> List[str]:
        """Get all tracked stages."""
        with self._lock:
            return list(self._data.keys())
    
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get percentiles for all stages."""
        return {stage: self.get_percentiles(stage) for stage in self.get_all_stages()}


# =============================================================================
# SUCCESS RATE TRACKER
# =============================================================================

class SuccessRateTracker:
    """
    Tracks command success rates by intent type.
    
    Provides insight into which commands are failing.
    """
    
    def __init__(self, window_size: int = 500):
        self._window_size = window_size
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._lock = threading.Lock()
    
    def record(self, intent_type: str, success: bool):
        """Record a command result."""
        with self._lock:
            self._data[intent_type].append(1 if success else 0)
    
    def get_success_rate(self, intent_type: str) -> float:
        """Get success rate for an intent type (0.0 to 1.0)."""
        with self._lock:
            data = self._data.get(intent_type, [])
            if not data:
                return 0.0
            return sum(data) / len(data)
    
    def get_all_rates(self) -> Dict[str, Dict[str, Any]]:
        """Get success rates for all intent types."""
        with self._lock:
            result = {}
            for intent_type, data in self._data.items():
                data_list = list(data)
                total = len(data_list)
                success = sum(data_list)
                result[intent_type] = {
                    "success_rate": success / total if total > 0 else 0,
                    "success_count": success,
                    "failure_count": total - success,
                    "total_count": total,
                }
            return result
    
    def get_overall_rate(self) -> float:
        """Get overall success rate across all intent types."""
        with self._lock:
            total = 0
            success = 0
            for data in self._data.values():
                total += len(data)
                success += sum(data)
            return success / total if total > 0 else 0


# =============================================================================
# FAILURE TRACKER
# =============================================================================

class FailureTracker:
    """
    Tracks and categorizes failures for debugging.
    
    Enables targeted fixes by showing which categories fail most.
    """
    
    def __init__(self, max_records: int = 500):
        self._max_records = max_records
        self._records: deque = deque(maxlen=max_records)
        self._counts: Counter = Counter()
        self._lock = threading.Lock()
    
    def record(
        self,
        category: FailureCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Record a failure."""
        record = FailureRecord(
            timestamp=datetime.now(),
            category=category,
            message=message,
            context=context or {},
            stack_trace=stack_trace,
            session_id=session_id,
        )
        
        with self._lock:
            self._records.append(record)
            self._counts[category] += 1
        
        # Log for immediate visibility
        logger.error(
            f"FAILURE [{category.value}]: {message} | Context: {context}"
        )
    
    def get_top_failures(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get most common failure categories."""
        with self._lock:
            return [(c.value, count) for c, count in self._counts.most_common(n)]
    
    def get_recent_failures(self, n: int = 20) -> List[Dict[str, Any]]:
        """Get most recent failures."""
        with self._lock:
            return [r.to_dict() for r in list(self._records)[-n:]]
    
    def get_failures_by_category(
        self,
        category: FailureCategory,
        n: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent failures of a specific category."""
        with self._lock:
            matching = [r for r in self._records if r.category == category]
            return [r.to_dict() for r in matching[-n:]]
    
    def get_failure_count(self, category: FailureCategory) -> int:
        """Get total count for a category."""
        with self._lock:
            return self._counts[category]
    
    def get_total_failures(self) -> int:
        """Get total failure count."""
        with self._lock:
            return sum(self._counts.values())


# =============================================================================
# UNIFIED METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """
    Unified metrics collector combining latency, success rates, and failures.
    
    Singleton pattern for application-wide metrics.
    """
    
    _instance: Optional['MetricsCollector'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.latency = LatencyTracker()
        self.success = SuccessRateTracker()
        self.failures = FailureTracker()
        
        # Session tracking
        self._sessions: deque = deque(maxlen=100)
        self._current_session: Optional[PerformanceSnapshot] = None
        self._session_lock = threading.Lock()
        
        self._initialized = True
        logger.info("Metrics collector initialized")
    
    def start_session(self, session_id: Optional[str] = None) -> PerformanceSnapshot:
        """Start tracking a new session (one voice command cycle)."""
        session = PerformanceSnapshot(
            session_id=session_id or f"s_{int(time.time() * 1000)}",
            timestamp=datetime.now(),
        )
        
        with self._session_lock:
            self._current_session = session
        
        return session
    
    def end_session(self, session: PerformanceSnapshot):
        """Complete and store a session."""
        with self._session_lock:
            session.total_time = (datetime.now() - session.timestamp).total_seconds()
            self._sessions.append(session)
            
            if self._current_session == session:
                self._current_session = None
        
        # Record latency
        self.latency.record("total", session.total_time)
        
        # Record success
        if session.intent_type != "unknown":
            self.success.record(session.intent_type, session.execution_success)
    
    def record_failure(
        self,
        category: FailureCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Record a failure."""
        session_id = None
        with self._session_lock:
            if self._current_session:
                session_id = self._current_session.session_id
        
        self.failures.record(
            category=category,
            message=message,
            context=context,
            session_id=session_id,
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            "latency": self.latency.get_summary(),
            "success_rates": self.success.get_all_rates(),
            "overall_success_rate": self.success.get_overall_rate(),
            "top_failures": self.failures.get_top_failures(10),
            "total_failures": self.failures.get_total_failures(),
            "recent_sessions": len(self._sessions),
        }
    
    def get_health_check(self) -> Dict[str, Any]:
        """Quick health check for monitoring."""
        overall_success = self.success.get_overall_rate()
        total_failures = self.failures.get_total_failures()
        
        # Determine health status
        if overall_success >= 0.95:
            status = "healthy"
        elif overall_success >= 0.80:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "success_rate": overall_success,
            "total_failures": total_failures,
            "latency_p50": self.latency.get_percentiles("total").get("p50", 0),
            "latency_p99": self.latency.get_percentiles("total").get("p99", 0),
        }
    
    def export_to_file(self, filepath: Path):
        """Export metrics to JSON file."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "recent_failures": self.failures.get_recent_failures(50),
            "recent_sessions": [s.to_dict() for s in list(self._sessions)[-50:]],
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Metrics exported to {filepath}")


# =============================================================================
# DECORATORS FOR INSTRUMENTATION
# =============================================================================

def track_latency(stage: str):
    """
    Decorator to track function latency.
    
    Usage:
        @track_latency("stt")
        def transcribe(audio):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            collector = MetricsCollector()
            with collector.latency.measure(stage):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def track_failure(default_category: FailureCategory = FailureCategory.UNKNOWN):
    """
    Decorator to track failures with automatic categorization.
    
    Usage:
        @track_failure(FailureCategory.STT_EXCEPTION)
        def transcribe(audio):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                collector = MetricsCollector()
                collector.record_failure(
                    category=default_category,
                    message=str(e),
                    context={"function": func.__name__},
                )
                raise
        return wrapper
    return decorator


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def get_metrics() -> MetricsCollector:
    """Get the singleton metrics collector."""
    return MetricsCollector()


def reset_metrics():
    """Reset all metrics (for testing)."""
    collector = MetricsCollector()
    collector.latency = LatencyTracker()
    collector.success = SuccessRateTracker()
    collector.failures = FailureTracker()
    collector._sessions.clear()
    collector._current_session = None


# =============================================================================
# DEBUGGING UTILITIES
# =============================================================================

def print_metrics_report():
    """Print human-readable metrics report to console."""
    collector = get_metrics()
    summary = collector.get_summary()
    
    print("\n" + "=" * 60)
    print("SAARTHI METRICS REPORT")
    print("=" * 60)
    
    # Latency
    print("\n📊 LATENCY (seconds):")
    print("-" * 40)
    for stage, percentiles in summary["latency"].items():
        print(f"  {stage:20s} | P50: {percentiles['p50']:.3f}s | P99: {percentiles['p99']:.3f}s | Count: {percentiles['count']}")
    
    # Success rates
    print("\n✅ SUCCESS RATES:")
    print("-" * 40)
    for intent, rates in summary["success_rates"].items():
        print(f"  {intent:20s} | {rates['success_rate']:.1%} ({rates['success_count']}/{rates['total_count']})")
    print(f"\n  {'OVERALL':20s} | {summary['overall_success_rate']:.1%}")
    
    # Failures
    print("\n❌ TOP FAILURES:")
    print("-" * 40)
    for category, count in summary["top_failures"]:
        print(f"  {category:30s} | {count}")
    
    print("\n" + "=" * 60 + "\n")


def generate_debug_context() -> Dict[str, Any]:
    """Generate comprehensive debug context for issue reporting."""
    import platform
    import sys
    
    collector = get_metrics()
    
    return {
        "system": {
            "platform": platform.system(),
            "version": platform.version(),
            "python": sys.version,
        },
        "health": collector.get_health_check(),
        "recent_failures": collector.failures.get_recent_failures(10),
        "latency_summary": collector.latency.get_summary(),
    }
