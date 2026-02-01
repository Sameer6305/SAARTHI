"""
Offline Graceful Degradation System
=====================================

Handle connectivity loss gracefully with cached responses and clear messaging.

PRODUCT GOALS:
- Detect when offline (no internet)
- Use cached knowledge answers when available
- Provide clear, short fallback messages
- Never hang or crash due to network issues
- Seamless recovery when back online

DESIGN DECISIONS:

1. WHY DETECT OFFLINE?
   - Prevents long timeouts (user waiting 30s for Wikipedia)
   - Allows immediate fallback to cached data
   - Clear messaging ("I'm offline, but I remember...")

2. OFFLINE DETECTION STRATEGY:
   - Quick DNS check (1 second timeout)
   - Cache connectivity state (don't check every command)
   - Background refresh every 30 seconds
   - Assume offline if check fails (fail-safe)

3. OFFLINE CAPABILITIES:
   - Open local apps ✓ (no internet needed)
   - Answer cached questions ✓
   - Built-in knowledge base ✓
   - Web searches ✗ (queue for later?)
   - Wikipedia lookups ✗
   
4. USER MESSAGING:
   - "I'm offline. I can still open apps and answer some questions."
   - "I don't have that cached. Ask me again when online."
   - "Back online! I can access the web again."
"""

import logging
import socket
import time
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ConnectivityStatus(Enum):
    """Internet connectivity status."""
    ONLINE = auto()
    OFFLINE = auto()
    CHECKING = auto()
    UNKNOWN = auto()


@dataclass
class ConnectivityState:
    """Current connectivity state."""
    status: ConnectivityStatus = ConnectivityStatus.UNKNOWN
    last_check: float = 0.0
    last_online: float = 0.0
    consecutive_failures: int = 0
    check_latency_ms: float = 0.0


class ConnectivityChecker:
    """
    Checks and caches internet connectivity status.
    
    DESIGN:
    - Quick DNS lookup to reliable hosts
    - Caches result to avoid repeated checks
    - Background thread for periodic refresh
    - Callbacks on status change
    
    USAGE:
        checker = ConnectivityChecker()
        checker.start()
        
        if checker.is_online():
            # Do online thing
        else:
            # Use offline fallback
        
        checker.stop()
    """
    
    # Hosts to check (reliable, fast DNS)
    CHECK_HOSTS = [
        ("8.8.8.8", 53),          # Google DNS
        ("1.1.1.1", 53),          # Cloudflare DNS
        ("208.67.222.222", 53),   # OpenDNS
    ]
    
    # How long to cache connectivity status (seconds)
    CACHE_DURATION = 30.0
    
    # Timeout for each connectivity check (seconds)
    CHECK_TIMEOUT = 2.0
    
    # How often to check in background (seconds)
    BACKGROUND_CHECK_INTERVAL = 30.0
    
    def __init__(
        self,
        on_status_change: Optional[Callable[[ConnectivityStatus], None]] = None,
    ):
        self._state = ConnectivityState()
        self._lock = threading.Lock()
        self._on_status_change = on_status_change
        
        # Background checker
        self._checker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def check_now(self) -> ConnectivityStatus:
        """
        Perform immediate connectivity check.
        
        Returns current status (ONLINE or OFFLINE).
        """
        start = time.time()
        
        for host, port in self.CHECK_HOSTS:
            try:
                socket.setdefaulttimeout(self.CHECK_TIMEOUT)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, port))
                s.close()
                
                # Success - we're online
                elapsed_ms = (time.time() - start) * 1000
                self._update_status(ConnectivityStatus.ONLINE, elapsed_ms)
                return ConnectivityStatus.ONLINE
                
            except (socket.error, socket.timeout):
                continue  # Try next host
        
        # All hosts failed - we're offline
        elapsed_ms = (time.time() - start) * 1000
        self._update_status(ConnectivityStatus.OFFLINE, elapsed_ms)
        return ConnectivityStatus.OFFLINE
    
    def is_online(self) -> bool:
        """
        Check if we're currently online.
        
        Uses cached result if fresh, otherwise checks.
        """
        with self._lock:
            # Check if cache is still fresh
            age = time.time() - self._state.last_check
            if age < self.CACHE_DURATION:
                return self._state.status == ConnectivityStatus.ONLINE
        
        # Cache expired, do a quick check
        return self.check_now() == ConnectivityStatus.ONLINE
    
    def is_offline(self) -> bool:
        """Convenience method - opposite of is_online."""
        return not self.is_online()
    
    def get_state(self) -> ConnectivityState:
        """Get current connectivity state."""
        with self._lock:
            return ConnectivityState(
                status=self._state.status,
                last_check=self._state.last_check,
                last_online=self._state.last_online,
                consecutive_failures=self._state.consecutive_failures,
                check_latency_ms=self._state.check_latency_ms,
            )
    
    def start(self):
        """Start background connectivity checking."""
        if self._checker_thread is not None:
            return
        
        self._stop_event.clear()
        self._checker_thread = threading.Thread(
            target=self._background_checker,
            daemon=True,
            name="ConnectivityChecker",
        )
        self._checker_thread.start()
        logger.info("Connectivity checker started")
        
        # Do initial check
        self.check_now()
    
    def stop(self):
        """Stop background connectivity checking."""
        if self._checker_thread is None:
            return
        
        self._stop_event.set()
        self._checker_thread.join(timeout=5.0)
        self._checker_thread = None
        logger.info("Connectivity checker stopped")
    
    def _update_status(self, status: ConnectivityStatus, latency_ms: float):
        """Update connectivity status with thread safety."""
        with self._lock:
            old_status = self._state.status
            now = time.time()
            
            self._state.status = status
            self._state.last_check = now
            self._state.check_latency_ms = latency_ms
            
            if status == ConnectivityStatus.ONLINE:
                self._state.last_online = now
                self._state.consecutive_failures = 0
            else:
                self._state.consecutive_failures += 1
        
        # Notify on status change
        if old_status != status and self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception as e:
                logger.warning(f"Status change callback failed: {e}")
    
    def _background_checker(self):
        """Background thread that periodically checks connectivity."""
        while not self._stop_event.wait(self.BACKGROUND_CHECK_INTERVAL):
            try:
                self.check_now()
            except Exception as e:
                logger.warning(f"Background check failed: {e}")


