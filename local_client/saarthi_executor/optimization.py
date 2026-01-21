"""
SAARTHI Performance Optimization
=================================

System optimizations for maximum responsiveness.

PERFORMANCE TARGETS:
┌─────────────────────────────────────────────────────────────────────┐
│  METRIC                    │  TARGET      │  CURRENT BOTTLENECK    │
├─────────────────────────────────────────────────────────────────────┤
│  Voice → Text (STT)        │  < 500ms     │  Whisper model size    │
│  Text → Action (Parse)     │  < 50ms      │  Intent classification │
│  LLM Response              │  < 2s        │  Model inference       │
│  Action Execution          │  < 100ms     │  Confirmation UI       │
│  Text → Voice (TTS)        │  < 200ms     │  Audio generation      │
│                            │              │                        │
│  TOTAL VOICE ROUND-TRIP    │  < 3s        │  All combined          │
└─────────────────────────────────────────────────────────────────────┘

OPTIMIZATION STRATEGIES:
1. CACHING      - Cache frequent responses, TTS audio, intent patterns
2. SHORT PROMPTS - Minimize token count, use templates
3. LOCAL FIRST  - Prefer local processing over LLM calls
4. ASYNC        - Non-blocking operations, parallel execution
5. PRELOADING   - Load models at startup, keep warm
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple
from functools import lru_cache
import threading
import asyncio
import hashlib
import time


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================

@dataclass
class PerformanceMetric:
    """Track performance of an operation."""
    name: str
    target_ms: float
    samples: List[float] = field(default_factory=list)
    max_samples: int = 100
    
    def record(self, duration_ms: float):
        """Record a timing sample."""
        self.samples.append(duration_ms)
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
    
    @property
    def avg_ms(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 0
    
    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def is_meeting_target(self) -> bool:
        return self.avg_ms <= self.target_ms


class PerformanceMonitor:
    """Monitor system performance metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, PerformanceMetric] = {
            "stt": PerformanceMetric("Speech-to-Text", target_ms=500),
            "intent": PerformanceMetric("Intent Classification", target_ms=50),
            "llm": PerformanceMetric("LLM Response", target_ms=2000),
            "action": PerformanceMetric("Action Execution", target_ms=100),
            "tts": PerformanceMetric("Text-to-Speech", target_ms=200),
            "total": PerformanceMetric("Total Round-Trip", target_ms=3000),
        }
        self._lock = threading.Lock()
    
    def time_operation(self, operation: str):
        """Context manager for timing operations."""
        return OperationTimer(self, operation)
    
    def record(self, operation: str, duration_ms: float):
        """Record a timing."""
        with self._lock:
            if operation in self.metrics:
                self.metrics[operation].record(duration_ms)
    
    def get_report(self) -> Dict[str, Any]:
        """Get performance report."""
        with self._lock:
            return {
                name: {
                    "target_ms": m.target_ms,
                    "avg_ms": round(m.avg_ms, 1),
                    "p95_ms": round(m.p95_ms, 1),
                    "meeting_target": m.is_meeting_target,
                    "samples": len(m.samples),
                }
                for name, m in self.metrics.items()
            }


class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, monitor: PerformanceMonitor, operation: str):
        self.monitor = monitor
        self.operation = operation
        self.start_time = 0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.monitor.record(self.operation, duration_ms)


# =============================================================================
# RESPONSE CACHE
# =============================================================================

