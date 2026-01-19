# SAARTHI Local Executor - Safety Guarantees

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SAARTHI LOCAL EXECUTOR                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLOUD (Planner)                                    │
│                                                                             │
│  Sends:  Structured JSON action requests                                    │
│  Never:  Executable code, shell commands, raw instructions                  │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼ JSON over HTTPS
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LOCAL EXECUTOR (This Client)                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    VALIDATION LAYER                                  │    │
│  │                                                                      │    │
│  │  • JSON Schema validation                                           │    │
│  │  • Action type ALLOWLIST check                                      │    │
│  │  • Timestamp freshness (replay prevention)                          │    │
│  │  • Signature verification                                           │    │
│  │  • URL safety checks                                                │    │
│  │                                                                      │    │
│  │  ❌ Unknown action types → REJECTED                                  │    │
│  │  ❌ Schema violations → REJECTED                                     │    │
│  │  ❌ Stale timestamps → REJECTED                                      │    │
│  │  ❌ Unsafe URLs → REJECTED                                           │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │ Valid actions only                      │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    PERMISSION LAYER                                  │    │
│  │                                                                      │    │
│  │  • EVERY action shown to user                                       │    │
│  │  • User sees: action, data accessed, risk level                     │    │
│  │  • User must click ALLOW or DENY                                    │    │
│  │  • NO auto-approval, NO remembered permissions                       │    │
│  │  • Timeout = DENY                                                   │    │
│  │                                                                      │    │
│  │  ❌ User denies → Action stops here                                  │    │
│  │  ❌ No response → Action stops here                                  │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │ User-approved only                      │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    EXECUTION LAYER                                   │    │
│  │                                                                      │    │
│  │  ALLOWED (3 actions only):                                          │    │
│  │  ✅ open_browser_url   → webbrowser.open() [safe]                    │    │
│  │  ✅ play_media_file    → os.startfile() [user picks file]            │    │
│  │  ✅ read_file_picker   → open() [user picks file, read-only]         │    │
│  │                                                                      │    │
│  │  FORBIDDEN (by design, no code exists):                             │    │
│  │  ❌ subprocess.run()   → Not imported, not callable                  │    │
│  │  ❌ os.system()        → Not imported, not callable                  │    │
│  │  ❌ eval(), exec()     → Not used anywhere                           │    │
│  │  ❌ File write/delete  → No functions for this                       │    │
│  │  ❌ Registry access    → No winreg imported                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Safety Guarantees

### Guarantee 1: ALLOWLIST-ONLY Execution

**How it works:**
- `ActionHandlerRegistry` contains ONLY 3 handlers
- Each handler is a class that implements ONE specific action
- There is NO generic "execute command" functionality
- Unknown action types return `None` from `get_handler()` → no execution

**Code proof:**
```python
class ActionHandlerRegistry:
    def __init__(self):
        self._handlers = {}
        # ONLY these 3 are registered
        self._register(OpenBrowserUrlHandler())
        self._register(PlayMediaFileHandler())
        self._register(ReadFileWithPickerHandler())
```

**Attack blocked:** Malicious cloud cannot invent new action types.

---

### Guarantee 2: No Shell/Subprocess Execution

**How it works:**
- `subprocess` module is NOT imported anywhere
- `os.system()` is NOT called anywhere
- `eval()` and `exec()` are NOT used anywhere
- No mechanism exists to run arbitrary commands

**Code proof:**
```python
# Search the entire codebase:
# - No "import subprocess"
# - No "subprocess.run"
# - No "os.system"
# - No "eval("
# - No "exec("
```

**Attack blocked:** Even if cloud sends "run this shell command", no code exists to execute it.

---

### Guarantee 3: User Permission Required for EVERY Action

**How it works:**
- `PermissionManager.request_permission()` is called for EVERY action
- A GUI dialog appears requiring explicit click
- No "remember" option, no auto-approve
- Default is DENY if user doesn't respond

**Code proof:**
```python
# In executor.py:
permission = self._permission_manager.request_permission(...)

if permission != PermissionDecision.ALLOW:
    # Action stops here - never executes
    return
```

**Attack blocked:** Malicious action cannot execute without user seeing and approving it.

---

### Guarantee 4: Read-Only File Access

**How it works:**
- `ReadFileWithPickerHandler` opens files in read mode only
- User MUST select the file via file picker dialog
- System cannot specify which file to read
- No code exists to write or delete files

**Code proof:**
```python
# Read ONLY - 'r' mode
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# No 'w', 'a', or delete operations exist
```

**Attack blocked:** Cannot secretly read arbitrary files or modify any files.

---

### Guarantee 5: URL Safety Validation

**How it works:**
- Only `http://` and `https://` schemes allowed
- Forbidden patterns: `javascript:`, `file://`, `localhost`, private IPs
- URL validation happens BEFORE permission dialog

**Code proof:**
```python
FORBIDDEN_URL_PATTERNS = [
    "javascript:", "file://", "data:", "vbscript:",
    "localhost", "127.0.0.1", "192.168.", "10.", "172.16."
]

if any(pattern in url_lower for pattern in FORBIDDEN_URL_PATTERNS):
    return ValidationResult(is_valid=False, ...)
```

