"""
Action Validator
================

Validates incoming action JSON against strict schema and security rules.

SECURITY: This is the FIRST line of defense.
- Schema validation
- Signature verification
- Timestamp freshness
- URL safety checks
- Parameter validation
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from saarthi_executor.schema import (
    ACTION_SCHEMA,
    ACTION_PARAMETER_REQUIREMENTS,
    FORBIDDEN_URL_PATTERNS,
    ALLOWED_URL_SCHEMES,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of action validation."""
    
    is_valid: bool
    action_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_rule: Optional[str] = None
    warnings: list[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ActionValidator:
    """
    Validates action JSON with strict security checks.
    
    SECURITY INVARIANTS:
    - Unknown action types are REJECTED
    - Schema violations are REJECTED
    - Missing signatures are REJECTED
    - Stale timestamps are REJECTED
    - Unsafe URLs are REJECTED
    - Extra fields are REJECTED
    """
    
    # Maximum age for action timestamps (prevents replay attacks)
    MAX_ACTION_AGE_SECONDS: int = 300  # 5 minutes
    
    def __init__(self):
        """Initialize the validator with compiled schema."""
        self._schema_validator = Draft7Validator(ACTION_SCHEMA)
    
    def validate(self, action_json: dict) -> ValidationResult:
        """
        Validate an action JSON completely.
        
        Returns ValidationResult with is_valid=False if ANY check fails.
        """
        # Step 1: Schema validation
        schema_result = self._validate_schema(action_json)
        if not schema_result.is_valid:
            return schema_result
        
        action_id = action_json.get("action_id", "unknown")
        
        # Step 2: Action type allowlist
        type_result = self._validate_action_type(action_json, action_id)
        if not type_result.is_valid:
            return type_result
        
        # Step 3: Timestamp freshness
        timestamp_result = self._validate_timestamp(action_json, action_id)
        if not timestamp_result.is_valid:
            return timestamp_result
        
        # Step 4: Signature presence (actual verification would need crypto keys)
        sig_result = self._validate_signature(action_json, action_id)
        if not sig_result.is_valid:
            return sig_result
        
        # Step 5: Action-specific parameter validation
        param_result = self._validate_parameters(action_json, action_id)
        if not param_result.is_valid:
            return param_result
        
        # Step 6: URL safety (if applicable)
        if action_json.get("action_type") == "open_browser_url":
            url_result = self._validate_url_safety(action_json, action_id)
            if not url_result.is_valid:
                return url_result
        
        logger.info(
            "Action validation passed",
            extra={
                "action_id": action_id,
                "action_type": action_json.get("action_type"),
            }
        )
        
        return ValidationResult(
            is_valid=True,
            action_id=action_id,
        )
    
    def _validate_schema(self, action_json: dict) -> ValidationResult:
        """Validate against JSON schema."""
        errors = list(self._schema_validator.iter_errors(action_json))
        
        if errors:
            # Get first error for user message
            first_error = errors[0]
            
            logger.warning(
                "Schema validation failed",
                extra={
                    "error_count": len(errors),
                    "first_error": str(first_error.message),
                    "path": list(first_error.path),
                }
            )
            
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"Schema validation failed: {first_error.message}",
                rejection_rule="SCHEMA_VIOLATION",
            )
        
        return ValidationResult(is_valid=True)
    
    def _validate_action_type(
        self, 
        action_json: dict, 
        action_id: str
    ) -> ValidationResult:
        """Validate action type is in allowlist."""
        action_type = action_json.get("action_type")
        
        allowed_types = [
            "open_browser_url",
            "play_media_file",
            "read_file_with_picker",
        ]
        
        if action_type not in allowed_types:
            logger.error(
                "SECURITY: Unknown action type rejected",
                extra={
                    "action_id": action_id,
                    "action_type": action_type,
                }
            )
            
            return ValidationResult(
                is_valid=False,
                action_id=action_id,
                rejection_reason=f"Unknown action type: {action_type}",
                rejection_rule="UNKNOWN_ACTION_TYPE",
            )
        
        return ValidationResult(is_valid=True, action_id=action_id)
    
    def _validate_timestamp(
        self, 
        action_json: dict, 
        action_id: str
    ) -> ValidationResult:
        """Validate timestamp is recent (prevents replay attacks)."""
        timestamp_str = action_json.get("timestamp")
        
        try:
            # Parse ISO 8601 timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            
            # Ensure timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age = (now - timestamp).total_seconds()
            
            if age > self.MAX_ACTION_AGE_SECONDS:
                logger.warning(
                    "SECURITY: Stale action rejected (potential replay)",
                    extra={
                        "action_id": action_id,
                        "age_seconds": age,
                        "max_age": self.MAX_ACTION_AGE_SECONDS,
                    }
                )
                
                return ValidationResult(
                    is_valid=False,
                    action_id=action_id,
                    rejection_reason=f"Action too old ({int(age)} seconds)",
                    rejection_rule="TIMESTAMP_STALE",
                )
            
            if age < -60:  # Allow 1 minute clock skew for future timestamps
                logger.warning(
                    "SECURITY: Future timestamp rejected",
                    extra={
                        "action_id": action_id,
                        "age_seconds": age,
                    }
                )
                
                return ValidationResult(
                    is_valid=False,
                    action_id=action_id,
                    rejection_reason="Action timestamp is in the future",
                    rejection_rule="TIMESTAMP_FUTURE",
                )
            
        except (ValueError, TypeError) as e:
            return ValidationResult(
                is_valid=False,
                action_id=action_id,
                rejection_reason=f"Invalid timestamp format: {e}",
                rejection_rule="TIMESTAMP_INVALID",
            )
        
        return ValidationResult(is_valid=True, action_id=action_id)
    
    def _validate_signature(
        self, 
        action_json: dict, 
        action_id: str
    ) -> ValidationResult:
        """Validate signature is present and well-formed."""
        signature = action_json.get("signature")
        
        if not signature:
            logger.error(
                "SECURITY: Missing signature rejected",
                extra={"action_id": action_id}
            )
            
            return ValidationResult(
                is_valid=False,
                action_id=action_id,
                rejection_reason="Missing cryptographic signature",
                rejection_rule="MISSING_SIGNATURE",
            )
        
        # Basic format check (actual verification needs crypto keys)
        if not re.match(r"^[a-fA-F0-9]{64,128}$", signature):
            return ValidationResult(
                is_valid=False,
                action_id=action_id,
                rejection_reason="Invalid signature format",
                rejection_rule="INVALID_SIGNATURE",
            )
        
        # NOTE: In production, actual cryptographic verification would happen here
        # using Ed25519 or similar, verifying against cloud's public key
        
        return ValidationResult(is_valid=True, action_id=action_id)
    
    def _validate_parameters(
        self, 
        action_json: dict, 
        action_id: str
    ) -> ValidationResult:
        """Validate action-specific parameters are present."""
        action_type = action_json.get("action_type")
        parameters = action_json.get("parameters", {})
        
        required_params = ACTION_PARAMETER_REQUIREMENTS.get(action_type, [])
        
        for param in required_params:
            if param not in parameters:
                return ValidationResult(
                    is_valid=False,
                    action_id=action_id,
                    rejection_reason=f"Missing required parameter: {param}",
                    rejection_rule="MISSING_PARAMETER",
                )
        
        return ValidationResult(is_valid=True, action_id=action_id)
    
    def _validate_url_safety(
        self, 
        action_json: dict, 
        action_id: str
    ) -> ValidationResult:
        """Validate URL is safe to open."""
        parameters = action_json.get("parameters", {})
        url = parameters.get("url", "")
        
        # Check scheme
        if not any(url.lower().startswith(scheme) for scheme in ALLOWED_URL_SCHEMES):
            logger.error(
                "SECURITY: Forbidden URL scheme rejected",
                extra={
                    "action_id": action_id,
                    "url_start": url[:50],
                }
            )
            
            return ValidationResult(
                is_valid=False,
                action_id=action_id,
                rejection_reason="URL must use http:// or https://",
                rejection_rule="FORBIDDEN_PROTOCOL",
            )
        
        # Check for forbidden patterns
        url_lower = url.lower()
        for pattern in FORBIDDEN_URL_PATTERNS:
            if pattern in url_lower:
                logger.error(
                    "SECURITY: Forbidden URL pattern rejected",
                    extra={
                        "action_id": action_id,
                        "pattern": pattern,
                    }
                )
                
                return ValidationResult(
                    is_valid=False,
                    action_id=action_id,
                    rejection_reason=f"URL contains forbidden pattern: {pattern}",
                    rejection_rule="MALFORMED_URL",
                )
        
        return ValidationResult(is_valid=True, action_id=action_id)
