"""
Memory Service
==============

Implements the memory system as defined in MEMORY_SYSTEM.md.

This service manages:
- Short-term memory (in-memory, per-task)
- Long-term memory interface (vector store abstraction)

SECURITY INVARIANTS:
- No raw data persistence (M-001)
- Abstraction before storage (M-002)
- Purpose-bound reads (M-004)
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from app.logging_config import get_logger
from app.models.memory import (
    LongTermMemoryEntry,
    LongTermMemoryQuery,
    LongTermMemoryType,
    MemoryEntryType,
    ShortTermMemoryEntry,
)

logger = get_logger("memory_service")


class MemoryService:
    """
    Memory service implementing SAARTHI's ethical memory system.
    
    ARCHITECTURE NOTES:
    - STM is purely in-memory (dict), scoped to service instance
    - LTM is abstracted via interface (mock implementation here)
    - All access is logged for audit
    - No raw data is ever stored
    """
    
    def __init__(self) -> None:
        """Initialize memory stores."""
        # Short-term memory: task_id -> list of entries
        self._stm_store: dict[str, list[ShortTermMemoryEntry]] = {}
        
        # Long-term memory: Mock store (in production, this would be a vector DB)
        # user_id -> list of entries
        self._ltm_store: dict[str, list[LongTermMemoryEntry]] = {}
        
        # Access log for audit (in production, this would be persistent)
        self._access_log: list[dict] = []
        
        logger.info("memory_service_initialized")
    
    # =========================================================================
    # SHORT-TERM MEMORY OPERATIONS
    # =========================================================================
    
    def create_stm_entry(
        self,
        task_id: str,
        session_id: str,
        entry_type: MemoryEntryType,
        content: dict,
        ttl_seconds: int = 3600,
        source: str = "system_derived",
    ) -> ShortTermMemoryEntry:
        """
        Create a new short-term memory entry.
        
        STM entries are volatile and auto-expire.
        No user approval required (per MEMORY_SYSTEM.md).
        """
        now = datetime.utcnow()
        
        entry = ShortTermMemoryEntry(
            stm_id=f"stm_{uuid4().hex[:24]}",
            session_id=session_id,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            entry_type=entry_type,
            content=content,
            source=source,
            ttl_seconds=ttl_seconds,
        )
        
        # Initialize task's STM list if needed
        if task_id not in self._stm_store:
            self._stm_store[task_id] = []
        
        self._stm_store[task_id].append(entry)
        
        logger.info(
            "stm_entry_created",
            task_id=task_id,
            stm_id=entry.stm_id,
            entry_type=entry_type.value,
        )
        
        return entry
    
    def get_stm_entries(
        self,
        task_id: str,
        entry_type: Optional[MemoryEntryType] = None,
    ) -> list[ShortTermMemoryEntry]:
        """
        Retrieve STM entries for a task.
        
        Automatically filters out expired entries.
        """
        now = datetime.utcnow()
        
        entries = self._stm_store.get(task_id, [])
        
        # Filter expired entries
        valid_entries = [e for e in entries if e.expires_at > now]
        
        # Update store with only valid entries
        self._stm_store[task_id] = valid_entries
        
        # Apply type filter if specified
        if entry_type is not None:
            valid_entries = [e for e in valid_entries if e.entry_type == entry_type]
        
        # Update access metadata
        for entry in valid_entries:
            entry.access_count += 1
            entry.last_accessed = now
        
        return valid_entries
    
    def clear_stm_for_task(self, task_id: str) -> int:
        """
        Clear all STM entries for a task.
        
        Called when task completes or session ends.
        Returns number of entries cleared.
        """
        entries = self._stm_store.pop(task_id, [])
        count = len(entries)
        
        logger.info(
            "stm_cleared",
            task_id=task_id,
            entries_cleared=count,
        )
        
        return count
    
    def cleanup_expired_stm(self) -> int:
        """
        Remove all expired STM entries across all tasks.
        
        Should be called periodically (e.g., every minute).
        Returns number of entries removed.
        """
        now = datetime.utcnow()
        total_removed = 0
        
        for task_id in list(self._stm_store.keys()):
            original_count = len(self._stm_store[task_id])
            self._stm_store[task_id] = [
                e for e in self._stm_store[task_id]
                if e.expires_at > now
            ]
            removed = original_count - len(self._stm_store[task_id])
            total_removed += removed
            
            # Remove empty task entries
            if not self._stm_store[task_id]:
                del self._stm_store[task_id]
        
        if total_removed > 0:
            logger.info(
                "stm_cleanup_complete",
                entries_removed=total_removed,
            )
        
        return total_removed
    
    # =========================================================================
    # LONG-TERM MEMORY OPERATIONS
    # =========================================================================
    
    def query_ltm(
        self,
        user_id: str,
        query: LongTermMemoryQuery,
    ) -> list[LongTermMemoryEntry]:
        """
        Query long-term memory with purpose-bound access.
        
        SECURITY: All queries are logged with purpose for audit.
        
        NOTE: This is a mock implementation. In production, this would
        perform semantic similarity search against a vector database.
        """
        # Log access for audit (INVARIANT M-004: Purpose-bound reads)
        self._log_ltm_access(
            user_id=user_id,
            query=query.query_text,
            purpose=query.purpose,
            requester=query.requester,
        )
        
        # Get user's memory entries
        entries = self._ltm_store.get(user_id, [])
        
        # Filter by type if specified
        if query.memory_types:
            entries = [
                e for e in entries
                if e.memory_type in query.memory_types
            ]
        
        # Filter by confidence
        entries = [e for e in entries if e.confidence >= query.min_confidence]
        
        # Filter by status (only active entries)
        entries = [e for e in entries if e.status == "active"]
        
        # In production: semantic similarity search would happen here
        # For now, return all matching entries up to max_results
        results = entries[:query.max_results]
        
        logger.info(
            "ltm_query_executed",
            user_id=user_id,
            purpose=query.purpose,
            results_count=len(results),
        )
        
        return results
    
    def propose_ltm_entry(
        self,
        user_id: str,
        memory_type: LongTermMemoryType,
        content: dict,
        creation_reason: str,
    ) -> str:
        """
        Propose a new LTM entry for user approval.
        
        SECURITY: LTM writes require user approval (INVARIANT M-003).
        This method creates a pending entry, not an active one.
        
        Returns: Entry ID for the proposed entry.
        """
        entry = LongTermMemoryEntry(
            ltm_id=f"ltm_{uuid4().hex[:24]}",
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            source_type="system_proposed",
            status="pending_approval",  # NOT active until user approves
        )
        
        # Store in pending state
        if user_id not in self._ltm_store:
            self._ltm_store[user_id] = []
        
        self._ltm_store[user_id].append(entry)
        
        logger.info(
            "ltm_entry_proposed",
            user_id=user_id,
            ltm_id=entry.ltm_id,
            memory_type=memory_type.value,
            reason=creation_reason,
        )
        
        return entry.ltm_id
    
    def approve_ltm_entry(self, user_id: str, ltm_id: str) -> bool:
        """
        Approve a pending LTM entry (user action).
        
        This activates the entry in long-term memory.
        """
        entries = self._ltm_store.get(user_id, [])
        
        for entry in entries:
            if entry.ltm_id == ltm_id and entry.status == "pending_approval":
                entry.status = "active"
                entry.source_type = "user_approved"
                entry.updated_at = datetime.utcnow()
                
                logger.info(
                    "ltm_entry_approved",
                    user_id=user_id,
                    ltm_id=ltm_id,
                )
                return True
        
        return False
    
    def reject_ltm_entry(self, user_id: str, ltm_id: str) -> bool:
        """
        Reject and delete a pending LTM entry (user action).
        
        SECURITY: Rejected entries are permanently deleted (INVARIANT M-005).
        """
        entries = self._ltm_store.get(user_id, [])
        
        for i, entry in enumerate(entries):
            if entry.ltm_id == ltm_id:
                # Permanently remove
                del entries[i]
                
                logger.info(
                    "ltm_entry_rejected",
                    user_id=user_id,
                    ltm_id=ltm_id,
                )
                return True
        
        return False
    
    def delete_ltm_entry(self, user_id: str, ltm_id: str) -> bool:
        """
        Delete an LTM entry (user-initiated only).
        
        SECURITY: 
        - Only user can delete (INVARIANT M-006)
        - Deletion is irreversible (INVARIANT M-005)
        """
        entries = self._ltm_store.get(user_id, [])
        
        for i, entry in enumerate(entries):
            if entry.ltm_id == ltm_id:
                # Permanently remove (no soft delete, no recycle bin)
                del entries[i]
                
                logger.info(
                    "ltm_entry_deleted",
                    user_id=user_id,
                    ltm_id=ltm_id,
                    deletion_type="user_initiated",
                )
                return True
        
        return False
    
    def _log_ltm_access(
        self,
        user_id: str,
        query: str,
        purpose: str,
        requester: str,
    ) -> None:
        """Log LTM access for audit trail."""
        self._access_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "query_hash": hash(query),  # Don't log actual query content
            "purpose": purpose,
            "requester": requester,
        })


# Singleton instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the singleton memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
