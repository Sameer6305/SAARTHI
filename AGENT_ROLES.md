# SAARTHI Agent Roles Specification

**Document Classification:** Internal Architecture Specification  
**Version:** 1.0.0  
**Last Updated:** 2026-01-19  
**Status:** Authoritative  

---

## Document Overview

This document defines the internal agent roles, contracts, input/output schemas, failure modes, and safety guarantees for the SAARTHI agentic AI system.

SAARTHI operates on a Planner–Executor architecture with strict cloud–local separation. All agents adhere to deterministic behavior, explicit validation, and fail-closed semantics.

---

## Global Design Invariants

The following invariants apply to ALL agents without exception:

| Invariant | Description |
|-----------|-------------|
| **INV-001** | No agent may consume input without schema validation |
| **INV-002** | No agent may emit output that fails its own output schema |
| **INV-003** | No agent may assume correctness of upstream agent output |
| **INV-004** | No agent may share state implicitly; all state passes through explicit channels |
| **INV-005** | All agents fail closed; ambiguity results in rejection, not assumption |
| **INV-006** | No agent may escalate privileges or bypass permission boundaries |
| **INV-007** | All inter-agent communication uses immutable message envelopes |

---

## Agent Execution Order (Canonical Pipeline)

```
User Request
     │
     ▼
┌─────────────────┐
│ Intent Analyzer │
└────────┬────────┘
         │ AnalyzedIntent
         ▼
┌─────────────────┐
│  Planner Agent  │
└────────┬────────┘
         │ ExecutionPlan
         ▼
┌─────────────────┐
│ Executor Agent  │
└────────┬────────┘
         │ ExecutionResult
         ▼
┌─────────────────┐
│ Verifier Agent  │
└────────┬────────┘
         │ VerifiedResult
         ▼
     Response

Memory Manager ◄──► [All Agents] (Explicit Read/Write Requests Only)
```

---

# AGENT 1: INTENT ANALYZER

## 1.1 Agent Responsibility

### Scope of Responsibility

The Intent Analyzer is responsible for:

- Receiving raw user input in structured form
- Decomposing user input into normalized intent components
- Classifying intent into a finite, enumerated set of intent categories
- Detecting ambiguity and surfacing it explicitly as uncertainty states
- Extracting entities, constraints, and parameters from user input
- Rejecting malformed, unsafe, or unclassifiable requests

### Allowed Actions

| Action | Description |
|--------|-------------|
| Parse structured user input | Extract fields from input envelope |
| Classify intent | Map to enumerated intent category |
| Extract entities | Identify named parameters, constraints, temporal markers |
| Flag ambiguity | Surface uncertainty as explicit state |
| Reject input | Return structured rejection with reason code |

### Prohibited Actions

| Prohibition | Rationale |
|-------------|-----------|
| MUST NOT interpret natural language beyond classification | No generative interpretation |
| MUST NOT assume missing information | Ambiguity must be explicit |
| MUST NOT execute any action | Read-only analysis only |
| MUST NOT access memory without explicit request | No implicit state access |
| MUST NOT modify input | Input is immutable |
| MUST NOT infer user identity | Identity is provided or absent |

### Trust Assumptions

| Assumption | Description |
|------------|-------------|
| Input envelope is well-formed JSON | Upstream transport layer responsibility |
| Timestamp is accurate | System clock is trusted |
| Session ID is authentic | Session management is external |
| No trust in content semantics | Content must be validated |

---

## 1.2 Input JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.intent_analyzer.input.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "session_id", "user_input"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$",
      "description": "Unique request identifier"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of request receipt"
    },
    "session_id": {
      "type": "string",
      "pattern": "^sess_[a-f0-9]{32}$",
      "description": "Session identifier for context binding"
    },
    "user_input": {
      "type": "object",
      "required": ["input_type", "content"],
      "additionalProperties": false,
      "properties": {
        "input_type": {
          "type": "string",
          "enum": ["text", "structured_command", "continuation"],
          "description": "Classification of input modality"
        },
        "content": {
          "type": "object",
          "required": ["raw_text"],
          "properties": {
            "raw_text": {
              "type": "string",
              "minLength": 1,
              "maxLength": 4096,
              "description": "User-provided text input"
            },
            "structured_fields": {
              "type": "object",
              "description": "Optional pre-parsed fields from UI",
              "additionalProperties": {
                "type": ["string", "number", "boolean", "null"]
              }
            }
          }
        },
        "context_hint": {
          "type": "string",
          "enum": ["new_conversation", "follow_up", "clarification", "correction"],
          "default": "new_conversation"
        }
      }
    },
    "permissions": {
      "type": "object",
      "required": ["allowed_intent_categories"],
      "properties": {
        "allowed_intent_categories": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "minItems": 1,
          "description": "Whitelist of permitted intent categories for this session"
        },
        "denied_operations": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "default": [],
          "description": "Explicit operation blacklist"
        }
      }
    }
  }
}
```

### Validation Constraints

| Field | Constraint | Rejection Condition |
|-------|------------|---------------------|
| `request_id` | Must match pattern | Malformed request ID |
| `timestamp` | Must be valid ISO 8601, not in future | Invalid or future timestamp |
| `session_id` | Must match pattern | Malformed session ID |
| `raw_text` | Length 1-4096 | Empty or oversized input |
| `input_type` | Must be enumerated value | Unknown input type |
| `allowed_intent_categories` | Non-empty array | No permitted categories |

### Explicit Rejection Conditions

| Code | Condition |
|------|-----------|
| `INPUT_SCHEMA_VIOLATION` | JSON does not conform to schema |
| `EMPTY_CONTENT` | raw_text is empty or whitespace-only |
| `CONTENT_TOO_LONG` | raw_text exceeds 4096 characters |
| `INVALID_TIMESTAMP` | Timestamp malformed or in future |
| `NO_PERMITTED_CATEGORIES` | allowed_intent_categories is empty |

---

## 1.3 Output JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.intent_analyzer.output.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "status", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$",
      "description": "Echo of input request_id"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of analysis completion"
    },
    "status": {
      "type": "string",
      "enum": ["success", "rejected", "ambiguous"],
      "description": "Deterministic outcome status"
    },
    "payload": {
      "oneOf": [
        { "$ref": "#/$defs/success_payload" },
        { "$ref": "#/$defs/rejected_payload" },
        { "$ref": "#/$defs/ambiguous_payload" }
      ]
    }
  },
  "$defs": {
    "success_payload": {
      "type": "object",
      "required": ["intent_category", "confidence_band", "entities", "constraints"],
      "additionalProperties": false,
      "properties": {
        "intent_category": {
          "type": "string",
          "description": "Classified intent from enumerated set"
        },
        "confidence_band": {
          "type": "string",
          "enum": ["high", "medium"],
          "description": "Discrete confidence level (low triggers ambiguous status)"
        },
        "entities": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["entity_type", "value", "source_span"],
            "properties": {
              "entity_type": {
                "type": "string"
              },
              "value": {
                "type": ["string", "number", "boolean"]
              },
              "source_span": {
                "type": "object",
                "required": ["start", "end"],
                "properties": {
                  "start": { "type": "integer", "minimum": 0 },
                  "end": { "type": "integer", "minimum": 0 }
                }
              },
              "normalized_value": {
                "type": ["string", "number", "boolean", "null"]
              }
            }
          }
        },
        "constraints": {
          "type": "object",
          "properties": {
            "temporal": {
              "type": "object",
              "properties": {
                "type": { "type": "string", "enum": ["absolute", "relative", "none"] },
                "value": { "type": ["string", "null"] }
              }
            },
            "scope": {
              "type": "string",
              "enum": ["single", "batch", "recurring", "unspecified"]
            }
          }
        },
        "requires_confirmation": {
          "type": "boolean",
          "default": false
        }
      }
    },
    "rejected_payload": {
      "type": "object",
      "required": ["rejection_code", "rejection_reason"],
      "additionalProperties": false,
      "properties": {
        "rejection_code": {
          "type": "string",
          "description": "Machine-readable rejection code"
        },
        "rejection_reason": {
          "type": "string",
          "description": "Human-readable rejection description"
        },
        "recoverable": {
          "type": "boolean",
          "default": false
        },
        "suggested_action": {
          "type": "string",
          "enum": ["retry", "rephrase", "provide_clarification", "contact_support", "none"]
        }
      }
    },
    "ambiguous_payload": {
      "type": "object",
      "required": ["ambiguity_type", "candidates", "clarification_required"],
      "additionalProperties": false,
      "properties": {
        "ambiguity_type": {
          "type": "string",
          "enum": ["multiple_intents", "missing_parameter", "conflicting_constraints", "unknown_entity"]
        },
        "candidates": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["intent_category", "confidence_score"],
            "properties": {
              "intent_category": { "type": "string" },
              "confidence_score": { "type": "number", "minimum": 0, "maximum": 1 }
            }
          },
          "minItems": 1,
          "maxItems": 5
        },
        "clarification_required": {
          "type": "object",
          "required": ["question_id", "options"],
          "properties": {
            "question_id": { "type": "string" },
            "options": {
              "type": "array",
              "items": { "type": "string" },
              "minItems": 2
            }
          }
        }
      }
    }
  }
}
```

