# SAARTHI Backend Integration

## Overview

This document describes how the SAARTHI Windows local tray client communicates with the cloud backend for task planning. The integration replaces the mock cloud client with real HTTP calls to the backend running at `localhost:8000`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SAARTHI Local Client                            │
│                                                                     │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────┐ │
│  │  Tray UI    │◄───│  SaarthiExecutor │◄───│   BackendClient     │ │
│  │  (pystray)  │    │  (orchestrator)  │    │   (HTTP/httpx)      │ │
│  └─────────────┘    └─────────────────┘    └──────────┬──────────┘ │
│                                                        │            │
└────────────────────────────────────────────────────────┼────────────┘
                                                         │
                                                         │ HTTP
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SAARTHI Backend (localhost:8000)                │
│                                                                     │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────┐ │
│  │  Tasks API  │───►│  Intent Analyzer │───►│   Planner Service   │ │
│  │  (FastAPI)  │    │                  │    │                     │ │
│  └─────────────┘    └─────────────────┘    └─────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Request-Response Flow

### 1. User Input → HTTP Request

**User Input:**
- Text command entered via the client
- Example: "open youtube"

**Local Validation (before sending):**
```python
# validate_user_input() performs:
1. Check for None/empty input
2. Strip whitespace
3. Enforce min/max length (1-10000 chars)
4. Remove null bytes and control characters
5. Return sanitized text or raise InputValidationError
```

**HTTP Request:**
```http
POST /api/v1/task HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Accept: application/json
User-Agent: SAARTHI-LocalClient/1.0

{
    "input_text": "open youtube",
    "session_id": null
}
```

---

### 2. Backend Planning → Response

**Backend Processing:**
1. Validate input (Pydantic model)
2. Analyze intent (IntentAnalyzer)
3. Generate execution plan (PlannerService)
4. Return task ID and status

**HTTP Response (Task Creation):**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
    "task_id": "task_ab4292a7bb3144f0",
    "status": "ready_for_execution",
    "message": "Ready for execution",
    "created_at": "2026-01-21T01:13:39.123Z",
    "intent_summary": "Web browser navigation request: open/launch operation",
    "step_count": 2
}
```

---

### 3. Fetch Executable Actions

**HTTP Request:**
```http
GET /api/v1/task/task_ab4292a7bb3144f0/actions HTTP/1.1
Host: localhost:8000
Accept: application/json
```

**HTTP Response (Actions):**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "task_id": "task_ab4292a7bb3144f0",
    "total_actions": 1,
    "actions": [
        {
            "action_id": "act_37fa61f3ffb540aaae804c8e",
            "action_type": "open_browser_url",
            "timestamp": "2026-01-21T01:13:39.456Z",
            "signature": "abc123...",
            "description": "Open https://www.youtube.com in your default browser",
            "risk_level": "LOW",
            "parameters": {
                "url": "https://www.youtube.com"
            }
        }
    ],
    "has_more": false
}
```

---

## Error Handling

### On Success

1. TaskCreationResult returned with:
   - `success = True`
   - `task_id = "task_xxx"`
   - `status = "ready_for_execution" | "awaiting_confirmation"`
   
2. ActionsResult returned with:
   - `success = True`
   - `actions = [ActionData, ...]`
   - Each action has: `action_id`, `action_type`, `parameters`

3. Notification shown to user
4. All events logged

### On Backend Failure

| Scenario | HTTP Status | Client Behavior |
|----------|-------------|-----------------|
| Backend unreachable | N/A (ConnectError) | Return error, log, show notification |
| Request timeout | N/A (TimeoutException) | Return error, log |
| Bad request | 400 | Return error with validation details |
| Task not found | 404 | Return error, log |
| Actions not ready | 409 | Return error (task may need confirmation) |
| Server error | 500 | Return generic error, log details |

**Error Response Example:**
```python
TaskCreationResult(
    success=False,
    error="Connection lost"
)
```

### On Invalid Response

1. **Non-JSON Response:**
   - Logged as error
   - Return `TaskCreationResult(success=False, error="Invalid JSON response")`

2. **Missing Required Fields:**
   - Validation rejects response
   - Return with specific error message

3. **Invalid task_id Format:**
   - Must match pattern `^task_[a-f0-9]{16}$`
   - Rejected if malformed

---

## Code Organization

### Files Modified/Created

| File | Purpose |
|------|---------|
| `saarthi_executor/backend_client.py` | **NEW** - Real HTTP client |
| `saarthi_executor/executor.py` | **MODIFIED** - Integration with BackendClient |
| `saarthi_executor/logging_config.py` | **MODIFIED** - Backend logging methods |
| `test_backend_integration.py` | **NEW** - Integration test suite |

### Key Classes

**BackendClient** (`backend_client.py`):
- `connect()` - Establish connection
- `disconnect()` - Close connection
- `send_command(text)` → TaskCreationResult
- `get_actions(task_id)` → ActionsResult

**SaarthiExecutor** (`executor.py`):
- `send_command(text)` - Send via BackendClient
- `fetch_actions(task_id)` - Get actions
- `process_command(text)` - Combined flow (send + fetch)

---

## Testing

### Run Integration Tests
```bash
cd local_client
python test_backend_integration.py
```

### Test Single Command
```bash
python test_backend_integration.py "open youtube"
```

### Expected Output
```
Testing command: "open youtube"

Task created: task_ab4292a7bb3144f0
Status: ready_for_execution

Actions (1):
  - open_browser_url
      url: https://www.youtube.com
```

---

## Security Constraints

### Local Client Constraints
- ❌ No execution of actions in this phase
- ❌ No polling loops (manual fetch only)
- ❌ No voice integration
- ✅ All responses treated as untrusted
- ✅ Input validated before sending
- ✅ Response structure validated
- ✅ All operations logged

### Backend Constraints (enforced by backend)
- ✅ Only allowlisted action types: `open_browser_url`, `play_media_file`, `read_file_with_picker`
- ✅ URLs validated (http/https only)
- ✅ Dangerous patterns blocked (localhost, 127.0.0.1, javascript:, etc.)
- ✅ Action signatures for verification
- ✅ 5-minute action expiry

---

## Configuration

### BackendConfig Defaults
```python
BackendConfig(
    base_url="http://localhost:8000",
    api_prefix="/api/v1",
    timeout_seconds=30.0,
    connect_timeout=5.0,
    min_input_length=1,
    max_input_length=10000
)
```

### Environment
- Backend must be running at `localhost:8000`
- No authentication required for local testing
- httpx used for HTTP communication

---

## Logging

All operations are logged with structured fields:

```
2026-01-21 01:13:39 | INFO     | backend_client           | Connected to backend
2026-01-21 01:13:39 | INFO     | backend_client           | Sending command to backend
2026-01-21 01:13:39 | INFO     | backend_client           | Task created successfully
2026-01-21 01:13:39 | INFO     | backend_client           | Fetching actions from backend
2026-01-21 01:13:39 | INFO     | backend_client           | Actions fetched successfully
```

Logs written to: `~/.saarthi/executor.log`

---

## Future Enhancements (Not Implemented)

1. **Action Execution** - Currently actions are received but not executed
2. **Voice Input** - Text-only input for now
3. **Background Polling** - Manual fetch only
4. **Production URLs** - Currently localhost only
5. **Authentication** - No API keys required locally
