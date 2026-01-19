"""
SAARTHI Cloud Backend
=====================

A privacy-preserving, Planner-Executor based AI assistant backend.

This package implements the CLOUD SIDE ONLY of SAARTHI.
All OS-level execution happens on the LOCAL CLIENT.

Security Invariants:
- No OS commands
- No subprocess calls  
- No dynamic code execution
- No filesystem writes (except /tmp if needed)
- No tool execution logic
"""

__version__ = "1.0.0"
__author__ = "SAARTHI Team"