class OfflineCache:
    """
    Cache for offline access to knowledge answers.
    
    DESIGN:
    - LRU cache with max size
    - Persists to disk for cross-session access
    - TTL for freshness (but we use stale data if offline)
    
    USAGE:
        cache = OfflineCache()
        cache.load()
        
        # Store when online
        cache.store("binary search", "Binary search is...")
        
        # Retrieve when offline
        answer = cache.get("binary search")
    """
    
    MAX_ENTRIES = 500
    TTL_SECONDS = 86400 * 7  # 7 days
    
    def __init__(self, storage_path: Optional[str] = None):
        from pathlib import Path
        self._storage_path = Path(storage_path) if storage_path else (
            Path(__file__).parent.parent / "offline_cache.json"
        )
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._dirty = False
    
    def load(self):
        """Load cache from disk."""
        if not self._storage_path.exists():
            return
        
        try:
            import json
            with open(self._storage_path) as f:
                data = json.load(f)
            
            now = time.time()
            for key, entry in data.items():
                # Skip expired entries
                if now - entry.get("timestamp", 0) > self.TTL_SECONDS:
                    continue
                self._cache[key] = entry
            
            logger.info(f"Loaded offline cache: {len(self._cache)} entries")
            
        except Exception as e:
            logger.warning(f"Failed to load offline cache: {e}")
    
    def save(self):
        """Save cache to disk."""
        if not self._dirty:
            return
        
        try:
            import json
            with self._lock:
                with open(self._storage_path, 'w') as f:
                    json.dump(dict(self._cache), f)
                self._dirty = False
                
        except Exception as e:
            logger.warning(f"Failed to save offline cache: {e}")
    
    def store(self, query: str, answer: str, source: str = "cache"):
        """Store an answer for offline access."""
        key = query.lower().strip()
        
        with self._lock:
            self._cache[key] = {
                "answer": answer,
                "source": source,
                "timestamp": time.time(),
            }
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            # Evict oldest if over max
            while len(self._cache) > self.MAX_ENTRIES:
                self._cache.popitem(last=False)
            
            self._dirty = True
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get cached answer.
        
        Returns dict with 'answer', 'source', 'timestamp' or None.
        """
        key = query.lower().strip()
        
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return entry.copy()
        
        return None
    
    def has(self, query: str) -> bool:
        """Check if query is cached."""
        return self.get(query) is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "max_entries": self.MAX_ENTRIES,
            }


class OfflineManager:
    """
    Orchestrates offline behavior across the assistant.
    
    RESPONSIBILITIES:
    - Monitor connectivity
    - Route requests to cache when offline
    - Generate appropriate user messages
    - Track what couldn't be done offline (for later retry)
    
    USAGE:
        manager = OfflineManager()
        manager.start()
        
        # Before any network operation
        if manager.is_offline():
            answer = manager.get_cached_answer("topic")
            if answer:
                return answer
            else:
                return manager.get_offline_message("question")
        
        manager.stop()
    """
    
    def __init__(
        self,
        on_connectivity_change: Optional[Callable[[bool], None]] = None,
    ):
        self._checker = ConnectivityChecker(
            on_status_change=self._on_status_change
        )
        self._cache = OfflineCache()
        self._on_connectivity_change = on_connectivity_change
        
        # Queue of operations that failed due to offline
        self._offline_queue: List[Dict[str, Any]] = []
    
    def start(self):
        """Start offline management."""
        self._cache.load()
        self._checker.start()
    
    def stop(self):
        """Stop offline management and save state."""
        self._checker.stop()
        self._cache.save()
    
    def is_online(self) -> bool:
        """Check if currently online."""
        return self._checker.is_online()
    
    def is_offline(self) -> bool:
        """Check if currently offline."""
        return self._checker.is_offline()
    
    def cache_answer(self, query: str, answer: str, source: str = "online"):
        """Cache an answer for offline use."""
        self._cache.store(query, answer, source)
    
    def get_cached_answer(self, query: str) -> Optional[str]:
        """
        Get cached answer if available.
        
        Returns answer text or None.
        """
        entry = self._cache.get(query)
        return entry["answer"] if entry else None
    
    def has_cached_answer(self, query: str) -> bool:
        """Check if answer is cached."""
        return self._cache.has(query)
    
    def get_offline_message(self, operation_type: str) -> str:
        """
        Get appropriate message for offline operation.
        
        Args:
            operation_type: 'question', 'search', 'wikipedia', etc.
        """
        messages = {
            "question": "I'm offline and don't have that cached. I can still open apps and answer some questions from memory.",
            "search": "I can't search the web while offline. Try opening a specific website instead.",
            "wikipedia": "I'm offline and can't access Wikipedia right now.",
            "default": "I'm currently offline. Some features may be limited.",
        }
        return messages.get(operation_type, messages["default"])
    
    def get_online_again_message(self) -> str:
        """Message when connectivity is restored."""
        return "I'm back online. I can access the web again."
    
    def get_connectivity_status_message(self) -> str:
        """Get a status message about connectivity."""
        if self.is_online():
            state = self._checker.get_state()
            return f"I'm online. Last check: {state.check_latency_ms:.0f}ms latency."
        else:
            state = self._checker.get_state()
            return (
                f"I'm offline. "
                f"Last online: {(time.time() - state.last_online):.0f}s ago."
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()
    
    def _on_status_change(self, status: ConnectivityStatus):
        """Handle connectivity status changes."""
        is_online = status == ConnectivityStatus.ONLINE
        
        logger.info(f"Connectivity changed: {'online' if is_online else 'offline'}")
        
        if self._on_connectivity_change:
            try:
                self._on_connectivity_change(is_online)
            except Exception as e:
                logger.warning(f"Connectivity change callback failed: {e}")


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_offline_manager: Optional[OfflineManager] = None


def get_offline_manager() -> OfflineManager:
    """Get the global offline manager."""
    global _offline_manager
    if _offline_manager is None:
        _offline_manager = OfflineManager()
        _offline_manager.start()
    return _offline_manager