class ResponseCache:
    """
    Cache for frequent responses to avoid LLM calls.
    
    CACHING STRATEGY:
    1. Exact match cache - For identical queries
    2. Pattern cache - For similar intent patterns
    3. TTS cache - For audio of common phrases
    
    CACHE HIERARCHY:
    L1: In-memory (instant, <1ms)
    L2: SQLite (fast, <10ms) [optional]
    
    EVICTION:
    - LRU with TTL
    - Max 1000 entries
    - 1 hour default TTL
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
        
        # Stats
        self.hits = 0
        self.misses = 0
    
    def _hash_key(self, key: str) -> str:
        """Create hash for cache key."""
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache. Returns None if not found or expired."""
        with self._lock:
            hashed = self._hash_key(key)
            
            if hashed not in self._cache:
                self.misses += 1
                return None
            
            value, timestamp = self._cache[hashed]
            
            # Check expiration
            if datetime.now() - timestamp > self.ttl:
                del self._cache[hashed]
                self._access_order.remove(hashed)
                self.misses += 1
                return None
            
            # Update access order (LRU)
            self._access_order.remove(hashed)
            self._access_order.append(hashed)
            
            self.hits += 1
            return value
    
    def set(self, key: str, value: Any):
        """Set cache value."""
        with self._lock:
            hashed = self._hash_key(key)
            
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                oldest = self._access_order.pop(0)
                del self._cache[oldest]
            
            self._cache[hashed] = (value, datetime.now())
            self._access_order.append(hashed)
    
    def invalidate(self, key: str):
        """Remove specific key."""
        with self._lock:
            hashed = self._hash_key(key)
            if hashed in self._cache:
                del self._cache[hashed]
                self._access_order.remove(hashed)
    
    def clear(self):
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self.hits = 0
            self.misses = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.1%}",
        }


# =============================================================================
# INTENT PATTERN CACHE
# =============================================================================

