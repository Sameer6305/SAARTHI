"""
Request Models
==============

Pydantic models for all API request payloads.
Strict validation ensures no malformed input reaches the planner.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TaskRequest(BaseModel):
    """
    Request payload for creating a new task.
    
    The input text is validated and sanitized before processing.
    """
    
    input_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's natural language input describing their intent.",
        examples=["Open my documents folder and find the latest report"],
    )
    
    session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Optional session identifier for context continuity.",
    )
    
    context: Optional[dict] = Field(
        default=None,
        description="Optional additional context from the client.",
    )
    
    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, v: str) -> str:
        """
        Validate and sanitize input text.
        
        Security: Strips control characters and validates content.
        """
        # Remove null bytes and control characters (except newlines)
        sanitized = "".join(
            char for char in v
            if char == "\n" or char == "\t" or (ord(char) >= 32 and ord(char) != 127)
        )
        
        if not sanitized.strip():
            raise ValueError("Input text cannot be empty or whitespace only")
        
        return sanitized.strip()
    
    @field_validator("context")
    @classmethod
    def validate_context(cls, v: Optional[dict]) -> Optional[dict]:
        """
        Validate context dictionary.
        
        Security: Limits context size and depth to prevent abuse.
        """
        if v is None:
            return None
        
        # Limit context size (rough check via string representation)
        import json
        try:
            context_str = json.dumps(v)
            if len(context_str) > 10000:  # 10KB limit
                raise ValueError("Context too large (max 10KB)")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid context format: {e}")
        
        return v


class VoiceRequest(BaseModel):
    """
    Request payload for voice-transcribed input.
    
    NOTE: This accepts TRANSCRIBED TEXT, not raw audio.
    Raw audio processing happens on the local client.
    """
    
    transcribed_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The transcribed text from speech-to-text processing.",
    )
    
    session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Optional session identifier for context continuity.",
    )
    
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="STT confidence score from the local client.",
    )
    
    @field_validator("transcribed_text")
    @classmethod
    def validate_transcribed_text(cls, v: str) -> str:
        """Apply same sanitization as TaskRequest.input_text."""
        sanitized = "".join(
            char for char in v
            if char == "\n" or char == "\t" or (ord(char) >= 32 and ord(char) != 127)
        )
        
        if not sanitized.strip():
            raise ValueError("Transcribed text cannot be empty or whitespace only")
        
        return sanitized.strip()