---

## 1.4 Failure Cases

| Failure Type | Trigger Condition | Response Status | Downstream Impact |
|--------------|-------------------|-----------------|-------------------|
| Invalid input schema | JSON validation fails | `rejected` | Pipeline halts; no downstream propagation |
| Empty or whitespace input | `raw_text` contains no meaningful content | `rejected` | Pipeline halts |
| Unsafe content detected | Content matches deny-list patterns | `rejected` | Pipeline halts; logged for audit |
| Unclassifiable intent | No intent category matches with confidence ≥ threshold | `ambiguous` | Pipeline halts; clarification requested |
| Multiple competing intents | Two or more intents with similar confidence | `ambiguous` | Pipeline halts; disambiguation required |
| Missing required entity | Intent requires parameter not extractable | `ambiguous` | Pipeline halts; parameter requested |
| Intent not permitted | Classified intent not in `allowed_intent_categories` | `rejected` | Pipeline halts; permission error |
| Timeout | Analysis exceeds time budget | `rejected` | Pipeline halts; code `TIMEOUT` |

### Failure Surfacing Protocol

All failures are surfaced through the standard output schema with `status` set to `rejected` or `ambiguous`. No exceptions are thrown. No partial results are emitted. Downstream agents receiving non-`success` status MUST halt processing.

---

## 1.5 Example Input and Output

### Example 1: Valid Input — Successful Classification

**Input:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "user_input": {
    "input_type": "text",
    "content": {
      "raw_text": "Schedule a meeting with John tomorrow at 3pm"
    },
    "context_hint": "new_conversation"
  },
  "permissions": {
    "allowed_intent_categories": ["scheduling", "calendar", "reminders"],
    "denied_operations": []
  }
}
```

**Output:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00.150Z",
  "status": "success",
  "payload": {
    "intent_category": "scheduling",
    "confidence_band": "high",
    "entities": [
      {
        "entity_type": "person",
        "value": "John",
        "source_span": { "start": 25, "end": 29 },
        "normalized_value": null
      },
      {
        "entity_type": "datetime",
        "value": "tomorrow at 3pm",
        "source_span": { "start": 30, "end": 45 },
        "normalized_value": "2026-01-20T15:00:00Z"
      }
    ],
    "constraints": {
      "temporal": {
        "type": "absolute",
        "value": "2026-01-20T15:00:00Z"
      },
      "scope": "single"
    },
    "requires_confirmation": false
  }
}
```

### Example 2: Failure — Rejected Due to Permission Violation

**Input:**
```json
{
  "request_id": "req_b2c3d4e5f6789012345678901234abcd",
  "timestamp": "2026-01-19T14:35:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "user_input": {
    "input_type": "text",
    "content": {
      "raw_text": "Delete all my emails from last week"
    },
    "context_hint": "new_conversation"
  },
  "permissions": {
    "allowed_intent_categories": ["scheduling", "calendar", "reminders"],
    "denied_operations": ["delete", "bulk_delete"]
  }
}
```

**Output:**
```json
{
  "request_id": "req_b2c3d4e5f6789012345678901234abcd",
  "timestamp": "2026-01-19T14:35:00.120Z",
  "status": "rejected",
  "payload": {
    "rejection_code": "INTENT_NOT_PERMITTED",
    "rejection_reason": "Classified intent 'email_management' is not in allowed_intent_categories. Additionally, operation 'delete' is in denied_operations list.",
    "recoverable": false,
    "suggested_action": "none"
  }
}
```

### Example 3: Failure — Ambiguous Intent

**Input:**
```json
{
  "request_id": "req_c3d4e5f6789012345678901234abcdef",
  "timestamp": "2026-01-19T14:40:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "user_input": {
    "input_type": "text",
    "content": {
      "raw_text": "Set it up for next week"
    },
    "context_hint": "new_conversation"
  },
  "permissions": {
    "allowed_intent_categories": ["scheduling", "calendar", "reminders"],
    "denied_operations": []
  }
}
```

**Output:**
```json
{
  "request_id": "req_c3d4e5f6789012345678901234abcdef",
  "timestamp": "2026-01-19T14:40:00.090Z",
  "status": "ambiguous",
  "payload": {
    "ambiguity_type": "missing_parameter",
    "candidates": [
      { "intent_category": "scheduling", "confidence_score": 0.45 },
      { "intent_category": "reminders", "confidence_score": 0.42 }
    ],
    "clarification_required": {
      "question_id": "clarify_object_and_intent",
      "options": [
        "Schedule a meeting",
        "Set a reminder",
        "Create a calendar event"
      ]
    }
  }
}
```

---
---

# AGENT 2: PLANNER AGENT

## 2.1 Agent Responsibility

### Scope of Responsibility

The Planner Agent is responsible for:

- Receiving validated, classified intents from the Intent Analyzer
- Decomposing intents into ordered, atomic execution steps
- Resolving dependencies between steps
- Validating that all steps are within granted permissions
- Producing a deterministic execution plan consumable by the Executor Agent
- Requesting memory reads (never writes) for context resolution

### Allowed Actions

| Action | Description |
|--------|-------------|
| Decompose intent into steps | Break complex intent into atomic operations |
| Order steps by dependency | Establish execution sequence |
| Validate permissions per step | Check each step against permission model |
| Request memory read | Query Memory Manager for context (read-only) |
| Emit execution plan | Produce structured plan for Executor |
| Reject unplannable intent | Return rejection if no valid plan exists |

### Prohibited Actions

| Prohibition | Rationale |
|-------------|-----------|
| MUST NOT execute any action | Planning only; no side effects |
| MUST NOT bypass permission checks | Every step must be authorized |
| MUST NOT invent new operation types | Steps must use defined operation vocabulary |
| MUST NOT write to memory | Read-only memory access |
| MUST NOT assume Executor capabilities | Plan must match Executor's operation set |
| MUST NOT emit partial plans | Plan is atomic; all-or-nothing |
| MUST NOT modify input intent | Intent is immutable |

### Trust Assumptions

| Assumption | Description |
|------------|-------------|
| Intent Analyzer output conforms to schema | Planner validates but trusts structure |
| Permission model is current and accurate | Permissions provided are authoritative |
| Memory reads return consistent data | Memory Manager ensures read consistency |
| No trust in semantic correctness | Planner validates all fields |

---

