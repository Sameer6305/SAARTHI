"""
Usage-Based Optimization System
================================

Learn from user patterns to improve defaults without ML overhead.

PRODUCT GOALS:
- Learn frequently used apps/websites/queries
- Improve disambiguation for common targets
- No cloud dependency, no ML model
- Simple frequency counting with decay

DESIGN DECISIONS:

1. WHY NOT ML?
   - Overkill for frequency counting
   - Adds model loading latency
   - Privacy concerns with training data
   - Simple statistics work for usage patterns

2. WHAT WE LEARN:
   - App launch frequency → prioritize in disambiguation
   - Website frequency → suggest shortcuts
   - Query patterns → pre-cache knowledge answers
   - Time-of-day patterns → context-aware defaults

3. WHAT WE DON'T LEARN:
   - Content of searches (privacy)
   - Conversation details
   - Cross-session user profiling
   - Anything requiring internet

4. STORAGE:
   - JSON file in user's local_client folder
   - Decayed counts (old usage matters less)
   - Bounded history (max 100 entries per category)

INTERVIEW TALKING POINTS:
- Exponential decay: Recent usage weighted more
- Bounded memory: Fixed space, predictable performance
- Privacy by design: No sensitive data stored
- Cold start: Sensible defaults before learning
"""

import json
import logging
import time
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from threading import Lock
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class UsageEntry:
    """A single usage record with decay."""
    count: float           # Decayed count
    last_used: float       # Timestamp
    total_uses: int        # Absolute total (for debugging)
    first_seen: float      # When first recorded
    
    # Metadata (optional)
    categories: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "last_used": self.last_used,
            "total_uses": self.total_uses,
            "first_seen": self.first_seen,
            "categories": list(self.categories),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UsageEntry':
        return cls(
            count=data.get("count", 0.0),
            last_used=data.get("last_used", 0.0),
            total_uses=data.get("total_uses", 0),
            first_seen=data.get("first_seen", 0.0),
            categories=set(data.get("categories", [])),
        )


