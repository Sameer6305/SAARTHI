"""
SAARTHI Local Execution Client
==============================

Windows tray application for executing planner-approved actions.

SECURITY INVARIANTS:
- No shell execution
- No subprocess spawning
- No file modification or deletion
- No registry access
- No background monitoring
- All actions require explicit user permission

This client is the ONLY component that can perform real-world actions,
and it does so ONLY with user consent.
"""

__version__ = "1.0.0"
__author__ = "SAARTHI Team"

# Explicit list of what this client CAN do
ALLOWED_CAPABILITIES = [
    "open_browser_url",
    "play_media_file",
    "read_file_with_picker",
]

# Explicit list of what this client will NEVER do
FORBIDDEN_CAPABILITIES = [
    "shell_execution",
    "subprocess_spawning",
    "file_deletion",
    "file_modification",
    "registry_access",
    "keyboard_monitoring",
    "mouse_monitoring",
    "screen_capture",
    "microphone_access",
    "webcam_access",
    "network_scanning",
    "arbitrary_code_execution",
]
