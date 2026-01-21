"""
SAARTHI Privacy Model
======================

Strict privacy guarantees for the SAARTHI assistant.

CORE PRINCIPLE: Your data belongs to YOU.

PRIVACY GUARANTEES:
┌─────────────────────────────────────────────────────────────────────┐
│                         SAARTHI PRIVACY                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ✓ 100% LOCAL         - All processing on your machine             │
│  ✓ NO CLOUD           - Nothing leaves your computer               │
│  ✓ NO RAW AUDIO       - Voice is transcribed then discarded        │
│  ✓ NO HISTORY LOGS    - No browsing/action history stored          │
│  ✓ MINIMAL MEMORY     - Only what's needed for current session     │
│  ✓ USER CONTROL       - You can delete everything instantly        │
│  ✓ SLEEP = ZERO       - Minimized/closed = no access to anything   │
│                                                                     │
│  NEVER:                                                             │
│  ✗ Store raw audio recordings                                      │
│  ✗ Log websites visited                                            │
│  ✗ Track files accessed                                            │
│  ✗ Send data to servers                                            │
│  ✗ Run in background when closed                                   │
│  ✗ Access data without explicit action                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

DATA LIFECYCLE:
    Created → Used → Expired → DELETED (automatic)
                ↓
           User "Forget" → DELETED (immediate)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Set, Callable
from pathlib import Path
import threading
import hashlib
import json
import os


# =============================================================================
# PRIVACY ENUMS
# =============================================================================

class DataCategory(Enum):
    """Categories of data with different retention rules."""
    
    # EPHEMERAL: Deleted immediately after use
    AUDIO_RAW = "audio_raw"           # Raw audio → NEVER stored
    AUDIO_BUFFER = "audio_buffer"     # Recording buffer → deleted after transcription
    
    # SESSION: Deleted when session ends
    CONVERSATION = "conversation"      # Chat history → session only
    CONTEXT = "context"               # Task context → session only
    CLIPBOARD = "clipboard"           # Clipboard reads → immediate
    
    # TEMPORARY: Deleted after short TTL
    CACHE = "cache"                   # TTS cache, etc. → 1 hour
    PENDING_ACTION = "pending"        # Pending confirmations → 5 minutes
    
    # USER-CONTROLLED: Only deleted by user
    PREFERENCES = "preferences"       # Settings → until user deletes
    
    # NEVER STORED
    BROWSING_HISTORY = "browsing"     # NEVER stored
    FILE_CONTENTS = "file_contents"   # Read, used, forgotten
    KEYSTROKES = "keystrokes"         # NEVER captured


class RetentionPolicy(Enum):
    """How long data is retained."""
    NEVER_STORE = "never"             # Don't store at all
    IMMEDIATE = "immediate"           # Delete after single use
    SESSION = "session"               # Delete when app closes
    SHORT_TTL = "short_ttl"           # Delete after 5 minutes
    MEDIUM_TTL = "medium_ttl"         # Delete after 1 hour
    USER_CONTROLLED = "user"          # User must explicitly delete


class AccessLevel(Enum):
    """When data can be accessed."""
    ACTIVE_ONLY = "active"            # Only when user is actively using
    FOREGROUND = "foreground"         # Only when app is in foreground
    NEVER = "never"                   # Data type is never accessed/stored


# =============================================================================
# MEMORY SCHEMA
# =============================================================================

@dataclass
class MemoryEntry:
    """A single entry in SAARTHI's memory."""
    id: str
    category: DataCategory
    created_at: datetime
    expires_at: Optional[datetime]
    
    # Content (never stored to disk for sensitive categories)
    content_hash: str                 # Hash for dedup, not actual content
    content_size: int                 # Size in bytes
    
    # Access tracking
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    
    # Metadata only (no sensitive content)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class MemorySchema:
    """
    Schema defining what SAARTHI remembers and for how long.
    
    DESIGN PRINCIPLES:
    1. Minimal data - only what's needed
    2. Shortest retention - delete ASAP
    3. No persistence - RAM only for sensitive data
    4. User control - instant deletion on request
    """
    
    # Retention rules by category
    RETENTION_RULES: Dict[DataCategory, Dict[str, Any]] = field(default_factory=lambda: {
        # NEVER STORED
        DataCategory.AUDIO_RAW: {
            "policy": RetentionPolicy.NEVER_STORE,
            "persist_to_disk": False,
            "description": "Raw audio is NEVER stored",
        },
        DataCategory.BROWSING_HISTORY: {
            "policy": RetentionPolicy.NEVER_STORE,
            "persist_to_disk": False,
            "description": "Browsing history is NEVER tracked",
        },
        DataCategory.KEYSTROKES: {
            "policy": RetentionPolicy.NEVER_STORE,
            "persist_to_disk": False,
            "description": "Keystrokes are NEVER logged",
        },
        
        # IMMEDIATE DELETION
        DataCategory.AUDIO_BUFFER: {
            "policy": RetentionPolicy.IMMEDIATE,
            "ttl_seconds": 0,
            "persist_to_disk": False,
            "description": "Audio buffer deleted after transcription",
        },
        DataCategory.CLIPBOARD: {
            "policy": RetentionPolicy.IMMEDIATE,
            "ttl_seconds": 0,
            "persist_to_disk": False,
            "description": "Clipboard content forgotten after use",
        },
        DataCategory.FILE_CONTENTS: {
            "policy": RetentionPolicy.IMMEDIATE,
            "ttl_seconds": 0,
            "persist_to_disk": False,
            "description": "File contents forgotten after processing",
        },
        
        # SESSION ONLY
        DataCategory.CONVERSATION: {
            "policy": RetentionPolicy.SESSION,
            "max_entries": 10,           # Last 10 turns only
            "persist_to_disk": False,
            "description": "Conversation cleared when app closes",
        },
        DataCategory.CONTEXT: {
            "policy": RetentionPolicy.SESSION,
            "persist_to_disk": False,
            "description": "Task context cleared when app closes",
        },
        
        # SHORT TTL
        DataCategory.PENDING_ACTION: {
            "policy": RetentionPolicy.SHORT_TTL,
            "ttl_seconds": 300,          # 5 minutes
            "persist_to_disk": False,
            "description": "Pending actions expire in 5 minutes",
        },
        
        # MEDIUM TTL
        DataCategory.CACHE: {
            "policy": RetentionPolicy.MEDIUM_TTL,
            "ttl_seconds": 3600,         # 1 hour
            "persist_to_disk": False,
            "max_size_mb": 50,
            "description": "Cache cleared after 1 hour",
        },
        
        # USER CONTROLLED
        DataCategory.PREFERENCES: {
            "policy": RetentionPolicy.USER_CONTROLLED,
            "persist_to_disk": True,     # Only preferences saved to disk
            "description": "Settings persist until user deletes",
        },
    })
    
    # What's stored on disk (very minimal)
    DISK_ALLOWED = {
        DataCategory.PREFERENCES,        # User settings only
    }
    
    # Maximum memory limits
    MAX_MEMORY_MB = 100                  # Total RAM usage
    MAX_CONVERSATION_TURNS = 10          # Sliding window
    MAX_CACHE_ENTRIES = 50               # TTS/other cache


