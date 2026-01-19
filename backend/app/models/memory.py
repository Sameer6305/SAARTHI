"""
Memory Models
=============

Pydantic models for the memory system.
Implements the schemas defined in MEMORY_SYSTEM.md.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MemoryEntryType(str, Enum):
    """Types of short-term memory entries."""
    
    TASK_STATE = "task_state"
    INTENT_SUMMARY = "intent_summary"
    CONTEXT_WINDOW = "context_window"
    COMPUTATION_TEMP = "computation_temp"
    PENDING_ACTION = "pending_action"


class ShortTermMemoryEntry(BaseModel):
    """
    Short-term memory entry (volatile, session-scoped).
    
    Follows the schema defined in MEMORY_SYSTEM.md Section 3.1.
    """
    
    stm_id: str = Field(
        ...,
        description="Unique entry identifier.",
    )
    
    session_id: str = Field(
        ...,
        description="Parent session identifier.",
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp.",
    )
    
    expires_at: datetime = Field(
        ...,
        description="Automatic expiration timestamp.",
    )
    
    entry_type: MemoryEntryType = Field(
        ...,
        description="Type of memory entry.",
    )
    
    content: dict[str, Any] = Field(
        ...,
        description="Type-specific content.",
    )
    
    # Metadata
    source: str = Field(
        default="system_derived",
        description="Origin: 'user_input', 'system_derived', 'execution_result'.",
    )
    
    ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,  # Max 24 hours
        description="Time-to-live in seconds.",
    )
    
    access_count: int = Field(
        default=0,
        ge=0,
        description="Read access counter.",
    )
    
    last_accessed: Optional[datetime] = Field(
        default=None,
        description="Last access timestamp.",
    )
    
    @field_validator("content")
    @classmethod
    def validate_content_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Enforce content size limit (10KB)."""
        import json
        content_str = json.dumps(v)
        if len(content_str) > 10240:
            raise ValueError("Content exceeds maximum size (10KB)")
        return v


class LongTermMemoryType(str, Enum):
    """Types of long-term memory entries."""
    
    PREFERENCE = "preference"
    APPROVAL_PATTERN = "approval_pattern"
    INTERACTION_SUMMARY = "interaction_summary"
    ERROR_RECOVERY = "error_recovery"


class LongTermMemoryEntry(BaseModel):
    """
    Long-term memory entry (persistent, vector-stored).
    
    Follows the schema defined in MEMORY_SYSTEM.md Section 3.2.
    
    NOTE: This is a simplified interface for the cloud backend.
    The actual vector storage is abstracted.
    """
    
    ltm_id: str = Field(
        ...,
        description="Unique entry identifier.",
    )
    
    user_id: str = Field(
        ...,
        description="User namespace for isolation.",
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp.",
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last modification timestamp.",
    )
    
    version: int = Field(
        default=1,
        ge=1,
        description="Entry version.",
    )
    
    memory_type: LongTermMemoryType = Field(
        ...,
        description="Type of long-term memory.",
    )
    
    content: dict[str, Any] = Field(
        ...,
        description="Type-specific content (MUST be abstracted).",
    )
    
    # Provenance (for audit)
    source_type: str = Field(
        default="user_approved",
        description="How this memory was created.",
    )
    
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in this memory.",
    )
    
    # Lifecycle
    status: str = Field(
        default="active",
        description="Status: 'active', 'deprecated', 'pending_deletion'.",
    )
    
    decay_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance decay score.",
    )


class LongTermMemoryQuery(BaseModel):
    """
    Query for long-term memory retrieval.
    
    Enforces purpose-bound access as required by MEMORY_SYSTEM.md.
    """
    
    query_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Semantic query text.",
    )
    
    purpose: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description="Explicit purpose for this query (REQUIRED for audit).",
    )
    
    memory_types: Optional[list[LongTermMemoryType]] = Field(
        default=None,
        description="Filter by memory type (optional).",
    )
    
    max_results: int = Field(
        default=5,
        ge=1,
        le=10,  # Hard limit as per MEMORY_SYSTEM.md
        description="Maximum results to return.",
    )
    
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold.",
    )
    
    requester: str = Field(
        default="planner",
        description="Who is making this query: 'planner' or 'executor'.",
    )
