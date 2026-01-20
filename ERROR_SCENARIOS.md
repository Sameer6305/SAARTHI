# SAARTHI Error Handling Scenarios

> Comprehensive documentation of all error scenarios, detection methods, user messages, and system behaviors.

**Last Updated:** January 2026  
**Version:** 1.0.0

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Backend Error Scenarios](#backend-error-scenarios)
3. [Local Client Error Scenarios](#local-client-error-scenarios)
4. [Error Response Format](#error-response-format)
5. [Retry Policy](#retry-policy)
6. [User Message Guidelines](#user-message-guidelines)

---

## Design Principles

### Core Invariants

| Principle | Description |
|-----------|-------------|
| **Fail Closed** | On any ambiguity or error, deny/stop rather than proceed |
| **No Silent Failures** | Every error must be visible to the user |
| **No Partial Execution** | Never execute partial plans or actions |
| **Maximum One Retry** | Retry at most ONCE per failure type |
| **Clear Messages** | Human-readable, non-technical error messages |
| **Full Logging** | Every failure logged for audit |

### What We NEVER Do

- ❌ Show stack traces to users
- ❌ Retry infinitely
- ❌ Auto-approve on timeout
- ❌ Execute partially completed plans
- ❌ Guess user intent when unclear
- ❌ Hide errors from users

---

## Backend Error Scenarios

### 1. Planner Timeout

**Description:** Planning phase exceeds the maximum allowed time.

| Attribute | Value |
|-----------|-------|
| **Timeout Limit** | 15 seconds (total planning) |
| **Phase Timeouts** | Intent: 5s, Plan Generation: 10s |
| **Detection** | `PlanningTimeoutError` exception |
| **HTTP Status** | 201 (task created but failed) |

**User Message:**
> "Your request took too long to process. Please try again with a simpler request."

**System Behavior:**
1. Abort planning immediately
2. Mark task as `FAILED`
3. Set `error_code: TIMEOUT_PLANNING`
4. Return error response
5. Log timeout with elapsed time

**Code Location:** `backend/app/services/task_service.py`

---

### 2. Empty Input

**Description:** User submitted empty or whitespace-only input.

| Attribute | Value |
|-----------|-------|
| **Detection** | `InputValidator.validate()` |
| **Error Code** | `INPUT_EMPTY` |

**User Message:**
> "Please enter a command or question."

**System Behavior:**
1. Reject before task creation
2. Return error immediately
3. No task state created
4. No retry

---

### 3. Input Too Short

**Description:** Input is below minimum length (2 characters).

| Attribute | Value |
|-----------|-------|
| **Minimum Length** | 2 characters |
| **Error Code** | `INPUT_TOO_SHORT` |

**User Message:**
> "Your input is too short. Please provide more details."

**System Behavior:**
1. Reject at validation phase
2. No task created
3. Recoverable (user can retry with better input)

---

### 4. Input Too Long

**Description:** Input exceeds maximum length (10,000 characters).

| Attribute | Value |
|-----------|-------|
| **Maximum Length** | 10,000 characters |
| **Error Code** | `INPUT_TOO_LONG` |

**User Message:**
> "Your input is too long. Please shorten your request."

**System Behavior:**
1. Reject at validation phase
2. No task created

---

### 5. Gibberish/Nonsensical Input

**Description:** Input contains no recognizable words or patterns.

| Attribute | Value |
|-----------|-------|
| **Detection Patterns** | No letters, repeated chars, only symbols |
| **Error Code** | `INPUT_GIBBERISH` |

**User Message:**
> "I couldn't understand your request. Please try rephrasing."

**System Behavior:**
1. Reject at validation phase
2. No planning attempted

---

### 6. Unsupported/Malicious Request

**Description:** Input contains keywords indicating unsupported or dangerous operations.

| Attribute | Value |
|-----------|-------|
| **Blocked Keywords** | hack, crack, exploit, ddos, malware, steal, password, bypass |
| **Error Code** | `INPUT_UNSUPPORTED` |

**User Message:**
> "I'm not able to help with that type of request."

**System Behavior:**
1. Immediate rejection
2. Log as security event
3. No execution path

---

### 7. Low Confidence Intent

**Description:** Intent analysis returned confidence below threshold.

| Attribute | Value |
|-----------|-------|
| **Confidence Threshold** | 0.3 (30%) |
| **Error Code** | `INTENT_LOW_CONFIDENCE` |

**User Message:**
> "I'm not sure what you're asking for. Could you please rephrase your request?"

**System Behavior:**
1. Stop after intent analysis
2. Do NOT proceed to planning
3. Recoverable with clearer input

---

### 8. Non-Actionable Intent

**Description:** Intent is understood but cannot be executed (e.g., pure information request).

| Attribute | Value |
|-----------|-------|
| **Detection** | Category is `information_request` with no tools |
| **Error Code** | `INTENT_NOT_ACTIONABLE` |

**User Message:**
> "I understand you're asking a question, but I can only help with actions like opening websites or playing media. Please ask me to do something specific."

**System Behavior:**
1. Stop after intent validation
2. Explain what the system CAN do

---

### 9. Plan Generation Timeout

**Description:** Plan generation specifically timed out.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 10 seconds |
| **Error Code** | `TIMEOUT_PLAN_GENERATION` |

**User Message:**
> "Your request took too long to process. Please try again with a simpler request."

**System Behavior:**
1. Abort plan generation
2. Mark task as `PLANNING_FAILED`
3. Intent already analyzed (not lost)

---

### 10. Plan Validation Failed

**Description:** Generated plan failed validation checks.

| Attribute | Value |
|-----------|-------|
| **Detection** | `PlannerService.validate_plan()` returns False |
| **Error Code** | `PLANNING_FAILED` |

**User Message:**
> "I wasn't able to plan how to complete your request. Please try rephrasing or simplifying your command."

**System Behavior:**
1. Mark task as `PLANNING_FAILED`
2. Do NOT return partial plan
3. Log validation issues

---

## Local Client Error Scenarios

### 11. Backend Unreachable (Connection Refused)

**Description:** Cannot establish TCP connection to backend server.

| Attribute | Value |
|-----------|-------|
| **Detection** | `httpx.ConnectError` |
| **Retry Policy** | ONE retry after 2 seconds |
| **Error Code** | `NETWORK_UNREACHABLE` |

**User Message:**
> "Unable to reach the SAARTHI backend. Please check that the server is running."

**System Behavior:**
1. Catch `ConnectError`
2. Wait 2 seconds
3. Retry connection ONCE
4. If retry fails:
   - Log final failure
   - Notify user
   - Remain in idle state

---

### 12. Network Timeout

**Description:** Backend request exceeded timeout limit.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 30 seconds (default) |
| **Retry Policy** | ONE retry after 2 seconds |
| **Error Code** | `NETWORK_TIMEOUT` |

**User Message:**
> "The request took too long to complete. Please try again."

**System Behavior:**
1. Catch `TimeoutException`
2. Wait 2 seconds
3. Retry ONCE
4. If retry fails: notify user, stop

---

### 13. Invalid Backend Response

**Description:** Backend returned malformed or unexpected response.

| Attribute | Value |
|-----------|-------|
| **Detection** | JSON parsing or validation fails |
| **Retry Policy** | NO retry (not transient) |
| **Error Code** | `INVALID_RESPONSE` |

**User Message:**
> "Received an invalid response from the backend. Please try again."

**System Behavior:**
1. Do NOT retry (server bug, not network issue)
2. Log response details (sanitized)
3. Notify user

---

### 14. Browser Open Failure

**Description:** Failed to open URL in default browser.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 10 seconds |
| **Detection** | `webbrowser.open()` returns False or throws |
| **Error Code** | `BROWSER_OPEN_FAILED` |

**User Message:**
> "Failed to open '[truncated URL]' in your browser."

**System Behavior:**
1. Detect False return value
2. Log failure with URL domain
3. Notify user with clear message
4. Do NOT retry automatically

---

### 15. Browser Open Timeout

**Description:** Browser open call took too long.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 10 seconds |
| **Error Code** | `EXECUTION_TIMEOUT` |

**User Message:**
> "The action 'Open Browser URL' took too long to complete and was cancelled for safety."

**System Behavior:**
1. Cancel execution
2. Log timeout
3. Notify user

---

### 16. Media Playback Failure

**Description:** Failed to open media file with default application.

| Attribute | Value |
|-----------|-------|
| **Detection** | `os.startfile()` raises `OSError` |
| **Error Code** | `MEDIA_PLAY_FAILED` |

**User Message:**
> "Failed to play [media_type] file. Reason: [error]"

**System Behavior:**
1. Catch OSError (file not found, no associated app, etc.)
2. Log error with media type
3. Notify user with specific reason

---

### 17. Media Open Timeout

**Description:** Media file open call timed out.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 10 seconds |
| **Error Code** | `EXECUTION_TIMEOUT` |

**User Message:**
> "The action 'Play Media File' took too long to complete and was cancelled for safety."

**System Behavior:**
1. Cancel execution
2. Log timeout
3. Notify user

---

### 18. Permission Denied by User

**Description:** User explicitly clicked "Deny" on permission dialog.

| Attribute | Value |
|-----------|-------|
| **Detection** | `PermissionDecision.DENY` |
| **Error Code** | `PERMISSION_DENIED` |

**User Message:**
> "'[Action Name]' was denied: User explicitly denied permission"

**System Behavior:**
1. Log permission denial
2. Do NOT execute action
3. Report denial to backend
4. Remain in idle state

---

### 19. Permission Dialog Timeout

**Description:** User did not respond to permission dialog within time limit.

| Attribute | Value |
|-----------|-------|
| **Timeout** | 60 seconds |
| **Detection** | `PermissionDecision.TIMEOUT` |
| **Error Code** | `PERMISSION_TIMEOUT` |

**User Message:**
> "Permission request timed out (60 seconds)"

**System Behavior:**
1. Close dialog automatically
2. Default to DENY (fail closed)
3. Log timeout
4. Do NOT execute action

---

### 20. Permission Dialog Closed

**Description:** User closed the permission dialog window.

| Attribute | Value |
|-----------|-------|
| **Detection** | `PermissionDecision.WINDOW_CLOSED` |
| **Behavior** | Same as explicit deny |

**User Message:**
> "Permission dialog was closed"

**System Behavior:**
1. Treat as denial
2. Do NOT execute action

---

### 21. Action Not in Allowlist

**Description:** Backend requested an action type not in the executor's allowlist.

| Attribute | Value |
|-----------|-------|
| **Allowlist** | `open_browser_url`, `play_media_file` |
| **Detection** | `PermissionEnforcer.is_action_allowed()` returns False |
| **Error Code** | `POLICY_VIOLATION` |

**User Message:**
> "'[action_type]' is not permitted by security policy"

**System Behavior:**
1. Reject WITHOUT showing permission dialog
2. Log as policy violation
3. Notify user of blocked action
4. Report rejection to backend

---

## Error Response Format

### Backend Task Response (with error)

```json
{
    "task_id": "task_abc123",
    "status": "failed",
    "message": "I'm not sure what you're asking for. Could you please rephrase your request?",
    "created_at": "2026-01-21T10:30:00Z",
    "intent_summary": null,
    "step_count": null,
    "error_code": "INTENT_LOW_CONFIDENCE",
    "recoverable": true
}
```

### Local Client UserError

```python
UserError(
    category=ErrorCategory.NETWORK_UNREACHABLE,
    severity=ErrorSeverity.ERROR,
    title="Cannot Connect",
    message="Unable to reach the SAARTHI backend...",
    internal_code="NETWORK_UNREACHABLE",
    retry_attempted=True,
    is_recoverable=True,
)
```

---

## Retry Policy

### What Gets Retried

| Error Type | Retry | Max Attempts | Delay |
|------------|-------|--------------|-------|
| Connection refused | ✅ Yes | 1 | 2 seconds |
| Network timeout | ✅ Yes | 1 | 2 seconds |
| Invalid response | ❌ No | 0 | - |
| Validation error | ❌ No | 0 | - |
| Permission denied | ❌ No | 0 | - |
| Execution timeout | ❌ No | 0 | - |

### Retry Flow

```
Request Failed
    │
    ├─► Is it a network error (connection/timeout)?
    │       │
    │       ├─► YES: Have we retried yet?
    │       │       │
    │       │       ├─► NO: Wait 2s, retry ONCE
    │       │       │
    │       │       └─► YES: Log final failure, notify user, STOP
    │       │
    │       └─► NO: Do NOT retry, notify user, STOP
    │
    └─► STOP - remain in safe idle state
```

---

## User Message Guidelines

### Message Tone

- **Calm:** Don't alarm the user
- **Honest:** Say what happened
- **Actionable:** Suggest what to do next
- **Non-technical:** No error codes shown to user
- **Brief:** 1-2 sentences maximum

### Good Examples ✅

> "I couldn't understand your request. Please try rephrasing."

> "Unable to reach the SAARTHI backend. Please check that the server is running."

> "The action took too long and was cancelled for safety."

### Bad Examples ❌

> "Error: httpx.ConnectError: [Errno 111] Connection refused"

> "NullPointerException in IntentAnalyzer.analyze() at line 142"

> "Task failed. Error code 0x80004005. Contact support."

---

## Audit Logging

All errors are logged with:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 timestamp |
| `error_code` | Internal error code |
| `category` | Error category enum |
| `severity` | Error severity level |
| `action_id` | Related action ID (if applicable) |
| `task_id` | Related task ID (if applicable) |
| `retry_attempted` | Whether retry was attempted |
| `message` | Internal message (may contain details) |

**Log Location:**
- Backend: Application logs
- Local Client: `~/.saarthi/audit/error_audit.jsonl`

---

## Summary

The SAARTHI error handling system ensures:

1. **No silent failures** - Every error is visible
2. **No infinite loops** - Maximum ONE retry
3. **Fail closed** - Errors default to denial/stop
4. **Clear communication** - Users understand what happened
5. **Full audit trail** - All errors logged
6. **Safe recovery** - System returns to idle state

Errors are part of the system — hiding them is a failure.
