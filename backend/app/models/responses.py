"""
Response Models
===============

Pydantic models for all API response payloads.
Ensures consistent, typed responses across all endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """
    A single step in the execution plan.
    
    This is the client-facing representation of a plan step.
    """
    
    step_id: str = Field(
        ...,
        description="Unique identifier for this step.",
    )
    
    step_number: int = Field(
        ...,
        ge=1,
        description="Sequential step number (1-indexed).",
    )
    
    description: str = Field(
        ...,
        max_length=500,
        description="Human-readable description of what this step does.",
    )
    
    step_type: str = Field(
        ...,
        description="Type of step: 'informational', 'tool_required', 'user_confirmation_required'.",
    )
    
    tool_id: Optional[str] = Field(
        default=None,
        description="Tool identifier if this step requires tool execution.",
    )
    
    risk_level: str = Field(
        default="LOW",
        description="Risk level: 'NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.",
    )
    
    requires_confirmation: bool = Field(
        default=False,
        description="Whether this step requires explicit user confirmation.",
    )


class TaskResponse(BaseModel):
    """
    Response returned when a new task is created.
    """
    
    task_id: str = Field(
        ...,
        description="Unique identifier for the created task.",
    )
    
    status: str = Field(
        ...,
        description="Current task status.",
    )
    
    message: str = Field(
        ...,
        description="Human-readable status message.",
    )
    
    created_at: datetime = Field(
        ...,
        description="Timestamp when the task was created.",
    )
    
    intent_summary: Optional[str] = Field(
        default=None,
        description="Abstracted summary of detected intent (no raw input).",
    )
    
    step_count: Optional[int] = Field(
        default=None,
        description="Number of steps in the generated plan.",
    )


class StatusResponse(BaseModel):
    """
    Response for task status queries.
    
    Provides detailed status information including plan steps if available.
    """
    
    task_id: str = Field(
        ...,
        description="The task identifier.",
    )
    
    status: str = Field(
        ...,
        description="Current task status.",
    )
    
    # Status flags for client decision-making
    planning_complete: bool = Field(
        default=False,
        description="Whether planning has finished.",
    )
    
    awaiting_confirmation: bool = Field(
        default=False,
        description="Whether task is waiting for user confirmation.",
    )
    
    ready_for_execution: bool = Field(
        default=False,
        description="Whether plan is ready to be sent to executor.",
    )
    
    failed: bool = Field(
        default=False,
        description="Whether the task has failed.",
    )
    
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure if failed=True.",
    )
    
    # Plan information (if available)
    plan_steps: Optional[list[PlanStep]] = Field(
        default=None,
        description="List of plan steps if planning is complete.",
    )
    
    current_step: Optional[int] = Field(
        default=None,
        description="Current step number (1-indexed) if execution has started.",
    )
    
    # Timestamps
    created_at: datetime = Field(
        ...,
        description="When the task was created.",
    )
    
    updated_at: datetime = Field(
        ...,
        description="When the task was last updated.",
    )


class HealthResponse(BaseModel):
    """
    Health check response.
    """
    
    status: str = Field(
        default="healthy",
        description="Overall health status.",
    )
    
    version: str = Field(
        ...,
        description="Application version.",
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Current server timestamp.",
    )
    
    components: dict[str, str] = Field(
        default_factory=dict,
        description="Health status of individual components.",
    )


class ErrorResponse(BaseModel):
    """
    Standard error response.
    
    Security: Never exposes stack traces or internal details.
    """
    
    error: str = Field(
        ...,
        description="Error type identifier.",
    )
    
    message: str = Field(
        ...,
        description="Human-readable error message.",
    )
    
    task_id: Optional[str] = Field(
        default=None,
        description="Associated task ID if applicable.",
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred.",
    )
    
    # Correlation ID for log tracing (no internal details)
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for support requests.",
    )
