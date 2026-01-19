"""
Structured Logging Configuration
================================

Provides structured, auditable logging for all SAARTHI components.
All logs include task_id, component, and event for traceability.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import get_settings


def add_app_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add application-level context to all log entries."""
    settings = get_settings()
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    event_dict["environment"] = settings.environment
    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging for the application.
    
    In production (log_format=json): Outputs JSON lines for log aggregation.
    In development (log_format=console): Outputs human-readable colored logs.
    """
    settings = get_settings()
    
    # Shared processors for all log entries
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]
    
    if settings.log_format == "json":
        # Production: JSON output
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger bound to a specific component.
    
    Args:
        component: The component name (e.g., "planner", "memory", "api")
    
    Returns:
        A structured logger with the component context bound.
    """
    return structlog.get_logger(component=component)