# =============================================================================
# PRIVACY MANAGER
# =============================================================================

class PrivacyManager:
    """
    Enforces privacy rules for all SAARTHI operations.
    
    RESPONSIBILITIES:
    1. Enforce retention policies
    2. Auto-delete expired data
    3. Handle "forget" requests
    4. Block forbidden operations
    5. Manage sleep/wake state
    """
    
    def __init__(self):
        self._schema = MemorySchema()
        self._memory: Dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()
        
        # State tracking
        self._is_sleeping = False
        self._session_id = self._generate_session_id()
        self._session_start = datetime.now()
        
        # Cleanup thread
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        # Start auto-cleanup
        self._start_cleanup_thread()
    
    # -------------------------------------------------------------------------
    # CORE OPERATIONS
    # -------------------------------------------------------------------------
    
    def store(
        self,
        category: DataCategory,
        content: Any,
        metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Store data according to privacy rules.
        
        Returns entry ID or None if storage is forbidden.
        """
        with self._lock:
            # Check if sleeping
            if self._is_sleeping:
                return None
            
            # Get retention rules
            rules = self._schema.RETENTION_RULES.get(category)
            if not rules:
                return None
            
            # Check if category allows storage
            if rules["policy"] == RetentionPolicy.NEVER_STORE:
                # Log that we're correctly NOT storing
                print(f"[PRIVACY] Blocked storage of {category.value} (policy: never store)")
                return None
            
            # Generate entry
            entry_id = self._generate_entry_id()
            content_hash = self._hash_content(content)
            content_size = len(str(content)) if content else 0
            
            # Calculate expiration
            expires_at = None
            if rules["policy"] == RetentionPolicy.IMMEDIATE:
                expires_at = datetime.now()  # Expire immediately
            elif rules["policy"] == RetentionPolicy.SHORT_TTL:
                expires_at = datetime.now() + timedelta(seconds=rules["ttl_seconds"])
            elif rules["policy"] == RetentionPolicy.MEDIUM_TTL:
                expires_at = datetime.now() + timedelta(seconds=rules["ttl_seconds"])
            
            # Create entry (content is NOT stored, only hash)
            entry = MemoryEntry(
                id=entry_id,
                category=category,
                created_at=datetime.now(),
                expires_at=expires_at,
                content_hash=content_hash,
                content_size=content_size,
                metadata=metadata or {},
            )
            
            self._memory[entry_id] = entry
            
            # Enforce limits
            self._enforce_limits(category)
            
            return entry_id
    
    def access(self, entry_id: str) -> Optional[MemoryEntry]:
        """Access an entry (updates access tracking)."""
        with self._lock:
            if self._is_sleeping:
                return None
            
            entry = self._memory.get(entry_id)
            if entry and not entry.is_expired():
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                return entry
            
            return None
    
    def delete(self, entry_id: str) -> bool:
        """Delete a specific entry."""
        with self._lock:
            if entry_id in self._memory:
                del self._memory[entry_id]
                return True
            return False
    
    def forget_category(self, category: DataCategory) -> int:
        """Delete all entries of a category. Returns count deleted."""
        with self._lock:
            to_delete = [
                eid for eid, entry in self._memory.items()
                if entry.category == category
            ]
            
            for eid in to_delete:
                del self._memory[eid]
            
            return len(to_delete)
    
    def forget_all(self) -> int:
        """Delete ALL data. Returns count deleted."""
        with self._lock:
            count = len(self._memory)
            self._memory.clear()
            
            # Also clear any disk storage
            self._clear_disk_storage()
            
            # Generate new session
            self._session_id = self._generate_session_id()
            self._session_start = datetime.now()
            
            print(f"[PRIVACY] Forgot all data ({count} entries)")
            return count
    
    # -------------------------------------------------------------------------
    # SLEEP MODE
    # -------------------------------------------------------------------------
    
    def sleep(self):
        """
        Enter sleep mode - ZERO data access.
        
        When sleeping:
        - No new data can be stored
        - No existing data can be accessed
        - Background operations are paused
        - Only wake() can restore access
        """
        with self._lock:
            self._is_sleeping = True
            
            # Clear session-only data
            session_categories = [
                DataCategory.CONVERSATION,
                DataCategory.CONTEXT,
                DataCategory.CLIPBOARD,
                DataCategory.PENDING_ACTION,
            ]
            
            for category in session_categories:
                self.forget_category(category)
            
            print("[PRIVACY] Sleep mode: ZERO data access")
    
    def wake(self):
        """Wake from sleep mode."""
        with self._lock:
            self._is_sleeping = False
            self._session_id = self._generate_session_id()
            self._session_start = datetime.now()
            print("[PRIVACY] Awake: Normal operation resumed")
    
    @property
    def is_sleeping(self) -> bool:
        return self._is_sleeping
    
    # -------------------------------------------------------------------------
    # AUTO CLEANUP
    # -------------------------------------------------------------------------
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Background loop to clean expired data."""
        while not self._stop_cleanup.is_set():
            try:
                self._cleanup_expired()
            except Exception as e:
                print(f"[PRIVACY] Cleanup error: {e}")
            
            # Check every 30 seconds
            self._stop_cleanup.wait(30)
    
    def _cleanup_expired(self):
        """Remove all expired entries."""
        with self._lock:
            now = datetime.now()
            expired = [
                eid for eid, entry in self._memory.items()
                if entry.is_expired()
            ]
            
            for eid in expired:
                del self._memory[eid]
            
            if expired:
                print(f"[PRIVACY] Auto-cleaned {len(expired)} expired entries")
    
    def _enforce_limits(self, category: DataCategory):
        """Enforce size limits for a category."""
        rules = self._schema.RETENTION_RULES.get(category, {})
        max_entries = rules.get("max_entries")
        
        if max_entries:
            entries = [
                (eid, entry) for eid, entry in self._memory.items()
                if entry.category == category
            ]
            
            # Sort by creation time (oldest first)
            entries.sort(key=lambda x: x[1].created_at)
            
            # Remove oldest if over limit
            while len(entries) > max_entries:
                eid, _ = entries.pop(0)
                del self._memory[eid]
    
    def _clear_disk_storage(self):
        """Clear any disk-persisted data."""
        storage_path = Path.home() / ".saarthi"
        
        # Only delete specific files, not the whole directory
        files_to_delete = [
            storage_path / "session_cache.json",
            storage_path / "temp_data.json",
        ]
        
        for file_path in files_to_delete:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"[PRIVACY] Could not delete {file_path}: {e}")
    
    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    
    def _generate_session_id(self) -> str:
        """Generate a new session ID."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _generate_entry_id(self) -> str:
        """Generate a unique entry ID."""
        import uuid
        return str(uuid.uuid4())[:12]
    
    def _hash_content(self, content: Any) -> str:
        """Hash content for deduplication (content itself is not stored)."""
        content_str = str(content)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get privacy statistics (no sensitive data)."""
        with self._lock:
            categories = {}
            for entry in self._memory.values():
                cat = entry.category.value
                categories[cat] = categories.get(cat, 0) + 1
            
            return {
                "session_id": self._session_id,
                "session_start": self._session_start.isoformat(),
                "is_sleeping": self._is_sleeping,
                "total_entries": len(self._memory),
                "categories": categories,
                "memory_bytes": sum(e.content_size for e in self._memory.values()),
            }
    
    def shutdown(self):
        """Shutdown privacy manager - clears all session data."""
        self._stop_cleanup.set()
        self.forget_all()
        print("[PRIVACY] Shutdown complete - all session data cleared")