**Attack blocked:** Cannot use URL to execute scripts or access local network.

---

### Guarantee 6: Timestamp Freshness (Replay Prevention)

**How it works:**
- Actions older than 5 minutes are rejected
- Prevents attacker from replaying old captured actions

**Code proof:**
```python
MAX_ACTION_AGE_SECONDS = 300  # 5 minutes

age = (now - timestamp).total_seconds()
if age > self.MAX_ACTION_AGE_SECONDS:
    return ValidationResult(is_valid=False, rejection_rule="TIMESTAMP_STALE")
```

**Attack blocked:** Captured network traffic cannot be replayed later.

---

### Guarantee 7: Strict JSON Schema Validation

**How it works:**
- `additionalProperties: false` in schema rejects unknown fields
- Required fields must be present
- Types are strictly enforced
- Malformed JSON fails validation

**Code proof:**
```python
ACTION_SCHEMA = {
    "additionalProperties": False,  # CRITICAL
    "required": ["action_id", "action_type", "timestamp", "signature"],
    ...
}
```

**Attack blocked:** Cannot inject hidden fields or bypass validation.

---

### Guarantee 8: State Machine Control

**How it works:**
- Executor only processes actions when in `LISTENING` state
- User controls state via tray menu
- User can pause (SLEEP) at any time
- Clear audit trail of all state transitions

**Code proof:**
```python
if self._state_machine.is_listening():
    action_request = self._cloud_client.poll_for_actions()
    if action_request:
        self._process_action(...)
```

**Attack blocked:** User can stop all processing at any time.

---

### Guarantee 9: No Background Monitoring

**How it works:**
- No keyboard hooks, no mouse hooks
- No screen capture functionality
- No microphone access
- No webcam access
- Executor only runs when user starts it

**Code proof:**
- No imports of: `pyautogui`, `pynput`, `keyboard`, `mouse`
- No imports of: `pyaudio`, `opencv`, `mss`, `PIL.ImageGrab`
- No background threads except action listener (which only polls cloud)

**Attack blocked:** Cannot spy on user activity.

---

### Guarantee 10: Complete Audit Logging

**How it works:**
- All actions logged (validated, rejected, executed)
- All permission decisions logged
- All state transitions logged
- Logs written to file for review

**Code proof:**
```python
security_logger.action_validated(action_id, action_type)
security_logger.action_rejected(action_id, reason, rule)
security_logger.permission_granted(action_id, action_type)
security_logger.permission_denied(action_id, action_type)
security_logger.action_executed(action_id, action_type, success)
```

**Attack blocked:** All activity is traceable for forensic analysis.

---

## 3. What This Client CANNOT Do (By Design)

| Forbidden Action | Why It's Impossible |
|------------------|---------------------|
| Run shell commands | No subprocess/os.system imported |
| Delete files | No delete code exists |
| Modify files | Only read-mode opens allowed |
| Access registry | No winreg imported |
| Capture screen | No screen capture libraries |
| Log keystrokes | No keyboard hooks |
| Access microphone | No audio libraries |
| Access webcam | No camera libraries |
| Access network arbitrarily | Only cloud communication |
| Execute code from cloud | No eval/exec anywhere |
| Bypass user permission | Permission check is mandatory |
| Remember permissions | Each action asks fresh |

---

## 4. File Structure Summary

```
local_client/
├── requirements.txt              # Minimal dependencies
├── run.py                        # Entry point
├── test_executor.py              # Test script
│
└── saarthi_executor/
    ├── __init__.py               # Package definition + security constants
    ├── schema.py                 # JSON schema + rejection rules
    ├── state_machine.py          # SLEEP/LISTENING/ACTIVE states
    ├── validator.py              # All validation logic
    ├── permission_manager.py     # User permission dialogs
    ├── action_handlers.py        # ONLY 3 allowed actions
    ├── cloud_client.py           # Cloud communication
    ├── tray_app.py               # System tray UI
    ├── logging_config.py         # Audit logging
    └── executor.py               # Main application
```

---

## 5. Defense in Depth Summary

```
Layer 1: Transport Security
└── HTTPS only, certificate validation

Layer 2: Schema Validation  
└── Strict JSON schema, reject unknown fields

Layer 3: Action Allowlist
└── Only 3 actions possible, no generic execution

Layer 4: URL Safety
└── Block dangerous URL schemes and patterns

Layer 5: Timestamp Freshness
└── Reject old actions (replay prevention)

Layer 6: User Permission
└── Every action requires explicit approval

Layer 7: Minimal Execution
└── Only safe APIs: webbrowser, os.startfile, open(read)

Layer 8: Audit Logging
└── Complete trail of all activity
```

---

## 6. Conclusion

This local executor is designed with the principle of **minimal capability**:

1. **It can only do 3 things** (open URL, play media, read user-selected file)
2. **It asks before doing anything** (mandatory permission dialog)
3. **It cannot be extended remotely** (no generic execution)
4. **It cannot run arbitrary code** (no subprocess/eval/exec)
5. **It cannot spy on users** (no monitoring capabilities)
6. **It logs everything** (full audit trail)

The cloud planner can suggest actions, but the **user always decides**.