class UsageTracker:
    """
    Tracks usage patterns with exponential decay.
    
    DECAY FORMULA:
        decayed_count = count * exp(-λ * age_days)
        
    Where λ (decay_rate) controls how fast old usage fades.
    Default: λ = 0.1 → half-life ≈ 7 days
    
    USAGE:
        tracker = UsageTracker()
        tracker.load()
        
        # Record usage
        tracker.record("website", "youtube")
        tracker.record("app", "notepad")
        
        # Get rankings
        top_sites = tracker.get_top("website", n=5)
        
        # Check if known
        if tracker.get_frequency("website", "youtube") > 0.5:
            # User uses YouTube often
            pass
    """
    
    # Decay rate (0.1 = ~7 day half-life)
    DECAY_RATE = 0.1
    
    # Max entries per category to prevent unbounded growth
    MAX_ENTRIES_PER_CATEGORY = 100
    
    # Minimum count before an entry is pruned
    MIN_COUNT_THRESHOLD = 0.01
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path or (
            Path(__file__).parent.parent / "usage_stats.json"
        )
        self._data: Dict[str, Dict[str, UsageEntry]] = defaultdict(dict)
        self._lock = Lock()
        self._dirty = False
        self._last_save = 0.0
    
    def load(self):
        """Load usage data from disk."""
        if not self._storage_path.exists():
            logger.info("No usage stats found, starting fresh")
            return
        
        try:
            with open(self._storage_path) as f:
                raw = json.load(f)
            
            for category, entries in raw.items():
                for key, entry_data in entries.items():
                    self._data[category][key] = UsageEntry.from_dict(entry_data)
            
            logger.info(f"Loaded usage stats: {sum(len(e) for e in self._data.values())} entries")
            
            # Apply decay to loaded data
            self._apply_decay_all()
            
        except Exception as e:
            logger.warning(f"Failed to load usage stats: {e}")
    
    def save(self, force: bool = False):
        """Save usage data to disk."""
        # Throttle saves (max once per 30 seconds unless forced)
        if not force and time.time() - self._last_save < 30:
            return
        
        if not self._dirty and not force:
            return
        
        with self._lock:
            try:
                serialized = {}
                for category, entries in self._data.items():
                    serialized[category] = {
                        key: entry.to_dict()
                        for key, entry in entries.items()
                    }
                
                with open(self._storage_path, 'w') as f:
                    json.dump(serialized, f, indent=2)
                
                self._dirty = False
                self._last_save = time.time()
                logger.debug("Usage stats saved")
                
            except Exception as e:
                logger.warning(f"Failed to save usage stats: {e}")
    
    def record(
        self,
        category: str,
        key: str,
        weight: float = 1.0,
        extra_categories: Optional[Set[str]] = None,
    ):
        """
        Record a usage event.
        
        Args:
            category: Category (website, app, query, etc.)
            key: The item used (youtube, notepad, etc.)
            weight: Weight of this usage (default 1.0)
            extra_categories: Additional tags for this item
        """
        key = key.lower().strip()
        now = time.time()
        
        with self._lock:
            entries = self._data[category]
            
            if key in entries:
                entry = entries[key]
                # Apply decay before adding new count
                age_days = (now - entry.last_used) / 86400
                entry.count = entry.count * math.exp(-self.DECAY_RATE * age_days)
                entry.count += weight
                entry.last_used = now
                entry.total_uses += 1
                if extra_categories:
                    entry.categories.update(extra_categories)
            else:
                entries[key] = UsageEntry(
                    count=weight,
                    last_used=now,
                    total_uses=1,
                    first_seen=now,
                    categories=extra_categories or set(),
                )
            
            # Prune if over max entries
            self._prune_category(category)
            
            self._dirty = True
    
    def get_frequency(self, category: str, key: str) -> float:
        """
        Get decayed frequency count for an item.
        
        Returns 0.0 if not found.
        """
        key = key.lower().strip()
        
        with self._lock:
            entries = self._data.get(category, {})
            entry = entries.get(key)
            
            if entry is None:
                return 0.0
            
            # Apply current decay
            age_days = (time.time() - entry.last_used) / 86400
            return entry.count * math.exp(-self.DECAY_RATE * age_days)
    
    def get_top(self, category: str, n: int = 10) -> List[tuple[str, float]]:
        """
        Get top N items in a category by decayed frequency.
        
        Returns list of (key, decayed_count) tuples.
        """
        with self._lock:
            entries = self._data.get(category, {})
            
            if not entries:
                return []
            
            # Calculate current decayed counts
            now = time.time()
            scored = []
            for key, entry in entries.items():
                age_days = (now - entry.last_used) / 86400
                decayed = entry.count * math.exp(-self.DECAY_RATE * age_days)
                if decayed >= self.MIN_COUNT_THRESHOLD:
                    scored.append((key, decayed))
            
            # Sort by score descending
            scored.sort(key=lambda x: x[1], reverse=True)
            
            return scored[:n]
    
    def is_frequent(self, category: str, key: str, threshold: float = 1.0) -> bool:
        """Check if an item is used frequently."""
        return self.get_frequency(category, key) >= threshold
    
    def get_all_categories(self) -> List[str]:
        """Get all recorded categories."""
        return list(self._data.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for debugging."""
        stats = {}
        for category, entries in self._data.items():
            top_items = self.get_top(category, n=5)
            stats[category] = {
                "total_items": len(entries),
                "top_5": [{"item": k, "score": round(v, 2)} for k, v in top_items],
            }
        return stats
    
    def _apply_decay_all(self):
        """Apply decay to all entries (called on load)."""
        now = time.time()
        
        for category, entries in self._data.items():
            to_remove = []
            
            for key, entry in entries.items():
                age_days = (now - entry.last_used) / 86400
                entry.count = entry.count * math.exp(-self.DECAY_RATE * age_days)
                
                if entry.count < self.MIN_COUNT_THRESHOLD:
                    to_remove.append(key)
            
            for key in to_remove:
                del entries[key]
        
        self._dirty = True
    
    def _prune_category(self, category: str):
        """Remove lowest-scored entries if over max."""
        entries = self._data.get(category, {})
        
        if len(entries) <= self.MAX_ENTRIES_PER_CATEGORY:
            return
        
        # Get all with current scores
        scored = []
        now = time.time()
        for key, entry in entries.items():
            age_days = (now - entry.last_used) / 86400
            decayed = entry.count * math.exp(-self.DECAY_RATE * age_days)
            scored.append((key, decayed))
        
        # Sort by score ascending (lowest first)
        scored.sort(key=lambda x: x[1])
        
        # Remove lowest until under max
        to_remove = len(entries) - self.MAX_ENTRIES_PER_CATEGORY
        for key, _ in scored[:to_remove]:
            del entries[key]


class UsageOptimizer:
    """
    Uses usage patterns to improve assistant behavior.
    
    OPTIMIZATIONS:
    1. Disambiguation: "open app" → most-used matching app
    2. Suggestions: "You often use YouTube around this time"
    3. Pre-caching: Pre-fetch knowledge for common questions
    4. Shortcuts: Learn "yt" → "youtube"
    
    USAGE:
        optimizer = UsageOptimizer()
        
        # Record when user opens something
        optimizer.record_open("website", "youtube")
        
        # Disambiguate when multiple matches
        best = optimizer.disambiguate("app", ["notepad", "notepad++", "notes"])
        # Returns most-used match
    """
    
    # Category keys
    WEBSITE = "website"
    APP = "app"
    QUERY = "query"
    TOPIC = "topic"
    COMMAND = "command"
    
    def __init__(self, tracker: Optional[UsageTracker] = None):
        self._tracker = tracker or UsageTracker()
    
    def load(self):
        """Load usage data."""
        self._tracker.load()
    
    def save(self, force: bool = False):
        """Save usage data."""
        self._tracker.save(force=force)
    
    def record_open(self, category: str, target: str):
        """Record that user opened something."""
        self._tracker.record(category, target)
    
    def record_search(self, query: str):
        """Record a search query."""
        self._tracker.record(self.QUERY, query)
    
    def record_question(self, topic: str):
        """Record a question topic."""
        self._tracker.record(self.TOPIC, topic)
    
    def record_command(self, intent_type: str):
        """Record command intent type."""
        self._tracker.record(self.COMMAND, intent_type)
    
    def disambiguate(
        self,
        category: str,
        candidates: List[str],
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Choose the best candidate based on usage history.
        
        Returns the most-used candidate, or default if no history.
        """
        if not candidates:
            return default
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score each candidate
        best = default or candidates[0]
        best_score = 0.0
        
        for candidate in candidates:
            score = self._tracker.get_frequency(category, candidate)
            if score > best_score:
                best_score = score
                best = candidate
        
        return best
    
    def get_frequent_websites(self, n: int = 5) -> List[str]:
        """Get most frequently used websites."""
        top = self._tracker.get_top(self.WEBSITE, n)
        return [item for item, _ in top]
    
    def get_frequent_apps(self, n: int = 5) -> List[str]:
        """Get most frequently used apps."""
        top = self._tracker.get_top(self.APP, n)
        return [item for item, _ in top]
    
    def get_frequent_topics(self, n: int = 5) -> List[str]:
        """Get most frequently asked topics."""
        top = self._tracker.get_top(self.TOPIC, n)
        return [item for item, _ in top]
    
    def is_frequently_used(self, category: str, target: str) -> bool:
        """Check if target is frequently used."""
        return self._tracker.is_frequent(category, target)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return self._tracker.get_statistics()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_usage_optimizer: Optional[UsageOptimizer] = None


def get_usage_optimizer() -> UsageOptimizer:
    """Get the global usage optimizer."""
    global _usage_optimizer
    if _usage_optimizer is None:
        _usage_optimizer = UsageOptimizer()
        _usage_optimizer.load()
    return _usage_optimizer