## 2.2 Input JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.planner_agent.input.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "analyzed_intent", "execution_context"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "analyzed_intent": {
      "type": "object",
      "required": ["intent_category", "confidence_band", "entities", "constraints"],
      "properties": {
        "intent_category": {
          "type": "string"
        },
        "confidence_band": {
          "type": "string",
          "enum": ["high", "medium"]
        },
        "entities": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["entity_type", "value"],
            "properties": {
              "entity_type": { "type": "string" },
              "value": { "type": ["string", "number", "boolean"] },
              "normalized_value": { "type": ["string", "number", "boolean", "null"] }
            }
          }
        },
        "constraints": {
          "type": "object",
          "properties": {
            "temporal": {
              "type": "object",
              "properties": {
                "type": { "type": "string", "enum": ["absolute", "relative", "none"] },
                "value": { "type": ["string", "null"] }
              }
            },
            "scope": {
              "type": "string",
              "enum": ["single", "batch", "recurring", "unspecified"]
            }
          }
        },
        "requires_confirmation": {
          "type": "boolean"
        }
      }
    },
    "execution_context": {
      "type": "object",
      "required": ["session_id", "permissions", "available_operations"],
      "properties": {
        "session_id": {
          "type": "string",
          "pattern": "^sess_[a-f0-9]{32}$"
        },
        "permissions": {
          "type": "object",
          "required": ["allowed_operations", "resource_access"],
          "properties": {
            "allowed_operations": {
              "type": "array",
              "items": { "type": "string" },
              "minItems": 1
            },
            "denied_operations": {
              "type": "array",
              "items": { "type": "string" },
              "default": []
            },
            "resource_access": {
              "type": "object",
              "additionalProperties": {
                "type": "string",
                "enum": ["read", "write", "none"]
              }
            },
            "max_steps": {
              "type": "integer",
              "minimum": 1,
              "maximum": 50,
              "default": 10
            }
          }
        },
        "available_operations": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["operation_id", "operation_type", "required_params"],
            "properties": {
              "operation_id": { "type": "string" },
              "operation_type": { "type": "string" },
              "required_params": {
                "type": "array",
                "items": { "type": "string" }
              },
              "optional_params": {
                "type": "array",
                "items": { "type": "string" },
                "default": []
              }
            }
          },
          "minItems": 1
        },
        "memory_snapshot": {
          "type": "object",
          "description": "Read-only memory context relevant to this request",
          "additionalProperties": true
        }
      }
    }
  }
}
```

### Validation Constraints

| Field | Constraint | Rejection Condition |
|-------|------------|---------------------|
| `analyzed_intent` | Must have `success` status indicators | Non-success intent passed |
| `confidence_band` | Must be `high` or `medium` | Low confidence intent |
| `allowed_operations` | Non-empty array | No operations available |
| `available_operations` | Non-empty array | No operations defined |
| `max_steps` | 1-50 | Step limit violation |

### Explicit Rejection Conditions

| Code | Condition |
|------|-----------|
| `INPUT_SCHEMA_VIOLATION` | JSON does not conform to schema |
| `INTENT_NOT_PLANNABLE` | No valid operation sequence exists for intent |
| `PERMISSION_DENIED` | Required operation not in `allowed_operations` |
| `RESOURCE_ACCESS_DENIED` | Required resource access level not granted |
| `STEP_LIMIT_EXCEEDED` | Plan requires more steps than `max_steps` |
| `CIRCULAR_DEPENDENCY` | Step dependencies form a cycle |
| `MISSING_REQUIRED_PARAM` | Entity cannot satisfy required operation parameter |

---

## 2.3 Output JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.planner_agent.output.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "status", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "status": {
      "type": "string",
      "enum": ["success", "rejected"]
    },
    "payload": {
      "oneOf": [
        { "$ref": "#/$defs/success_payload" },
        { "$ref": "#/$defs/rejected_payload" }
      ]
    }
  },
  "$defs": {
    "success_payload": {
      "type": "object",
      "required": ["plan_id", "steps", "execution_order", "rollback_strategy"],
      "additionalProperties": false,
      "properties": {
        "plan_id": {
          "type": "string",
          "pattern": "^plan_[a-f0-9]{32}$"
        },
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["step_id", "operation_id", "operation_type", "parameters", "dependencies", "is_reversible"],
            "additionalProperties": false,
            "properties": {
              "step_id": {
                "type": "string",
                "pattern": "^step_[0-9]{3}$"
              },
              "operation_id": {
                "type": "string"
              },
              "operation_type": {
                "type": "string"
              },
              "parameters": {
                "type": "object",
                "additionalProperties": true
              },
              "dependencies": {
                "type": "array",
                "items": {
                  "type": "string",
                  "pattern": "^step_[0-9]{3}$"
                }
              },
              "is_reversible": {
                "type": "boolean"
              },
              "timeout_ms": {
                "type": "integer",
                "minimum": 100,
                "maximum": 300000,
                "default": 30000
              },
              "retry_policy": {
                "type": "object",
                "properties": {
                  "max_retries": { "type": "integer", "minimum": 0, "maximum": 3, "default": 0 },
                  "backoff_ms": { "type": "integer", "minimum": 100, "default": 1000 }
                }
              }
            }
          },
          "minItems": 1
        },
        "execution_order": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^step_[0-9]{3}$"
          },
          "minItems": 1,
          "description": "Topologically sorted step execution order"
        },
        "rollback_strategy": {
          "type": "string",
          "enum": ["full_rollback", "partial_rollback", "no_rollback"],
          "description": "Strategy if execution fails mid-plan"
        },
        "requires_confirmation": {
          "type": "boolean",
          "default": false
        },
        "estimated_duration_ms": {
          "type": "integer",
          "minimum": 0
        },
        "resource_locks_required": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["resource_id", "lock_type"],
            "properties": {
              "resource_id": { "type": "string" },
              "lock_type": { "type": "string", "enum": ["read", "write", "exclusive"] }
            }
          }
        }
      }
    },
    "rejected_payload": {
      "type": "object",
      "required": ["rejection_code", "rejection_reason"],
      "additionalProperties": false,
      "properties": {
        "rejection_code": {
          "type": "string"
        },
        "rejection_reason": {
          "type": "string"
        },
        "failed_at_step": {
          "type": "string",
          "description": "Step ID where planning failed, if applicable"
        },
        "missing_permissions": {
          "type": "array",
          "items": { "type": "string" }
        },
        "missing_resources": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

---

## 2.4 Failure Cases

| Failure Type | Trigger Condition | Response Status | Downstream Impact |
|--------------|-------------------|-----------------|-------------------|
| Invalid input schema | JSON validation fails | `rejected` | Pipeline halts |
| Intent not plannable | No operation sequence satisfies intent | `rejected` | Pipeline halts |
| Permission denied | Required operation not permitted | `rejected` | Pipeline halts; missing permissions listed |
| Resource access denied | Required resource level not granted | `rejected` | Pipeline halts; missing resources listed |
| Step limit exceeded | Plan exceeds `max_steps` | `rejected` | Pipeline halts |
| Circular dependency | Steps have cyclic dependencies | `rejected` | Pipeline halts |
| Missing parameter | Cannot bind entity to required param | `rejected` | Pipeline halts |
| Memory read failure | Memory Manager returns error | `rejected` | Pipeline halts; code `MEMORY_UNAVAILABLE` |
| Timeout | Planning exceeds time budget | `rejected` | Pipeline halts; code `TIMEOUT` |

### Failure Surfacing Protocol

All planning failures result in `status: rejected` with explicit `rejection_code` and `rejection_reason`. If the failure occurs at a specific step during plan construction, `failed_at_step` is populated. Missing permissions and resources are enumerated explicitly to enable debugging.

---

## 2.5 Example Input and Output

### Example 1: Valid Input — Successful Plan Generation

**Input:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00.200Z",
  "analyzed_intent": {
    "intent_category": "scheduling",
    "confidence_band": "high",
    "entities": [
      {
        "entity_type": "person",
        "value": "John",
        "normalized_value": "john.doe@company.com"
      },
      {
        "entity_type": "datetime",
        "value": "tomorrow at 3pm",
        "normalized_value": "2026-01-20T15:00:00Z"
      }
    ],
    "constraints": {
      "temporal": {
        "type": "absolute",
        "value": "2026-01-20T15:00:00Z"
      },
      "scope": "single"
    },
    "requires_confirmation": false
  },
  "execution_context": {
    "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
    "permissions": {
      "allowed_operations": ["calendar_read", "calendar_create", "notification_send"],
      "denied_operations": ["calendar_delete"],
      "resource_access": {
        "calendar": "write",
        "contacts": "read",
        "notifications": "write"
      },
      "max_steps": 10
    },
    "available_operations": [
      {
        "operation_id": "op_calendar_read",
        "operation_type": "calendar_read",
        "required_params": ["start_time", "end_time"]
      },
      {
        "operation_id": "op_calendar_create",
        "operation_type": "calendar_create",
        "required_params": ["title", "start_time", "attendees"],
        "optional_params": ["duration", "location", "description"]
      },
      {
        "operation_id": "op_notification_send",
        "operation_type": "notification_send",
        "required_params": ["recipient", "message"]
      }
    ],
    "memory_snapshot": {
      "user_preferences": {
        "default_meeting_duration": 30
      }
    }
  }
}
```

