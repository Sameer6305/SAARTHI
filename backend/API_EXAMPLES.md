# SAARTHI Backend API Examples

## Overview

The backend provides a RESTful API for task management. The local client communicates with these endpoints.

**Base URL:** `http://localhost:8000/api/v1`

---

## Endpoints

### 1. Create Task (POST /task)

Create a new task from plain text input.

**Request:**
```http
POST /api/v1/task HTTP/1.1
Content-Type: application/json

{
    "input_text": "open youtube",
    "session_id": "sess_abc123",
    "context": {}
}
```

**Response (201 Created):**
```json
{
    "task_id": "task_a1b2c3d4e5f67890",
    "status": "ready_for_execution",
    "message": "Ready for execution",
    "created_at": "2026-01-21T10:30:00.000Z",
    "intent_summary": "Open YouTube website in browser",
    "step_count": 2
}
```

---

### 2. Get Task Status (GET /status/{task_id})

Check the current status of a task.

**Request:**
```http
GET /api/v1/status/task_a1b2c3d4e5f67890 HTTP/1.1
```

**Response (200 OK):**
```json
{
    "task_id": "task_a1b2c3d4e5f67890",
    "status": "ready_for_execution",
    "planning_complete": true,
    "awaiting_confirmation": false,
    "ready_for_execution": true,
    "failed": false,
    "failure_reason": null,
    "plan_steps": [
        {
            "step_id": "task_a1b2c3d4e5f67890_step_1",
            "step_number": 1,
            "description": "Identify target URL or search query",
            "step_type": "informational",
            "tool_id": null,
            "risk_level": "NONE",
            "requires_confirmation": false
        },
        {
            "step_id": "task_a1b2c3d4e5f67890_step_2",
            "step_number": 2,
            "description": "Open or navigate browser",
            "step_type": "tool_required",
            "tool_id": "browser.navigate",
            "risk_level": "LOW",
            "requires_confirmation": false
        }
    ],
    "current_step": null,
    "created_at": "2026-01-21T10:30:00.000Z",
    "updated_at": "2026-01-21T10:30:01.000Z"
}
```

---

### 3. Get Executable Actions (GET /task/{task_id}/actions)

**This is the key endpoint for local client integration.**

Retrieves actions in the exact format expected by the local executor.

**Request:**
```http
GET /api/v1/task/task_a1b2c3d4e5f67890/actions HTTP/1.1
```

**Response (200 OK):**
```json
{
    "task_id": "task_a1b2c3d4e5f67890",
    "execution_status": "ready_for_execution",
    "actions": [
        {
            "action_id": "act_1a2b3c4d5e6f7890abcd",
            "action_type": "open_browser_url",
            "timestamp": "2026-01-21T10:30:05.000Z",
            "signature": "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
            "description": "Open https://www.youtube.com in your default browser",
            "risk_level": "LOW",
            "parameters": {
                "url": "https://www.youtube.com"
            },
            "task_id": "task_a1b2c3d4e5f67890",
            "step_id": "task_a1b2c3d4e5f67890_step_2"
        }
    ],
    "total_actions": 1,
    "current_action_index": 0,
    "requires_confirmation": false,
    "created_at": "2026-01-21T10:30:05.000Z",
    "expires_at": "2026-01-21T10:35:05.000Z"
}
```

---

### 4. Confirm Task (POST /task/{task_id}/confirm)

Confirm a task that requires user approval.

**Request:**
```http
POST /api/v1/task/task_a1b2c3d4e5f67890/confirm HTTP/1.1
```

**Response (200 OK):**
```json
{
    "task_id": "task_a1b2c3d4e5f67890",
    "status": "ready_for_execution",
    "planning_complete": true,
    "awaiting_confirmation": false,
    "ready_for_execution": true,
    "failed": false,
    "failure_reason": null,
    "plan_steps": [...],
    "current_step": null,
    "created_at": "2026-01-21T10:30:00.000Z",
    "updated_at": "2026-01-21T10:30:30.000Z"
}
```

---

### 5. Report Execution Result (POST /task/{task_id}/execution-update)

Called by local client after executing an action.

**Request:**
```http
POST /api/v1/task/task_a1b2c3d4e5f67890/execution-update?step_id=task_a1b2c3d4e5f67890_step_2&success=true HTTP/1.1
```

**Response (200 OK):**
```json
{
    "task_id": "task_a1b2c3d4e5f67890",
    "status": "completed",
    "planning_complete": true,
    "awaiting_confirmation": false,
    "ready_for_execution": false,
    "failed": false,
    "failure_reason": null,
    "plan_steps": [...],
    "current_step": 2,
    "created_at": "2026-01-21T10:30:00.000Z",
    "updated_at": "2026-01-21T10:31:00.000Z"
}
```

---

## Action Types (Allowlist)

The backend ONLY produces these action types:

| Action Type | Description | Parameters |
|-------------|-------------|------------|
| `open_browser_url` | Open URL in default browser | `url` (https:// only) |
| `play_media_file` | Open file picker for media | `media_type` (audio/video/image) |
| `read_file_with_picker` | Open file picker to read file | `file_types` (e.g., [".txt", ".pdf"]) |

---

## Error Responses

**400 Bad Request:**
```json
{
    "error": "validation_error",
    "message": "Input text cannot be empty",
    "task_id": null,
    "timestamp": "2026-01-21T10:30:00.000Z",
    "correlation_id": "req_abc123"
}
```

**404 Not Found:**
```json
{
    "detail": "Task task_nonexistent not found"
}
```

**409 Conflict:**
```json
{
    "detail": "Actions not ready (current status: awaiting_confirmation)"
}
```

---

## Integration Flow

```
LOCAL CLIENT                          BACKEND
     │                                    │
     │  POST /task                        │
     │  {"input_text": "open youtube"}    │
     │ ─────────────────────────────────▶ │
     │                                    │ ← Analyze intent
     │                                    │ ← Generate plan
     │  {task_id, status}                 │
     │ ◀───────────────────────────────── │
     │                                    │
     │  GET /task/{id}/actions            │
     │ ─────────────────────────────────▶ │
     │                                    │
     │  {actions: [{action_id, ...}]}     │
     │ ◀───────────────────────────────── │
     │                                    │
     │ ← Validate action (schema, sig)    │
     │ ← Show permission dialog           │
     │ ← Execute action                   │
     │                                    │
     │  POST /task/{id}/execution-update  │
     │ ─────────────────────────────────▶ │
     │                                    │
     │  {status: "completed"}             │
     │ ◀───────────────────────────────── │
     │                                    │
```

---

## Security Notes

1. **No OS execution** - Backend only plans, never executes
2. **Allowlist enforced** - Only 3 action types possible
3. **Signatures** - All actions are cryptographically signed
4. **Expiry** - Actions expire after 5 minutes
5. **No raw input stored** - Only abstracted intent is kept
