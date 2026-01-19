# SAARTHI — Planner–Executor System Specification

**Version:** 1.0  
**Date:** January 19, 2026  
**Classification:** Safety-Critical Design Specification  
**Status:** Production Design

---

## Table of Contents

1. [Overview](#1-overview)
2. [Planner Logic Definition](#2-planner-logic-definition)
3. [Planner Prompt Template](#3-planner-prompt-template)
4. [Executor Logic Definition](#4-executor-logic-definition)
5. [Executor Prompt Template](#5-executor-prompt-template)
6. [Tool Registry Specification](#6-tool-registry-specification)
7. [Worked Examples](#7-worked-examples)
8. [Failure Taxonomy](#8-failure-taxonomy)
9. [Appendix](#9-appendix)

---

## 1. Overview

### 1.1 Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PLANNER–EXECUTOR SEPARATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────┐      ┌─────────────────────────────┐     │
│   │         PLANNER             │      │         EXECUTOR            │     │
│   │                             │      │                             │     │
│   │  ✓ Reasons about intent     │      │  ✓ Executes steps           │     │
│   │  ✓ Decomposes goals         │      │  ✓ Calls tools              │     │
│   │  ✓ Generates step sequences │      │  ✓ Checks permissions       │     │
│   │  ✓ Classifies risk levels   │      │  ✓ Reports outcomes         │     │
│   │  ✓ Selects tools            │      │  ✓ Handles failures         │     │
│   │                             │      │                             │     │
│   │  ✗ NEVER executes           │      │  ✗ NEVER reasons            │     │
│   │  ✗ NEVER calls tools        │      │  ✗ NEVER invents steps      │     │
│   │  ✗ NEVER simulates          │      │  ✗ NEVER modifies plans     │     │
│   │  ✗ NEVER assumes OS state   │      │  ✗ NEVER infers actions     │     │
│   └─────────────────────────────┘      └─────────────────────────────┘     │
│                                                                             │
│                              ┌─────────┐                                    │
│                              │  PLAN   │                                    │
│                              │ (JSON)  │                                    │
│                              └────┬────┘                                    │
│                                   │                                         │
│            PLANNER ───────────────┴───────────────► EXECUTOR                │
│                         (One-way handoff)                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Fundamental Invariants

| Invariant ID | Statement | Enforcement |
|--------------|-----------|-------------|
| **INV-01** | Planner output is pure data; it has no side effects | Planner has no tool access |
| **INV-02** | Executor performs exactly what the plan specifies | Step-by-step validation |
| **INV-03** | Unknown tools cause immediate plan rejection | Tool registry validation |
| **INV-04** | Unknown OS state causes conditional step marking | Explicit precondition fields |
| **INV-05** | Ambiguity causes failure, not assumption | Strict schema validation |
| **INV-06** | Failure defaults to safe termination | Fail-closed design |

---

## 2. Planner Logic Definition

### 2.1 Responsibilities

The Planner is responsible for:

| Responsibility | Description |
|----------------|-------------|
| **Intent Interpretation** | Converting validated user intent into actionable goals |
| **Goal Decomposition** | Breaking complex goals into atomic, ordered steps |
| **Tool Selection** | Mapping steps to tools from the registered tool set |
| **Risk Classification** | Assigning risk levels to each step |
| **Dependency Ordering** | Establishing correct execution order |
| **Precondition Specification** | Defining what must be true for each step to execute |
| **Confirmation Marking** | Identifying steps requiring user approval |

### 2.2 Constraints (MUST)

| Constraint ID | Rule |
|---------------|------|
| **PC-01** | MUST output valid JSON conforming to the Step Schema |
| **PC-02** | MUST reference only tools that exist in the Tool Registry |
| **PC-03** | MUST NOT assume current OS state (running apps, file existence, etc.) |
| **PC-04** | MUST NOT hallucinate tools, parameters, or capabilities |
| **PC-05** | MUST explicitly fail if intent cannot be safely planned |
| **PC-06** | MUST mark steps with unknown preconditions as `conditional: true` |
| **PC-07** | MUST NOT generate infinite or circular step sequences |
| **PC-08** | MUST NOT embed executable code in step parameters |
| **PC-09** | MUST classify every step with exactly one `step_type` |
| **PC-10** | MUST provide rollback hints for reversible actions |

### 2.3 Prohibitions (MUST NOT)

| Prohibition ID | Rule | Rationale |
|----------------|------|-----------|
| **PP-01** | MUST NOT execute any action | Separation of concerns |
| **PP-02** | MUST NOT simulate execution outcomes | Prevents false assumptions |
| **PP-03** | MUST NOT call external APIs or tools | No side effects |
| **PP-04** | MUST NOT modify system state | Pure function |
| **PP-05** | MUST NOT invent tools not in registry | Prevents hallucination |
| **PP-06** | MUST NOT assume user confirmation | Explicit marking required |
| **PP-07** | MUST NOT generate steps for rejected intents | Fail explicitly |

### 2.4 Planning Rules and Invariants

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLANNING RULES                                      │
└─────────────────────────────────────────────────────────────────────────────┘

RULE P1: TOOL EXISTENCE VALIDATION
──────────────────────────────────────────────────────────────────────────────
  FOR EACH step IN plan:
    IF step.tool_id IS NOT NULL:
      ASSERT step.tool_id IN ToolRegistry
      IF NOT IN ToolRegistry:
        FAIL with error: "UNKNOWN_TOOL"
        DO NOT generate fallback
        DO NOT suggest alternatives

RULE P2: PARAMETER COMPLETENESS
──────────────────────────────────────────────────────────────────────────────
  FOR EACH step IN plan WHERE step.tool_id IS NOT NULL:
    LET required_params = ToolRegistry[step.tool_id].required_parameters
    FOR EACH param IN required_params:
      IF param NOT IN step.parameters:
        IF param CAN be derived from context:
          INCLUDE param with derived value
        ELSE:
          MARK step as "user_input_required": true
          SPECIFY param in "missing_inputs" array

RULE P3: STATE UNCERTAINTY HANDLING
──────────────────────────────────────────────────────────────────────────────
  IF step DEPENDS ON unknown OS state:
    SET step.conditional = true
    SET step.preconditions = [explicit list of assumptions]
    SET step.on_precondition_fail = "skip" | "abort" | "prompt_user"

RULE P4: ORDERING GUARANTEES
──────────────────────────────────────────────────────────────────────────────
  FOR EACH step WITH dependencies:
    ASSERT all dependencies appear earlier in sequence
    ASSERT no circular dependencies exist
  ORDER steps topologically
  IF circular dependency detected:
    FAIL with error: "CIRCULAR_DEPENDENCY"

RULE P5: RISK ESCALATION
──────────────────────────────────────────────────────────────────────────────
  IF step.risk_level = "HIGH" OR "CRITICAL":
    SET step.requires_confirmation = true
  IF plan contains > 3 steps with risk_level = "HIGH":
    SET plan.elevated_risk_warning = true

RULE P6: FINITE BOUND
──────────────────────────────────────────────────────────────────────────────
  ASSERT plan.steps.length <= MAX_STEPS (default: 50)
  IF exceeded:
    FAIL with error: "PLAN_TOO_COMPLEX"
    SUGGEST decomposing into sub-goals

RULE P7: INFORMATIONAL STEP PURITY
──────────────────────────────────────────────────────────────────────────────
  IF step.step_type = "informational":
    ASSERT step.tool_id IS NULL
    ASSERT step.parameters IS EMPTY OR contains only display data
    ASSERT step.risk_level = "NONE"
```

### 2.5 Step Structure Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SAARTHI Plan Step Schema",
  "type": "object",
  "required": ["step_id", "step_type", "description", "risk_level"],
  "properties": {
    "step_id": {
      "type": "string",
      "pattern": "^step_[0-9]{3}$",
      "description": "Unique step identifier (step_001, step_002, ...)"
    },
    "step_type": {
      "type": "string",
      "enum": ["informational", "tool_required", "user_confirmation_required"],
      "description": "Classification of step execution mode"
    },
    "description": {
      "type": "string",
      "maxLength": 500,
      "description": "Human-readable description of the step"
    },
    "tool_id": {
      "type": ["string", "null"],
      "description": "Tool from registry to invoke; null for informational steps"
    },
    "parameters": {
      "type": "object",
      "description": "Tool-specific parameters; must match tool schema"
    },
    "risk_level": {
      "type": "string",
      "enum": ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    },
    "requires_confirmation": {
      "type": "boolean",
      "default": false,
      "description": "Whether user must explicitly approve before execution"
    },
    "conditional": {
      "type": "boolean",
      "default": false,
      "description": "Whether step depends on runtime conditions"
    },
    "preconditions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "condition_id": { "type": "string" },
          "description": { "type": "string" },
          "check_type": { 
            "type": "string",
            "enum": ["file_exists", "app_running", "app_installed", "network_available", "permission_granted", "custom"]
          },
          "check_params": { "type": "object" }
        }
      }
    },
    "on_precondition_fail": {
      "type": "string",
      "enum": ["skip", "abort", "prompt_user"],
      "default": "abort"
    },
    "depends_on": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of step_ids that must complete before this step"
    },
    "rollback_hint": {
      "type": ["string", "null"],
      "description": "Guidance for reversing this step if needed"
    },
    "timeout_ms": {
      "type": "integer",
      "default": 30000,
      "minimum": 1000,
      "maximum": 300000
    },
    "retry_policy": {
      "type": "object",
      "properties": {
        "max_attempts": { "type": "integer", "default": 1, "maximum": 5 },
        "backoff_ms": { "type": "integer", "default": 1000 }
      }
    },
    "user_input_required": {
      "type": "boolean",
      "default": false
    },
    "missing_inputs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "param_name": { "type": "string" },
          "prompt": { "type": "string" },
          "input_type": { "type": "string", "enum": ["text", "choice", "file_path", "confirmation"] }
        }
      }
    }
  },
  "allOf": [
    {
      "if": { "properties": { "step_type": { "const": "informational" } } },
      "then": { 
        "properties": { 
          "tool_id": { "const": null },
          "risk_level": { "const": "NONE" }
        }
      }
    },
    {
      "if": { "properties": { "step_type": { "const": "tool_required" } } },
      "then": { 
        "required": ["tool_id", "parameters"],
        "properties": {
          "tool_id": { "type": "string", "minLength": 1 }
        }
      }
    }
  ]
}
```

### 2.6 Plan Envelope Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SAARTHI Plan Envelope",
  "type": "object",
  "required": ["plan_id", "version", "created_at", "intent_hash", "status", "steps"],
  "properties": {
    "plan_id": {
      "type": "string",
      "format": "uuid"
    },
    "version": {
      "type": "string",
      "const": "1.0"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "intent_hash": {
      "type": "string",
      "description": "SHA-256 hash of the original user intent"
    },
    "intent_summary": {
      "type": "string",
      "maxLength": 200
    },
    "status": {
      "type": "string",
      "enum": ["valid", "rejected", "requires_clarification"]
    },
    "rejection_reason": {
      "type": ["string", "null"],
      "description": "Present only when status is 'rejected'"
    },
    "clarification_needed": {
      "type": ["array", "null"],
      "items": { "type": "string" },
      "description": "Questions to ask user when status is 'requires_clarification'"
    },
    "elevated_risk_warning": {
      "type": "boolean",
      "default": false
    },
    "total_steps": {
      "type": "integer"
    },
    "steps": {
      "type": "array",
      "items": { "$ref": "#/$defs/step" },
      "minItems": 0,
      "maxItems": 50
    },
    "metadata": {
      "type": "object",
      "properties": {
        "estimated_duration_ms": { "type": "integer" },
        "tools_used": { "type": "array", "items": { "type": "string" } },
        "risk_summary": {
          "type": "object",
          "properties": {
            "NONE": { "type": "integer" },
            "LOW": { "type": "integer" },
            "MEDIUM": { "type": "integer" },
            "HIGH": { "type": "integer" },
            "CRITICAL": { "type": "integer" }
          }
        }
      }
    }
  }
}
```

### 2.7 Conditions for Planning Failure

The Planner MUST fail explicitly (status: "rejected") when:

| Failure Condition | Error Code | Response |
|-------------------|------------|----------|
| Intent requests unsupported capability | `UNSUPPORTED_CAPABILITY` | Reject with explanation |
| Intent requires tool not in registry | `UNKNOWN_TOOL_REQUIRED` | Reject; do not suggest |
| Intent is ambiguous after analysis | `AMBIGUOUS_INTENT` | Request clarification |
| Intent requests harmful action | `HARMFUL_INTENT` | Reject categorically |
| Intent requires prohibited system access | `PROHIBITED_ACCESS` | Reject with policy reference |
| Goal cannot be decomposed into finite steps | `UNBOUNDED_GOAL` | Reject; suggest refinement |
| Circular dependency detected | `CIRCULAR_DEPENDENCY` | Reject plan |
| Step count exceeds limit | `PLAN_TOO_COMPLEX` | Reject; suggest decomposition |
| Required context unavailable | `MISSING_CONTEXT` | Request clarification |
| Tool parameters cannot be determined | `INCOMPLETE_PARAMETERS` | Mark as requiring user input |

---

## 3. Planner Prompt Template

### 3.1 System Prompt

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SAARTHI PLANNER SYSTEM PROMPT v1.0                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

You are the PLANNER component of the SAARTHI agentic AI system.

YOUR ROLE:
You analyze user intent and generate execution plans. You are a PURE REASONING 
component. You have NO ability to execute actions, call tools, or affect 
system state.

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE CONSTRAINTS — VIOLATION CAUSES IMMEDIATE REJECTION
═══════════════════════════════════════════════════════════════════════════════

1. OUTPUT FORMAT: You MUST respond with ONLY valid JSON conforming to the 
   Plan Envelope Schema. No markdown, no explanations, no prose. Pure JSON only.

2. TOOL REFERENCES: You may ONLY reference tools that appear in the 
   TOOL_REGISTRY provided below. If a required tool does not exist:
   - DO NOT invent a tool
   - DO NOT suggest a workaround
   - RETURN status: "rejected" with error_code: "UNKNOWN_TOOL_REQUIRED"

3. NO EXECUTION: You have no ability to execute. Do not claim to perform actions.
   Do not use phrases like "I will open..." or "I am launching...". 
   Describe steps the EXECUTOR will perform.

4. NO STATE ASSUMPTIONS: You DO NOT know:
   - Which applications are currently running
   - Which files exist on the system
   - Network connectivity status
   - User's current activity
   
   If a step depends on unknown state, mark it: "conditional": true
   and specify preconditions explicitly.

5. NO HALLUCINATION: If you cannot generate a safe, complete plan:
   - RETURN status: "rejected" with specific reason
   - DO NOT guess, assume, or fabricate steps

═══════════════════════════════════════════════════════════════════════════════
STEP CLASSIFICATION RULES
═══════════════════════════════════════════════════════════════════════════════

Every step MUST be classified as exactly one of:

• "informational" — No tool invocation. Display/explain only.
  - tool_id MUST be null
  - risk_level MUST be "NONE"
  - Use for summaries, confirmations, status updates

• "tool_required" — Requires tool execution by Executor.
  - tool_id MUST reference valid registry entry
  - parameters MUST match tool's parameter schema
  - risk_level MUST be assessed based on tool capability

• "user_confirmation_required" — Requires explicit user approval.
  - Set requires_confirmation: true
  - Provide clear description of what will happen
  - Use for HIGH/CRITICAL risk operations

═══════════════════════════════════════════════════════════════════════════════
RISK LEVEL ASSIGNMENT
═══════════════════════════════════════════════════════════════════════════════

NONE     — Informational only; no system changes
LOW      — Read-only operations; reversible; low impact
MEDIUM   — Writes data; launches apps; potentially reversible
HIGH     — Modifies system state; deletes data; may be irreversible
CRITICAL — Executes system commands; modifies configs; admin operations

HIGH and CRITICAL steps MUST have requires_confirmation: true

═══════════════════════════════════════════════════════════════════════════════
TOOL REGISTRY (ACTIVE FOR THIS SESSION)
═══════════════════════════════════════════════════════════════════════════════

{{TOOL_REGISTRY}}

═══════════════════════════════════════════════════════════════════════════════
OUTPUT SCHEMA REFERENCE
═══════════════════════════════════════════════════════════════════════════════

{
  "plan_id": "<uuid>",
  "version": "1.0",
  "created_at": "<ISO-8601>",
  "intent_hash": "<sha256 of intent>",
  "intent_summary": "<brief description>",
  "status": "valid" | "rejected" | "requires_clarification",
  "rejection_reason": "<if rejected>",
  "clarification_needed": ["<questions if needed>"],
  "elevated_risk_warning": false,
  "total_steps": <count>,
  "steps": [
    {
      "step_id": "step_001",
      "step_type": "informational" | "tool_required" | "user_confirmation_required",
      "description": "<what this step does>",
      "tool_id": "<from registry or null>",
      "parameters": { },
      "risk_level": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": [],
      "rollback_hint": "<optional>",
      "timeout_ms": 30000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    }
  ],
  "metadata": {
    "estimated_duration_ms": <total>,
    "tools_used": ["<tool_ids>"],
    "risk_summary": { "NONE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0 }
  }
}

═══════════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST (APPLY BEFORE RETURNING)
═══════════════════════════════════════════════════════════════════════════════

□ Every tool_id exists in TOOL_REGISTRY
□ Every step has required fields
□ Steps are ordered respecting dependencies
□ No circular dependencies
□ HIGH/CRITICAL steps have requires_confirmation: true
□ Conditional steps have preconditions specified
□ No invented or hallucinated capabilities
□ Output is pure JSON with no surrounding text

═══════════════════════════════════════════════════════════════════════════════
USER INTENT TO PLAN
═══════════════════════════════════════════════════════════════════════════════

{{USER_INTENT}}

```

---

## 4. Executor Logic Definition

### 4.1 Responsibilities

The Executor is responsible for:

| Responsibility | Description |
|----------------|-------------|
| **Plan Reception** | Receiving and validating plan JSON |
| **Step Dispatch** | Executing exactly one step at a time in order |
| **Tool Invocation** | Calling tools with specified parameters |
| **Permission Checking** | Verifying permissions before each step |
| **Precondition Evaluation** | Checking runtime conditions for conditional steps |
| **Result Capture** | Recording success/failure for each step |
| **Failure Handling** | Applying retry logic or safe termination |
| **Progress Reporting** | Communicating status to user and audit log |

### 4.2 Constraints (MUST)

| Constraint ID | Rule |
|---------------|------|
| **EC-01** | MUST execute steps in exact order specified by plan |
| **EC-02** | MUST execute exactly one step at a time |
| **EC-03** | MUST NOT skip steps unless precondition fails with policy "skip" |
| **EC-04** | MUST NOT add, remove, or modify steps |
| **EC-05** | MUST NOT reason about intent or infer additional actions |
| **EC-06** | MUST validate tool_id against local Tool Registry before invocation |
| **EC-07** | MUST check Permission Engine before every tool invocation |
| **EC-08** | MUST respect timeout_ms for each step |
| **EC-09** | MUST report explicit success or failure for every step |
| **EC-10** | MUST halt on unrecoverable failure (fail-closed) |

### 4.3 Prohibitions (MUST NOT)

| Prohibition ID | Rule | Rationale |
|----------------|------|-----------|
| **EP-01** | MUST NOT generate new steps | No planning capability |
| **EP-02** | MUST NOT modify step parameters | Plan is immutable |
| **EP-03** | MUST NOT interpret user intent | Intent already processed |
| **EP-04** | MUST NOT call tools not in plan | Prevents deviation |
| **EP-05** | MUST NOT assume step success | Explicit verification required |
| **EP-06** | MUST NOT continue after critical failure | Fail-closed |
| **EP-07** | MUST NOT bypass permission checks | Security enforcement |
| **EP-08** | MUST NOT execute rejected plans | Status must be "valid" |

### 4.4 Step Execution Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP EXECUTION LIFECYCLE                               │
└─────────────────────────────────────────────────────────────────────────────┘

FOR EACH step IN plan.steps (in order):

┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: VALIDATION                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1.1 Verify step schema conformance                                         │
│      IF invalid → HALT with SCHEMA_ERROR                                    │
│                                                                             │
│  1.2 Verify tool_id exists in local Tool Registry                           │
│      IF not found → HALT with UNKNOWN_TOOL (do not execute)                 │
│                                                                             │
│  1.3 Verify parameters match tool's expected schema                         │
│      IF mismatch → HALT with PARAMETER_ERROR                                │
│                                                                             │
│  1.4 Verify dependencies completed successfully                             │
│      IF dependency failed → Apply on_precondition_fail policy               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: PRECONDITION EVALUATION (if step.conditional = true)               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FOR EACH precondition IN step.preconditions:                               │
│      EVALUATE precondition.check_type with check_params                     │
│      IF precondition NOT satisfied:                                         │
│          SWITCH step.on_precondition_fail:                                  │
│              "skip"       → Mark step SKIPPED, continue to next step        │
│              "abort"      → HALT execution with PRECONDITION_FAILED         │
│              "prompt_user"→ Request user decision, await response           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: PERMISSION CHECK                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  3.1 Query Permission Engine with:                                          │
│      - tool_id                                                              │
│      - parameters                                                           │
│      - risk_level                                                           │
│      - requires_confirmation flag                                           │
│                                                                             │
│  3.2 IF Permission Engine returns DENIED:                                   │
│      → Record denial reason                                                 │
│      → HALT with PERMISSION_DENIED                                          │
│                                                                             │
│  3.3 IF requires_confirmation = true:                                       │
│      → Display confirmation prompt to user                                  │
│      → Await explicit APPROVE/DENY                                          │
│      → IF timeout or DENY → HALT with USER_DENIED                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: EXECUTION                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  4.1 IF step.step_type = "informational":                                   │
│      → Display step.description to user                                     │
│      → Mark step SUCCESS                                                    │
│      → Continue to next step                                                │
│                                                                             │
│  4.2 IF step.step_type = "tool_required":                                   │
│      → Capture pre-execution state (for rollback)                           │
│      → Start timeout timer (step.timeout_ms)                                │
│      → Invoke tool with parameters                                          │
│      → Await result                                                         │
│                                                                             │
│  4.3 IF timeout expires before result:                                      │
│      → Attempt graceful cancellation                                        │
│      → IF cancellation fails → Force terminate                              │
│      → Apply retry_policy if attempts remain                                │
│      → IF no retries → HALT with TIMEOUT                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: RESULT PROCESSING                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  5.1 IF tool returns SUCCESS:                                               │
│      → Record result data                                                   │
│      → Mark step SUCCESS                                                    │
│      → Log to audit                                                         │
│      → Continue to next step                                                │
│                                                                             │
│  5.2 IF tool returns FAILURE:                                               │
│      → Record error details                                                 │
│      → IF retry_policy.max_attempts not exhausted:                          │
│          → Wait retry_policy.backoff_ms                                     │
│          → Retry from PHASE 4                                               │
│      → IF retries exhausted:                                                │
│          → Mark step FAILED                                                 │
│          → Evaluate failure severity                                        │
│          → IF CRITICAL failure → HALT immediately                           │
│          → IF NON-CRITICAL → Apply failure policy                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 6: AUDIT & PROGRESS                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  6.1 Write audit log entry with:                                            │
│      - step_id, step_type, tool_id                                          │
│      - outcome (SUCCESS/FAILED/SKIPPED)                                     │
│      - duration_ms                                                          │
│      - error details (if any)                                               │
│                                                                             │
│  6.2 Update progress indicator                                              │
│                                                                             │
│  6.3 Continue to next step OR finalize if last step                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Retry and Failure Handling Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FAILURE HANDLING DECISION TREE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────┐
                        │  STEP FAILED    │
                        └────────┬────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Retries remaining?     │
                    │  (attempts < max)       │
                    └────────────┬────────────┘
                           │           │
                      YES  │           │  NO
                           ▼           ▼
                  ┌─────────────┐  ┌────────────────────────┐
                  │ WAIT backoff│  │ Classify failure type  │
                  │ RETRY step  │  └───────────┬────────────┘
                  └─────────────┘              │
                                    ┌──────────┴──────────┐
                                    │                     │
                            ┌───────▼───────┐     ┌───────▼───────┐
                            │  RECOVERABLE  │     │    FATAL      │
                            │  (transient)  │     │  (permanent)  │
                            └───────┬───────┘     └───────┬───────┘
                                    │                     │
                                    ▼                     ▼
                        ┌───────────────────┐   ┌─────────────────────┐
                        │ Mark step FAILED  │   │ HALT IMMEDIATELY    │
                        │ Check criticality │   │ Initiate rollback   │
                        └─────────┬─────────┘   │ Report to user      │
                                  │             └─────────────────────┘
                    ┌─────────────┴─────────────┐
                    │                           │
            ┌───────▼───────┐           ┌───────▼───────┐
            │   CRITICAL    │           │  NON-CRITICAL │
            │   step?       │           │   step?       │
            └───────┬───────┘           └───────┬───────┘
                    │                           │
                    ▼                           ▼
          ┌─────────────────────┐     ┌─────────────────────────┐
          │ HALT IMMEDIATELY    │     │ Log failure             │
          │ No partial execution│     │ Continue to next step   │
          │ Initiate rollback   │     │ Mark plan as "partial"  │
          └─────────────────────┘     └─────────────────────────┘


FAILURE CLASSIFICATION:
───────────────────────

FATAL (Always Halt):
• Security violation detected
• Permission system failure
• Unrecognized tool invocation attempt
• Plan schema corruption
• System resource exhaustion

RECOVERABLE (May Continue After Retry Exhaustion):
• Transient network error
• Temporary file lock
• Application not responding (if non-critical step)
• Timeout (if retry available)

ALWAYS HALT CONDITIONS:
• step.risk_level = "CRITICAL" AND step failed
• 3+ consecutive step failures
• Security policy violation
• User requests stop
```

### 4.6 Conditions for Execution Halt

| Halt Condition | Error Code | Behavior |
|----------------|------------|----------|
| Plan status is not "valid" | `INVALID_PLAN_STATUS` | Do not begin execution |
| Unknown tool_id encountered | `UNKNOWN_TOOL` | Halt immediately; do not attempt |
| Parameter schema mismatch | `PARAMETER_ERROR` | Halt immediately |
| Permission denied | `PERMISSION_DENIED` | Halt; log denial |
| User denies confirmation | `USER_DENIED` | Halt; respect user decision |
| Timeout with no retries | `STEP_TIMEOUT` | Halt or skip based on criticality |
| Critical step failure | `CRITICAL_FAILURE` | Halt immediately; trigger rollback |
| Security violation | `SECURITY_VIOLATION` | Halt immediately; lockdown |
| Consecutive failures (3+) | `CASCADING_FAILURE` | Halt; trigger safe-stop |
| User stop command | `USER_STOP` | Halt immediately |

---

## 5. Executor Prompt Template

### 5.1 System Prompt

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                   SAARTHI EXECUTOR SYSTEM PROMPT v1.0                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

You are the EXECUTOR component of the SAARTHI agentic AI system.

YOUR ROLE:
You execute plans produced by the Planner. You are a PURE EXECUTION component.
You have NO reasoning capability. You perform exactly what the plan specifies.

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE CONSTRAINTS — VIOLATION CAUSES IMMEDIATE HALT
═══════════════════════════════════════════════════════════════════════════════

1. PLAN ADHERENCE: You MUST execute EXACTLY the steps in the provided plan.
   - DO NOT add steps
   - DO NOT remove steps
   - DO NOT modify steps
   - DO NOT reorder steps
   - DO NOT interpret intent

2. ONE STEP AT A TIME: Execute each step sequentially. Never parallelize
   unless explicitly marked safe for parallel execution in the plan.

3. NO REASONING: You are not a reasoning engine.
   - DO NOT analyze why a step exists
   - DO NOT question the plan's logic
   - DO NOT infer unstated steps
   - DO NOT "help" by adding related actions

4. TOOL REGISTRY BINDING: You may ONLY invoke tools that:
   - Appear in the plan's tool_id fields
   - Exist in your local TOOL_REGISTRY
   - Pass parameter validation

   IF a tool_id is unknown → HALT IMMEDIATELY. Do not substitute.

5. PERMISSION FIRST: Before EVERY tool invocation:
   - Query Permission Engine
   - IF denied → HALT with PERMISSION_DENIED
   - IF requires_confirmation → Await explicit user approval

6. EXPLICIT OUTCOMES: For every step, report exactly one of:
   - SUCCESS: Step completed as specified
   - FAILED: Step could not complete; include error
   - SKIPPED: Precondition not met; policy was "skip"
   - TIMEOUT: Step exceeded timeout_ms
   - DENIED: Permission or confirmation refused

7. FAIL-CLOSED: When in doubt, HALT. Do not proceed with partial execution.

═══════════════════════════════════════════════════════════════════════════════
EXECUTION PROTOCOL
═══════════════════════════════════════════════════════════════════════════════

FOR EACH step IN plan.steps:

1. VALIDATE
   □ step_id is present and unique
   □ step_type is recognized
   □ tool_id (if present) exists in TOOL_REGISTRY
   □ parameters match tool schema
   □ dependencies (depends_on) have completed successfully
   IF validation fails → HALT

2. CHECK PRECONDITIONS (if step.conditional = true)
   □ Evaluate each precondition
   □ IF failed → Apply on_precondition_fail policy
   □ "skip" → Mark SKIPPED, continue
   □ "abort" → HALT
   □ "prompt_user" → Await decision

3. CHECK PERMISSIONS
   □ Query Permission Engine
   □ IF denied → HALT with PERMISSION_DENIED
   □ IF requires_confirmation → Display prompt, await APPROVE/DENY
   □ IF user denies → HALT with USER_DENIED

4. EXECUTE
   □ IF informational → Display description, mark SUCCESS
   □ IF tool_required → Invoke tool with parameters
   □ Start timeout timer
   □ Await result

5. PROCESS RESULT
   □ IF SUCCESS → Log, continue
   □ IF FAILURE → Check retry_policy
      □ IF retries remain → Wait backoff, retry
      □ IF retries exhausted → Evaluate criticality
         □ CRITICAL → HALT
         □ NON-CRITICAL → Log, continue

6. AUDIT
   □ Log step outcome with all details
   □ Update progress

═══════════════════════════════════════════════════════════════════════════════
TOOL REGISTRY (LOCAL — EXECUTION AUTHORITY)
═══════════════════════════════════════════════════════════════════════════════

{{TOOL_REGISTRY}}

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (Per Step)
═══════════════════════════════════════════════════════════════════════════════

After each step, report:

{
  "step_id": "<from plan>",
  "outcome": "SUCCESS" | "FAILED" | "SKIPPED" | "TIMEOUT" | "DENIED",
  "executed_at": "<ISO-8601>",
  "duration_ms": <actual duration>,
  "tool_invoked": "<tool_id or null>",
  "result_data": { <tool output if any> },
  "error": {
    "code": "<error code>",
    "message": "<human readable>",
    "recoverable": true | false
  } | null,
  "permission_decision": "APPROVED" | "DENIED" | "AUTO" | null,
  "user_confirmation": "APPROVED" | "DENIED" | "NOT_REQUIRED" | null,
  "retries_used": <count>,
  "rollback_available": true | false
}

═══════════════════════════════════════════════════════════════════════════════
FINAL REPORT (After All Steps)
═══════════════════════════════════════════════════════════════════════════════

{
  "plan_id": "<from plan>",
  "execution_status": "COMPLETED" | "PARTIAL" | "HALTED" | "ABORTED",
  "completed_at": "<ISO-8601>",
  "total_steps": <count>,
  "successful_steps": <count>,
  "failed_steps": <count>,
  "skipped_steps": <count>,
  "halt_reason": "<if halted>" | null,
  "step_reports": [ <all step reports> ],
  "rollback_performed": true | false,
  "rollback_details": { } | null
}

═══════════════════════════════════════════════════════════════════════════════
PLAN TO EXECUTE
═══════════════════════════════════════════════════════════════════════════════

{{PLAN_JSON}}

```

---

## 6. Tool Registry Specification

### 6.1 Registry Structure

```json
{
  "registry_version": "1.0",
  "last_updated": "2026-01-19T00:00:00Z",
  "tools": {
    "<tool_id>": {
      "name": "<human readable name>",
      "description": "<what the tool does>",
      "category": "<file|app|input|shell|system|notification>",
      "risk_baseline": "LOW | MEDIUM | HIGH | CRITICAL",
      "requires_confirmation_default": true | false,
      "parameters": {
        "<param_name>": {
          "type": "string | number | boolean | array | object",
          "required": true | false,
          "description": "<what this param does>",
          "constraints": { <validation rules> }
        }
      },
      "returns": {
        "type": "<return type>",
        "description": "<what is returned>"
      },
      "preconditions": ["<what must be true>"],
      "side_effects": ["<what this tool changes>"],
      "rollback_capable": true | false,
      "timeout_default_ms": 30000
    }
  }
}
```

### 6.2 Example Tool Entries

```json
{
  "registry_version": "1.0",
  "last_updated": "2026-01-19T00:00:00Z",
  "tools": {
    "app.launch": {
      "name": "Launch Application",
      "description": "Launches a desktop application by name or path",
      "category": "app",
      "risk_baseline": "LOW",
      "requires_confirmation_default": false,
      "parameters": {
        "app_identifier": {
          "type": "string",
          "required": true,
          "description": "Application name (e.g., 'notepad') or full path",
          "constraints": {
            "pattern": "^[a-zA-Z0-9_.\\-\\\\/: ]+$",
            "maxLength": 500
          }
        },
        "arguments": {
          "type": "array",
          "required": false,
          "description": "Command line arguments to pass",
          "constraints": {
            "maxItems": 20
          }
        },
        "wait_for_window": {
          "type": "boolean",
          "required": false,
          "description": "Whether to wait for app window to appear"
        }
      },
      "returns": {
        "type": "object",
        "description": "Process info including PID and window handle"
      },
      "preconditions": ["Application must be installed"],
      "side_effects": ["Launches new process", "May acquire focus"],
      "rollback_capable": true,
      "timeout_default_ms": 15000
    },

    "app.focus": {
      "name": "Focus Application Window",
      "description": "Brings an application window to foreground",
      "category": "app",
      "risk_baseline": "LOW",
      "requires_confirmation_default": false,
      "parameters": {
        "app_identifier": {
          "type": "string",
          "required": true,
          "description": "Application name or window title pattern"
        }
      },
      "returns": {
        "type": "object",
        "description": "Window handle and focus status"
      },
      "preconditions": ["Application must be running"],
      "side_effects": ["Changes foreground window"],
      "rollback_capable": false,
      "timeout_default_ms": 5000
    },

    "browser.navigate": {
      "name": "Navigate Browser",
      "description": "Opens a URL in the default or specified browser",
      "category": "app",
      "risk_baseline": "LOW",
      "requires_confirmation_default": false,
      "parameters": {
        "url": {
          "type": "string",
          "required": true,
          "description": "URL to navigate to",
          "constraints": {
            "pattern": "^https?://",
            "maxLength": 2000
          }
        },
        "browser": {
          "type": "string",
          "required": false,
          "description": "Specific browser to use (default: system default)"
        },
        "new_window": {
          "type": "boolean",
          "required": false,
          "description": "Open in new window vs new tab"
        }
      },
      "returns": {
        "type": "object",
        "description": "Browser process info"
      },
      "preconditions": ["Browser must be installed", "Network connectivity"],
      "side_effects": ["Opens browser window/tab", "Network request"],
      "rollback_capable": false,
      "timeout_default_ms": 10000
    },

    "keyboard.type": {
      "name": "Type Text",
      "description": "Simulates keyboard input to type text",
      "category": "input",
      "risk_baseline": "MEDIUM",
      "requires_confirmation_default": false,
      "parameters": {
        "text": {
          "type": "string",
          "required": true,
          "description": "Text to type",
          "constraints": {
            "maxLength": 10000
          }
        },
        "delay_ms": {
          "type": "number",
          "required": false,
          "description": "Delay between keystrokes in ms"
        }
      },
      "returns": {
        "type": "object",
        "description": "Typing completion status"
      },
      "preconditions": ["Target window must be focused"],
      "side_effects": ["Inserts text at cursor position"],
      "rollback_capable": false,
      "timeout_default_ms": 60000
    },

    "keyboard.shortcut": {
      "name": "Execute Keyboard Shortcut",
      "description": "Simulates a keyboard shortcut combination",
      "category": "input",
      "risk_baseline": "MEDIUM",
      "requires_confirmation_default": false,
      "parameters": {
        "keys": {
          "type": "array",
          "required": true,
          "description": "Key combination (e.g., ['ctrl', 'c'])",
          "constraints": {
            "minItems": 1,
            "maxItems": 5
          }
        }
      },
      "returns": {
        "type": "object",
        "description": "Shortcut execution status"
      },
      "preconditions": ["Target window must be focused"],
      "side_effects": ["Triggers shortcut action in focused app"],
      "rollback_capable": false,
      "timeout_default_ms": 5000
    },

    "file.read": {
      "name": "Read File",
      "description": "Reads contents of a file",
      "category": "file",
      "risk_baseline": "LOW",
      "requires_confirmation_default": false,
      "parameters": {
        "path": {
          "type": "string",
          "required": true,
          "description": "Absolute file path",
          "constraints": {
            "pattern": "^[a-zA-Z]:\\\\|^/",
            "maxLength": 500
          }
        },
        "encoding": {
          "type": "string",
          "required": false,
          "description": "File encoding (default: utf-8)"
        }
      },
      "returns": {
        "type": "object",
        "description": "File contents and metadata"
      },
      "preconditions": ["File must exist", "Read permission required"],
      "side_effects": [],
      "rollback_capable": false,
      "timeout_default_ms": 10000
    },

    "file.write": {
      "name": "Write File",
      "description": "Writes content to a file",
      "category": "file",
      "risk_baseline": "MEDIUM",
      "requires_confirmation_default": true,
      "parameters": {
        "path": {
          "type": "string",
          "required": true,
          "description": "Absolute file path"
        },
        "content": {
          "type": "string",
          "required": true,
          "description": "Content to write"
        },
        "mode": {
          "type": "string",
          "required": false,
          "description": "Write mode: overwrite, append",
          "constraints": {
            "enum": ["overwrite", "append"]
          }
        }
      },
      "returns": {
        "type": "object",
        "description": "Write status and bytes written"
      },
      "preconditions": ["Directory must exist", "Write permission required"],
      "side_effects": ["Creates or modifies file"],
      "rollback_capable": true,
      "timeout_default_ms": 10000
    },

    "notification.show": {
      "name": "Show Notification",
      "description": "Displays a system notification to the user",
      "category": "notification",
      "risk_baseline": "NONE",
      "requires_confirmation_default": false,
      "parameters": {
        "title": {
          "type": "string",
          "required": true,
          "description": "Notification title",
          "constraints": { "maxLength": 100 }
        },
        "message": {
          "type": "string",
          "required": true,
          "description": "Notification body",
          "constraints": { "maxLength": 500 }
        },
        "type": {
          "type": "string",
          "required": false,
          "description": "Notification type",
          "constraints": { "enum": ["info", "success", "warning", "error"] }
        }
      },
      "returns": {
        "type": "object",
        "description": "Notification ID"
      },
      "preconditions": [],
      "side_effects": ["Displays OS notification"],
      "rollback_capable": false,
      "timeout_default_ms": 5000
    },

    "user.prompt": {
      "name": "Prompt User for Input",
      "description": "Displays a prompt and waits for user input",
      "category": "notification",
      "risk_baseline": "NONE",
      "requires_confirmation_default": false,
      "parameters": {
        "message": {
          "type": "string",
          "required": true,
          "description": "Prompt message"
        },
        "input_type": {
          "type": "string",
          "required": false,
          "description": "Expected input type",
          "constraints": { "enum": ["text", "choice", "confirmation"] }
        },
        "choices": {
          "type": "array",
          "required": false,
          "description": "Options for choice type"
        }
      },
      "returns": {
        "type": "object",
        "description": "User's response"
      },
      "preconditions": [],
      "side_effects": ["Blocks for user input"],
      "rollback_capable": false,
      "timeout_default_ms": 120000
    }
  }
}
```

---

## 7. Worked Examples

### 7.1 Example A: "Plan my week based on these goals"

#### User Intent

```
"Plan my week based on these goals:
1. Complete project report by Wednesday
2. Exercise 3 times
3. Prepare for Friday presentation"
```

#### Analysis

This intent is **primarily informational**. The user is asking for a schedule/plan, not for SAARTHI to execute calendar modifications or file operations. The Planner must:
- Recognize this as a planning/advisory request
- Generate informational steps
- NOT assume calendar tool access
- NOT create files without confirmation

#### Planner Output

```json
{
  "plan_id": "550e8400-e29b-41d4-a716-446655440001",
  "version": "1.0",
  "created_at": "2026-01-19T10:30:00Z",
  "intent_hash": "sha256:a1b2c3d4e5f6...",
  "intent_summary": "Generate weekly schedule based on three goals",
  "status": "valid",
  "rejection_reason": null,
  "clarification_needed": null,
  "elevated_risk_warning": false,
  "total_steps": 5,
  "steps": [
    {
      "step_id": "step_001",
      "step_type": "informational",
      "description": "Acknowledge the three goals received: (1) Complete project report by Wednesday, (2) Exercise 3 times this week, (3) Prepare for Friday presentation.",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": [],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    },
    {
      "step_id": "step_002",
      "step_type": "informational",
      "description": "Present proposed weekly schedule:\n\nMONDAY:\n- Morning: Start project report draft\n- Evening: Exercise session #1\n\nTUESDAY:\n- Continue project report (aim for 60% complete)\n- Begin presentation outline\n\nWEDNESDAY:\n- Morning: Finalize and submit project report (DEADLINE)\n- Evening: Exercise session #2\n\nTHURSDAY:\n- Full day: Prepare presentation slides and rehearse\n\nFRIDAY:\n- Morning: Final presentation rehearsal\n- Scheduled time: Deliver presentation\n- Evening: Exercise session #3",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_001"],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    },
    {
      "step_id": "step_003",
      "step_type": "user_confirmation_required",
      "description": "Ask user: Would you like me to save this schedule to a file?",
      "tool_id": "user.prompt",
      "parameters": {
        "message": "Would you like me to save this weekly schedule to a file?",
        "input_type": "confirmation"
      },
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_002"],
      "rollback_hint": null,
      "timeout_ms": 60000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 },
      "user_input_required": true,
      "missing_inputs": []
    },
    {
      "step_id": "step_004",
      "step_type": "tool_required",
      "description": "If user confirmed, write the schedule to a text file.",
      "tool_id": "file.write",
      "parameters": {
        "path": "{{USER_DOCUMENTS}}/weekly_schedule_2026-01-19.txt",
        "content": "WEEKLY SCHEDULE (Week of Jan 19, 2026)\n\n[Schedule content as above]",
        "mode": "overwrite"
      },
      "risk_level": "MEDIUM",
      "requires_confirmation": true,
      "conditional": true,
      "preconditions": [
        {
          "condition_id": "user_confirmed_save",
          "description": "User confirmed they want to save the schedule",
          "check_type": "custom",
          "check_params": { "depends_on_step": "step_003", "expected_response": true }
        }
      ],
      "on_precondition_fail": "skip",
      "depends_on": ["step_003"],
      "rollback_hint": "Delete the created file",
      "timeout_ms": 10000,
      "retry_policy": { "max_attempts": 2, "backoff_ms": 1000 }
    },
    {
      "step_id": "step_005",
      "step_type": "informational",
      "description": "Summarize completion: Weekly schedule has been presented. Remind user of key deadlines: Report due Wednesday, Presentation on Friday.",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_003"],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    }
  ],
  "metadata": {
    "estimated_duration_ms": 95000,
    "tools_used": ["user.prompt", "file.write"],
    "risk_summary": {
      "NONE": 4,
      "LOW": 0,
      "MEDIUM": 1,
      "HIGH": 0,
      "CRITICAL": 0
    }
  }
}
```

#### Executor Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXECUTION TRACE: Example A                               │
└─────────────────────────────────────────────────────────────────────────────┘

STEP step_001
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  Tool:       (none)
  Action:     Display acknowledgment message
  Permission: Not required (no tool invocation)
  
  EXECUTION:
  → Display: "Acknowledge the three goals received..."
  → Outcome: SUCCESS
  → Duration: 50ms

STEP step_002
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  Tool:       (none)
  Action:     Display proposed schedule
  Permission: Not required (no tool invocation)
  Depends on: step_001 ✓ (completed successfully)
  
  EXECUTION:
  → Display: Full weekly schedule breakdown
  → Outcome: SUCCESS
  → Duration: 100ms

STEP step_003
─────────────────────────────────────────────────────────────────────────────
  Type:       user_confirmation_required
  Tool:       user.prompt
  Action:     Ask user about saving schedule
  Permission: Check required
  Depends on: step_002 ✓
  
  EXECUTION:
  → Validate: tool_id "user.prompt" exists in registry ✓
  → Validate: parameters match schema ✓
  → Permission check: APPROVED (user.prompt is NONE risk)
  → Invoke tool: Display prompt "Would you like me to save..."
  → Await user response...
  
  USER RESPONSE: YES (confirmed)
  
  → Outcome: SUCCESS
  → Result: { "response": true }
  → Duration: 8500ms

STEP step_004
─────────────────────────────────────────────────────────────────────────────
  Type:       tool_required
  Tool:       file.write
  Action:     Write schedule to file
  Permission: Confirmation required (MEDIUM risk + requires_confirmation)
  Depends on: step_003 ✓
  Conditional: true
  
  EXECUTION:
  → Evaluate precondition: "user_confirmed_save"
    → Check step_003 result: response = true ✓
    → Precondition: SATISFIED
  
  → Validate: tool_id "file.write" exists in registry ✓
  → Validate: parameters match schema ✓
  
  → Permission check:
    → Risk level: MEDIUM
    → requires_confirmation: true
    → Display confirmation UI:
      "SAARTHI wants to create file:
       C:\Users\...\Documents\weekly_schedule_2026-01-19.txt
       
       [APPROVE] [DENY]"
    → Await user response...
    
  USER DECISION: APPROVE
  
  → Capture pre-execution state (file does not exist)
  → Invoke tool: file.write with parameters
  → Result: { "success": true, "bytes_written": 456 }
  → Outcome: SUCCESS
  → Duration: 250ms
  → Rollback available: true (can delete file)

STEP step_005
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  Tool:       (none)
  Action:     Display summary
  Permission: Not required
  Depends on: step_003 ✓ (not step_004, so runs regardless of file save)
  
  EXECUTION:
  → Display: "Weekly schedule presented. Key deadlines..."
  → Outcome: SUCCESS
  → Duration: 50ms


═══════════════════════════════════════════════════════════════════════════════
FINAL EXECUTION REPORT
═══════════════════════════════════════════════════════════════════════════════

{
  "plan_id": "550e8400-e29b-41d4-a716-446655440001",
  "execution_status": "COMPLETED",
  "completed_at": "2026-01-19T10:30:12Z",
  "total_steps": 5,
  "successful_steps": 5,
  "failed_steps": 0,
  "skipped_steps": 0,
  "halt_reason": null,
  "rollback_performed": false
}
```

---

### 7.2 Example B: "Open YouTube and play latest podcast"

#### User Intent

```
"Open YouTube and play the latest podcast from Lex Fridman"
```

#### Analysis

This intent requires:
- Launching a browser (or YouTube app)
- Navigating to a specific URL
- Potentially interacting with the page

The Planner must:
- Mark steps as conditional (browser availability unknown)
- NOT assume YouTube is already open
- NOT assume specific DOM structure for clicking
- Handle the fact that "play latest podcast" requires dynamic content

#### Planner Output

```json
{
  "plan_id": "550e8400-e29b-41d4-a716-446655440002",
  "version": "1.0",
  "created_at": "2026-01-19T14:00:00Z",
  "intent_hash": "sha256:b2c3d4e5f6g7...",
  "intent_summary": "Open YouTube and navigate to Lex Fridman podcast channel",
  "status": "valid",
  "rejection_reason": null,
  "clarification_needed": null,
  "elevated_risk_warning": false,
  "total_steps": 6,
  "steps": [
    {
      "step_id": "step_001",
      "step_type": "informational",
      "description": "Acknowledge request: Open YouTube and navigate to Lex Fridman podcast. Note: Automatic video playback depends on page content and cannot be guaranteed.",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": [],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    },
    {
      "step_id": "step_002",
      "step_type": "tool_required",
      "description": "Open default web browser and navigate to Lex Fridman's YouTube channel videos page, sorted by newest.",
      "tool_id": "browser.navigate",
      "parameters": {
        "url": "https://www.youtube.com/@lexfridman/videos?view=0&sort=dd",
        "new_window": false
      },
      "risk_level": "LOW",
      "requires_confirmation": false,
      "conditional": true,
      "preconditions": [
        {
          "condition_id": "network_available",
          "description": "Network connectivity is available",
          "check_type": "network_available",
          "check_params": {}
        },
        {
          "condition_id": "browser_installed",
          "description": "A web browser is installed on the system",
          "check_type": "app_installed",
          "check_params": { "app_category": "web_browser" }
        }
      ],
      "on_precondition_fail": "abort",
      "depends_on": ["step_001"],
      "rollback_hint": "Close the opened browser tab",
      "timeout_ms": 15000,
      "retry_policy": { "max_attempts": 2, "backoff_ms": 2000 }
    },
    {
      "step_id": "step_003",
      "step_type": "informational",
      "description": "Wait for page to load. YouTube channel page should display with videos sorted by newest first.",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_002"],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    },
    {
      "step_id": "step_004",
      "step_type": "user_confirmation_required",
      "description": "Ask user to confirm: The YouTube channel is now open. Would you like me to attempt to click on the first (newest) video? Note: This requires keyboard navigation and may not work if page layout differs.",
      "tool_id": "user.prompt",
      "parameters": {
        "message": "YouTube channel is open. Would you like me to try clicking the first video? (This uses keyboard navigation and may require manual intervention)",
        "input_type": "confirmation"
      },
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_003"],
      "rollback_hint": null,
      "timeout_ms": 60000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 },
      "user_input_required": true
    },
    {
      "step_id": "step_005",
      "step_type": "tool_required",
      "description": "If user confirmed, attempt to play first video by pressing Tab to navigate to video grid, then Enter to select first video.",
      "tool_id": "keyboard.shortcut",
      "parameters": {
        "keys": ["tab"]
      },
      "risk_level": "MEDIUM",
      "requires_confirmation": false,
      "conditional": true,
      "preconditions": [
        {
          "condition_id": "user_confirmed_play",
          "description": "User confirmed attempt to click video",
          "check_type": "custom",
          "check_params": { "depends_on_step": "step_004", "expected_response": true }
        },
        {
          "condition_id": "browser_focused",
          "description": "Browser window is in focus",
          "check_type": "app_running",
          "check_params": { "app_category": "web_browser", "state": "focused" }
        }
      ],
      "on_precondition_fail": "prompt_user",
      "depends_on": ["step_004"],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 3, "backoff_ms": 500 }
    },
    {
      "step_id": "step_006",
      "step_type": "informational",
      "description": "Execution complete. If the video did not auto-play, user may need to manually click on the desired video. The channel page shows videos sorted by newest.",
      "tool_id": null,
      "parameters": {},
      "risk_level": "NONE",
      "requires_confirmation": false,
      "conditional": false,
      "preconditions": [],
      "on_precondition_fail": "abort",
      "depends_on": ["step_002"],
      "rollback_hint": null,
      "timeout_ms": 5000,
      "retry_policy": { "max_attempts": 1, "backoff_ms": 1000 }
    }
  ],
  "metadata": {
    "estimated_duration_ms": 100000,
    "tools_used": ["browser.navigate", "user.prompt", "keyboard.shortcut"],
    "risk_summary": {
      "NONE": 4,
      "LOW": 1,
      "MEDIUM": 1,
      "HIGH": 0,
      "CRITICAL": 0
    }
  }
}
```

#### Executor Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXECUTION TRACE: Example B                               │
└─────────────────────────────────────────────────────────────────────────────┘

STEP step_001
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  EXECUTION:
  → Display acknowledgment
  → Outcome: SUCCESS

STEP step_002
─────────────────────────────────────────────────────────────────────────────
  Type:       tool_required
  Tool:       browser.navigate
  Conditional: true
  
  EXECUTION:
  → Evaluate preconditions:
    → "network_available": Checking... ✓ SATISFIED
    → "browser_installed": Checking... ✓ SATISFIED (Chrome detected)
  
  → Validate: tool_id "browser.navigate" exists in registry ✓
  → Validate: parameters match schema ✓
  → Permission check: APPROVED (LOW risk, no confirmation needed)
  
  → Invoke tool: browser.navigate
    → URL: https://www.youtube.com/@lexfridman/videos?view=0&sort=dd
    → new_window: false
  
  → Result: { "success": true, "browser": "Chrome", "pid": 12345 }
  → Outcome: SUCCESS
  → Duration: 3200ms

STEP step_003
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  EXECUTION:
  → Display: "Waiting for page to load..."
  → Outcome: SUCCESS

STEP step_004
─────────────────────────────────────────────────────────────────────────────
  Type:       user_confirmation_required
  Tool:       user.prompt
  
  EXECUTION:
  → Permission check: APPROVED
  → Invoke tool: user.prompt
  → Display: "YouTube channel is open. Would you like me to try clicking..."
  → Await response...
  
  USER RESPONSE: YES
  
  → Outcome: SUCCESS
  → Result: { "response": true }

STEP step_005
─────────────────────────────────────────────────────────────────────────────
  Type:       tool_required
  Tool:       keyboard.shortcut
  Conditional: true
  
  EXECUTION:
  → Evaluate preconditions:
    → "user_confirmed_play": Check step_004 result = true ✓ SATISFIED
    → "browser_focused": Checking... ✗ NOT SATISFIED (user switched windows)
  
  → on_precondition_fail: "prompt_user"
  → Display: "Browser window is not in focus. Please click on the browser 
              window and confirm when ready."
  → Await user action...
  
  USER ACTION: [Clicked browser window, confirmed ready]
  
  → Re-evaluate precondition: "browser_focused" ✓ SATISFIED
  
  → Validate: tool_id "keyboard.shortcut" exists in registry ✓
  → Permission check: APPROVED (MEDIUM risk, but no confirmation required)
  
  → Invoke tool: keyboard.shortcut
    → keys: ["tab"]
  
  → Result: { "success": true, "keys_sent": ["tab"] }
  → Outcome: SUCCESS
  → Duration: 150ms
  
  NOTE: Video navigation attempted. Actual video playback depends on 
        YouTube's current page state and is not verifiable.

STEP step_006
─────────────────────────────────────────────────────────────────────────────
  Type:       informational
  EXECUTION:
  → Display: "Execution complete. If video did not auto-play..."
  → Outcome: SUCCESS


═══════════════════════════════════════════════════════════════════════════════
FINAL EXECUTION REPORT
═══════════════════════════════════════════════════════════════════════════════

{
  "plan_id": "550e8400-e29b-41d4-a716-446655440002",
  "execution_status": "COMPLETED",
  "completed_at": "2026-01-19T14:01:45Z",
  "total_steps": 6,
  "successful_steps": 6,
  "failed_steps": 0,
  "skipped_steps": 0,
  "halt_reason": null,
  "notes": [
    "Video playback not verified - depends on external page state"
  ]
}
```

#### Failure Scenario: Browser Not Installed

```
STEP step_002 — FAILURE SCENARIO
─────────────────────────────────────────────────────────────────────────────
  Type:       tool_required
  Tool:       browser.navigate
  Conditional: true
  
  EXECUTION:
  → Evaluate preconditions:
    → "network_available": Checking... ✓ SATISFIED
    → "browser_installed": Checking... ✗ NOT SATISFIED
      (No web browser detected on system)
  
  → on_precondition_fail: "abort"
  
  → HALT EXECUTION
  → Reason: PRECONDITION_FAILED
  → Details: "browser_installed check failed - no web browser installed"


═══════════════════════════════════════════════════════════════════════════════
FINAL EXECUTION REPORT (FAILURE)
═══════════════════════════════════════════════════════════════════════════════

{
  "plan_id": "550e8400-e29b-41d4-a716-446655440002",
  "execution_status": "HALTED",
  "completed_at": "2026-01-19T14:00:02Z",
  "total_steps": 6,
  "successful_steps": 1,
  "failed_steps": 1,
  "skipped_steps": 4,
  "halt_reason": "PRECONDITION_FAILED: No web browser installed on system",
  "step_reports": [
    { "step_id": "step_001", "outcome": "SUCCESS" },
    { 
      "step_id": "step_002", 
      "outcome": "FAILED",
      "error": {
        "code": "PRECONDITION_FAILED",
        "message": "browser_installed check failed - no web browser detected",
        "recoverable": false
      }
    }
  ]
}
```

---

## 8. Failure Taxonomy

### 8.1 Planning Failures

| Error Code | Description | Response |
|------------|-------------|----------|
| `UNKNOWN_TOOL_REQUIRED` | Intent requires tool not in registry | Reject plan; no substitution |
| `AMBIGUOUS_INTENT` | Cannot determine clear goal | Request clarification |
| `HARMFUL_INTENT` | Intent violates safety policies | Categorical rejection |
| `UNBOUNDED_GOAL` | Cannot decompose into finite steps | Suggest refinement |
| `CIRCULAR_DEPENDENCY` | Steps have circular requirements | Reject plan |
| `PLAN_TOO_COMPLEX` | Exceeds step limit | Suggest decomposition |
| `MISSING_CONTEXT` | Required information unavailable | Request input |
| `UNSUPPORTED_CAPABILITY` | Beyond system capabilities | Explain limitation |

### 8.2 Execution Failures

| Error Code | Description | Response |
|------------|-------------|----------|
| `INVALID_PLAN_STATUS` | Plan status is not "valid" | Do not execute |
| `UNKNOWN_TOOL` | tool_id not in local registry | Halt immediately |
| `PARAMETER_ERROR` | Parameters fail schema validation | Halt immediately |
| `PERMISSION_DENIED` | Permission Engine denied action | Halt; log denial |
| `USER_DENIED` | User rejected confirmation | Halt; respect decision |
| `STEP_TIMEOUT` | Execution exceeded timeout | Apply retry or halt |
| `PRECONDITION_FAILED` | Runtime condition not met | Apply policy (skip/abort/prompt) |
| `TOOL_ERROR` | Tool execution returned error | Apply retry or halt |
| `CRITICAL_FAILURE` | Critical step failed | Halt; trigger rollback |
| `CASCADING_FAILURE` | 3+ consecutive failures | Halt; trigger safe-stop |
| `SECURITY_VIOLATION` | Security boundary breached | Immediate lockdown |

### 8.3 Validation Rules Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   VALIDATION REJECTION RULES                                │
└─────────────────────────────────────────────────────────────────────────────┘

PLANNER MUST REJECT IF:
───────────────────────
□ Tool does not exist in provided registry
□ Intent requests direct system access not mediated by tools
□ Intent is ambiguous after best-effort interpretation
□ Intent requests actions violating safety policies
□ Plan would exceed 50 steps
□ Plan contains circular dependencies
□ Required parameters cannot be determined or derived

EXECUTOR MUST REJECT/HALT IF:
─────────────────────────────
□ Plan status ≠ "valid"
□ Step contains unknown tool_id
□ Step parameters fail schema validation
□ Permission Engine returns DENIED
□ User explicitly denies confirmation
□ Precondition fails with on_precondition_fail = "abort"
□ Step marked CRITICAL fails execution
□ Three consecutive step failures occur
□ Security policy violation detected

DEFAULT BEHAVIOR ON UNCERTAINTY:
────────────────────────────────
• Planner: REJECT (do not generate speculative plans)
• Executor: HALT (do not execute uncertain steps)
• Both: NEVER assume, invent, or improvise
```

---

## 9. Appendix

### 9.1 JSON Schema Validation Checklist

Before a Planner outputs a plan:

- [ ] `plan_id` is valid UUID v4
- [ ] `version` equals "1.0"
- [ ] `created_at` is valid ISO-8601
- [ ] `status` is one of: valid, rejected, requires_clarification
- [ ] If status = "rejected", `rejection_reason` is present
- [ ] If status = "requires_clarification", `clarification_needed` is array
- [ ] `total_steps` equals `steps.length`
- [ ] Each step has unique `step_id` matching pattern `step_###`
- [ ] Each step has valid `step_type`
- [ ] Each step has `description` ≤ 500 chars
- [ ] Each step has valid `risk_level`
- [ ] If `step_type` = "informational", then `tool_id` is null
- [ ] If `step_type` = "tool_required", then `tool_id` is non-null string
- [ ] All `tool_id` values exist in provided Tool Registry
- [ ] All `depends_on` references exist in earlier steps
- [ ] No circular dependencies exist
- [ ] HIGH/CRITICAL risk steps have `requires_confirmation` = true
- [ ] Conditional steps have non-empty `preconditions`
- [ ] `metadata.tools_used` matches actual tools in steps

### 9.2 Executor Pre-Flight Checklist

Before an Executor begins execution:

- [ ] Plan JSON is well-formed
- [ ] Plan `status` = "valid"
- [ ] All `tool_id` values exist in local Tool Registry
- [ ] All parameter schemas match tool definitions
- [ ] Dependency graph is acyclic
- [ ] Permission Engine is available
- [ ] Audit log is writable
- [ ] User notification channel is open

### 9.3 Glossary

| Term | Definition |
|------|------------|
| **Planner** | Cloud component that generates execution plans from user intent |
| **Executor** | Local component that executes plans step by step |
| **Tool Registry** | Allowlist of available tools with schemas |
| **Step** | Atomic unit of work in a plan |
| **Precondition** | Runtime check that must pass before step execution |
| **Conditional Step** | Step whose execution depends on runtime state |
| **Hallucination** | Generation of non-existent tools or capabilities |
| **Fail-Closed** | Design where uncertainty causes denial/halt |

---

### 9.4 Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-19 | Principal AI Systems Architect | Initial release |

---

**END OF DOCUMENT**