**Output:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00.350Z",
  "status": "success",
  "payload": {
    "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
    "steps": [
      {
        "step_id": "step_001",
        "operation_id": "op_calendar_read",
        "operation_type": "calendar_read",
        "parameters": {
          "start_time": "2026-01-20T14:00:00Z",
          "end_time": "2026-01-20T16:00:00Z"
        },
        "dependencies": [],
        "is_reversible": false,
        "timeout_ms": 5000,
        "retry_policy": {
          "max_retries": 2,
          "backoff_ms": 500
        }
      },
      {
        "step_id": "step_002",
        "operation_id": "op_calendar_create",
        "operation_type": "calendar_create",
        "parameters": {
          "title": "Meeting with John",
          "start_time": "2026-01-20T15:00:00Z",
          "attendees": ["john.doe@company.com"],
          "duration": 30
        },
        "dependencies": ["step_001"],
        "is_reversible": true,
        "timeout_ms": 10000,
        "retry_policy": {
          "max_retries": 1,
          "backoff_ms": 1000
        }
      },
      {
        "step_id": "step_003",
        "operation_id": "op_notification_send",
        "operation_type": "notification_send",
        "parameters": {
          "recipient": "john.doe@company.com",
          "message": "Meeting invitation: Meeting with John at 2026-01-20T15:00:00Z"
        },
        "dependencies": ["step_002"],
        "is_reversible": false,
        "timeout_ms": 5000,
        "retry_policy": {
          "max_retries": 2,
          "backoff_ms": 500
        }
      }
    ],
    "execution_order": ["step_001", "step_002", "step_003"],
    "rollback_strategy": "partial_rollback",
    "requires_confirmation": false,
    "estimated_duration_ms": 20000,
    "resource_locks_required": [
      {
        "resource_id": "calendar",
        "lock_type": "write"
      }
    ]
  }
}
```

### Example 2: Failure — Permission Denied

**Input:**
```json
{
  "request_id": "req_e5f6789012345678901234abcdef1234",
  "timestamp": "2026-01-19T14:45:00Z",
  "analyzed_intent": {
    "intent_category": "scheduling",
    "confidence_band": "high",
    "entities": [
      {
        "entity_type": "event_id",
        "value": "evt_123456",
        "normalized_value": "evt_123456"
      }
    ],
    "constraints": {
      "temporal": { "type": "none", "value": null },
      "scope": "single"
    },
    "requires_confirmation": false
  },
  "execution_context": {
    "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
    "permissions": {
      "allowed_operations": ["calendar_read"],
      "denied_operations": ["calendar_delete"],
      "resource_access": {
        "calendar": "read"
      },
      "max_steps": 10
    },
    "available_operations": [
      {
        "operation_id": "op_calendar_delete",
        "operation_type": "calendar_delete",
        "required_params": ["event_id"]
      }
    ],
    "memory_snapshot": {}
  }
}
```

**Output:**
```json
{
  "request_id": "req_e5f6789012345678901234abcdef1234",
  "timestamp": "2026-01-19T14:45:00.100Z",
  "status": "rejected",
  "payload": {
    "rejection_code": "PERMISSION_DENIED",
    "rejection_reason": "Intent requires operation 'calendar_delete' which is not in allowed_operations and is explicitly in denied_operations.",
    "failed_at_step": null,
    "missing_permissions": ["calendar_delete"],
    "missing_resources": []
  }
}
```

---
---

# AGENT 3: EXECUTOR AGENT

## 3.1 Agent Responsibility

### Scope of Responsibility

The Executor Agent is responsible for:

- Receiving validated execution plans from the Planner Agent
- Executing each step in the specified order
- Respecting step dependencies
- Capturing execution results per step
- Handling step failures according to retry policy
- Triggering rollback on unrecoverable failure
- Reporting deterministic execution outcomes

### Allowed Actions

| Action | Description |
|--------|-------------|
| Execute plan steps | Invoke operations as specified |
| Respect dependency order | Execute steps only when dependencies complete |
| Capture results | Record success/failure per step |
| Retry on transient failure | Apply retry policy for failed steps |
| Trigger rollback | Execute rollback for reversible steps on failure |
| Request memory write | Submit write request to Memory Manager (authorized only) |
| Report execution outcome | Emit structured result |

### Prohibited Actions

| Prohibition | Rationale |
|-------------|-----------|
| MUST NOT invent actions | Can only execute steps in the plan |
| MUST NOT modify plan | Plan is immutable once received |
| MUST NOT skip steps | All steps must be attempted or explicitly failed |
| MUST NOT reorder steps | Execution order is authoritative |
| MUST NOT exceed step parameters | Parameters are fixed |
| MUST NOT execute without valid plan | Plan must pass input validation |
| MUST NOT assume step success | Each step result must be captured |
| MUST NOT write memory without authorization | Write requests are gated |

### Trust Assumptions

| Assumption | Description |
|------------|-------------|
| Plan conforms to output schema of Planner | Executor validates but trusts structure |
| Operations are available | Operations listed in plan are executable |
| Timeouts are reasonable | Step timeouts are within system limits |
| No trust in operation outcomes | All outcomes are verified |

---

## 3.2 Input JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.executor_agent.input.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "plan", "execution_config"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "plan": {
      "type": "object",
      "required": ["plan_id", "steps", "execution_order", "rollback_strategy"],
      "properties": {
        "plan_id": {
          "type": "string",
          "pattern": "^plan_[a-f0-9]{32}$"
        },
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["step_id", "operation_id", "operation_type", "parameters", "dependencies", "is_reversible"],
            "properties": {
              "step_id": {
                "type": "string",
                "pattern": "^step_[0-9]{3}$"
              },
              "operation_id": { "type": "string" },
              "operation_type": { "type": "string" },
              "parameters": { "type": "object" },
              "dependencies": {
                "type": "array",
                "items": { "type": "string" }
              },
              "is_reversible": { "type": "boolean" },
              "timeout_ms": { "type": "integer" },
              "retry_policy": {
                "type": "object",
                "properties": {
                  "max_retries": { "type": "integer" },
                  "backoff_ms": { "type": "integer" }
                }
              }
            }
          },
          "minItems": 1
        },
        "execution_order": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        },
        "rollback_strategy": {
          "type": "string",
          "enum": ["full_rollback", "partial_rollback", "no_rollback"]
        },
        "resource_locks_required": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "resource_id": { "type": "string" },
              "lock_type": { "type": "string" }
            }
          }
        }
      }
    },
    "execution_config": {
      "type": "object",
      "required": ["session_id", "dry_run"],
      "properties": {
        "session_id": {
          "type": "string",
          "pattern": "^sess_[a-f0-9]{32}$"
        },
        "dry_run": {
          "type": "boolean",
          "description": "If true, simulate execution without side effects"
        },
        "halt_on_first_failure": {
          "type": "boolean",
          "default": true
        },
        "memory_write_authorization": {
          "type": "object",
          "properties": {
            "authorized": { "type": "boolean", "default": false },
            "scope": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

### Validation Constraints

| Field | Constraint | Rejection Condition |
|-------|------------|---------------------|
| `plan_id` | Must match pattern | Invalid plan ID |
| `steps` | Non-empty array | Empty plan |
| `execution_order` | Must reference valid step IDs | Invalid step reference |
| `execution_order` | No duplicates | Duplicate step in order |
| `dependencies` | Must reference steps earlier in order | Forward dependency |
| `dry_run` | Required boolean | Missing execution mode |

### Explicit Rejection Conditions

| Code | Condition |
|------|-----------|
| `INPUT_SCHEMA_VIOLATION` | JSON does not conform to schema |
| `EMPTY_PLAN` | No steps in plan |
| `INVALID_STEP_REFERENCE` | Execution order references non-existent step |
| `FORWARD_DEPENDENCY` | Step depends on step not yet executed |
| `DUPLICATE_STEP` | Step appears multiple times in execution order |
| `RESOURCE_LOCK_FAILED` | Cannot acquire required resource lock |

---

## 3.3 Output JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.executor_agent.output.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "plan_id", "status", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "plan_id": {
      "type": "string",
      "pattern": "^plan_[a-f0-9]{32}$"
    },
    "status": {
      "type": "string",
      "enum": ["completed", "partial_failure", "failed", "rejected", "rolled_back"]
    },
    "payload": {
      "type": "object",
      "required": ["step_results", "summary"],
      "additionalProperties": false,
      "properties": {
        "step_results": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["step_id", "status", "started_at", "completed_at"],
            "additionalProperties": false,
            "properties": {
              "step_id": {
                "type": "string",
                "pattern": "^step_[0-9]{3}$"
              },
              "status": {
                "type": "string",
                "enum": ["success", "failed", "skipped", "rolled_back", "not_executed"]
              },
              "started_at": {
                "type": "string",
                "format": "date-time"
              },
              "completed_at": {
                "type": "string",
                "format": "date-time"
              },
              "duration_ms": {
                "type": "integer",
                "minimum": 0
              },
              "retries_attempted": {
                "type": "integer",
                "minimum": 0,
                "default": 0
              },
              "result": {
                "type": "object",
                "description": "Operation-specific result payload"
              },
              "error": {
                "type": "object",
                "properties": {
                  "error_code": { "type": "string" },
                  "error_message": { "type": "string" },
                  "recoverable": { "type": "boolean" }
                }
              }
            }
          }
        },
        "summary": {
          "type": "object",
          "required": ["total_steps", "succeeded", "failed", "skipped", "rolled_back"],
          "properties": {
            "total_steps": { "type": "integer", "minimum": 0 },
            "succeeded": { "type": "integer", "minimum": 0 },
            "failed": { "type": "integer", "minimum": 0 },
            "skipped": { "type": "integer", "minimum": 0 },
            "rolled_back": { "type": "integer", "minimum": 0 },
            "total_duration_ms": { "type": "integer", "minimum": 0 }
          }
        },
        "rollback_executed": {
          "type": "boolean",
          "default": false
        },
        "rollback_results": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["step_id", "rollback_status"],
            "properties": {
              "step_id": { "type": "string" },
              "rollback_status": { "type": "string", "enum": ["success", "failed", "not_applicable"] }
            }
          }
        },
        "memory_writes_requested": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["key", "value", "authorization_status"],
            "properties": {
              "key": { "type": "string" },
              "value": { "type": ["object", "string", "number", "boolean", "null"] },
              "authorization_status": { "type": "string", "enum": ["authorized", "denied", "pending"] }
            }
          }
        }
      }
    }
  }
}
```

---

## 3.4 Failure Cases

| Failure Type | Trigger Condition | Response Status | Downstream Impact |
|--------------|-------------------|-----------------|-------------------|
| Invalid input schema | JSON validation fails | `rejected` | Pipeline halts |
| Empty plan | No steps to execute | `rejected` | Pipeline halts |
| Resource lock failed | Cannot acquire lock | `rejected` | Pipeline halts |
| Step timeout | Step exceeds timeout | Step `failed` | Depends on `halt_on_first_failure` |
| Operation error | Step operation fails | Step `failed` | Depends on `halt_on_first_failure` |
| Retries exhausted | All retries fail | Step `failed` | Depends on `halt_on_first_failure` |
| Rollback failure | Rollback step fails | `failed` with partial rollback | Inconsistent state flagged |
| Memory write denied | Write not authorized | Write skipped, logged | Execution continues |
| Dependency failure | Dependent step failed | Step `skipped` | Cascading skip |

