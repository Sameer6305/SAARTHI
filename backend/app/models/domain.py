"""
Domain Models
=============

Internal domain models representing core business logic entities.
These are not exposed directly via API but drive internal processing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Possible states of a task throughout its lifecycle."""
    
    # Initial states
    CREATED = "created"
    ANALYZING = "analyzing"
    
    # Planning states
    PLANNING = "planning"
    PLANNING_COMPLETE = "planning_complete"
    PLANNING_FAILED = "planning_failed"
    
    # Confirmation states
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    
    # Execution states (tracked but execution happens on client)
    READY_FOR_EXECUTION = "ready_for_execution"
    EXECUTING = "executing"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"
    
    # Terminal states
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """Risk level classification for plan steps."""
    
    NONE = "NONE"          # Pure informational, no side effects
    LOW = "LOW"            # Read-only operations
    MEDIUM = "MEDIUM"      # Reversible modifications
    HIGH = "HIGH"          # Significant changes, hard to reverse
    CRITICAL = "CRITICAL"  # Destructive or security-sensitive


class StepType(str, Enum):
    """Type of plan step."""
    
    INFORMATIONAL = "informational"
    TOOL_REQUIRED = "tool_required"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"


class IntentAnalysis(BaseModel):
    """
    Result of intent analysis on user input.
    
    IMPORTANT: This stores ABSTRACTED intent, not raw input.
    """
    
    intent_category: str = Field(
        ...,
        description="High-level category of intent (e.g., 'file_operation', 'app_control').",
    )
    
    intent_summary: str = Field(
        ...,
        max_length=200,
        description="Abstracted summary of intent (NO raw user text).",
    )
    
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in intent classification.",
    )
    
    detected_entities: list[str] = Field(
        default_factory=list,
        description="Abstracted entities detected (e.g., 'document_folder', not actual path).",
    )
    
    # Specific parameters extracted for action execution
    target_url: Optional[str] = Field(
        default=None,
        description="Target URL for browser actions (safe URLs only).",
    )
    
    requires_tools: list[str] = Field(
        default_factory=list,
        description="Tool categories likely needed.",
    )
    
    estimated_risk: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Estimated overall risk level.",
    )
    
    clarification_needed: bool = Field(
        default=False,
        description="Whether clarification is needed from user.",
    )
    
    clarification_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask if clarification needed.",
    )


class PlanStepDomain(BaseModel):
    """
    Internal representation of a plan step.
    
    This includes all metadata needed for execution and audit.
    """
    
    step_id: str = Field(
        ...,
        description="Unique step identifier.",
    )
    
    step_number: int = Field(
        ...,
        ge=1,
        description="Sequential step number.",
    )
    
    step_type: StepType = Field(
        ...,
        description="Type of this step.",
    )
    
    description: str = Field(
        ...,
        max_length=500,
        description="Human-readable step description.",
    )
    
    tool_id: Optional[str] = Field(
        default=None,
        description="Tool to invoke (if tool_required).",
    )
    
    tool_parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Parameters for tool invocation.",
    )
    
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Risk level of this step.",
    )
    
    requires_confirmation: bool = Field(
        default=False,
        description="Whether explicit confirmation is required.",
    )
    
    preconditions: list[str] = Field(
        default_factory=list,
        description="Step IDs that must complete before this step.",
    )
    
    on_failure: str = Field(
        default="abort",
        description="Failure handling: 'abort', 'skip', 'retry'.",
    )
    
    max_retries: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Maximum retry attempts.",
    )
    
    timeout_seconds: Optional[float] = Field(
        default=None,
        description="Execution timeout for this step.",
    )


class Plan(BaseModel):
    """
    A complete execution plan generated by the Planner.
    
    This is the structured output that gets sent to the Executor.
    """
    
    plan_id: str = Field(
        ...,
        description="Unique plan identifier.",
    )
    
    task_id: str = Field(
        ...,
        description="Associated task identifier.",
    )
    
    version: int = Field(
        default=1,
        ge=1,
        description="Plan version (incremented on modifications).",
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this plan was created.",
    )
    
    intent_summary: str = Field(
        ...,
        max_length=200,
        description="Abstracted intent summary (for audit).",
    )
    
    steps: list[PlanStepDomain] = Field(
        ...,
        min_length=1,
        description="Ordered list of plan steps.",
    )
    
    total_steps: int = Field(
        ...,
        ge=1,
        description="Total number of steps.",
    )
    
    estimated_risk: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Overall plan risk level (max of step risks).",
    )
    
    requires_any_confirmation: bool = Field(
        default=False,
        description="Whether any step requires confirmation.",
    )
    
    # Planner metadata (for audit)
    planner_version: str = Field(
        default="1.0.0",
        description="Version of planner that generated this plan.",
    )
    
    generation_time_ms: Optional[float] = Field(
        default=None,
        description="Time taken to generate plan (milliseconds).",
    )


class TaskState(BaseModel):
    """
    Complete state of a task.
    
    This is the authoritative state object stored in memory.
    """
    
    task_id: str = Field(
        ...,
        description="Unique task identifier.",
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier if provided.",
    )
    
    status: TaskStatus = Field(
        default=TaskStatus.CREATED,
        description="Current task status.",
    )
    
    # Intent analysis (abstracted)
    intent: Optional[IntentAnalysis] = Field(
        default=None,
        description="Analyzed intent (abstracted, no raw input).",
    )
    
    # Generated plan
    plan: Optional[Plan] = Field(
        default=None,
        description="Generated execution plan.",
    )
    
    # Execution tracking
    current_step_index: int = Field(
        default=0,
        ge=0,
        description="Current step index (0-based).",
    )
    
    completed_steps: list[str] = Field(
        default_factory=list,
        description="List of completed step IDs.",
    )
    
    failed_step: Optional[str] = Field(
        default=None,
        description="Step ID that failed (if any).",
    )
    
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure (if failed).",
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Task creation timestamp.",
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp.",
    )
    
    # Audit
    status_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="History of status changes for audit.",
    )
    
    def update_status(self, new_status: TaskStatus, reason: Optional[str] = None) -> None:
        """Update status with audit trail."""
        self.status_history.append({
            "from_status": self.status.value,
            "to_status": new_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
        })
        self.status = new_status
        self.updated_at = datetime.utcnow()