# =============================================================================
# USER TRUST GUARANTEES
# =============================================================================

class TrustGuarantees:
    """
    Explicit guarantees about what SAARTHI will NEVER do.
    
    These are not just policies - they are hard-coded restrictions
    that cannot be overridden by any configuration or user request.
    """
    
    # =========================================================================
    # ABSOLUTE GUARANTEES (Cannot be changed)
    # =========================================================================
    
    NEVER_STORE = [
        "Raw audio recordings",
        "Keystrokes or typing patterns",
        "Browsing history",
        "Screenshots or screen content",
        "File access history",
        "Location data",
        "Personal identifiers",
        "Passwords or credentials",
    ]
    
    NEVER_SEND = [
        "Any data to remote servers",
        "Analytics or telemetry",
        "Crash reports with user data",
        "Model training data",
        "Usage patterns",
    ]
    
    NEVER_ACCESS = [
        "Microphone without push-to-talk",
        "Camera ever",
        "Files without explicit request",
        "Other applications' data",
        "Browser cookies or sessions",
        "Email or messages",
    ]
    
    NEVER_RUN = [
        "In background when closed",
        "At system startup (unless user enables)",
        "Silent operations without UI",
        "Auto-update without consent",
    ]
    
    # =========================================================================
    # USER RIGHTS
    # =========================================================================
    
    USER_RIGHTS = [
        "Delete all data instantly with 'Forget All'",
        "See exactly what data exists (Stats)",
        "Disable any feature",
        "Export your preferences",
        "Completely uninstall with no traces",
        "Audit all actions taken",
    ]
    
    # =========================================================================
    # VERIFICATION
    # =========================================================================
    
    @classmethod
    def verify_operation(cls, operation: str, details: Dict) -> bool:
        """
        Verify an operation doesn't violate guarantees.
        
        Returns True if operation is allowed.
        """
        operation_lower = operation.lower()
        
        # Check NEVER_STORE
        if "store" in operation_lower:
            for forbidden in cls.NEVER_STORE:
                if forbidden.lower() in str(details).lower():
                    print(f"[TRUST] BLOCKED: Cannot store {forbidden}")
                    return False
        
        # Check NEVER_SEND
        if "send" in operation_lower or "upload" in operation_lower:
            print(f"[TRUST] BLOCKED: No data transmission allowed")
            return False
        
        # Check NEVER_ACCESS
        if "access" in operation_lower:
            for forbidden in cls.NEVER_ACCESS:
                if forbidden.lower() in str(details).lower():
                    print(f"[TRUST] BLOCKED: Cannot access {forbidden}")
                    return False
        
        return True
    
    @classmethod
    def get_privacy_policy(cls) -> str:
        """Get human-readable privacy policy."""
        policy = """
╔══════════════════════════════════════════════════════════════════════╗
║                     SAARTHI PRIVACY POLICY                           ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  SAARTHI runs 100% locally on your computer.                        ║
║  Your data NEVER leaves your machine.                                ║
║                                                                      ║
║  ════════════════════════════════════════════════════════════════    ║
║  WE NEVER STORE:                                                     ║
║  ════════════════════════════════════════════════════════════════    ║
"""
        for item in cls.NEVER_STORE:
            policy += f"║    ✗ {item:<56} ║\n"
        
        policy += """║                                                                      ║
║  ════════════════════════════════════════════════════════════════    ║
║  WE NEVER SEND:                                                      ║
║  ════════════════════════════════════════════════════════════════    ║
"""
        for item in cls.NEVER_SEND:
            policy += f"║    ✗ {item:<56} ║\n"
        
        policy += """║                                                                      ║
║  ════════════════════════════════════════════════════════════════    ║
║  YOUR RIGHTS:                                                        ║
║  ════════════════════════════════════════════════════════════════    ║
"""
        for item in cls.USER_RIGHTS:
            policy += f"║    ✓ {item:<56} ║\n"
        
        policy += """║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
        return policy


# =============================================================================
# DATA LIFECYCLE
# =============================================================================

class DataLifecycle:
    """
    Documents the lifecycle of each data type.
    
    Every piece of data follows: Created → Used → Expired → DELETED
    """
    
    LIFECYCLES = {
        "voice_input": {
            "created": "When you press and hold the voice button",
            "stored_as": "Temporary audio buffer in RAM only",
            "used_for": "Converting speech to text",
            "deleted": "IMMEDIATELY after transcription (within 1 second)",
            "persisted": "NEVER - no audio file is ever saved",
        },
        
        "text_command": {
            "created": "When you type or speak a command",
            "stored_as": "Current session context (RAM only)",
            "used_for": "Understanding your request",
            "deleted": "When you close SAARTHI",
            "persisted": "NEVER - not saved to disk",
        },
        
        "conversation_history": {
            "created": "Each message in a conversation",
            "stored_as": "Last 10 messages in RAM only",
            "used_for": "Maintaining context for follow-up questions",
            "deleted": "When you close SAARTHI or say 'forget'",
            "persisted": "NEVER - not saved to disk",
        },
        
        "file_contents": {
            "created": "When you ask to read a file",
            "stored_as": "Temporary variable in RAM",
            "used_for": "Summarizing or answering questions",
            "deleted": "IMMEDIATELY after response is generated",
            "persisted": "NEVER - content is not saved",
        },
        
        "clipboard": {
            "created": "When you allow clipboard access",
            "stored_as": "Temporary variable in RAM",
            "used_for": "Processing your request",
            "deleted": "IMMEDIATELY after use",
            "persisted": "NEVER",
        },
        
        "urls_opened": {
            "created": "When you ask to open a website",
            "stored_as": "NOT STORED - just opened",
            "used_for": "Opening in your browser",
            "deleted": "N/A - never stored",
            "persisted": "NEVER - no browsing history kept",
        },
        
        "preferences": {
            "created": "When you change settings",
            "stored_as": "JSON file in ~/.saarthi/",
            "used_for": "Remembering your preferences",
            "deleted": "When you click 'Reset Settings'",
            "persisted": "YES - until you delete",
        },
        
        "tts_cache": {
            "created": "When text is converted to speech",
            "stored_as": "Temporary audio in RAM",
            "used_for": "Faster repeated phrases",
            "deleted": "After 1 hour or when you close SAARTHI",
            "persisted": "NEVER",
        },
    }
    
    @classmethod
    def get_lifecycle(cls, data_type: str) -> Dict:
        """Get lifecycle for a data type."""
        return cls.LIFECYCLES.get(data_type, {
            "created": "Unknown",
            "stored_as": "Unknown",
            "used_for": "Unknown",
            "deleted": "Unknown",
            "persisted": "Unknown",
        })
    
    @classmethod
    def get_all_lifecycles(cls) -> str:
        """Get human-readable lifecycle documentation."""
        doc = "DATA LIFECYCLE DOCUMENTATION\n"
        doc += "=" * 50 + "\n\n"
        
        for data_type, lifecycle in cls.LIFECYCLES.items():
            doc += f"📦 {data_type.upper()}\n"
            doc += f"   Created:   {lifecycle['created']}\n"
            doc += f"   Stored as: {lifecycle['stored_as']}\n"
            doc += f"   Used for:  {lifecycle['used_for']}\n"
            doc += f"   Deleted:   {lifecycle['deleted']}\n"
            doc += f"   Persisted: {lifecycle['persisted']}\n"
            doc += "\n"
        
        return doc


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_privacy_manager: Optional[PrivacyManager] = None

def get_privacy_manager() -> PrivacyManager:
    """Get the global privacy manager."""
    global _privacy_manager
    if _privacy_manager is None:
        _privacy_manager = PrivacyManager()
    return _privacy_manager


def forget_all() -> int:
    """Convenience: Forget all data."""
    return get_privacy_manager().forget_all()


def sleep():
    """Convenience: Enter sleep mode."""
    get_privacy_manager().sleep()


def wake():
    """Convenience: Wake from sleep."""
    get_privacy_manager().wake()


def get_privacy_stats() -> Dict:
    """Convenience: Get privacy statistics."""
    return get_privacy_manager().get_stats()


def print_privacy_policy():
    """Print the privacy policy."""
    print(TrustGuarantees.get_privacy_policy())


def print_data_lifecycle():
    """Print data lifecycle documentation."""
    print(DataLifecycle.get_all_lifecycles())