### Failure Surfacing Protocol

Each step's outcome is recorded in `step_results`. Overall status reflects the aggregate:
- `completed`: All steps succeeded
- `partial_failure`: Some steps failed but execution continued
- `failed`: Critical failure, execution halted
- `rolled_back`: Failure triggered rollback
- `rejected`: Input validation failed

---

## 3.5 Example Input and Output

### Example 1: Successful Execution

**Input:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:00.400Z",
  "plan": {
    "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
    "steps": [
      {
        "step_id": "step_001",
        "operation_id": "op_calendar_read",
        "operation_type": "calendar_read",
        "parameters": {
          "start_time": "2026-01-20T14:00:00Z",
          "end_time": "2026-01-20T16:00:00Z"
        },
        "dependencies": [],
        "is_reversible": false,
        "timeout_ms": 5000,
        "retry_policy": { "max_retries": 2, "backoff_ms": 500 }
      },
      {
        "step_id": "step_002",
        "operation_id": "op_calendar_create",
        "operation_type": "calendar_create",
        "parameters": {
          "title": "Meeting with John",
          "start_time": "2026-01-20T15:00:00Z",
          "attendees": ["john.doe@company.com"],
          "duration": 30
        },
        "dependencies": ["step_001"],
        "is_reversible": true,
        "timeout_ms": 10000,
        "retry_policy": { "max_retries": 1, "backoff_ms": 1000 }
      }
    ],
    "execution_order": ["step_001", "step_002"],
    "rollback_strategy": "partial_rollback",
    "resource_locks_required": [
      { "resource_id": "calendar", "lock_type": "write" }
    ]
  },
  "execution_config": {
    "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
    "dry_run": false,
    "halt_on_first_failure": true,
    "memory_write_authorization": {
      "authorized": true,
      "scope": ["last_created_event"]
    }
  }
}
```

**Output:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:01.200Z",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "status": "completed",
  "payload": {
    "step_results": [
      {
        "step_id": "step_001",
        "status": "success",
        "started_at": "2026-01-19T14:30:00.410Z",
        "completed_at": "2026-01-19T14:30:00.650Z",
        "duration_ms": 240,
        "retries_attempted": 0,
        "result": {
          "events_found": 0,
          "conflicts": []
        }
      },
      {
        "step_id": "step_002",
        "status": "success",
        "started_at": "2026-01-19T14:30:00.660Z",
        "completed_at": "2026-01-19T14:30:01.150Z",
        "duration_ms": 490,
        "retries_attempted": 0,
        "result": {
          "event_id": "evt_789xyz",
          "created": true
        }
      }
    ],
    "summary": {
      "total_steps": 2,
      "succeeded": 2,
      "failed": 0,
      "skipped": 0,
      "rolled_back": 0,
      "total_duration_ms": 730
    },
    "rollback_executed": false,
    "rollback_results": [],
    "memory_writes_requested": [
      {
        "key": "last_created_event",
        "value": { "event_id": "evt_789xyz", "created_at": "2026-01-19T14:30:01.150Z" },
        "authorization_status": "authorized"
      }
    ]
  }
}
```

### Example 2: Failure with Rollback

**Input:**
```json
{
  "request_id": "req_f6789012345678901234abcdef123456",
  "timestamp": "2026-01-19T15:00:00Z",
  "plan": {
    "plan_id": "plan_e5f6a7b8c9012345678901234abcdef0",
    "steps": [
      {
        "step_id": "step_001",
        "operation_id": "op_db_insert",
        "operation_type": "database_insert",
        "parameters": { "table": "orders", "data": {} },
        "dependencies": [],
        "is_reversible": true,
        "timeout_ms": 5000,
        "retry_policy": { "max_retries": 1, "backoff_ms": 500 }
      },
      {
        "step_id": "step_002",
        "operation_id": "op_payment_charge",
        "operation_type": "payment_charge",
        "parameters": { "amount": 100 },
        "dependencies": ["step_001"],
        "is_reversible": true,
        "timeout_ms": 30000,
        "retry_policy": { "max_retries": 2, "backoff_ms": 2000 }
      }
    ],
    "execution_order": ["step_001", "step_002"],
    "rollback_strategy": "full_rollback",
    "resource_locks_required": []
  },
  "execution_config": {
    "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
    "dry_run": false,
    "halt_on_first_failure": true,
    "memory_write_authorization": { "authorized": false }
  }
}
```

**Output:**
```json
{
  "request_id": "req_f6789012345678901234abcdef123456",
  "timestamp": "2026-01-19T15:00:35.500Z",
  "plan_id": "plan_e5f6a7b8c9012345678901234abcdef0",
  "status": "rolled_back",
  "payload": {
    "step_results": [
      {
        "step_id": "step_001",
        "status": "rolled_back",
        "started_at": "2026-01-19T15:00:00.100Z",
        "completed_at": "2026-01-19T15:00:00.350Z",
        "duration_ms": 250,
        "retries_attempted": 0,
        "result": { "insert_id": "ord_abc123" }
      },
      {
        "step_id": "step_002",
        "status": "failed",
        "started_at": "2026-01-19T15:00:00.400Z",
        "completed_at": "2026-01-19T15:00:35.000Z",
        "duration_ms": 34600,
        "retries_attempted": 2,
        "error": {
          "error_code": "PAYMENT_GATEWAY_TIMEOUT",
          "error_message": "Payment gateway did not respond within timeout",
          "recoverable": false
        }
      }
    ],
    "summary": {
      "total_steps": 2,
      "succeeded": 0,
      "failed": 1,
      "skipped": 0,
      "rolled_back": 1,
      "total_duration_ms": 35400
    },
    "rollback_executed": true,
    "rollback_results": [
      {
        "step_id": "step_001",
        "rollback_status": "success"
      }
    ],
    "memory_writes_requested": []
  }
}
```

---
---

# AGENT 4: VERIFIER AGENT

## 4.1 Agent Responsibility

### Scope of Responsibility

The Verifier Agent is responsible for:

- Receiving execution results from the Executor Agent
- Validating that execution outcomes match expected states
- Verifying data integrity and consistency
- Acting as a hard gate for downstream propagation
- Rejecting results that fail verification
- Never acting in an advisory capacity

### Allowed Actions

| Action | Description |
|--------|-------------|
| Validate execution results | Check results against expected outcomes |
| Verify data integrity | Confirm consistency of produced data |
| Apply verification rules | Execute deterministic verification logic |
| Gate downstream propagation | Pass or reject results |
| Emit verification verdict | Produce structured pass/fail output |

### Prohibited Actions

| Prohibition | Rationale |
|-------------|-----------|
| MUST NOT advise or suggest | Verifier is a gate, not an advisor |
| MUST NOT modify results | Results are immutable |
| MUST NOT execute any action | Verification only; no side effects |
| MUST NOT waive verification | All rules must be applied |
| MUST NOT infer expected state | Expected state must be explicit |
| MUST NOT produce partial verdicts | Verdict is atomic pass/fail |
| MUST NOT trust Executor output | All fields must be verified |

### Trust Assumptions

| Assumption | Description |
|------------|-------------|
| Execution result conforms to schema | Verifier validates structure |
| Verification rules are complete | Rule set covers all scenarios |
| Timestamp ordering is accurate | Temporal assertions are valid |
| No trust in result semantics | All claims must be verified |

---

