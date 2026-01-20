"""
Action Models
=============

Models for executable actions sent to the local client.
These are the FINAL output format that the executor expects.

CRITICAL: These must match the schema in local_client/schema.py exactly.
"""

import hashlib
import hmac
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings


class ActionType(str, Enum):
    """
    Allowlisted action types.
    
    SECURITY: Only these action types can be sent to the executor.
    Must match local_client/saarthi_executor/schema.py EXACTLY.
    """
    
    OPEN_BROWSER_URL = "open_browser_url"
    PLAY_MEDIA_FILE = "play_media_file"
    READ_FILE_WITH_PICKER = "read_file_with_picker"


class ActionRiskLevel(str, Enum):
    """Risk level for user awareness."""
    
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionParameters(BaseModel):
    """
    Parameters for an action.
    
    Different action types use different fields.
    All fields are optional to support different action types.
    """
    
    # For open_browser_url
    url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="URL to open (http/https only)"
    )
    
    # For play_media_file
    media_type: Optional[str] = Field(
        default=None,
        description="Type of media: audio, video, image"
    )
    
    # For read_file_with_picker
    file_types: Optional[list[str]] = Field(
        default=None,
        max_length=10,
        description="Allowed file extensions"
    )
    
    read_mode: Optional[str] = Field(
        default=None,
        description="How to read: text, binary, metadata"
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Ensure URL uses safe protocols only."""
        if v is None:
            return None
        
        v = v.strip()
        
        # SECURITY: Only allow http/https
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must use http:// or https://")
        
        # Block dangerous patterns
        dangerous_patterns = [
            "javascript:",
            "data:",
            "file:",
            "vbscript:",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ]
        
        lower_url = v.lower()
        for pattern in dangerous_patterns:
            if pattern in lower_url:
                raise ValueError(f"URL contains forbidden pattern: {pattern}")
        
        return v
    
    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate media type."""
        if v is None:
            return None
        
        allowed = ["audio", "video", "image"]
        if v.lower() not in allowed:
            raise ValueError(f"media_type must be one of: {allowed}")
        
        return v.lower()


class ExecutableAction(BaseModel):
    """
    An executable action ready for the local client.
    
    This is the EXACT format expected by the executor.
    Matches local_client/saarthi_executor/schema.py
    """
    
    action_id: str = Field(
        ...,
        pattern=r"^act_[a-f0-9]{16,32}$",
        description="Unique action identifier"
    )
    
    action_type: ActionType = Field(
        ...,
        description="Type of action (from allowlist)"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When action was created"
    )
    
    signature: str = Field(
        ...,
        min_length=64,
        max_length=128,
        description="Cryptographic signature"
    )
    
    description: str = Field(
        ...,
        max_length=500,
        description="Human-readable description for user consent"
    )
    
    risk_level: ActionRiskLevel = Field(
        default=ActionRiskLevel.LOW,
        description="Risk level for user awareness"
    )
    
    parameters: ActionParameters = Field(
        default_factory=ActionParameters,
        description="Action-specific parameters"
    )
    
    # Metadata for tracking
    task_id: str = Field(
        ...,
        description="Associated task ID"
    )
    
    step_id: Optional[str] = Field(
        default=None,
        description="Associated plan step ID (if from plan)"
    )
    
    def to_executor_format(self) -> dict:
        """
        Convert to the exact format expected by executor.
        
        This strips internal fields and formats for transmission.
        """
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "parameters": {
                k: v for k, v in self.parameters.model_dump().items()
                if v is not None
            },
        }


class ActionResponse(BaseModel):
    """Response containing executable actions for the client."""
    
    task_id: str = Field(
        ...,
        description="The task these actions belong to"
    )
    
    execution_status: str = Field(
        ...,
        description="Current execution status"
    )
    
    actions: list[ExecutableAction] = Field(
        default_factory=list,
        description="List of actions to execute"
    )
    
    total_actions: int = Field(
        default=0,
        description="Total number of actions"
    )
    
    current_action_index: int = Field(
        default=0,
        description="Index of current action (0-based)"
    )
    
    requires_confirmation: bool = Field(
        default=False,
        description="Whether user confirmation is needed"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When response was generated"
    )
    
    expires_at: datetime = Field(
        ...,
        description="When these actions expire (must execute before)"
    )


def generate_action_signature(action_id: str, action_type: str, timestamp: str) -> str:
    """
    Generate a signature for action verification.
    
    In production, this would use proper HMAC with a shared secret.
    For now, uses a deterministic hash for testing.
    """
    settings = get_settings()
    
    # Create message to sign
    message = f"{action_id}:{action_type}:{timestamp}"
    
    # Use secret key for HMAC (or fallback for dev)
    secret = settings.secret_key.encode() if settings.secret_key else b"dev-secret-key"
    
    # Generate HMAC-SHA256
    signature = hmac.new(
        secret,
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature
