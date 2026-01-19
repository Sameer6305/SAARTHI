# SAARTHI — Ethical Memory System Specification

**Version:** 1.0  
**Date:** January 19, 2026  
**Classification:** Privacy-Critical Design Specification  
**Status:** Production Design

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Memory Architecture Overview](#2-memory-architecture-overview)
3. [Memory Schemas](#3-memory-schemas)
4. [What Gets Stored vs NOT Stored](#4-what-gets-stored-vs-not-stored)
5. [Memory Lifecycle Rules](#5-memory-lifecycle-rules)
6. [Example Memory Entries](#6-example-memory-entries)
7. [Safety Invariants](#7-safety-invariants)
8. [Appendix](#8-appendix)

---

## 1. Design Philosophy

### 1.1 Core Principles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY SYSTEM DESIGN PRINCIPLES                          │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │   "Memory exists to improve usefulness, not to maximize retention"  │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

PRINCIPLE 1: DATA MINIMIZATION
──────────────────────────────
Store the MINIMUM information necessary to improve future interactions.
If uncertain whether to store → DO NOT STORE.

PRINCIPLE 2: ABSTRACTION OVER RAW DATA
──────────────────────────────────────
Store learned patterns, preferences, and summaries.
NEVER store raw inputs, transcripts, or recordings.

PRINCIPLE 3: USER SOVEREIGNTY
─────────────────────────────
User owns all memory. User controls all memory.
System is a steward, not an owner.

PRINCIPLE 4: INTENTIONAL WRITES
───────────────────────────────
No implicit, passive, or background memory collection.
Every write has explicit intent and user awareness.

PRINCIPLE 5: FORGETTING AS FEATURE
──────────────────────────────────
Forgetting is intentional, not accidental.
Short-term memory SHOULD expire.
Long-term memory SHOULD be deletable.

PRINCIPLE 6: PURPOSE-BOUND READS
────────────────────────────────
Memory is read only when relevant to active task.
No speculative retrieval. No profiling. No inference beyond task.
```

### 1.2 Trust Model

| Actor | Trust Level | Memory Access |
|-------|-------------|---------------|
| **User** | Root Trust | Full read, write, delete authority |
| **Local Executor** | High Trust | Read STM; Read LTM (purpose-bound); Write to sync queue |
| **Cloud Planner** | Limited Trust | Read LTM (via abstraction API); No direct write |
| **External Services** | Zero Trust | No memory access |

---

## 2. Memory Architecture Overview

### 2.1 System Topology

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       SAARTHI MEMORY ARCHITECTURE                            │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOCAL CLIENT                                   │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    SHORT-TERM MEMORY (STM)                            │  │
│  │                                                                       │  │
│  │  LOCATION:    Local RAM only (never persisted)                        │  │
│  │  SCOPE:       Single session or task                                  │  │
│  │  LIFETIME:    Session end OR task completion OR timeout               │  │
│  │  ENCRYPTION:  In-memory encryption (defense-in-depth)                 │  │
│  │  ACCESS:      Local Executor only                                     │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Session Context                                                │  │  │
│  │  │  • Current task state                                           │  │  │
│  │  │  • Pending action queue                                         │  │  │
│  │  │  • Recent intent summaries (last N turns)                       │  │  │
│  │  │  • Temporary computation results                                │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    LOCAL MEMORY CACHE                                 │  │
│  │                                                                       │  │
│  │  LOCATION:    Encrypted local storage                                 │  │
│  │  SCOPE:       Recently accessed LTM entries                           │  │
│  │  LIFETIME:    LRU eviction OR session end                             │  │
│  │  ENCRYPTION:  AES-256-GCM with local key                              │  │
│  │  ACCESS:      Local Executor (read-only from cloud perspective)       │  │
│  │                                                                       │  │
│  │  PURPOSE:     Reduce cloud dependency; enable offline operation       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    MEMORY WRITE QUEUE                                 │  │
│  │                                                                       │  │
│  │  LOCATION:    Local (encrypted, temporary)                            │  │
│  │  PURPOSE:     Stage approved memory writes before cloud sync          │  │
│  │  REVIEW:      All entries subject to user review before sync          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Secure Sync (mTLS)
                                     │ (User-approved writes only)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD SERVICES                                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                 LONG-TERM VECTOR MEMORY (LTM)                         │  │
│  │                                                                       │  │
│  │  LOCATION:    Cloud vector database (user-isolated namespace)         │  │
│  │  SCOPE:       Cross-session persistent memory                         │  │
│  │  LIFETIME:    Until user deletion                                     │  │
│  │  ENCRYPTION:  Encrypted at rest + in transit                          │  │
│  │  ACCESS:      Cloud Planner (read via abstraction API)                │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Preference Memory                                              │  │  │
│  │  │  • Communication style preferences                              │  │  │
│  │  │  • Tool usage patterns                                          │  │  │
│  │  │  • Workflow preferences                                         │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Approval Pattern Memory                                        │  │  │
│  │  │  • Action type → typical user decision                          │  │  │
│  │  │  • Risk threshold patterns                                      │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Interaction Summary Memory                                     │  │  │
│  │  │  • Generalized task patterns                                    │  │  │
│  │  │  • Error recovery learnings                                     │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    MEMORY ABSTRACTION API                             │  │
│  │                                                                       │  │
│  │  • Planner queries memory via semantic similarity                     │  │
│  │  • Returns only relevant, purpose-matched entries                     │  │
│  │  • No bulk export, no full enumeration                                │  │
│  │  • Query intent logged for audit                                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Memory Type Comparison

| Property | Short-Term Memory (STM) | Long-Term Memory (LTM) |
|----------|-------------------------|------------------------|
| **Location** | Local RAM only | Cloud vector store |
| **Persistence** | Volatile (session-bound) | Persistent (until deleted) |
| **Encryption** | In-memory encryption | At-rest + in-transit |
| **Scope** | Single session/task | Cross-session |
| **Content** | Task state, recent context | Abstractions, preferences |
| **Write Authority** | Automatic (system) | User-approved only |
| **Read Authority** | Local Executor | Planner via API |
| **Deletion** | Automatic on session end | User-initiated only |
| **Auditability** | Session logs | Full audit trail |

### 2.3 Access Control Matrix

| Memory Type | User | Local Executor | Cloud Planner | External |
|-------------|------|----------------|---------------|----------|
| **STM Read** | ✓ (inspect) | ✓ | ✗ | ✗ |
| **STM Write** | ✗ (system only) | ✓ | ✗ | ✗ |
| **STM Delete** | ✓ (clear session) | ✓ (auto-expire) | ✗ | ✗ |
| **LTM Read** | ✓ (full access) | ✓ (purpose-bound) | ✓ (via API) | ✗ |
| **LTM Write** | ✓ (direct) | ✓ (queued + approved) | ✗ | ✗ |
| **LTM Delete** | ✓ (authoritative) | ✗ | ✗ | ✗ |

---

## 3. Memory Schemas

### 3.1 Short-Term Memory Entry Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SHORT-TERM MEMORY ENTRY SCHEMA                           │
└─────────────────────────────────────────────────────────────────────────────┘

ENTRY STRUCTURE:
{
  // === IDENTIFICATION ===
  "stm_id": "<uuid>",                    // Unique entry identifier
  "session_id": "<uuid>",                // Parent session
  "created_at": "<ISO-8601>",            // Creation timestamp
  "expires_at": "<ISO-8601>",            // Automatic expiration
  
  // === CLASSIFICATION ===
  "entry_type": "<enum>",                // Type of memory entry
    // ALLOWED VALUES:
    // - "task_state"        : Current task execution state
    // - "intent_summary"    : Summarized user intent (NOT transcript)
    // - "context_window"    : Recent interaction context
    // - "computation_temp"  : Temporary computation results
    // - "pending_action"    : Queued actions awaiting execution
  
  // === CONTENT ===
  "content": {
    // Type-specific content (see sub-schemas below)
  },
  
  // === METADATA ===
  "metadata": {
    "source": "<enum>",                  // Origin of entry
      // ALLOWED VALUES:
      // - "user_input"      : Derived from user input
      // - "system_derived"  : System-generated
      // - "execution_result": Result of action execution
    "ttl_seconds": <integer>,            // Time-to-live
    "access_count": <integer>,           // Read access counter
    "last_accessed": "<ISO-8601>"        // Last access timestamp
  },
  
  // === CONSTRAINTS ===
  "constraints": {
    "max_size_bytes": 10240,             // 10KB per entry max
    "prohibits_pii": true,               // No PII allowed
    "prohibits_raw_input": true,         // No verbatim user text
    "auto_expire": true                  // Must auto-expire
  }
}
```

#### 3.1.1 Sub-Schema: Task State

```
"content": {
  "task_id": "<uuid>",
  "task_description": "<summarized, max 200 chars>",
  "current_step_id": "<step_id>",
  "completed_steps": ["<step_id>", ...],
  "pending_steps": ["<step_id>", ...],
  "execution_status": "in_progress | paused | completed | failed",
  "error_summary": "<if failed, abstracted error>",
  "started_at": "<ISO-8601>",
  "progress_percent": <0-100>
}
```

#### 3.1.2 Sub-Schema: Intent Summary

```
"content": {
  "intent_id": "<uuid>",
  "intent_category": "<enum>",           // e.g., "file_operation", "app_control"
  "intent_summary": "<abstracted, max 150 chars>",
  "confidence_score": <0.0-1.0>,
  "requires_tools": ["<tool_id>", ...],
  "risk_assessment": "LOW | MEDIUM | HIGH",
  "user_confirmed": <boolean>
}

// CRITICAL: intent_summary is ABSTRACTED, not verbatim.
// WRONG: "User said: Open my taxes folder and find the 2024 return"
// RIGHT: "File navigation request: locate specific document in user folder"
```

#### 3.1.3 Sub-Schema: Context Window

```
"content": {
  "window_size": <integer>,              // Number of turns represented
  "turn_summaries": [
    {
      "turn_id": <integer>,
      "actor": "user | system",
      "summary": "<abstracted, max 100 chars>",
      "outcome": "success | failure | pending",
      "timestamp": "<ISO-8601>"
    }
  ],
  "active_entities": ["<abstracted references>"],
  "session_goal_summary": "<if identified, max 200 chars>"
}

// CRITICAL: turn_summaries contain ABSTRACTIONS, never transcripts.
// WRONG: turn_summaries contains "User: Can you open Chrome and go to gmail"
// RIGHT: turn_summaries contains "Browser navigation request to email service"
```

### 3.2 Long-Term Memory Entry Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LONG-TERM MEMORY ENTRY SCHEMA                            │
└─────────────────────────────────────────────────────────────────────────────┘

ENTRY STRUCTURE:
{
  // === IDENTIFICATION ===
  "ltm_id": "<uuid>",                    // Unique entry identifier
  "user_id": "<user_namespace>",         // User isolation
  "created_at": "<ISO-8601>",            // Creation timestamp
  "updated_at": "<ISO-8601>",            // Last modification
  "version": <integer>,                  // Entry version (for updates)
  
  // === CLASSIFICATION ===
  "memory_type": "<enum>",               // Type of long-term memory
    // ALLOWED VALUES:
    // - "preference"        : User preference or setting
    // - "approval_pattern"  : Learned approval/denial pattern
    // - "interaction_summary": Generalized interaction learning
    // - "error_recovery"    : Learned error handling pattern
  
  // === VECTOR EMBEDDING ===
  "embedding": {
    "vector": [<float>, ...],            // Semantic embedding (1536-dim)
    "model_version": "<embedding_model>",// Model used for embedding
    "embedding_date": "<ISO-8601>"       // When embedded
  },
  
  // === CONTENT ===
  "content": {
    // Type-specific content (see sub-schemas below)
  },
  
  // === PROVENANCE ===
  "provenance": {
    "source_type": "<enum>",             // How this memory was created
      // ALLOWED VALUES:
      // - "user_explicit"   : User explicitly saved this
      // - "user_approved"   : System proposed, user approved
      // - "aggregated"      : Derived from multiple interactions
    "source_session_count": <integer>,   // Sessions contributing to this
    "confidence": <0.0-1.0>,             // Confidence in this memory
    "last_validated": "<ISO-8601>",      // Last user validation
    "creation_reason": "<max 200 chars>" // Why this was stored
  },
  
  // === ACCESS CONTROL ===
  "access": {
    "read_count": <integer>,             // Times accessed
    "last_read": "<ISO-8601>",           // Last access
    "purpose_log": [                     // Audit trail of access purposes
      {
        "timestamp": "<ISO-8601>",
        "purpose": "<max 100 chars>",
        "requester": "planner | executor"
      }
    ]
  },
  
  // === LIFECYCLE ===
  "lifecycle": {
    "status": "active | deprecated | pending_deletion",
    "deprecation_reason": "<if deprecated>",
    "scheduled_review": "<ISO-8601>",    // Next review date
    "decay_score": <0.0-1.0>             // Relevance decay
  },
  
  // === CONSTRAINTS ===
  "constraints": {
    "max_size_bytes": 4096,              // 4KB per entry max
    "prohibits_pii": true,
    "prohibits_raw_content": true,
    "requires_abstraction": true,
    "deletion_authority": "user_only"
  }
}
```

#### 3.2.1 Sub-Schema: Preference Memory

```
"content": {
  "preference_category": "<enum>",
    // ALLOWED VALUES:
    // - "communication_style" : How user prefers responses
    // - "tool_preference"     : Preferred tools for tasks
    // - "workflow_pattern"    : Preferred task sequences
    // - "timing_preference"   : Preferred times/durations
    // - "confirmation_level"  : How much confirmation desired
  
  "preference_key": "<identifier>",      // What preference this is
  "preference_value": "<abstracted>",    // The preference (abstracted)
  "strength": <0.0-1.0>,                 // How strong this preference is
  "observation_count": <integer>,        // Times this was observed
  "example_context": "<abstracted, max 100 chars>"
}

// EXAMPLE (VALID):
{
  "preference_category": "communication_style",
  "preference_key": "response_verbosity",
  "preference_value": "concise",
  "strength": 0.85,
  "observation_count": 12,
  "example_context": "User frequently requested shorter explanations"
}

// EXAMPLE (INVALID - too specific):
{
  "preference_category": "workflow_pattern",
  "preference_key": "morning_routine",
  "preference_value": "Opens Gmail, then Slack, then VS Code at 9am",  // TOO SPECIFIC
  "example_context": "User said 'every morning I open Gmail first'"   // RAW QUOTE
}
```

#### 3.2.2 Sub-Schema: Approval Pattern Memory

```
"content": {
  "action_category": "<tool_category>",  // Category of action
  "action_pattern": "<abstracted>",      // Generalized action description
  "typical_decision": "approve | deny | ask",
  "decision_confidence": <0.0-1.0>,
  "context_factors": [                   // What influences decision
    {
      "factor": "<abstracted>",
      "weight": <0.0-1.0>
    }
  ],
  "observation_count": <integer>,
  "last_observed": "<ISO-8601>"
}

// EXAMPLE (VALID):
{
  "action_category": "file_operations",
  "action_pattern": "read operations in document folders",
  "typical_decision": "approve",
  "decision_confidence": 0.92,
  "context_factors": [
    { "factor": "low_risk_level", "weight": 0.8 },
    { "factor": "user_initiated", "weight": 0.9 }
  ],
  "observation_count": 24,
  "last_observed": "2026-01-15T10:30:00Z"
}
```

#### 3.2.3 Sub-Schema: Interaction Summary Memory

```
"content": {
  "pattern_type": "<enum>",
    // ALLOWED VALUES:
    // - "task_success_pattern"  : What makes tasks succeed
    // - "task_failure_pattern"  : Common failure modes
    // - "clarification_pattern" : When clarification helps
    // - "workflow_efficiency"   : Efficient task sequences
  
  "pattern_description": "<abstracted, max 200 chars>",
  "applicability": "<when this pattern applies>",
  "success_correlation": <0.0-1.0>,
  "observation_count": <integer>,
  "generalization_level": "specific | moderate | general"
}
```

---

## 4. What Gets Stored vs NOT Stored

### 4.1 Storage Decision Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STORAGE DECISION FLOWCHART                               │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────────────┐
                        │  Candidate Data for   │
                        │       Storage         │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ Is it on the DENYLIST?│
                        └───────────┬───────────┘
                               │         │
                          YES  │         │  NO
                               ▼         ▼
                    ┌─────────────┐  ┌───────────────────────┐
                    │   REJECT    │  │ Is it on the ALLOWLIST?│
                    │  (No store) │  └───────────┬───────────┘
                    └─────────────┘         │         │
                                       YES  │         │  NO
                                            ▼         ▼
                              ┌─────────────────┐  ┌─────────────┐
                              │ Can it be       │  │   REJECT    │
                              │ ABSTRACTED?     │  │ (Not allowed)│
                              └────────┬────────┘  └─────────────┘
                                  │         │
                             YES  │         │  NO
                                  ▼         ▼
                    ┌─────────────────┐  ┌─────────────┐
                    │ Is storage      │  │   REJECT    │
                    │ USER-APPROVED?  │  │ (Raw data)  │
                    └────────┬────────┘  └─────────────┘
                        │         │
                   YES  │         │  NO
                        ▼         ▼
              ┌─────────────────┐  ┌─────────────────┐
              │     STORE       │  │ Queue for user  │
              │  (Abstracted)   │  │    approval     │
              └─────────────────┘  └─────────────────┘
```

### 4.2 ALLOWLIST — What CAN Be Stored

| Category | Storable Content | Storage Type | Rationale |
|----------|------------------|--------------|-----------|
| **Communication Preferences** | Response length preference, formality level, explanation depth | LTM | Improves interaction quality |
| **Tool Preferences** | Preferred browser, preferred editor (by category, not name) | LTM | Reduces confirmation friction |
| **Approval Patterns** | "User typically approves low-risk file reads" | LTM | Learns trust boundaries |
| **Workflow Patterns** | "User prefers step-by-step confirmation for multi-step tasks" | LTM | Adapts to user style |
| **Error Recovery Patterns** | "Retry with simplified approach when X fails" | LTM | Improves reliability |
| **Task State** | Current step, pending actions, progress | STM | Enables task continuity |
| **Intent Summary** | Abstracted goal description | STM | Maintains context |
| **Session Context** | Turn count, active entities (abstracted) | STM | Enables coherent sessions |

#### 4.2.1 Abstraction Requirements

Every stored item MUST be abstracted according to these rules:

| Raw Data | ❌ FORBIDDEN | ✅ ACCEPTABLE ABSTRACTION |
|----------|--------------|---------------------------|
| "Open my taxes folder" | Store verbatim | "File navigation: document folder access" |
| "Search for John Smith email" | Store verbatim | "Email search: contact lookup" |
| "My password is abc123" | Store anything | (NEVER STORE - immediate discard) |
| "I prefer Chrome" | "I prefer Chrome" | "Browser preference: Chromium-based" |
| "Every morning at 9am" | "Every morning at 9am" | "Timing preference: morning, early" |
| User said "yes" to file delete | "User said yes" | "Approval pattern: file delete, approved" |

### 4.3 DENYLIST — What MUST NEVER Be Stored

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ABSOLUTE STORAGE PROHIBITIONS                            ║
║                     (Violation is a critical failure)                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

| Category | Prohibited Content | Rationale | Enforcement |
|----------|-------------------|-----------|-------------|
| **Raw Audio** | Voice recordings, audio files, waveforms | Privacy; biometric data | Discard after STT |
| **Raw Transcripts** | Verbatim user speech or text | Privacy; re-identification risk | Abstract immediately |
| **File Contents** | Document text, file data, attachments | Data minimization | Never capture |
| **Screenshots** | Screen captures, window images | Surveillance risk | Never capture |
| **Keystrokes** | Raw keyboard input logs | Surveillance; credential risk | Never capture |
| **Credentials** | Passwords, tokens, API keys, secrets | Security critical | Immediate discard |
| **OS Action Logs** | Detailed logs of mouse/keyboard actions | Surveillance risk | Discard after execution |
| **File Paths** | Full absolute file paths | Privacy; structure exposure | Generalize to patterns |
| **Contact Details** | Names, emails, phone numbers | PII protection | Never store |
| **Location Data** | GPS, addresses, place names | Privacy; tracking risk | Never store |
| **Financial Data** | Account numbers, transactions | Security; compliance | Never store |
| **Health Information** | Medical data, health status | Regulatory; sensitivity | Never store |
| **Biometric Data** | Fingerprints, face data, voice prints | Identity risk | Never store |
| **Conversation History** | Full chat logs, message archives | Privacy; storage creep | Abstract only |
| **Browsing History** | URLs visited, search queries | Privacy; profiling risk | Never store |
| **Application State** | Window positions, open tabs, etc. | Surveillance risk | Session-only if needed |

### 4.4 Detailed Denylist Rationale

#### 4.4.1 Raw Audio

```
STATUS: ABSOLUTELY PROHIBITED

WHY:
• Audio contains biometric voiceprint data
• May capture background conversations (third-party privacy)
• Can be used for voice cloning/impersonation
• Regulatory risk (wiretapping laws, GDPR voice data)

ENFORCEMENT:
• Audio is processed by STT in a streaming pipeline
• Raw audio buffers are overwritten immediately after processing
• No audio file is ever created on disk
• STT output (text) is immediately abstracted before any storage
```

#### 4.4.2 Full Conversation Transcripts

```
STATUS: ABSOLUTELY PROHIBITED

WHY:
• Contains verbatim user statements (re-identification)
• May contain incidental PII ("my SSN is...")
• Enables surveillance if compromised
• Not necessary for system improvement (abstractions suffice)

ENFORCEMENT:
• User input is immediately summarized into intent
• Original text is discarded after intent extraction
• Only intent category + confidence stored in STM
• No mechanism exists to retrieve original text
```

#### 4.4.3 File Paths and Contents

```
STATUS: ABSOLUTELY PROHIBITED

WHY:
• File paths reveal folder structure (privacy)
• Paths may contain username, project names
• Contents may contain any type of sensitive data
• File access patterns are surveillance data

ENFORCEMENT:
• File operations use opaque handles internally
• Paths are generalized: "/Users/X/Documents/taxes/2024.pdf" 
  → "document folder: financial category"
• Contents are NEVER read into memory for storage
• Only operation type and abstracted location stored
```

### 4.5 Edge Cases and Decisions

| Scenario | Decision | Rationale |
|----------|----------|-----------|
| User explicitly says "Remember my name is John" | DENY storage of name | PII prohibition is absolute |
| User frequently uses specific app | Store as "preference: productivity app category" | Abstracted, not specific |
| User's voice has distinctive accent | NEVER store | Biometric data |
| Task requires remembering a meeting time | STM only, abstracted as "scheduled task: afternoon" | Temporary, abstracted |
| User corrects system error | Store abstracted error recovery pattern | Improves system |
| User makes same request daily | Store as "recurring task pattern: daily, morning" | Abstracted frequency |

---

## 5. Memory Lifecycle Rules

### 5.1 Memory Write Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY WRITE LIFECYCLE                              │
└─────────────────────────────────────────────────────────────────────────────┘

SHORT-TERM MEMORY WRITES:
─────────────────────────

WHEN:
• Session starts → Initialize session context
• User provides input → Store intent summary (abstracted)
• Task begins → Store task state
• Step completes → Update task state
• Error occurs → Store error summary (abstracted)

AUTHORIZATION:
• Automatic (system-managed)
• No user approval required (volatile, session-scoped)
• Bounded by STM constraints (size, TTL, no PII)

VALIDATION:
• Schema validation before write
• Denylist check before write
• Abstraction verification before write


LONG-TERM MEMORY WRITES:
────────────────────────

WHEN:
• Pattern observed repeatedly (threshold: 5+ observations)
• User explicitly requests "remember this preference"
• System proposes memory, user approves
• Session ends with learnable pattern detected

AUTHORIZATION:
• User approval REQUIRED for all LTM writes
• System proposes → User reviews → User approves/rejects
• No silent or background LTM writes

PROCESS:
1. System identifies candidate pattern
2. System abstracts pattern (remove specifics)
3. System adds to Memory Write Queue (local)
4. User is notified of pending memory
5. User reviews proposed memory entry
6. User approves → Sync to LTM
   User rejects → Discard permanently
7. Approved entry is synced to cloud LTM

NEVER:
• Write to LTM without user awareness
• Write raw data to LTM (even if user approves)
• Write to LTM from cloud Planner (local only)
```

### 5.2 Memory Read Rules

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY READ LIFECYCLE                               │
└─────────────────────────────────────────────────────────────────────────────┘

SHORT-TERM MEMORY READS:
────────────────────────

WHO:     Local Executor only
WHEN:    During active task execution
PURPOSE: Maintain session continuity, track progress
LOGGING: Access count updated; no detailed audit (volatile data)


LONG-TERM MEMORY READS:
───────────────────────

WHO:     Cloud Planner (via API), Local Executor (via cache)
WHEN:    When generating plan that benefits from context
PURPOSE: Must be stated explicitly in query
LOGGING: Full audit trail (timestamp, purpose, requester)

PROCESS:
1. Planner/Executor formulates memory query
2. Query includes explicit PURPOSE statement
3. Memory API performs semantic search
4. Only entries with similarity > threshold returned
5. Entries returned are PURPOSE-MATCHED (no speculative data)
6. Access logged in entry's purpose_log

CONSTRAINTS:
• No bulk export (max 10 entries per query)
• No enumeration (no "list all memories")
• No speculative retrieval (purpose must match)
• Read-only for Planner (cannot modify via API)
```

### 5.3 Memory Update Rules

```
LONG-TERM MEMORY UPDATES:
─────────────────────────

WHEN UPDATES OCCUR:
• Pattern strengthens (more observations)
• User explicitly corrects a preference
• Confidence score changes significantly
• Entry becomes stale and needs refresh

UPDATE AUTHORIZATION:
• Strengthening updates: Automatic (within bounds)
• Content changes: User approval required
• Confidence adjustments: Automatic (algorithm-driven)
• User corrections: Immediate (user-initiated)

VERSION CONTROL:
• Each update increments version number
• Previous version NOT retained (no history hoarding)
• Updated_at timestamp reflects latest change
```

### 5.4 Memory Expiration and Deletion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY EXPIRATION & DELETION                             │
└─────────────────────────────────────────────────────────────────────────────┘

SHORT-TERM MEMORY EXPIRATION:
─────────────────────────────

AUTOMATIC EXPIRATION TRIGGERS:
• Session ends → All STM cleared
• Task completes → Task-specific STM cleared
• TTL expires → Entry removed
• Memory pressure → LRU eviction

VERIFICATION:
• Memory buffers overwritten (not just dereferenced)
• No recovery mechanism exists
• Expiration is automatic and guaranteed


LONG-TERM MEMORY DELETION:
──────────────────────────

DELETION AUTHORITY:
• User is SOLE authority for LTM deletion
• System cannot delete user memory
• No automatic expiration (unless user configures)

DELETION TYPES:
1. Single Entry Deletion
   • User selects specific memory
   • Immediate removal from vector store
   • Embedding vectors overwritten
   
2. Category Deletion
   • User selects memory type (e.g., "all preferences")
   • Batch removal of matching entries
   
3. Full Memory Wipe
   • User requests complete LTM deletion
   • All entries in user namespace removed
   • Namespace itself preserved (for future use)

DELETION VERIFICATION:
• Deletion is IRREVERSIBLE (no recycle bin)
• Deleted vectors are overwritten with zeros
• Deletion confirmed in audit log
• User receives confirmation
• No backup retention of deleted memories

DECAY AND DEPRECATION:
• Entries unused for 180+ days → decay_score increases
• High decay entries → flagged for user review
• User can: confirm (reset decay), delete, or ignore
• Ignored entries remain but are de-prioritized
```

### 5.5 Memory Lifecycle State Machine

```
                              ┌─────────────────┐
                              │   CANDIDATE     │
                              │   (Proposed)    │
                              └────────┬────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │                           │
                   User Approves              User Rejects
                         │                           │
                         ▼                           ▼
              ┌─────────────────┐          ┌─────────────────┐
              │     ACTIVE      │          │    DISCARDED    │
              │   (In LTM)      │          │   (Permanent)   │
              └────────┬────────┘          └─────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
     Strengthened   Decayed    User Deletes
         │             │             │
         ▼             ▼             ▼
   ┌───────────┐ ┌───────────┐ ┌─────────────────┐
   │  ACTIVE   │ │DEPRECATED │ │     DELETED     │
   │ (Updated) │ │(Low prio) │ │   (Permanent)   │
   └───────────┘ └─────┬─────┘ └─────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
         User Confirms     User Ignores
              │                 │
              ▼                 ▼
       ┌───────────┐     ┌───────────┐
       │  ACTIVE   │     │DEPRECATED │
       │ (Renewed) │     │ (Remains) │
       └───────────┘     └───────────┘
```

---

## 6. Example Memory Entries

### 6.1 Short-Term Memory Example

```json
{
  "stm_id": "stm_7f8a9b0c-1d2e-3f4a-5b6c-7d8e9f0a1b2c",
  "session_id": "sess_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "created_at": "2026-01-19T14:30:00Z",
  "expires_at": "2026-01-19T15:30:00Z",
  
  "entry_type": "intent_summary",
  
  "content": {
    "intent_id": "int_001",
    "intent_category": "file_operation",
    "intent_summary": "Document access request: user documents folder, specific file type",
    "confidence_score": 0.89,
    "requires_tools": ["file.read"],
    "risk_assessment": "LOW",
    "user_confirmed": true
  },
  
  "metadata": {
    "source": "user_input",
    "ttl_seconds": 3600,
    "access_count": 2,
    "last_accessed": "2026-01-19T14:32:00Z"
  },
  
  "constraints": {
    "max_size_bytes": 10240,
    "prohibits_pii": true,
    "prohibits_raw_input": true,
    "auto_expire": true
  }
}
```

**What this entry DOES:**
- Stores that user requested file access (abstracted)
- Tracks confidence and risk assessment
- Enables task continuity within session
- Auto-expires in 1 hour

**What this entry DOES NOT contain:**
- The actual file name or path
- The verbatim user request
- Any identifying information

---

### 6.2 Long-Term Memory Example

```json
{
  "ltm_id": "ltm_3e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b",
  "user_id": "user_ns_abc123",
  "created_at": "2026-01-10T09:00:00Z",
  "updated_at": "2026-01-19T14:00:00Z",
  "version": 3,
  
  "memory_type": "preference",
  
  "embedding": {
    "vector": [0.0234, -0.0891, 0.1456, "... (1536 dimensions)"],
    "model_version": "text-embedding-3-small",
    "embedding_date": "2026-01-10T09:00:00Z"
  },
  
  "content": {
    "preference_category": "confirmation_level",
    "preference_key": "file_operations_confirmation",
    "preference_value": "minimal_for_read_operations",
    "strength": 0.87,
    "observation_count": 18,
    "example_context": "User typically approves read operations without detailed review"
  },
  
  "provenance": {
    "source_type": "aggregated",
    "source_session_count": 12,
    "confidence": 0.87,
    "last_validated": "2026-01-15T10:00:00Z",
    "creation_reason": "Consistent approval pattern for low-risk file reads"
  },
  
  "access": {
    "read_count": 8,
    "last_read": "2026-01-19T14:00:00Z",
    "purpose_log": [
      {
        "timestamp": "2026-01-19T14:00:00Z",
        "purpose": "Determine confirmation level for file read request",
        "requester": "planner"
      }
    ]
  },
  
  "lifecycle": {
    "status": "active",
    "deprecation_reason": null,
    "scheduled_review": "2026-04-10T00:00:00Z",
    "decay_score": 0.1
  },
  
  "constraints": {
    "max_size_bytes": 4096,
    "prohibits_pii": true,
    "prohibits_raw_content": true,
    "requires_abstraction": true,
    "deletion_authority": "user_only"
  }
}
```

**What this entry DOES:**
- Stores user's preference for minimal confirmation on reads
- Tracks how this preference was learned (18 observations)
- Enables system to adapt confirmation behavior
- Maintains full audit trail of access

**What this entry DOES NOT contain:**
- Which specific files were accessed
- When the user works (time patterns)
- Any quotes from user conversations

---

### 6.3 Rejected Memory Example

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REJECTED MEMORY ENTRY EXAMPLE                            │
└─────────────────────────────────────────────────────────────────────────────┘

PROPOSED MEMORY (FROM SYSTEM):
{
  "memory_type": "preference",
  "content": {
    "preference_category": "workflow_pattern",
    "preference_key": "morning_routine",
    "preference_value": "Opens Chrome to Gmail at 9:15am, then Slack, then VS Code",
    "strength": 0.95,
    "observation_count": 20
  }
}

REJECTION DECISION: REJECT

REJECTION REASONS:

1. SPECIFICITY VIOLATION
   ───────────────────────
   "Opens Chrome to Gmail at 9:15am" is too specific.
   
   CONTAINS:
   • Specific application name (Chrome)
   • Specific service name (Gmail)
   • Specific time (9:15am)
   • Specific sequence (Chrome → Slack → VS Code)
   
   This level of detail enables:
   • Activity profiling
   • Routine surveillance
   • Presence detection

2. DENYLIST VIOLATION
   ───────────────────
   This entry effectively stores:
   • Browsing pattern (which sites/services)
   • Schedule information (when user works)
   • Application usage log

3. ABSTRACTION FAILURE
   ────────────────────
   Entry should have been abstracted to:
   
   {
     "preference_category": "workflow_pattern",
     "preference_key": "session_start_pattern",
     "preference_value": "multi_app_sequential_startup",
     "strength": 0.95,
     "observation_count": 20,
     "example_context": "User prefers launching multiple productivity tools at session start"
   }
   
   This abstracted version:
   • Does not reveal which apps
   • Does not reveal timing
   • Does not reveal order
   • Still enables useful adaptation

SYSTEM RESPONSE:
• Proposed memory discarded
• Abstracted version created as alternative
• Alternative presented to user for approval
• If user rejects abstracted version: nothing stored
```

---

## 7. Safety Invariants

### 7.1 Invariant Definitions

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MEMORY SYSTEM SAFETY INVARIANTS                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

INVARIANT M-001: NO RAW DATA PERSISTENCE
────────────────────────────────────────
STATEMENT: Raw user input, audio, or file contents must never persist 
           beyond immediate processing.

ENFORCEMENT:
• Audio buffers overwritten after STT
• Text input discarded after intent extraction
• File contents never loaded into memory system
• Verification: Memory dumps contain no raw strings


INVARIANT M-002: ABSTRACTION BEFORE STORAGE
───────────────────────────────────────────
STATEMENT: All stored data must be abstracted to remove identifying 
           details before any persistence.

ENFORCEMENT:
• Abstraction function applied before STM write
• Abstraction verification before LTM queue
• Schema validation rejects non-abstracted content
• Verification: Regex patterns detect forbidden specifics


INVARIANT M-003: USER APPROVAL FOR PERSISTENCE
──────────────────────────────────────────────
STATEMENT: No data may be written to LTM without explicit user approval.

ENFORCEMENT:
• All LTM writes go through approval queue
• Queue entries expire after 24 hours if not reviewed
• No background or silent writes
• Verification: Audit log shows approval for every LTM entry


INVARIANT M-004: PURPOSE-BOUND READS
────────────────────────────────────
STATEMENT: Memory reads must have explicit, logged purpose. No 
           speculative or bulk retrieval.

ENFORCEMENT:
• Query API requires purpose parameter
• Purpose logged in access audit
• Max 10 results per query
• No enumeration or export endpoints


INVARIANT M-005: IRREVERSIBLE DELETION
──────────────────────────────────────
STATEMENT: Deleted memories must be unrecoverable. No soft delete, 
           no recycle bin, no backup retention.

ENFORCEMENT:
• Deletion overwrites vectors with zeros
• No version history retained
• No backup includes deleted entries
• Verification: Deleted IDs return 404 permanently


INVARIANT M-006: USER-ONLY DELETION AUTHORITY
─────────────────────────────────────────────
STATEMENT: Only the user may delete LTM entries. System cannot 
           delete user memories.

ENFORCEMENT:
• Delete API requires user authentication
• No system-initiated deletion pathways
• Admin access cannot delete user memories
• Verification: Deletion audit shows user-initiated only


INVARIANT M-007: FORGETTING IS DEFAULT
──────────────────────────────────────
STATEMENT: Memory should expire and decay by default. Persistence 
           requires affirmative action.

ENFORCEMENT:
• STM auto-expires (TTL)
• LTM decay_score increases with non-use
• High-decay entries flagged for review
• Default is non-persistence; storage is exception
```

### 7.2 Invariant Verification

| Invariant | Verification Method | Frequency |
|-----------|---------------------|-----------|
| M-001 | Memory dump analysis for raw strings | Per session |
| M-002 | Schema validation + regex detection | Per write |
| M-003 | Audit log analysis for unapproved writes | Daily |
| M-004 | Query log analysis for purpose presence | Per query |
| M-005 | Attempt to retrieve deleted IDs | Per deletion |
| M-006 | Audit log analysis for non-user deletions | Daily |
| M-007 | Decay score distribution analysis | Weekly |

---

## 8. Appendix

### 8.1 Abstraction Guidelines

| Data Type | Raw Example | Abstracted Form |
|-----------|-------------|-----------------|
| File path | `/Users/john/Documents/taxes/2024.pdf` | `document folder: financial category` |
| App name | `Google Chrome` | `web browser` |
| Person name | `John Smith` | (NEVER STORE) |
| Time | `9:15 AM every day` | `morning, recurring` |
| URL | `https://gmail.com` | `email service` |
| Email address | `john@example.com` | (NEVER STORE) |
| Search query | `how to file taxes` | `information seeking: financial topic` |
| Voice command | "Open my photos from last vacation" | `media access request: personal photos` |

### 8.2 Glossary

| Term | Definition |
|------|------------|
| **STM** | Short-Term Memory; volatile, session-scoped |
| **LTM** | Long-Term Memory; persistent vector store |
| **Abstraction** | Process of removing identifying details |
| **Decay Score** | Measure of memory staleness (0=fresh, 1=stale) |
| **Purpose-Bound** | Access limited to stated, logged purpose |
| **Provenance** | Record of how memory was created |

### 8.3 Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-19 | Principal AI Systems Architect | Initial release |

---

**END OF DOCUMENT**