## 4.2 Input JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.verifier_agent.input.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "execution_result", "verification_rules"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "execution_result": {
      "type": "object",
      "required": ["plan_id", "status", "payload"],
      "properties": {
        "plan_id": {
          "type": "string",
          "pattern": "^plan_[a-f0-9]{32}$"
        },
        "status": {
          "type": "string",
          "enum": ["completed", "partial_failure", "failed", "rejected", "rolled_back"]
        },
        "payload": {
          "type": "object",
          "required": ["step_results", "summary"],
          "properties": {
            "step_results": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["step_id", "status"],
                "properties": {
                  "step_id": { "type": "string" },
                  "status": { "type": "string" },
                  "result": { "type": "object" },
                  "error": { "type": "object" }
                }
              }
            },
            "summary": {
              "type": "object",
              "required": ["total_steps", "succeeded", "failed"],
              "properties": {
                "total_steps": { "type": "integer" },
                "succeeded": { "type": "integer" },
                "failed": { "type": "integer" },
                "skipped": { "type": "integer" },
                "rolled_back": { "type": "integer" }
              }
            },
            "rollback_executed": { "type": "boolean" }
          }
        }
      }
    },
    "verification_rules": {
      "type": "object",
      "required": ["rules"],
      "properties": {
        "rules": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["rule_id", "rule_type", "target", "condition"],
            "additionalProperties": false,
            "properties": {
              "rule_id": {
                "type": "string",
                "pattern": "^rule_[a-f0-9]{16}$"
              },
              "rule_type": {
                "type": "string",
                "enum": ["step_status", "result_field", "summary_constraint", "temporal_order", "consistency"]
              },
              "target": {
                "type": "string",
                "description": "JSONPath-like reference to target field"
              },
              "condition": {
                "type": "object",
                "required": ["operator", "expected"],
                "properties": {
                  "operator": {
                    "type": "string",
                    "enum": ["equals", "not_equals", "greater_than", "less_than", "contains", "exists", "not_exists", "matches_pattern"]
                  },
                  "expected": {
                    "type": ["string", "number", "boolean", "null", "array"]
                  }
                }
              },
              "severity": {
                "type": "string",
                "enum": ["critical", "major", "minor"],
                "default": "critical"
              },
              "fail_fast": {
                "type": "boolean",
                "default": true,
                "description": "If true, stop verification on this rule failure"
              }
            }
          },
          "minItems": 1
        },
        "require_all_critical": {
          "type": "boolean",
          "default": true,
          "description": "If true, all critical rules must pass"
        }
      }
    },
    "original_intent": {
      "type": "object",
      "description": "Original analyzed intent for cross-reference verification",
      "properties": {
        "intent_category": { "type": "string" },
        "entities": { "type": "array" },
        "constraints": { "type": "object" }
      }
    }
  }
}
```

### Validation Constraints

| Field | Constraint | Rejection Condition |
|-------|------------|---------------------|
| `execution_result` | Must conform to Executor output schema | Invalid execution result |
| `rules` | Non-empty array | No verification rules |
| `rule_id` | Must match pattern | Invalid rule ID |
| `operator` | Must be enumerated value | Unknown operator |
| `target` | Must be valid path reference | Invalid target path |

### Explicit Rejection Conditions

| Code | Condition |
|------|-----------|
| `INPUT_SCHEMA_VIOLATION` | JSON does not conform to schema |
| `NO_VERIFICATION_RULES` | Empty rules array |
| `INVALID_TARGET_PATH` | Target path cannot be resolved |
| `INVALID_OPERATOR` | Unknown comparison operator |
| `TYPE_MISMATCH` | Expected value type incompatible with operator |

---

## 4.3 Output JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.verifier_agent.output.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "plan_id", "verdict", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "plan_id": {
      "type": "string",
      "pattern": "^plan_[a-f0-9]{32}$"
    },
    "verdict": {
      "type": "string",
      "enum": ["pass", "fail", "rejected"],
      "description": "Deterministic verification verdict"
    },
    "payload": {
      "type": "object",
      "required": ["rule_results", "summary"],
      "additionalProperties": false,
      "properties": {
        "rule_results": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["rule_id", "passed", "evaluated_at"],
            "additionalProperties": false,
            "properties": {
              "rule_id": {
                "type": "string",
                "pattern": "^rule_[a-f0-9]{16}$"
              },
              "passed": {
                "type": "boolean"
              },
              "evaluated_at": {
                "type": "string",
                "format": "date-time"
              },
              "actual_value": {
                "type": ["string", "number", "boolean", "null", "object", "array"],
                "description": "Actual value found at target path"
              },
              "expected_value": {
                "type": ["string", "number", "boolean", "null", "array"],
                "description": "Expected value from rule condition"
              },
              "failure_reason": {
                "type": "string",
                "description": "Populated only if passed is false"
              }
            }
          }
        },
        "summary": {
          "type": "object",
          "required": ["total_rules", "passed", "failed", "critical_failures"],
          "properties": {
            "total_rules": { "type": "integer", "minimum": 0 },
            "passed": { "type": "integer", "minimum": 0 },
            "failed": { "type": "integer", "minimum": 0 },
            "critical_failures": { "type": "integer", "minimum": 0 },
            "major_failures": { "type": "integer", "minimum": 0 },
            "minor_failures": { "type": "integer", "minimum": 0 }
          }
        },
        "execution_result_passthrough": {
          "type": "object",
          "description": "Original execution result, passed through only if verdict is 'pass'"
        }
      }
    }
  }
}
```

---

## 4.4 Failure Cases

| Failure Type | Trigger Condition | Response Verdict | Downstream Impact |
|--------------|-------------------|------------------|-------------------|
| Invalid input schema | JSON validation fails | `rejected` | Pipeline halts |
| No verification rules | Rules array is empty | `rejected` | Pipeline halts |
| Critical rule failure | Any critical rule fails | `fail` | Result not propagated |
| All critical pass, major fail | Critical pass but major fails | `fail` (if require_all_critical false) | Result not propagated |
| Target path unresolvable | Cannot evaluate rule target | `rejected` | Pipeline halts |
| Type mismatch in comparison | Operator incompatible with value types | `rejected` | Pipeline halts |

### Failure Surfacing Protocol

The Verifier produces a deterministic verdict:
- `pass`: All rules passed; execution result is propagated downstream
- `fail`: One or more rules failed; execution result is NOT propagated
- `rejected`: Input validation failed; no verification performed

There is no "partial pass" or "advisory" verdict. The Verifier is a binary gate.

---

## 4.5 Example Input and Output

### Example 1: Verification Passed

