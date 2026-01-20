# SAARTHI Safety Specification

## Executive Summary

This document defines the comprehensive safety mechanisms and guardrails for SAARTHI, an agentic AI system following a strict Planner–Executor architecture. Safety is treated as a **system invariant**, not a feature.

**Core Philosophy:** The system must always fail in a way that protects the user. When in doubt, do nothing.

---

## Table of Contents

1. [Guardrail Architecture Overview](#1-guardrail-architecture-overview)
2. [Permission Enforcement](#2-permission-enforcement)
3. [Kill Switch Behavior](#3-kill-switch-behavior)
4. [Action Allowlist](#4-action-allowlist)
5. [Rate Limiting & Abuse Prevention](#5-rate-limiting--abuse-prevention)
6. [Safe Error Responses](#6-safe-error-responses)
7. [Failure Scenarios](#7-failure-scenarios)
8. [Safe Shutdown & Degradation Strategy](#8-safe-shutdown--degradation-strategy)
9. [Safety Invariants Checklist](#9-safety-invariants-checklist)

---

## 1. Guardrail Architecture Overview

### 1.1 Defense-in-Depth Model

SAARTHI implements **8 layers of defense**, each capable of independently blocking unsafe actions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SAFETY LAYER STACK                                 │
│                     (Each layer can independently BLOCK)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 8: USER PERMISSION                                                   │
│  └── Final gate: User must explicitly approve every action                  │
│                                                                              │
│  LAYER 7: EXECUTION SANDBOX                                                 │
│  └── Action handlers have no capabilities beyond their specific function    │
│                                                                              │
│  LAYER 6: TEMPORAL VALIDATION                                               │
│  └── Actions expire after 5 minutes, replay attacks blocked                 │
│                                                                              │
│  LAYER 5: PARAMETER SANITIZATION                                            │
│  └── All parameters validated, dangerous patterns rejected                  │
│                                                                              │
│  LAYER 4: SIGNATURE VERIFICATION                                            │
│  └── Cryptographic proof that action came from authorized planner           │
│                                                                              │
│  LAYER 3: ALLOWLIST ENFORCEMENT                                             │
│  └── Only 3 action types permitted, all others rejected                     │
│                                                                              │
│  LAYER 2: SCHEMA VALIDATION                                                 │
│  └── Strict JSON schema, additionalProperties: false                        │
│                                                                              │
│  LAYER 1: TRANSPORT SECURITY                                                │
│  └── HTTPS only, certificate pinning, no plaintext                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Cloud vs Local Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESPONSIBILITY SEPARATION                                 │
├────────────────────────────────┬────────────────────────────────────────────┤
│         CLOUD (Planner)        │           LOCAL (Executor)                 │
├────────────────────────────────┼────────────────────────────────────────────┤
│                                │                                            │
│  ✓ Intent interpretation       │  ✓ ALL permission enforcement              │
│  ✓ Action planning             │  ✓ ALL execution decisions                 │
│  ✓ Response generation         │  ✓ ALL user interactions                   │
│  ✓ Context management          │  ✓ ALL system access                       │
│                                │  ✓ ALL safety validations                  │
│  ✗ NO execution capability     │  ✓ ALL kill switch control                 │
│  ✗ NO system access            │  ✓ ALL audit logging                       │
│  ✗ NO permission granting      │                                            │
│                                │                                            │
├────────────────────────────────┴────────────────────────────────────────────┤
│                                                                              │
│  CRITICAL INVARIANT: Cloud can only SUGGEST. Local DECIDES and EXECUTES.   │
│                                                                              │
│  The cloud has ZERO ability to:                                             │
│  • Force an action                                                          │
│  • Bypass permission checks                                                 │
│  • Access local resources directly                                          │
│  • Override user decisions                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Order of Enforcement

When an action request arrives, checks occur in this **strict order**:

```
ACTION REQUEST ARRIVES
        │
        ▼
┌───────────────────┐
│ 1. TRANSPORT      │ ──▶ Reject if not HTTPS
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 2. SCHEMA         │ ──▶ Reject if malformed JSON
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 3. ALLOWLIST      │ ──▶ Reject if action_type not in allowlist
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 4. SIGNATURE      │ ──▶ Reject if signature invalid
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 5. TIMESTAMP      │ ──▶ Reject if older than 5 minutes
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 6. PARAMETERS     │ ──▶ Reject if dangerous patterns detected
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 7. RATE LIMITS    │ ──▶ Reject if limits exceeded
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 8. USER PERMISSION│ ──▶ Reject if user denies
└───────────────────┘
        │
        ▼
    EXECUTE ACTION

* Any rejection stops the pipeline immediately
* All rejections are logged with reason
* User is notified of relevant rejections
```

---

## 2. Permission Enforcement

### 2.1 Permission Check Locations

| Check Type | Location | Bypass Possible? |
|------------|----------|------------------|
| Action allowlist | Local Executor | ❌ No |
| Schema validation | Local Executor | ❌ No |
| Signature verification | Local Executor | ❌ No |
| Parameter validation | Local Executor | ❌ No |
| User consent dialog | Local Executor | ❌ No |
| Rate limiting | Local Executor | ❌ No |

**All permission checks occur locally. The cloud cannot bypass any check.**

### 2.2 Permission Validation Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERMISSION VALIDATION FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Pre-Validation (Automatic)                                        │
│  ├── Is action_type in allowlist?                                          │
│  ├── Is signature valid?                                                   │
│  ├── Is timestamp fresh?                                                   │
│  └── Are parameters safe?                                                  │
│      │                                                                      │
│      ├── ANY FAIL ──▶ REJECT (no user prompt, log reason)                  │
│      │                                                                      │
│      └── ALL PASS ──▶ Continue to Step 2                                   │
│                                                                              │
│  STEP 2: User Consent Dialog                                                │
│  ├── Show action description (human-readable)                              │
│  ├── Show risk level (NONE/LOW/MEDIUM/HIGH)                                │
│  ├── Show specific parameters (what will happen)                           │
│  ├── Require explicit button click (not Enter key alone)                   │
│  └── Timeout after 60 seconds ──▶ Auto-DENY                                │
│      │                                                                      │
│      ├── USER DENIES ──▶ REJECT (log denial)                               │
│      │                                                                      │
│      └── USER APPROVES ──▶ Continue to Step 3                              │
│                                                                              │
│  STEP 3: Execution Permission                                               │
│  ├── Verify state is still valid                                           │
│  ├── Verify no concurrent action                                           │
│  └── Execute with timeout                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Permission Denial Handling

| Denial Count | System Response |
|--------------|-----------------|
| 1st denial | Log, continue normally |
| 2nd denial (same action) | Log, warn planner |
| 3rd denial (same action) | Log, block this action type for session |
| 5 denials (any actions) | Log, suggest user may want to disable feature |
| 10 denials (any actions) | Log, auto-pause, require user to explicitly resume |

### 2.4 Permission Dialog Requirements

The permission dialog MUST:

- Be **modal** (blocks all other interaction)
- Be **topmost** (cannot be hidden behind other windows)
- Show **exactly what will happen** (no vague descriptions)
- Require **explicit click** (not just pressing Enter)
- Have **Deny as default** (pre-selected)
- **Timeout to Deny** (never timeout to Allow)
- Be **non-dismissable** except via Allow/Deny buttons

---

## 3. Kill Switch Behavior

### 3.1 Kill Switch Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KILL SWITCH TAXONOMY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TYPE 1: USER-TRIGGERED (Immediate)                                        │
│  ├── Tray icon "Exit" button                                               │
│  ├── Keyboard shortcut (Ctrl+Shift+Q or configurable)                      │
│  ├── Clicking recording indicator during voice capture                     │
│  └── Closing permission dialog via X button                                │
│                                                                              │
│  TYPE 2: AUTOMATIC - SAFETY VIOLATIONS                                      │
│  ├── 3+ consecutive validation failures                                    │
│  ├── Signature verification failure                                        │
│  ├── Attempted execution of forbidden action                               │
│  ├── Detection of action injection attempt                                 │
│  └── Memory corruption detected                                            │
│                                                                              │
│  TYPE 3: AUTOMATIC - OPERATIONAL FAILURES                                   │
│  ├── 5+ consecutive action execution failures                              │
│  ├── 10+ permission denials in 5 minutes                                   │
│  ├── Unhandled exception in core loop                                      │
│  ├── Resource exhaustion (memory > 500MB, CPU > 90% for 30s)              │
│  └── Infinite loop detection (same action requested 10x in 1 minute)      │
│                                                                              │
│  TYPE 4: AUTOMATIC - SUBSYSTEM FAILURES                                     │
│  ├── Voice system: 5+ consecutive STT failures                             │
│  ├── Voice system: Recording exceeds max duration                          │
│  ├── Cloud client: 10+ consecutive connection failures                     │
│  └── State machine: Invalid state transition attempted                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Kill Switch Activation Effects

```
KILL SWITCH ACTIVATED
        │
        ▼
┌───────────────────────────────────────┐
│ PHASE 1: IMMEDIATE HALT (< 100ms)     │
├───────────────────────────────────────┤
│ • Cancel all in-progress actions      │
│ • Cancel voice recording              │
│ • Stop TTS output                     │
│ • Close all permission dialogs        │
│ • Set state to EMERGENCY_STOP         │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ PHASE 2: RESOURCE CLEANUP (< 500ms)   │
├───────────────────────────────────────┤
│ • Clear audio buffers                 │
│ • Clear pending action queue          │
│ • Disconnect cloud client             │
│ • Release microphone                  │
│ • Flush logs to disk                  │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ PHASE 3: USER NOTIFICATION            │
├───────────────────────────────────────┤
│ • Show system notification            │
│ • Log shutdown reason                 │
│ • Update tray icon to "stopped"       │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ PHASE 4: SAFE STATE                   │
├───────────────────────────────────────┤
│ • System in SLEEP state               │
│ • Requires explicit user action to    │
│   restart (not automatic)             │
│ • Recovery reason logged              │
└───────────────────────────────────────┘
```

### 3.3 Component Shutdown Order

```
SHUTDOWN SEQUENCE (Ordered by Safety Priority)

1. ACTION HANDLERS      ──▶ Stop immediately, no cleanup
2. VOICE CAPTURE        ──▶ Cancel, clear buffers
3. VOICE TTS            ──▶ Stop playback
4. PERMISSION MANAGER   ──▶ Close dialogs (deny pending)
5. CLOUD CLIENT         ──▶ Disconnect, cancel pending requests
6. STATE MACHINE        ──▶ Transition to SLEEP
7. AUDIT LOGGER         ──▶ Flush, then close (last to preserve logs)
8. TRAY APPLICATION     ──▶ Update icon, keep running for restart

* Each component has 500ms timeout
* If timeout exceeded, force-terminate
* Log any component that fails graceful shutdown
```

### 3.4 Recovery After Kill Switch

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RECOVERY REQUIREMENTS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  RECOVERY REQUIRES EXPLICIT USER ACTION:                                    │
│                                                                              │
│  1. System will NOT auto-restart after kill switch                          │
│  2. User must click "Wake Up" in tray menu                                  │
│  3. If kill was due to safety violation:                                    │
│     └── Show explanation of what happened                                   │
│     └── Require acknowledgment before restart                               │
│  4. If kill was due to repeated failures:                                   │
│     └── Suggest troubleshooting steps                                       │
│     └── Offer to reset to defaults                                          │
│                                                                              │
│  AUTOMATIC RESTART IS NEVER PERMITTED                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Action Allowlist

### 4.1 Allowlist Definition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMPLETE ACTION ALLOWLIST                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ALLOWED ACTIONS (Exhaustive List):                                         │
│                                                                              │
│  1. open_browser_url                                                        │
│     ├── Opens URL in default browser                                        │
│     ├── ONLY http:// and https:// schemes                                   │
│     ├── Forbidden: file://, javascript:, data:, vbscript:                  │
│     └── Forbidden: localhost, 127.0.0.1, internal IPs                       │
│                                                                              │
│  2. play_media_file                                                         │
│     ├── Opens media file with default player                                │
│     ├── ONLY via file picker (user selects file)                           │
│     ├── ONLY audio/video/image types                                       │
│     └── NO direct path execution                                            │
│                                                                              │
│  3. read_file_with_picker                                                   │
│     ├── Reads file content (read-only)                                      │
│     ├── ONLY via file picker (user selects file)                           │
│     ├── User sees exactly which file                                        │
│     └── NO hidden file access                                               │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  FORBIDDEN FOREVER (Cannot be added):                                       │
│                                                                              │
│  • shell_execute          • subprocess_spawn                                │
│  • file_write             • file_delete                                     │
│  • registry_access        • process_inject                                  │
│  • keyboard_simulate      • mouse_simulate                                  │
│  • screen_capture         • clipboard_access                                │
│  • network_scan           • arbitrary_code_exec                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Allowlist Enforcement

```
WHERE ALLOWLIST IS CHECKED:

1. SCHEMA LEVEL
   └── action_type field has enum constraint
   └── Any unlisted type fails JSON Schema validation

2. VALIDATOR LEVEL
   └── Explicit check: action_type in ALLOWED_ACTIONS
   └── Logs rejection with full context

3. HANDLER REGISTRY LEVEL
   └── Registry only contains handlers for allowed actions
   └── Unknown action_type → KeyError → Safe failure

4. HANDLER LEVEL
   └── Each handler validates its own parameters
   └── Refuses to execute if parameters unsafe

TOTAL: 4 independent checks. All must pass.
```

### 4.3 Allowlist Violation Response

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ALLOWLIST VIOLATION RESPONSE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WHEN NON-ALLOWLISTED ACTION REQUESTED:                                     │
│                                                                              │
│  1. IMMEDIATE REJECTION                                                     │
│     └── Action never reaches execution                                      │
│     └── No user prompt (not a permission decision)                          │
│                                                                              │
│  2. SECURITY LOGGING                                                        │
│     └── Log: timestamp, action_type, source, full payload                   │
│     └── Mark as SECURITY_VIOLATION                                          │
│     └── Increment violation counter                                         │
│                                                                              │
│  3. CLOUD NOTIFICATION                                                      │
│     └── Report rejection to cloud (sanitized)                               │
│     └── Cloud can log for analysis                                          │
│     └── Cloud CANNOT override rejection                                     │
│                                                                              │
│  4. ESCALATION (if pattern detected)                                        │
│     └── 3+ violations in 1 minute → Trigger kill switch                     │
│     └── Suggests possible attack or malfunctioning planner                  │
│                                                                              │
│  5. USER VISIBILITY                                                         │
│     └── Notification: "Blocked unsafe action request"                       │
│     └── Details available in security log                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Rate Limiting & Abuse Prevention

### 5.1 Rate Limit Definitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RATE LIMIT MATRIX                                    │
├──────────────────────────┬──────────────────┬───────────────────────────────┤
│ Resource                 │ Limit            │ Window                        │
├──────────────────────────┼──────────────────┼───────────────────────────────┤
│ Planner requests         │ 30 requests      │ per minute                    │
│ Action execution attempts│ 10 actions       │ per minute                    │
│ Permission prompts       │ 5 prompts        │ per minute                    │
│ Same action retry        │ 3 attempts       │ per 5 minutes                 │
│ Failed validations       │ 10 failures      │ per minute                    │
│ Voice recordings         │ 20 recordings    │ per 5 minutes                 │
│ TTS outputs              │ 30 utterances    │ per 5 minutes                 │
│ Cloud connections        │ 5 reconnects     │ per minute                    │
├──────────────────────────┴──────────────────┴───────────────────────────────┤
│                                                                              │
│ SPECIAL LIMITS:                                                             │
│ • Identical action (same type + params): Max 1 per 30 seconds              │
│ • Permission denial (same action): Max 3, then block for session           │
│ • Security violations: Max 3 per session, then kill switch                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Infinite Loop Protection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INFINITE LOOP DETECTION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DETECTION METHODS:                                                         │
│                                                                              │
│  1. REPETITION DETECTION                                                    │
│     └── Same action requested 5+ times in 1 minute                          │
│     └── Action hash computed from type + parameters                         │
│                                                                              │
│  2. PATTERN DETECTION                                                       │
│     └── A → B → A → B pattern repeated 3+ times                             │
│     └── Suggests oscillating retry logic                                    │
│                                                                              │
│  3. EXECUTION TIME DETECTION                                                │
│     └── More than 60 seconds in ACTIVE state                                │
│     └── Single action should never take this long                           │
│                                                                              │
│  4. RESOURCE DETECTION                                                      │
│     └── Memory usage growing continuously                                   │
│     └── Action queue growing without processing                             │
│                                                                              │
│  RESPONSE TO LOOP DETECTION:                                                │
│                                                                              │
│  • Immediately cancel current action                                        │
│  • Clear action queue                                                       │
│  • Notify user: "Detected repeated action pattern, stopping for safety"    │
│  • Log full pattern for debugging                                           │
│  • Transition to SLEEP state                                                │
│  • Require user action to resume                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Rate Limit Exceeded Behavior

```
WHEN RATE LIMIT EXCEEDED:

├── SOFT LIMIT (80% of threshold)
│   └── Log warning
│   └── Continue processing
│   └── No user notification
│
├── HARD LIMIT (100% of threshold)
│   └── Reject new requests
│   └── Notify user: "Too many requests, please wait"
│   └── Show cooldown timer
│   └── Auto-resume after window expires
│
└── ABUSE THRESHOLD (sustained limit for 5+ minutes)
    └── Trigger kill switch
    └── Log as potential abuse
    └── Require manual restart
    └── Show explanation to user
```

---

## 6. Safe Error Responses

### 6.1 Error Classification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ERROR CLASSIFICATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CLASS A: USER-VISIBLE ERRORS                                               │
│  (Show to user with helpful message)                                        │
│  ├── Action denied by user                                                  │
│  ├── Action failed (browser didn't open, etc.)                             │
│  ├── Voice not understood                                                   │
│  ├── Network unavailable                                                    │
│  └── Rate limit exceeded                                                    │
│                                                                              │
│  CLASS B: LOGGED-ONLY ERRORS                                                │
│  (Log internally, show generic message to user)                             │
│  ├── Schema validation failures                                             │
│  ├── Signature verification failures                                        │
│  ├── Internal state errors                                                  │
│  └── Component initialization failures                                      │
│                                                                              │
│  CLASS C: SECURITY ERRORS                                                   │
│  (Log with full context, minimal user message)                              │
│  ├── Allowlist violations                                                   │
│  ├── Injection attempts                                                     │
│  ├── Replay attacks                                                         │
│  └── Privilege escalation attempts                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Error Message Guidelines

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ERROR MESSAGE RULES                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  NEVER INCLUDE:                                                             │
│  ✗ Stack traces                                                             │
│  ✗ File paths (beyond user-selected files)                                  │
│  ✗ Internal function names                                                  │
│  ✗ Configuration values                                                     │
│  ✗ API keys or tokens                                                       │
│  ✗ Network addresses (internal)                                             │
│  ✗ Detailed validation failure reasons                                      │
│                                                                              │
│  ALWAYS INCLUDE:                                                            │
│  ✓ What the user was trying to do                                           │
│  ✓ That it didn't work                                                      │
│  ✓ What they can try instead                                                │
│  ✓ How to get help if needed                                                │
│                                                                              │
│  EXAMPLES:                                                                  │
│                                                                              │
│  ✗ BAD:  "JSONDecodeError at line 47: unexpected token"                    │
│  ✓ GOOD: "Could not process the request. Please try again."                │
│                                                                              │
│  ✗ BAD:  "Invalid signature: expected abc123, got def456"                  │
│  ✓ GOOD: "Request could not be verified. Please try again."                │
│                                                                              │
│  ✗ BAD:  "Action 'shell_execute' not in allowlist"                         │
│  ✓ GOOD: "This action is not supported."                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Partial Failure Handling

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARTIAL FAILURE HANDLING                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PRINCIPLE: Partial failure must never cascade to unsafe state              │
│                                                                              │
│  SCENARIO: Multi-step action partially completes                            │
│  ├── Step 1 succeeds                                                        │
│  ├── Step 2 fails                                                           │
│  └── Step 3 never starts                                                    │
│                                                                              │
│  RESPONSE:                                                                  │
│  ├── Immediately stop processing                                            │
│  ├── Do NOT attempt rollback (could cause more damage)                      │
│  ├── Log exactly what completed and what didn't                            │
│  ├── Tell user: "Action partially completed. Step 2 failed."              │
│  ├── Provide details of what DID happen                                    │
│  └── Suggest manual verification                                            │
│                                                                              │
│  CRITICAL RULE:                                                             │
│  ├── Never hide partial completion                                          │
│  ├── Never pretend full failure when partial success                        │
│  └── User must know exactly what happened                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Failure Scenarios

### 7.1 Scenario: Planner Hallucinates Action

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 1: PLANNER HALLUCINATED ACTION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  Cloud planner sends action_type: "delete_all_files"                        │
│  (This action does not exist in allowlist)                                  │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Layer 2: Schema validation fails (invalid enum value)                  │
│  └── Layer 3: Allowlist check fails (not in ALLOWED_ACTIONS)               │
│  └── Detection time: < 10ms                                                 │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Action rejected before parsing parameters                              │
│  └── No permission dialog shown                                             │
│  └── No execution attempted                                                 │
│  └── Violation counter incremented                                          │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Notification: "Blocked an unsupported action request"                 │
│  └── System continues normal operation                                      │
│  └── No further action required from user                                   │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Log violation with full context                                        │
│  └── Report to cloud (for planner improvement)                              │
│  └── If 3+ violations in 1 minute: trigger kill switch                      │
│  └── Otherwise: continue accepting requests                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Scenario: Malformed JSON from Cloud

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 2: EXECUTOR RECEIVES MALFORMED JSON                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  Cloud sends truncated or corrupted JSON:                                   │
│  {"action_type": "open_browser_url", "parameters": {"url": "https://       │
│  (Connection dropped mid-transmission)                                      │
│                                                                              │
│  DETECTION:                                                                 │
│  └── JSON parse fails with syntax error                                     │
│  └── Detection time: immediate                                              │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Discard entire payload                                                 │
│  └── Do not attempt partial parsing                                         │
│  └── No state changes                                                       │
│  └── Increment failure counter                                              │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── If single occurrence: No notification (transient error)               │
│  └── If repeated: "Communication error with server"                        │
│  └── System remains functional                                              │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Log parse error (without raw payload for security)                     │
│  └── Request retransmission from cloud                                      │
│  └── If 5+ failures in 1 minute: show connection warning                    │
│  └── If 10+ failures: suggest offline mode                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Scenario: User Repeatedly Denies Permissions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 3: USER REPEATEDLY DENIES PERMISSIONS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  User denies permission for same action 5 times                             │
│  (Planner keeps requesting "open_browser_url" to youtube.com)               │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Permission denial counter per action hash                              │
│  └── Pattern: same action_type + similar parameters                         │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── After 3 denials: Block this specific action for session               │
│  └── After 5 denials (any actions): Pause and ask user                     │
│  └── After 10 denials: Trigger kill switch                                 │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── 3rd denial: "You've denied this action multiple times.                │
│       It won't be requested again this session."                            │
│  └── 5th denial: "Multiple actions denied. Would you like to               │
│       pause SAARTHI or continue?"                                           │
│  └── Clear option to continue or stop                                       │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Log pattern for planner improvement                                    │
│  └── Report to cloud: "User repeatedly denied action type X"               │
│  └── Planner should stop requesting blocked actions                         │
│  └── Session block clears on restart                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Scenario: Handler Crashes Mid-Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 4: TOOL CRASHES MID-EXECUTION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  OpenBrowserUrlHandler crashes while launching browser                      │
│  (e.g., default browser was uninstalled)                                    │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Handler raises unhandled exception                                     │
│  └── Execution timeout triggered (30 seconds)                               │
│  └── Handler returns non-success result                                     │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Exception caught at executor level                                     │
│  └── Handler isolated - cannot affect other components                      │
│  └── State machine transitions to LISTENING (not ACTIVE)                   │
│  └── No partial execution left running                                      │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Notification: "Could not open browser. Is a browser installed?"       │
│  └── No technical details exposed                                           │
│  └── System remains functional                                              │
│  └── Other actions still work                                               │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Log full exception (internal only)                                     │
│  └── Report failure to cloud                                                │
│  └── Increment failure counter for this handler                             │
│  └── If handler fails 5x: disable it for session, notify user              │
│  └── Continue processing other action types                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Scenario: Cloud Becomes Unreachable

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 5: CLOUD BECOMES UNREACHABLE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  Network disconnected, cloud server down, or firewall blocks               │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Connection timeout (30 seconds)                                        │
│  └── HTTP error responses (5xx)                                             │
│  └── DNS resolution failure                                                 │
│  └── Certificate validation failure                                         │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Stop polling for new actions                                           │
│  └── Do not retry aggressively (exponential backoff)                       │
│  └── Do not queue actions locally                                           │
│  └── Preserve current safe state                                            │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Tray icon changes to indicate offline status                          │
│  └── Notification: "SAARTHI is offline. Will reconnect when available."   │
│  └── System remains running but idle                                        │
│  └── Local features (voice input) may still work                           │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Exponential backoff: 5s → 10s → 30s → 60s → 5min                      │
│  └── When connection restored: notify user                                  │
│  └── Resume normal operation                                                │
│  └── Do NOT replay queued actions (stale)                                   │
│  └── Require fresh requests from cloud                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.6 Scenario: Voice Subsystem Misbehaves

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 6: VOICE SUBSYSTEM MISBEHAVES                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  Voice module behaves unexpectedly:                                         │
│  • Recording doesn't stop                                                   │
│  • STT returns nonsensical output                                           │
│  • TTS speaks unexpected content                                            │
│  • Audio buffer grows unbounded                                             │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Recording exceeds max_duration (30s)                                   │
│  └── STT confidence < 30% repeatedly                                        │
│  └── Audio buffer > 10MB                                                    │
│  └── Voice state inconsistent with user input                               │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Immediately cancel recording                                           │
│  └── Clear all audio buffers (overwrite with zeros)                        │
│  └── Stop TTS output                                                        │
│  └── Disable voice module                                                   │
│  └── Core system continues without voice                                    │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Recording indicator disappears                                         │
│  └── Notification: "Voice features disabled due to an error."             │
│  └── "You can re-enable voice in settings when ready."                     │
│  └── Text input still works normally                                        │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Voice disabled for session                                             │
│  └── Log detailed error for debugging                                       │
│  └── User must manually re-enable via settings                              │
│  └── On re-enable: fresh initialization                                     │
│  └── If fails again: suggest checking microphone settings                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.7 Scenario: Action Injection Attempt

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 7: ACTION INJECTION ATTEMPT                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  Malicious actor attempts to inject action via:                             │
│  • Compromised cloud endpoint                                               │
│  • Man-in-the-middle attack                                                 │
│  • Local process sending fake actions                                       │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Signature verification fails                                           │
│  └── Action origin doesn't match expected source                            │
│  └── Timestamp indicates replay attack                                      │
│  └── Parameters contain known attack patterns                               │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Immediate rejection (no processing)                                    │
│  └── All pending actions cleared                                            │
│  └── Cloud connection terminated                                            │
│  └── Kill switch triggered                                                  │
│  └── Full audit log captured                                                │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Notification: "SAARTHI detected a security issue and stopped."        │
│  └── "Please restart when you're ready."                                   │
│  └── No technical details exposed                                           │
│  └── Suggest checking for system compromise                                 │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Requires explicit user restart                                         │
│  └── Show security warning on restart                                       │
│  └── Require acknowledgment before resuming                                 │
│  └── Consider recommending security scan                                    │
│  └── Log preserved for forensic analysis                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.8 Scenario: Memory Exhaustion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO 8: MEMORY EXHAUSTION                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SITUATION:                                                                 │
│  System memory usage exceeds safe limits:                                   │
│  • Audio buffers not cleared                                                │
│  • Log accumulation                                                         │
│  • Memory leak in component                                                 │
│                                                                              │
│  DETECTION:                                                                 │
│  └── Memory monitor: usage > 500MB                                          │
│  └── Memory growth rate > 10MB/minute                                       │
│  └── System memory pressure detected                                        │
│                                                                              │
│  CONTAINMENT:                                                               │
│  └── Immediately clear all buffers                                          │
│  └── Force garbage collection                                               │
│  └── If still high: disable non-essential features                          │
│  └── If critical: trigger graceful shutdown                                 │
│                                                                              │
│  USER-FACING BEHAVIOR:                                                      │
│  └── Warning: "SAARTHI is using high memory. Restarting..."               │
│  └── Automatic graceful shutdown                                            │
│  └── Suggest restart for fresh state                                        │
│                                                                              │
│  SYSTEM RECOVERY:                                                           │
│  └── Clean shutdown preserving logs                                         │
│  └── On restart: start fresh                                                │
│  └── If recurs: log for debugging, suggest support                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Safe Shutdown & Degradation Strategy

### 8.1 Graceful Shutdown Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GRACEFUL SHUTDOWN SEQUENCE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: STOP NEW WORK (immediate)                                        │
│  ├── Set accepting_new_work = false                                        │
│  ├── Reject any new action requests                                         │
│  ├── Cancel pending permission dialogs (deny)                               │
│  └── Stop polling cloud for actions                                         │
│                                                                              │
│  PHASE 2: STOP IN-PROGRESS WORK (< 5 seconds)                               │
│  ├── Signal action handlers to stop                                         │
│  ├── Wait up to 5 seconds for completion                                    │
│  ├── If not complete: force terminate                                       │
│  ├── Cancel voice recording                                                 │
│  └── Stop TTS output                                                        │
│                                                                              │
│  PHASE 3: CLEANUP RESOURCES (< 2 seconds)                                   │
│  ├── Clear audio buffers (zero-fill)                                        │
│  ├── Clear action queue                                                     │
│  ├── Disconnect cloud client                                                │
│  ├── Release microphone                                                     │
│  └── Release other system resources                                         │
│                                                                              │
│  PHASE 4: PRESERVE STATE (< 2 seconds)                                      │
│  ├── Flush logs to disk                                                     │
│  ├── Save configuration                                                     │
│  ├── Record shutdown reason                                                 │
│  └── Record timestamp                                                       │
│                                                                              │
│  PHASE 5: EXIT (< 1 second)                                                 │
│  ├── Stop tray icon                                                         │
│  ├── Final log entry                                                        │
│  └── Process exit                                                           │
│                                                                              │
│  TOTAL SHUTDOWN TIME: < 10 seconds                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 What Happens to In-Progress Work

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  IN-PROGRESS WORK DURING SHUTDOWN                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ACTION EXECUTION IN PROGRESS:                                              │
│  ├── If browser opening: Let complete (already launched)                   │
│  ├── If file picker open: Close picker, action cancelled                   │
│  ├── If file reading: Cancel read, partial data discarded                  │
│  └── Log what was interrupted                                               │
│                                                                              │
│  PERMISSION DIALOG OPEN:                                                    │
│  ├── Close dialog                                                           │
│  ├── Treat as DENIED                                                        │
│  └── Log that permission was interrupted                                    │
│                                                                              │
│  VOICE RECORDING IN PROGRESS:                                               │
│  ├── Immediately cancel recording                                           │
│  ├── Clear all audio buffers                                                │
│  ├── Release microphone                                                     │
│  └── Audio is NEVER preserved on shutdown                                   │
│                                                                              │
│  VOICE TTS IN PROGRESS:                                                     │
│  ├── Stop speech immediately                                                │
│  ├── May cut off mid-word                                                   │
│  └── Clean stop, no residual sound                                          │
│                                                                              │
│  CLOUD COMMUNICATION IN PROGRESS:                                           │
│  ├── Cancel pending requests                                                │
│  ├── Do not wait for response                                               │
│  ├── Do not retry                                                           │
│  └── Report incomplete transmission in logs                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Degradation Levels

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GRACEFUL DEGRADATION LEVELS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LEVEL 0: FULL OPERATION                                                    │
│  ├── All features available                                                 │
│  ├── Cloud connected                                                        │
│  ├── Voice enabled (if configured)                                          │
│  └── Normal operation                                                       │
│                                                                              │
│  LEVEL 1: DEGRADED - VOICE DISABLED                                         │
│  ├── Voice subsystem failed or misbehaving                                  │
│  ├── Text input still works                                                 │
│  ├── Actions still execute                                                  │
│  └── User notified, can re-enable manually                                  │
│                                                                              │
│  LEVEL 2: DEGRADED - OFFLINE MODE                                           │
│  ├── Cloud unreachable                                                      │
│  ├── No new actions from planner                                            │
│  ├── Local features still work                                              │
│  ├── Will auto-reconnect when possible                                      │
│  └── User notified of offline status                                        │
│                                                                              │
│  LEVEL 3: DEGRADED - SAFE MODE                                              │
│  ├── Multiple failures detected                                             │
│  ├── Only essential features enabled                                        │
│  ├── Conservative rate limits                                               │
│  ├── Extra confirmation required                                            │
│  └── User should restart for full function                                  │
│                                                                              │
│  LEVEL 4: PAUSED                                                            │
│  ├── Too many failures or denials                                           │
│  ├── System stopped processing                                              │
│  ├── Tray icon shows paused state                                           │
│  ├── Requires explicit "Resume" from user                                   │
│  └── Safe state, no actions possible                                        │
│                                                                              │
│  LEVEL 5: EMERGENCY STOP                                                    │
│  ├── Kill switch triggered                                                  │
│  ├── All features disabled                                                  │
│  ├── Waiting for user to restart                                            │
│  ├── No automatic recovery                                                  │
│  └── Safest possible state                                                  │
│                                                                              │
│  TRANSITIONS:                                                               │
│  ├── Can degrade from any level to any lower level                          │
│  ├── Can only RECOVER through explicit user action                          │
│  ├── Never auto-recover from LEVEL 4 or LEVEL 5                            │
│  └── Degradation is logged with reason                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.4 Memory and Audio Handling on Shutdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 MEMORY & AUDIO CLEANUP ON SHUTDOWN                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AUDIO BUFFERS:                                                             │
│  ├── All audio data MUST be cleared before exit                             │
│  ├── Clear = overwrite with zeros, then free                                │
│  ├── Never persist audio to disk during shutdown                            │
│  ├── Microphone released before exit                                        │
│  └── Verified: no audio survives shutdown                                   │
│                                                                              │
│  ACTION QUEUE:                                                              │
│  ├── Queue emptied without processing                                       │
│  ├── Pending actions logged as "not executed"                               │
│  ├── Cloud notified of incomplete actions                                   │
│  └── No queue persistence across restarts                                   │
│                                                                              │
│  TEMPORARY DATA:                                                            │
│  ├── All temp files deleted                                                 │
│  ├── Memory caches cleared                                                  │
│  ├── Session state cleared                                                  │
│  └── Sensitive data zeroed before free                                      │
│                                                                              │
│  PERSISTENT DATA (preserved):                                               │
│  ├── Audit logs (for security review)                                       │
│  ├── Configuration (for restart)                                            │
│  ├── Shutdown reason (for diagnostics)                                      │
│  └── User preferences (for convenience)                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Safety Invariants Checklist

### Pre-Deployment Verification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SAFETY INVARIANTS CHECKLIST                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER CONTROL:                                                              │
│  □ User can stop system at any time via tray icon                           │
│  □ User can stop system via keyboard shortcut                               │
│  □ User can deny any action                                                 │
│  □ User can disable voice at any time                                       │
│  □ User can uninstall without leaving residue                               │
│                                                                              │
│  NO SILENT FAILURES:                                                        │
│  □ Every error results in user notification or log                          │
│  □ No exception is silently swallowed                                       │
│  □ Partial failures are reported as partial                                 │
│  □ System state is always visible via tray icon                             │
│                                                                              │
│  NO UNCONTROLLED LOOPS:                                                     │
│  □ All loops have maximum iteration counts                                  │
│  □ Retry logic has exponential backoff                                      │
│  □ Repetition detection is active                                           │
│  □ Rate limits prevent runaway behavior                                     │
│                                                                              │
│  NO PRIVILEGE ESCALATION:                                                   │
│  □ Allowlist is hardcoded, not configurable                                 │
│  □ No action can grant new capabilities                                     │
│  □ Cloud cannot modify local permissions                                    │
│  □ No dynamic code execution                                                │
│                                                                              │
│  NO HIDDEN BEHAVIOR:                                                        │
│  □ All actions require visible permission dialog                            │
│  □ Recording indicator always visible when mic active                       │
│  □ No background threads that access resources                              │
│  □ All network communication logged                                         │
│                                                                              │
│  FAIL CLOSED:                                                               │
│  □ Any validation failure results in rejection                              │
│  □ Timeout results in rejection, not retry                                  │
│  □ Ambiguous input results in no action                                     │
│  □ Silence results in no action                                             │
│  □ Error results in safe state, not undefined behavior                      │
│                                                                              │
│  RECOVERY REQUIRES USER:                                                    │
│  □ Kill switch requires manual restart                                      │
│  □ Paused state requires explicit resume                                    │
│  □ Disabled features require explicit re-enable                             │
│  □ No automatic recovery from safety states                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-21 | SAARTHI Safety Team | Initial specification |

---

## Approval

This specification requires sign-off from:

- [ ] Security Team Lead
- [ ] Privacy Officer
- [ ] Platform Safety Reviewer
- [ ] Engineering Lead
- [ ] Product Owner

---

*Safety is not a feature. It is a system invariant.*