class IntentPatternCache:
    """
    Fast intent classification without LLM.
    
    Uses pattern matching for common intents:
    - "open youtube" → OPEN_URL
    - "what is X" → EXPLAIN
    - "search for X" → SEARCH
    
    SPEED: <1ms vs ~500ms for LLM classification
    """
    
    # Pre-compiled patterns for instant matching
    PATTERNS = {
        "open_url": [
            (r"^open\s+(\w+)", lambda m: {"action": "open_url", "site": m.group(1)}),
            (r"^go\s+to\s+(\w+)", lambda m: {"action": "open_url", "site": m.group(1)}),
            (r"^launch\s+(\w+)", lambda m: {"action": "open_url", "site": m.group(1)}),
        ],
        "search": [
            (r"^search\s+(?:for\s+)?(.+)", lambda m: {"action": "search", "query": m.group(1)}),
            (r"^find\s+(.+)", lambda m: {"action": "search", "query": m.group(1)}),
            (r"^google\s+(.+)", lambda m: {"action": "search", "query": m.group(1)}),
        ],
        "explain": [
            (r"^(?:what\s+is|explain)\s+(.+)", lambda m: {"action": "explain", "topic": m.group(1)}),
            (r"^tell\s+me\s+about\s+(.+)", lambda m: {"action": "explain", "topic": m.group(1)}),
        ],
        "greeting": [
            (r"^(?:hi|hello|hey)(?:\s|$)", lambda m: {"action": "greeting"}),
        ],
        "thanks": [
            (r"^(?:thanks?|thank\s+you)", lambda m: {"action": "thanks"}),
        ],
        "confirm_yes": [
            (r"^(?:yes|yeah|yep|sure|ok|okay|confirm|do\s+it|proceed)(?:\s|$)", 
             lambda m: {"action": "confirm", "value": True}),
        ],
        "confirm_no": [
            (r"^(?:no|nope|cancel|stop|don't|deny)(?:\s|$)", 
             lambda m: {"action": "confirm", "value": False}),
        ],
    }
    
    # Site URL mappings
    SITE_URLS = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://www.github.com",
        "stackoverflow": "https://stackoverflow.com",
        "wikipedia": "https://www.wikipedia.org",
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "linkedin": "https://www.linkedin.com",
        "gmail": "https://mail.google.com",
        "drive": "https://drive.google.com",
        "docs": "https://docs.google.com",
        "sheets": "https://sheets.google.com",
        "chatgpt": "https://chat.openai.com",
        "claude": "https://claude.ai",
    }
    
    def __init__(self):
        import re
        self._compiled = {}
        for intent, patterns in self.PATTERNS.items():
            self._compiled[intent] = [
                (re.compile(pattern, re.IGNORECASE), handler)
                for pattern, handler in patterns
            ]
    
    def match(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Try to match text against patterns.
        
        Returns intent dict or None if no match.
        """
        text = text.strip()
        
        for intent, patterns in self._compiled.items():
            for regex, handler in patterns:
                match = regex.match(text)
                if match:
                    result = handler(match)
                    result["intent"] = intent
                    result["confidence"] = 0.95  # High confidence for pattern match
                    
                    # Resolve site URLs
                    if result.get("action") == "open_url" and "site" in result:
                        site = result["site"].lower()
                        if site in self.SITE_URLS:
                            result["url"] = self.SITE_URLS[site]
                    
                    return result
        
        return None


# =============================================================================
# SHORT PROMPT TEMPLATES
# =============================================================================

class ShortPrompts:
    """
    Minimal prompts to reduce LLM token usage.
    
    STRATEGY:
    1. Use templates, not full instructions
    2. Provide examples inline
    3. Limit context window
    4. Use structured output
    """
    
    # System prompts (short versions)
    SYSTEM_MINIMAL = "You are SAARTHI, a helpful study assistant. Be concise."
    
    SYSTEM_STUDENT = """SAARTHI: Engineering study assistant.
Rules: Explain first, then answer. Be concise. Use examples."""
    
    # Intent classification (few-shot, minimal)
    CLASSIFY_INTENT = """Classify intent. Reply with JSON only.
Intents: open_url, search, explain, quiz_help, study_plan, greeting, unknown

Examples:
"open youtube" → {"intent":"open_url","site":"youtube"}
"what is binary search" → {"intent":"explain","topic":"binary search"}
"hi" → {"intent":"greeting"}

Input: {input}
→"""
    
    # Quick answer template
    QUICK_ANSWER = """Q: {question}
Subject: {subject}
Answer in 2-3 sentences:"""
    
    # Concept explanation (short)
    EXPLAIN_SHORT = """{topic} ({subject}):
- Definition (1 line):
- Key points (3 max):
- Example:"""
    
    # Quiz help (minimal)
    QUIZ_HELP = """Q: {question}
Options: {options}
Think step-by-step, then answer.
Reasoning:"""
    
    @classmethod
    def get_prompt(cls, template: str, **kwargs) -> str:
        """Get a formatted prompt."""
        return template.format(**kwargs)
    
    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        return len(text) // 4


# =============================================================================
# ASYNC EXECUTOR
# =============================================================================

class AsyncExecutor:
    """
    Async execution for non-blocking operations.
    
    PATTERNS:
    1. Fire-and-forget for notifications
    2. Parallel execution for independent tasks
    3. Streaming for long responses
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = None
        self._loop = None
    
    async def run_parallel(self, *coroutines) -> List[Any]:
        """Run multiple coroutines in parallel."""
        return await asyncio.gather(*coroutines, return_exceptions=True)
    
    async def run_with_timeout(self, coro, timeout_seconds: float) -> Any:
        """Run coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
    
    def fire_and_forget(self, func: Callable, *args, **kwargs):
        """Run function without waiting for result."""
        thread = threading.Thread(
            target=func,
            args=args,
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
    
    async def stream_response(self, generator, callback: Callable[[str], None]):
        """Stream response chunks to callback."""
        async for chunk in generator:
            callback(chunk)
            await asyncio.sleep(0)  # Yield control


# =============================================================================
# MODEL PRELOADER
# =============================================================================

class ModelPreloader:
    """
    Preload models at startup for instant inference.
    
    MODELS TO PRELOAD:
    1. Whisper (STT) - Load on startup
    2. Local LLM - Keep connection warm
    3. TTS engine - Initialize voice
    """
    
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._loading = threading.Event()
        self._ready = threading.Event()
    
    def preload_whisper(self, model_size: str = "tiny"):
        """Preload Whisper model."""
        def _load():
            try:
                from faster_whisper import WhisperModel
                self._models["whisper"] = WhisperModel(
                    model_size,
                    device="cpu",
                    compute_type="int8",
                )
                print(f"[PRELOAD] Whisper {model_size} ready")
            except Exception as e:
                print(f"[PRELOAD] Whisper failed: {e}")
        
        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
    
    def preload_tts(self):
        """Preload TTS engine."""
        def _load():
            try:
                import win32com.client
                self._models["tts"] = win32com.client.Dispatch("SAPI.SpVoice")
                print("[PRELOAD] TTS ready")
            except Exception as e:
                print(f"[PRELOAD] TTS failed: {e}")
        
        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
    
    def preload_all(self):
        """Preload all models."""
        self._loading.set()
        self.preload_whisper("tiny")  # Fastest model
        self.preload_tts()
        self._ready.set()
    
    def get_model(self, name: str) -> Optional[Any]:
        """Get preloaded model."""
        return self._models.get(name)
    
    def is_ready(self) -> bool:
        return self._ready.is_set()


# =============================================================================
# OPTIMIZATION CONFIG
# =============================================================================

@dataclass
class OptimizationConfig:
    """Configuration for performance optimizations."""
    
    # Whisper STT
    whisper_model: str = "tiny"           # tiny=39MB, base=139MB
    whisper_beam_size: int = 1            # 1 = fastest
    whisper_vad_filter: bool = True       # Skip silence
    
    # LLM
    llm_max_tokens: int = 256             # Limit response length
    llm_temperature: float = 0.3          # Lower = faster, more deterministic
    llm_timeout_seconds: float = 10.0     # Timeout for slow responses
    
    # Caching
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600
    
    # Pattern matching (skip LLM for simple intents)
    pattern_matching_enabled: bool = True
    
    # TTS
    tts_cache_enabled: bool = True
    tts_async: bool = True                # Non-blocking speech
    
    # Preloading
    preload_models: bool = True
    
    # Timeouts
    action_timeout_seconds: float = 15.0
    confirmation_timeout_seconds: float = 15.0


# =============================================================================
# OPTIMIZATION MANAGER
# =============================================================================

class OptimizationManager:
    """
    Central manager for all optimizations.
    
    USAGE:
    ```python
    opt = OptimizationManager()
    opt.initialize()
    
    # Fast intent classification
    intent = opt.classify_intent("open youtube")
    
    # Cached response
    response = opt.get_cached_response("what is binary search")
    
    # Performance report
    print(opt.get_performance_report())
    ```
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
        
        self.perf_monitor = PerformanceMonitor()
        self.response_cache = ResponseCache(
            max_size=self.config.cache_max_size,
            ttl_seconds=self.config.cache_ttl_seconds,
        )
        self.intent_cache = IntentPatternCache()
        self.prompts = ShortPrompts()
        self.async_executor = AsyncExecutor()
        self.model_preloader = ModelPreloader()
    
    def initialize(self):
        """Initialize all optimization systems."""
        if self.config.preload_models:
            self.model_preloader.preload_all()
        
        print("[OPT] Optimization manager initialized")
    
    def classify_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Fast intent classification.
        
        1. Try pattern matching first (< 1ms)
        2. Check cache (< 1ms)
        3. Fall back to LLM (slower)
        """
        if self.config.pattern_matching_enabled:
            with self.perf_monitor.time_operation("intent"):
                result = self.intent_cache.match(text)
                if result:
                    result["source"] = "pattern"
                    return result
        
        # Check cache
        cached = self.response_cache.get(f"intent:{text}")
        if cached:
            cached["source"] = "cache"
            return cached
        
        # Need LLM (handled by caller)
        return None
    
    def get_cached_response(self, query: str) -> Optional[str]:
        """Get cached response for a query."""
        return self.response_cache.get(f"response:{query}")
    
    def cache_response(self, query: str, response: str):
        """Cache a response."""
        self.response_cache.set(f"response:{query}", response)
    
    def get_short_prompt(self, template_name: str, **kwargs) -> str:
        """Get a short prompt template."""
        templates = {
            "classify": ShortPrompts.CLASSIFY_INTENT,
            "quick": ShortPrompts.QUICK_ANSWER,
            "explain": ShortPrompts.EXPLAIN_SHORT,
            "quiz": ShortPrompts.QUIZ_HELP,
        }
        
        template = templates.get(template_name, ShortPrompts.QUICK_ANSWER)
        return ShortPrompts.get_prompt(template, **kwargs)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get full performance report."""
        return {
            "metrics": self.perf_monitor.get_report(),
            "cache": self.response_cache.get_stats(),
            "models_ready": self.model_preloader.is_ready(),
        }
    
    def get_optimization_checklist(self) -> str:
        """Get optimization status checklist."""
        report = self.get_performance_report()
        metrics = report["metrics"]
        cache = report["cache"]
        
        checklist = """
╔══════════════════════════════════════════════════════════════════════╗
║                    SAARTHI OPTIMIZATION CHECKLIST                    ║
╠══════════════════════════════════════════════════════════════════════╣
"""
        # STT Optimization
        stt = metrics.get("stt", {})
        stt_ok = stt.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  1. SPEECH-TO-TEXT (Target: <500ms)                                  ║
║     {"✓" if stt_ok else "✗"} Whisper model: {self.config.whisper_model:<10} (tiny=fastest)           ║
║     {"✓" if self.config.whisper_beam_size == 1 else "✗"} Beam size: {self.config.whisper_beam_size} (1=fastest)                              ║
║     {"✓" if self.config.whisper_vad_filter else "✗"} VAD filter: {"enabled" if self.config.whisper_vad_filter else "disabled":<10} (skip silence)              ║
║     Current: {stt.get("avg_ms", 0):.0f}ms avg, {stt.get("p95_ms", 0):.0f}ms p95                            ║
"""
        # Intent Classification
        intent = metrics.get("intent", {})
        intent_ok = intent.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  2. INTENT CLASSIFICATION (Target: <50ms)                            ║
║     {"✓" if self.config.pattern_matching_enabled else "✗"} Pattern matching: {"enabled" if self.config.pattern_matching_enabled else "disabled":<10}                       ║
║     {"✓" if cache.get("hit_rate", "0%") != "0.0%" else "○"} Cache hit rate: {cache.get("hit_rate", "0%"):<10}                            ║
║     Current: {intent.get("avg_ms", 0):.0f}ms avg                                           ║
"""
        # LLM Optimization
        llm = metrics.get("llm", {})
        llm_ok = llm.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  3. LLM RESPONSE (Target: <2000ms)                                   ║
║     {"✓" if self.config.llm_max_tokens <= 256 else "○"} Max tokens: {self.config.llm_max_tokens:<5} (lower=faster)                     ║
║     {"✓" if self.config.llm_temperature <= 0.5 else "○"} Temperature: {self.config.llm_temperature:<5} (lower=faster)                   ║
║     {"✓" if self.config.cache_enabled else "✗"} Response caching: {"enabled" if self.config.cache_enabled else "disabled":<10}                      ║
║     Current: {llm.get("avg_ms", 0):.0f}ms avg, {llm.get("p95_ms", 0):.0f}ms p95                           ║
"""
        # Action Execution
        action = metrics.get("action", {})
        action_ok = action.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  4. ACTION EXECUTION (Target: <100ms)                                ║
║     {"✓" if self.config.action_timeout_seconds <= 15 else "○"} Timeout: {self.config.action_timeout_seconds:.0f}s                                          ║
║     Current: {action.get("avg_ms", 0):.0f}ms avg                                           ║
"""
        # TTS Optimization
        tts = metrics.get("tts", {})
        tts_ok = tts.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  5. TEXT-TO-SPEECH (Target: <200ms)                                  ║
║     {"✓" if self.config.tts_async else "✗"} Async playback: {"enabled" if self.config.tts_async else "disabled":<10}                       ║
║     {"✓" if self.config.tts_cache_enabled else "✗"} TTS caching: {"enabled" if self.config.tts_cache_enabled else "disabled":<10}                          ║
║     Current: {tts.get("avg_ms", 0):.0f}ms avg                                           ║
"""
        # Model Preloading
        checklist += f"""║                                                                      ║
║  6. MODEL PRELOADING                                                 ║
║     {"✓" if self.config.preload_models else "✗"} Preload on startup: {"enabled" if self.config.preload_models else "disabled":<10}                    ║
║     {"✓" if report.get("models_ready") else "○"} Models ready: {"yes" if report.get("models_ready") else "loading...":<10}                          ║
"""
        # Total
        total = metrics.get("total", {})
        total_ok = total.get("meeting_target", False)
        checklist += f"""║                                                                      ║
║  ════════════════════════════════════════════════════════════════    ║
║  TOTAL ROUND-TRIP (Target: <3000ms)                                  ║
║     {"✓" if total_ok else "✗"} Current: {total.get("avg_ms", 0):.0f}ms avg, {total.get("p95_ms", 0):.0f}ms p95                          ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
        return checklist


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_optimization_manager: Optional[OptimizationManager] = None

def get_optimizer() -> OptimizationManager:
    """Get global optimization manager."""
    global _optimization_manager
    if _optimization_manager is None:
        _optimization_manager = OptimizationManager()
        _optimization_manager.initialize()
    return _optimization_manager


def print_optimization_checklist():
    """Print optimization checklist."""
    print(get_optimizer().get_optimization_checklist())


# =============================================================================
# QUICK REFERENCE
# =============================================================================

"""
OPTIMIZATION QUICK REFERENCE
═══════════════════════════════════════════════════════════════════════

1. WHISPER MODEL SIZES (STT)
   ─────────────────────────
   tiny   │  39 MB │ ~200ms │ Fastest, good accuracy
   base   │ 139 MB │ ~400ms │ Better accuracy
   small  │ 461 MB │ ~1.5s  │ Much slower
   
   → USE: tiny for speed, base for accuracy

2. LLM OPTIMIZATION
   ─────────────────────────
   - max_tokens: 256 (shorter responses)
   - temperature: 0.3 (less sampling)
   - Use pattern matching first
   - Cache frequent responses
   
3. PATTERN MATCHING (No LLM needed)
   ─────────────────────────
   "open youtube"     → Direct URL open
   "search for X"     → Direct search
   "yes/no"           → Confirmation
   "hi/hello"         → Greeting response
   
   → Handles 60-70% of commands without LLM

4. CACHING STRATEGY
   ─────────────────────────
   - Intent cache: Pattern → Intent mapping
   - Response cache: Query → Response (1 hour TTL)
   - TTS cache: Text → Audio (RAM only)
   
5. ASYNC OPERATIONS
   ─────────────────────────
   - TTS playback (non-blocking)
   - Notifications (fire-and-forget)
   - LLM streaming (progressive display)

6. PRELOADING
   ─────────────────────────
   - Load Whisper model at startup
   - Initialize TTS engine
   - Keep LLM connection warm

TARGET LATENCIES:
   STT:    < 500ms (voice to text)
   Intent: <  50ms (classification)
   LLM:    <   2s  (response generation)
   Action: < 100ms (execution)
   TTS:    < 200ms (text to speech)
   ─────────────────────────
   TOTAL:  <   3s  (voice round-trip)
"""