**Input:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:01.300Z",
  "execution_result": {
    "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
    "status": "completed",
    "payload": {
      "step_results": [
        { "step_id": "step_001", "status": "success", "result": { "events_found": 0 } },
        { "step_id": "step_002", "status": "success", "result": { "event_id": "evt_789xyz", "created": true } }
      ],
      "summary": {
        "total_steps": 2,
        "succeeded": 2,
        "failed": 0,
        "skipped": 0,
        "rolled_back": 0
      },
      "rollback_executed": false
    }
  },
  "verification_rules": {
    "rules": [
      {
        "rule_id": "rule_a1b2c3d4e5f67890",
        "rule_type": "step_status",
        "target": "$.payload.step_results[*].status",
        "condition": { "operator": "equals", "expected": "success" },
        "severity": "critical",
        "fail_fast": true
      },
      {
        "rule_id": "rule_b2c3d4e5f6789012",
        "rule_type": "result_field",
        "target": "$.payload.step_results[1].result.created",
        "condition": { "operator": "equals", "expected": true },
        "severity": "critical",
        "fail_fast": true
      },
      {
        "rule_id": "rule_c3d4e5f678901234",
        "rule_type": "summary_constraint",
        "target": "$.payload.summary.failed",
        "condition": { "operator": "equals", "expected": 0 },
        "severity": "critical",
        "fail_fast": false
      }
    ],
    "require_all_critical": true
  },
  "original_intent": {
    "intent_category": "scheduling",
    "entities": [{ "entity_type": "person", "value": "John" }],
    "constraints": { "temporal": { "type": "absolute", "value": "2026-01-20T15:00:00Z" } }
  }
}
```

**Output:**
```json
{
  "request_id": "req_a1b2c3d4e5f6789012345678901234ab",
  "timestamp": "2026-01-19T14:30:01.450Z",
  "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
  "verdict": "pass",
  "payload": {
    "rule_results": [
      {
        "rule_id": "rule_a1b2c3d4e5f67890",
        "passed": true,
        "evaluated_at": "2026-01-19T14:30:01.320Z",
        "actual_value": ["success", "success"],
        "expected_value": "success"
      },
      {
        "rule_id": "rule_b2c3d4e5f6789012",
        "passed": true,
        "evaluated_at": "2026-01-19T14:30:01.350Z",
        "actual_value": true,
        "expected_value": true
      },
      {
        "rule_id": "rule_c3d4e5f678901234",
        "passed": true,
        "evaluated_at": "2026-01-19T14:30:01.380Z",
        "actual_value": 0,
        "expected_value": 0
      }
    ],
    "summary": {
      "total_rules": 3,
      "passed": 3,
      "failed": 0,
      "critical_failures": 0,
      "major_failures": 0,
      "minor_failures": 0
    },
    "execution_result_passthrough": {
      "plan_id": "plan_d4e5f6a7b8c9012345678901234abcde",
      "status": "completed",
      "payload": {
        "step_results": [
          { "step_id": "step_001", "status": "success", "result": { "events_found": 0 } },
          { "step_id": "step_002", "status": "success", "result": { "event_id": "evt_789xyz", "created": true } }
        ],
        "summary": {
          "total_steps": 2,
          "succeeded": 2,
          "failed": 0,
          "skipped": 0,
          "rolled_back": 0
        },
        "rollback_executed": false
      }
    }
  }
}
```

### Example 2: Verification Failed

**Input:**
```json
{
  "request_id": "req_g7890123456789abcdef01234567890a",
  "timestamp": "2026-01-19T15:10:00Z",
  "execution_result": {
    "plan_id": "plan_f6a7b8c9012345678901234abcdef012",
    "status": "completed",
    "payload": {
      "step_results": [
        { "step_id": "step_001", "status": "success", "result": { "balance": 50 } },
        { "step_id": "step_002", "status": "success", "result": { "transferred": true, "amount": 200 } }
      ],
      "summary": {
        "total_steps": 2,
        "succeeded": 2,
        "failed": 0,
        "skipped": 0,
        "rolled_back": 0
      },
      "rollback_executed": false
    }
  },
  "verification_rules": {
    "rules": [
      {
        "rule_id": "rule_d4e5f67890123456",
        "rule_type": "consistency",
        "target": "$.payload.step_results[1].result.amount",
        "condition": { "operator": "less_than", "expected": 100 },
        "severity": "critical",
        "fail_fast": true
      }
    ],
    "require_all_critical": true
  }
}
```

**Output:**
```json
{
  "request_id": "req_g7890123456789abcdef01234567890a",
  "timestamp": "2026-01-19T15:10:00.200Z",
  "plan_id": "plan_f6a7b8c9012345678901234abcdef012",
  "verdict": "fail",
  "payload": {
    "rule_results": [
      {
        "rule_id": "rule_d4e5f67890123456",
        "passed": false,
        "evaluated_at": "2026-01-19T15:10:00.150Z",
        "actual_value": 200,
        "expected_value": 100,
        "failure_reason": "Actual value 200 is not less than expected value 100"
      }
    ],
    "summary": {
      "total_rules": 1,
      "passed": 0,
      "failed": 1,
      "critical_failures": 1,
      "major_failures": 0,
      "minor_failures": 0
    }
  }
}
```

---
---

# AGENT 5: MEMORY MANAGER

## 5.1 Agent Responsibility

### Scope of Responsibility

The Memory Manager is responsible for:

- Providing read access to stored memory for authorized agents
- Processing authorized write requests to memory
- Enforcing memory access authorization
- Maintaining memory consistency and isolation
- Rejecting unauthorized access attempts
- Managing memory lifecycle (creation, update, expiration)

### Allowed Actions

| Action | Description |
|--------|-------------|
| Process read requests | Return memory values for authorized reads |
| Process write requests | Store values for authorized writes |
| Validate authorization | Check access permissions before any operation |
| Enforce isolation | Ensure session isolation |
| Manage expiration | Handle TTL and memory cleanup |
| Return operation status | Emit structured success/failure |

### Prohibited Actions

| Prohibition | Rationale |
|-------------|-----------|
| MUST NOT mutate without authorization | All writes require explicit authorization token |
| MUST NOT infer authorization | Authorization must be explicit, not implied |
| MUST NOT cross session boundaries | Sessions are strictly isolated |
| MUST NOT expose memory to unauthorized agents | Access control is mandatory |
| MUST NOT modify access control rules | Rules are externally managed |
| MUST NOT cache authorization decisions | Each request is validated independently |
| MUST NOT perform speculative writes | Writes are atomic and explicit |

### Trust Assumptions

| Assumption | Description |
|------------|-------------|
| Authorization tokens are authentic | Token validation is external |
| Session IDs are unique and unforgeable | Session management is trusted |
| Timestamps are accurate | System clock is trusted |
| Storage backend is reliable | Persistence is guaranteed by infrastructure |

---

## 5.2 Input JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.memory_manager.input.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "session_id", "operation"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "session_id": {
      "type": "string",
      "pattern": "^sess_[a-f0-9]{32}$"
    },
    "requesting_agent": {
      "type": "string",
      "enum": ["intent_analyzer", "planner_agent", "executor_agent", "verifier_agent"],
      "description": "Identifier of the agent making the request"
    },
    "operation": {
      "type": "object",
      "required": ["operation_type"],
      "oneOf": [
        { "$ref": "#/$defs/read_operation" },
        { "$ref": "#/$defs/write_operation" },
        { "$ref": "#/$defs/delete_operation" },
        { "$ref": "#/$defs/query_operation" }
      ]
    }
  },
  "$defs": {
    "read_operation": {
      "type": "object",
      "required": ["operation_type", "key"],
      "additionalProperties": false,
      "properties": {
        "operation_type": {
          "type": "string",
          "const": "read"
        },
        "key": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256,
          "pattern": "^[a-zA-Z_][a-zA-Z0-9_\\.]*$"
        },
        "default_value": {
          "type": ["string", "number", "boolean", "object", "array", "null"],
          "description": "Value to return if key does not exist"
        }
      }
    },
    "write_operation": {
      "type": "object",
      "required": ["operation_type", "key", "value", "authorization"],
      "additionalProperties": false,
      "properties": {
        "operation_type": {
          "type": "string",
          "const": "write"
        },
        "key": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256,
          "pattern": "^[a-zA-Z_][a-zA-Z0-9_\\.]*$"
        },
        "value": {
          "type": ["string", "number", "boolean", "object", "array", "null"]
        },
        "authorization": {
          "type": "object",
          "required": ["token", "scope"],
          "properties": {
            "token": {
              "type": "string",
              "pattern": "^authz_[a-f0-9]{64}$"
            },
            "scope": {
              "type": "array",
              "items": { "type": "string" },
              "minItems": 1,
              "description": "Keys this token is authorized to write"
            }
          }
        },
        "ttl_seconds": {
          "type": "integer",
          "minimum": 0,
          "maximum": 86400,
          "description": "Time-to-live in seconds; 0 means no expiration"
        },
        "if_not_exists": {
          "type": "boolean",
          "default": false,
          "description": "Only write if key does not already exist"
        }
      }
    },
    "delete_operation": {
      "type": "object",
      "required": ["operation_type", "key", "authorization"],
      "additionalProperties": false,
      "properties": {
        "operation_type": {
          "type": "string",
          "const": "delete"
        },
        "key": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256,
          "pattern": "^[a-zA-Z_][a-zA-Z0-9_\\.]*$"
        },
        "authorization": {
          "type": "object",
          "required": ["token", "scope"],
          "properties": {
            "token": {
              "type": "string",
              "pattern": "^authz_[a-f0-9]{64}$"
            },
            "scope": {
              "type": "array",
              "items": { "type": "string" },
              "minItems": 1
            }
          }
        }
      }
    },
    "query_operation": {
      "type": "object",
      "required": ["operation_type", "key_pattern"],
      "additionalProperties": false,
      "properties": {
        "operation_type": {
          "type": "string",
          "const": "query"
        },
        "key_pattern": {
          "type": "string",
          "description": "Glob pattern for key matching",
          "minLength": 1,
          "maxLength": 256
        },
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100,
          "default": 10
        }
      }
    }
  }
}
```

### Validation Constraints

| Field | Constraint | Rejection Condition |
|-------|------------|---------------------|
| `key` | Valid pattern, 1-256 chars | Invalid key format |
| `authorization.token` | Must match pattern | Invalid token format |
| `authorization.scope` | Non-empty array | Empty scope |
| `ttl_seconds` | 0-86400 | TTL out of range |
| `operation_type` | Must be enumerated | Unknown operation |

### Explicit Rejection Conditions

| Code | Condition |
|------|-----------|
| `INPUT_SCHEMA_VIOLATION` | JSON does not conform to schema |
| `INVALID_KEY_FORMAT` | Key does not match allowed pattern |
| `INVALID_TOKEN_FORMAT` | Authorization token format invalid |
| `AUTHORIZATION_REQUIRED` | Write/delete without authorization |
| `AUTHORIZATION_DENIED` | Token not valid for requested scope |
| `KEY_NOT_IN_SCOPE` | Key not in authorization scope |
| `SESSION_MISMATCH` | Session ID mismatch with token |
| `KEY_NOT_FOUND` | Read/delete for non-existent key (no default) |

---

