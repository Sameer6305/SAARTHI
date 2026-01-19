"""
Action JSON Schema
==================

Defines the EXACT schema for actions the cloud can send.
Any deviation results in immediate rejection.

SECURITY: Schema validation is the FIRST line of defense.
"""

from typing import Any

# =============================================================================
# ACTION JSON SCHEMA (JSON Schema Draft 7)
# =============================================================================

ACTION_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SAARTHI Action",
    "description": "Schema for actions sent from cloud planner to local executor",
    "type": "object",
    "required": ["action_id", "action_type", "timestamp", "signature"],
    "additionalProperties": False,  # CRITICAL: Reject unknown fields
    
    "properties": {
        "action_id": {
            "type": "string",
            "pattern": "^act_[a-f0-9]{16,32}$",
            "description": "Unique action identifier"
        },
        
        "action_type": {
            "type": "string",
            "enum": [
                "open_browser_url",
                "play_media_file", 
                "read_file_with_picker"
            ],
            "description": "Type of action (ALLOWLIST ONLY)"
        },
        
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp when action was created"
        },
        
        "signature": {
            "type": "string",
            "minLength": 64,
            "maxLength": 128,
            "description": "Cryptographic signature for verification"
        },
        
        "description": {
            "type": "string",
            "maxLength": 500,
            "description": "Human-readable description for user consent"
        },
        
        "risk_level": {
            "type": "string",
            "enum": ["NONE", "LOW", "MEDIUM", "HIGH"],
            "default": "LOW",
            "description": "Risk level for user awareness"
        },
        
        "parameters": {
            "type": "object",
            "description": "Action-specific parameters",
            "additionalProperties": False,
            
            "properties": {
                # For open_browser_url
                "url": {
                    "type": "string",
                    "format": "uri",
                    "pattern": "^https?://",
                    "maxLength": 2048,
                    "description": "URL to open (http/https only)"
                },
                
                # For play_media_file
                "media_type": {
                    "type": "string",
                    "enum": ["audio", "video", "image"],
                    "description": "Type of media to play"
                },
                
                # For read_file_with_picker
                "file_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^\\.[a-zA-Z0-9]{1,10}$"
                    },
                    "maxItems": 10,
                    "description": "Allowed file extensions for picker"
                },
                
                "purpose": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Why this data is being accessed"
                }
            }
        },
        
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "task_id": {
                    "type": "string",
                    "pattern": "^task_[a-f0-9]{16}$"
                },
                "plan_id": {
                    "type": "string", 
                    "pattern": "^plan_[a-f0-9]{16}$"
                },
                "step_number": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100
                }
            }
        }
    }
}


# =============================================================================
# ACTION-SPECIFIC SCHEMA RULES
# =============================================================================

ACTION_PARAMETER_REQUIREMENTS: dict[str, list[str]] = {
    "open_browser_url": ["url"],
    "play_media_file": ["media_type"],
    "read_file_with_picker": ["file_types", "purpose"],
}


# =============================================================================
# REJECTION RULES
# =============================================================================

REJECTION_RULES: list[dict[str, str]] = [
    {
        "rule": "UNKNOWN_ACTION_TYPE",
        "description": "Action type not in allowlist",
        "response": "Reject immediately, log as security event"
    },
    {
        "rule": "SCHEMA_VIOLATION",
        "description": "JSON does not match schema",
        "response": "Reject immediately, do not process"
    },
    {
        "rule": "MISSING_SIGNATURE",
        "description": "No cryptographic signature present",
        "response": "Reject as potentially tampered"
    },
    {
        "rule": "TIMESTAMP_STALE",
        "description": "Action timestamp older than 5 minutes",
        "response": "Reject as potential replay attack"
    },
    {
        "rule": "MALFORMED_URL",
        "description": "URL contains suspicious patterns",
        "response": "Reject, present warning to user"
    },
    {
        "rule": "EXTRA_FIELDS",
        "description": "JSON contains fields not in schema",
        "response": "Reject as potentially malicious"
    },
    {
        "rule": "FORBIDDEN_PROTOCOL",
        "description": "URL uses non-http/https protocol",
        "response": "Reject immediately (file://, javascript:, etc.)"
    },
]


# =============================================================================
# URL VALIDATION RULES
# =============================================================================

FORBIDDEN_URL_PATTERNS: list[str] = [
    "javascript:",
    "file://",
    "data:",
    "vbscript:",
    "about:",
    "chrome://",
    "edge://",
    "localhost",  # Prevent local network access
    "127.0.0.1",
    "0.0.0.0",
    "192.168.",
    "10.",
    "172.16.",
]

ALLOWED_URL_SCHEMES: list[str] = ["http://", "https://"]
