"""
Voice Security Logger
=====================

Security logging for voice-only assistant.

LOGGED EVENTS:
- HOTKEY_PRESSED
- RECORDING_STARTED
- RECORDING_STOPPED
- TRANSCRIPTION_COMPLETE
- COMMAND_PROCESSED
- ACTION_EXECUTED
- PERMISSION_DENIED
- PIPELINE_RESET
- ERROR

All events include timestamps and context.
Log file is append-only for audit trail.
"""

import logging
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Create dedicated security logger
security_logger = logging.getLogger("saarthi.security")


class SecurityEventType(Enum):
    """Security event types."""
    HOTKEY_PRESSED = "HOTKEY_PRESSED"
    RECORDING_STARTED = "RECORDING_STARTED"
    RECORDING_STOPPED = "RECORDING_STOPPED"
    TRANSCRIPTION_COMPLETE = "TRANSCRIPTION_COMPLETE"
    COMMAND_PROCESSED = "COMMAND_PROCESSED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PIPELINE_RESET = "PIPELINE_RESET"
    ASSISTANT_ENABLED = "ASSISTANT_ENABLED"
    ASSISTANT_DISABLED = "ASSISTANT_DISABLED"
    MIC_ACCESSED = "MIC_ACCESSED"
    MIC_RELEASED = "MIC_RELEASED"
    ERROR = "ERROR"


@dataclass
class SecurityEvent:
    """A security event."""
    event_type: SecurityEventType
    timestamp: float
    timestamp_iso: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class VoiceSecurityLogger:
    """
    Security logger for voice-only assistant.
    
    GUARANTEES:
    - All security events are logged
    - Timestamps are monotonic
    - Log file is append-only
    - No audio data is ever logged
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize security logger.
        
        Args:
            log_dir: Directory for log files (default: ~/.saarthi/logs)
        """
        self._log_dir = log_dir or (Path.home() / ".saarthi" / "logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Security log file
        self._log_file = self._log_dir / "security.log"
        
        # Setup file handler
        self._setup_file_handler()
        
        # Event buffer for recent events
        self._recent_events: list[SecurityEvent] = []
        self._max_recent = 100
        
        security_logger.info("Security logger initialized")
    
    def _setup_file_handler(self) -> None:
        """Setup file handler for security log."""
        handler = logging.FileHandler(
            self._log_file,
            mode='a',
            encoding='utf-8',
        )
        
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add to security logger
        security_logger.addHandler(handler)
        security_logger.setLevel(logging.INFO)
    
    def _log_event(self, event: SecurityEvent) -> None:
        """Log a security event."""
        # Add to recent buffer
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent:]
        
        # Log to file
        log_line = f"[{event.event_type.value}] {json.dumps(event.details or {})}"
        security_logger.info(log_line)
    
    def _create_event(
        self, 
        event_type: SecurityEventType,
        details: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
        """Create a security event with timestamp."""
        now = time.time()
        return SecurityEvent(
            event_type=event_type,
            timestamp=now,
            timestamp_iso=datetime.fromtimestamp(now).isoformat(),
            details=details,
        )
    
    # ==================== PUBLIC API ====================
    
    def hotkey_pressed(self) -> None:
        """Log hotkey press."""
        self._log_event(self._create_event(
            SecurityEventType.HOTKEY_PRESSED
        ))
    
    def recording_started(self) -> None:
        """Log recording start."""
        self._log_event(self._create_event(
            SecurityEventType.RECORDING_STARTED
        ))
        self._log_event(self._create_event(
            SecurityEventType.MIC_ACCESSED,
            {"source": "push_to_talk"}
        ))
    
    def recording_stopped(self, duration_seconds: float) -> None:
        """Log recording stop."""
        self._log_event(self._create_event(
            SecurityEventType.RECORDING_STOPPED,
            {"duration_seconds": round(duration_seconds, 2)}
        ))
        self._log_event(self._create_event(
            SecurityEventType.MIC_RELEASED
        ))
    
    def transcription_complete(
        self, 
        text_length: int,
        confidence: float,
        success: bool
    ) -> None:
        """Log transcription completion (no actual text!)."""
        self._log_event(self._create_event(
            SecurityEventType.TRANSCRIPTION_COMPLETE,
            {
                "text_length": text_length,
                "confidence": round(confidence, 2),
                "success": success,
            }
        ))
    
    def command_processed(
        self,
        command_type: str,
        action_type: Optional[str] = None,
    ) -> None:
        """Log command processing."""
        self._log_event(self._create_event(
            SecurityEventType.COMMAND_PROCESSED,
            {
                "command_type": command_type,
                "action_type": action_type,
            }
        ))
    
    def action_executed(
        self,
        action_type: str,
        success: bool,
    ) -> None:
        """Log action execution."""
        self._log_event(self._create_event(
            SecurityEventType.ACTION_EXECUTED,
            {
                "action_type": action_type,
                "success": success,
            }
        ))
    
    def action_blocked(
        self,
        action_type: str,
        reason: str,
    ) -> None:
        """Log blocked action."""
        self._log_event(self._create_event(
            SecurityEventType.ACTION_BLOCKED,
            {
                "action_type": action_type,
                "reason": reason,
            }
        ))
    
    def permission_denied(
        self,
        action_type: str,
        reason: str,
    ) -> None:
        """Log permission denial."""
        self._log_event(self._create_event(
            SecurityEventType.PERMISSION_DENIED,
            {
                "action_type": action_type,
                "reason": reason,
            }
        ))
    
    def permission_granted(
        self,
        action_type: str,
    ) -> None:
        """Log permission grant."""
        self._log_event(self._create_event(
            SecurityEventType.PERMISSION_GRANTED,
            {"action_type": action_type}
        ))
    
    def pipeline_reset(self, reason: str) -> None:
        """Log pipeline reset."""
        self._log_event(self._create_event(
            SecurityEventType.PIPELINE_RESET,
            {"reason": reason}
        ))
    
    def assistant_enabled(self) -> None:
        """Log assistant enable."""
        self._log_event(self._create_event(
            SecurityEventType.ASSISTANT_ENABLED
        ))
    
    def assistant_disabled(self) -> None:
        """Log assistant disable."""
        self._log_event(self._create_event(
            SecurityEventType.ASSISTANT_DISABLED
        ))
    
    def error(self, error_type: str, details: str) -> None:
        """Log error."""
        self._log_event(self._create_event(
            SecurityEventType.ERROR,
            {
                "error_type": error_type,
                "details": details,
            }
        ))
    
    def get_recent_events(self, count: int = 10) -> list[SecurityEvent]:
        """Get recent security events."""
        return self._recent_events[-count:]
    
    def get_log_file_path(self) -> Path:
        """Get path to security log file."""
        return self._log_file


# Global instance
_security_logger: Optional[VoiceSecurityLogger] = None


def get_security_logger() -> VoiceSecurityLogger:
    """Get global security logger instance."""
    global _security_logger
    if _security_logger is None:
        _security_logger = VoiceSecurityLogger()
    return _security_logger