## 5.3 Output JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "saarthi.memory_manager.output.v1",
  "type": "object",
  "required": ["request_id", "timestamp", "session_id", "status", "payload"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "pattern": "^req_[a-f0-9]{32}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "session_id": {
      "type": "string",
      "pattern": "^sess_[a-f0-9]{32}$"
    },
    "status": {
      "type": "string",
      "enum": ["success", "rejected"]
    },
    "payload": {
      "oneOf": [
        { "$ref": "#/$defs/read_success" },
        { "$ref": "#/$defs/write_success" },
        { "$ref": "#/$defs/delete_success" },
        { "$ref": "#/$defs/query_success" },
        { "$ref": "#/$defs/rejected_payload" }
      ]
    }
  },
  "$defs": {
    "read_success": {
      "type": "object",
      "required": ["operation_type", "key", "value", "found"],
      "additionalProperties": false,
      "properties": {
        "operation_type": { "type": "string", "const": "read" },
        "key": { "type": "string" },
        "value": { "type": ["string", "number", "boolean", "object", "array", "null"] },
        "found": { "type": "boolean" },
        "metadata": {
          "type": "object",
          "properties": {
            "created_at": { "type": "string", "format": "date-time" },
            "updated_at": { "type": "string", "format": "date-time" },
            "expires_at": { "type": ["string", "null"], "format": "date-time" }
          }
        }
      }
    },
    "write_success": {
      "type": "object",
      "required": ["operation_type", "key", "written"],
      "additionalProperties": false,
      "properties": {
        "operation_type": { "type": "string", "const": "write" },
        "key": { "type": "string" },
        "written": { "type": "boolean" },
        "was_update": { "type": "boolean" },
        "expires_at": { "type": ["string", "null"], "format": "date-time" }
      }
    },
    "delete_success": {
      "type": "object",
      "required": ["operation_type", "key", "deleted"],
      "additionalProperties": false,
      "properties": {
        "operation_type": { "type": "string", "const": "delete" },
        "key": { "type": "string" },
        "deleted": { "type": "boolean" }
      }
    },
    "query_success": {
      "type": "object",
      "required": ["operation_type", "keys"],
      "additionalProperties": false,
      "properties": {
        "operation_type": { "type": "string", "const": "query" },
        "keys": {
          "type": "array",
          "items": { "type": "string" }
        },
        "total_matches": { "type": "integer", "minimum": 0 },
        "truncated": { "type": "boolean" }
      }
    },
    "rejected_payload": {
      "type": "object",
      "required": ["rejection_code", "rejection_reason"],
      "additionalProperties": false,
      "properties": {
        "rejection_code": { "type": "string" },
        "rejection_reason": { "type": "string" },
        "operation_type": { "type": "string" },
        "key": { "type": "string" }
      }
    }
  }
}
```

---

## 5.4 Failure Cases

| Failure Type | Trigger Condition | Response Status | Downstream Impact |
|--------------|-------------------|-----------------|-------------------|
| Invalid input schema | JSON validation fails | `rejected` | Operation not performed |
| Invalid key format | Key pattern mismatch | `rejected` | Operation not performed |
| Authorization required | Write/delete without token | `rejected` | Operation not performed |
| Authorization denied | Token invalid or expired | `rejected` | Operation not performed |
| Key not in scope | Key not covered by token scope | `rejected` | Operation not performed |
| Session mismatch | Token session ≠ request session | `rejected` | Operation not performed |
| Key not found | Read/delete non-existent, no default | `rejected` | Operation not performed |
| Storage error | Backend storage failure | `rejected` | Code `STORAGE_ERROR` |

### Failure Surfacing Protocol

All failures result in `status: rejected` with explicit `rejection_code` and `rejection_reason`. The Memory Manager never performs partial operations. Authorization failures are logged for audit.

---

## 5.5 Example Input and Output

### Example 1: Successful Read

**Input:**
```json
{
  "request_id": "req_h890123456789abcdef01234567890ab",
  "timestamp": "2026-01-19T14:29:50Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "requesting_agent": "planner_agent",
  "operation": {
    "operation_type": "read",
    "key": "user_preferences.default_meeting_duration",
    "default_value": 30
  }
}
```

**Output:**
```json
{
  "request_id": "req_h890123456789abcdef01234567890ab",
  "timestamp": "2026-01-19T14:29:50.050Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "status": "success",
  "payload": {
    "operation_type": "read",
    "key": "user_preferences.default_meeting_duration",
    "value": 45,
    "found": true,
    "metadata": {
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-01-18T14:30:00Z",
      "expires_at": null
    }
  }
}
```

### Example 2: Successful Write with Authorization

**Input:**
```json
{
  "request_id": "req_i901234567890abcdef1234567890abc",
  "timestamp": "2026-01-19T14:30:01.200Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "requesting_agent": "executor_agent",
  "operation": {
    "operation_type": "write",
    "key": "last_created_event",
    "value": {
      "event_id": "evt_789xyz",
      "created_at": "2026-01-19T14:30:01.150Z",
      "title": "Meeting with John"
    },
    "authorization": {
      "token": "authz_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
      "scope": ["last_created_event", "session_context"]
    },
    "ttl_seconds": 3600
  }
}
```

**Output:**
```json
{
  "request_id": "req_i901234567890abcdef1234567890abc",
  "timestamp": "2026-01-19T14:30:01.250Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "status": "success",
  "payload": {
    "operation_type": "write",
    "key": "last_created_event",
    "written": true,
    "was_update": false,
    "expires_at": "2026-01-19T15:30:01.250Z"
  }
}
```

### Example 3: Rejected — Authorization Denied

**Input:**
```json
{
  "request_id": "req_j012345678901abcdef2345678901bcd",
  "timestamp": "2026-01-19T14:35:00Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "requesting_agent": "executor_agent",
  "operation": {
    "operation_type": "write",
    "key": "user_credentials",
    "value": { "password": "secret" },
    "authorization": {
      "token": "authz_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678",
      "scope": ["last_created_event", "session_context"]
    }
  }
}
```

**Output:**
```json
{
  "request_id": "req_j012345678901abcdef2345678901bcd",
  "timestamp": "2026-01-19T14:35:00.050Z",
  "session_id": "sess_f1e2d3c4b5a6789012345678901234cd",
  "status": "rejected",
  "payload": {
    "rejection_code": "KEY_NOT_IN_SCOPE",
    "rejection_reason": "Key 'user_credentials' is not in the authorization scope. Authorized keys: ['last_created_event', 'session_context']",
    "operation_type": "write",
    "key": "user_credentials"
  }
}
```

---
---

# APPENDIX A: CROSS-AGENT SAFETY GUARANTEES

## A.1 Safety Invariants Matrix

| Invariant ID | Description | Enforcing Agent(s) | Verification Method |
|--------------|-------------|---------------------|---------------------|
| **SAFE-001** | No action executed without valid plan | Executor | Input validation + schema enforcement |
| **SAFE-002** | No permission bypass | Planner, Executor | Permission check per step |
| **SAFE-003** | No unauthorized memory mutation | Memory Manager | Authorization token validation |
| **SAFE-004** | No implicit trust between agents | All agents | Input validation on every boundary |
| **SAFE-005** | Ambiguity surfaces as explicit state | Intent Analyzer | Ambiguous status with clarification |
| **SAFE-006** | Verification is a hard gate | Verifier | Binary pass/fail verdict |
| **SAFE-007** | All failures are explicit | All agents | Structured rejection payloads |
| **SAFE-008** | No partial outputs | All agents | Atomic output emission |
| **SAFE-009** | Rollback on execution failure | Executor | Rollback strategy execution |
| **SAFE-010** | Session isolation | Memory Manager | Session ID binding |

---

## A.2 Trust Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│                         UNTRUSTED ZONE                           │
│                        (User Input)                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Raw Input
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      VALIDATION BOUNDARY                          │
│                     (Intent Analyzer)                             │
│  • Schema validation                                              │
│  • Content sanitization                                           │
│  • Permission filtering                                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Validated Intent
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      PLANNING BOUNDARY                            │
│                      (Planner Agent)                              │
│  • Permission validation per step                                 │
│  • Operation vocabulary enforcement                               │
│  • Dependency validation                                          │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Validated Plan
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     EXECUTION BOUNDARY                            │
│                     (Executor Agent)                              │
│  • Plan immutability enforcement                                  │
│  • Step-by-step result capture                                    │
│  • Rollback execution                                             │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Execution Result
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    VERIFICATION BOUNDARY                          │
│                     (Verifier Agent)                              │
│  • Rule-based verification                                        │
│  • Hard gate enforcement                                          │
│  • No advisory output                                             │
└───────────────────────────┬──────────────────────────────────────┘
                            │ Verified Result (only if pass)
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       TRUSTED OUTPUT                              │
│                    (Response to User)                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## A.3 Failure Propagation Rules

| Origin Agent | Failure Type | Propagation Behavior |
|--------------|--------------|----------------------|
| Intent Analyzer | `rejected` | Pipeline halts; user notified |
| Intent Analyzer | `ambiguous` | Pipeline halts; clarification requested |
| Planner Agent | `rejected` | Pipeline halts; error surfaced |
| Executor Agent | `failed` | Rollback triggered (if applicable); Verifier receives failure |
| Executor Agent | `partial_failure` | Verifier receives partial result |
| Verifier Agent | `fail` | Result not propagated; user receives failure |
| Memory Manager | `rejected` | Requesting agent handles; may cascade |

---

## A.4 Audit Log Requirements

All agents MUST emit audit events for the following:

| Event Type | Required Fields | Retention |
|------------|-----------------|-----------|
| Input received | `request_id`, `timestamp`, `agent_id`, `input_hash` | 90 days |
| Input rejected | `request_id`, `timestamp`, `agent_id`, `rejection_code` | 1 year |
| Output emitted | `request_id`, `timestamp`, `agent_id`, `status`, `output_hash` | 90 days |
| Permission denied | `request_id`, `timestamp`, `agent_id`, `denied_operation` | 1 year |
| Authorization failure | `request_id`, `timestamp`, `agent_id`, `key`, `token_hash` | 1 year |
| Rollback executed | `request_id`, `timestamp`, `plan_id`, `rolled_back_steps` | 1 year |

---

# APPENDIX B: SCHEMA VERSION COMPATIBILITY

| Schema | Current Version | Backward Compatible With |
|--------|-----------------|--------------------------|
| Intent Analyzer Input | v1 | N/A (initial) |
| Intent Analyzer Output | v1 | N/A (initial) |
| Planner Agent Input | v1 | N/A (initial) |
| Planner Agent Output | v1 | N/A (initial) |
| Executor Agent Input | v1 | N/A (initial) |
| Executor Agent Output | v1 | N/A (initial) |
| Verifier Agent Input | v1 | N/A (initial) |
| Verifier Agent Output | v1 | N/A (initial) |
| Memory Manager Input | v1 | N/A (initial) |
| Memory Manager Output | v1 | N/A (initial) |

Schema evolution MUST follow semantic versioning. Breaking changes require major version increment and explicit migration path documentation.

---

**END OF DOCUMENT**
