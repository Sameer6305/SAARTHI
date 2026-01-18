# SAARTHI — System Architecture Document

**Version:** 1.0  
**Date:** January 19, 2026  
**Classification:** Principal Architecture Specification  
**Status:** Production Design

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architectural Principles](#2-architectural-principles)
3. [Component Diagram](#3-component-diagram)
4. [End-to-End Data Flow](#4-end-to-end-data-flow)
5. [Security, Trust, and Isolation Boundaries](#5-security-trust-and-isolation-boundaries)
6. [Agent Operational States](#6-agent-operational-states)
7. [Memory Architecture](#7-memory-architecture)
8. [Failure, Safety, and Recovery Strategy](#8-failure-safety-and-recovery-strategy)
9. [Observability and Auditability](#9-observability-and-auditability)
10. [Appendix](#10-appendix)

---

## 1. Executive Summary

SAARTHI (Secure Agentic Assistant for Reasoning, Tasks, and Human Interaction) is a Planner–Executor AI system designed to operate as a secure desktop OS agent. The architecture enforces a strict separation between cognition (cloud) and action (local), ensuring that all OS-level operations remain under local control with explicit user consent.

### Core Design Tenets

| Principle | Description |
|-----------|-------------|
| **Cognition–Action Separation** | Cloud reasons and plans; Local validates and executes |
| **Zero-Trust Cloud Execution** | Cloud may never directly invoke OS actions |
| **Explicit Consent** | Every sensitive action requires verified permission |
| **Minimal Attack Surface** | Local client exposes no direct network endpoints |
| **Auditability** | Every decision and action is logged with provenance |

---

## 2. Architectural Principles

### 2.1 Trust Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Root Trust)                       │
│                    Final authority on all actions               │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL EXECUTOR (Trusted Agent)               │
│         Enforces permissions, validates plans, executes         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD PLANNER (Untrusted Advisor)            │
│        Suggests actions, generates plans, stores memory         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Design Constraints

1. **Unidirectional Control Flow:** Cloud → Local (suggestions only); Local → OS (execution)
2. **No Remote Code Execution:** Cloud cannot transmit executable code
3. **Deterministic Action Schema:** All actions use pre-defined, versioned schemas
4. **Fail-Closed Security:** Ambiguity or error results in action denial

---

## 3. Component Diagram

### 3.1 System Overview

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              SAARTHI SYSTEM                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                         CLOUD SUBSYSTEM                                 │  ║
║  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │  ║
║  │  │   PLANNER AGENT   │  │   MEMORY SERVICE  │  │   INTENT ENGINE   │   │  ║
║  │  │                   │  │                   │  │                   │   │  ║
║  │  │ • Goal Decomp     │  │ • Vector Store    │  │ • NLU Pipeline    │   │  ║
║  │  │ • Plan Generation │  │ • User Prefs      │  │ • Entity Extract  │   │  ║
║  │  │ • Tool Selection  │  │ • Approval History│  │ • Intent Classify │   │  ║
║  │  │ • Context Mgmt    │  │ • Session Summaries│ │ • Ambiguity Detect│   │  ║
║  │  └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘   │  ║
║  │            │                      │                      │             │  ║
║  │            └──────────────────────┼──────────────────────┘             │  ║
║  │                                   │                                     │  ║
║  │                    ┌──────────────▼──────────────┐                      │  ║
║  │                    │      PLAN SYNTHESIZER       │                      │  ║
║  │                    │  • Action Graph Builder     │                      │  ║
║  │                    │  • Dependency Resolution    │                      │  ║
║  │                    │  • Risk Classification      │                      │  ║
║  │                    └──────────────┬──────────────┘                      │  ║
║  └───────────────────────────────────┼─────────────────────────────────────┘  ║
║                                      │                                        ║
║                           ┌──────────▼──────────┐                             ║
║                           │   SECURE CHANNEL    │                             ║
║                           │  (mTLS + Signed)    │                             ║
║                           └──────────┬──────────┘                             ║
║                                      │                                        ║
║  ┌───────────────────────────────────▼─────────────────────────────────────┐  ║
║  │                        LOCAL CLIENT SUBSYSTEM                           │  ║
║  │                                                                         │  ║
║  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │  ║
║  │  │  INPUT GATEWAY    │  │  EXECUTOR AGENT   │  │  PERMISSION ENGINE│   │  ║
║  │  │                   │  │                   │  │                   │   │  ║
║  │  │ • Voice Capture   │  │ • Plan Validator  │  │ • Policy Store    │   │  ║
║  │  │ • Text Input      │  │ • Action Dispatch │  │ • Consent Manager │   │  ║
║  │  │ • STT Processing  │  │ • State Machine   │  │ • Risk Evaluator  │   │  ║
║  │  │ • Wake Detection  │  │ • Rollback Handler│  │ • Audit Logger    │   │  ║
║  │  └─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘   │  ║
║  │            │                      │                      │             │  ║
║  │            │            ┌─────────▼─────────┐            │             │  ║
║  │            │            │   OS INTERFACE    │◄───────────┘             │  ║
║  │            │            │  LAYER (SANDBOXED)│                          │  ║
║  │            │            │                   │                          │  ║
║  │            │            │ • File System API │                          │  ║
║  │            │            │ • Process Control │                          │  ║
║  │            │            │ • Input Simulation│                          │  ║
║  │            │            │ • Shell Executor  │                          │  ║
║  │            │            └─────────┬─────────┘                          │  ║
║  │            │                      │                                     │  ║
║  │  ┌─────────▼─────────┐  ┌─────────▼─────────┐  ┌───────────────────┐   │  ║
║  │  │   LOCAL CACHE     │  │   DESKTOP OS      │  │   STATE MANAGER   │   │  ║
║  │  │ • Session Context │  │  (Windows/macOS)  │  │ • Agent State FSM │   │  ║
║  │  │ • Pending Actions │  │                   │  │ • Transition Rules│   │  ║
║  │  │ • Rollback Data   │  │                   │  │ • Timeout Handler │   │  ║
║  │  └───────────────────┘  └───────────────────┘  └───────────────────┘   │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                                                               ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │                       EXTERNAL SERVICES                                 │  ║
║  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │  ║
║  │  │   LLM PROVIDER    │  │  VECTOR DATABASE  │  │   AUTH SERVICE    │   │  ║
║  │  │  (OpenAI/Claude)  │  │   (Pinecone/etc)  │  │   (Identity Mgmt) │   │  ║
║  │  └───────────────────┘  └───────────────────┘  └───────────────────┘   │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

### 3.2 Component Specifications

#### 3.2.1 CLOUD SUBSYSTEM

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| **Planner Agent** | Multi-step reasoning, goal decomposition, plan generation | Parsed intent, user context, memory | Structured Action Plan |
| **Memory Service** | Long-term storage of preferences, approvals, summaries | User interactions, outcomes | Contextual embeddings, preference data |
| **Intent Engine** | Natural language understanding, entity extraction, intent classification | Raw user input (text) | Structured Intent Object |
| **Plan Synthesizer** | Converts reasoning output into validated action graphs | Planner output, tool registry | Executable Plan (JSON Schema) |

#### 3.2.2 LOCAL CLIENT SUBSYSTEM

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| **Input Gateway** | Multimodal input capture, wake word detection, STT | Voice audio, keyboard input | Normalized text input |
| **Executor Agent** | Plan validation, action dispatch, state management | Action Plan, permissions | Execution results, status |
| **Permission Engine** | Policy enforcement, consent collection, risk evaluation | Action requests | Approve/Deny decisions |
| **OS Interface Layer** | Sandboxed OS operations (files, processes, input) | Approved actions | OS state changes |
| **State Manager** | Agent state FSM, transition logic, timeout handling | Events, triggers | State transitions |
| **Local Cache** | Session context, pending actions, rollback snapshots | Execution data | Recovery data |

#### 3.2.3 EXTERNAL SERVICES

| Service | Purpose | Integration Pattern |
|---------|---------|---------------------|
| **LLM Provider** | Foundation model for reasoning | Cloud-to-Cloud API (authenticated) |
| **Vector Database** | Embedding storage and retrieval | Cloud-managed, encrypted at rest |
| **Auth Service** | User identity, device attestation | OAuth 2.0 / OIDC |

---

## 4. End-to-End Data Flow

### 4.1 Complete Request Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SAARTHI REQUEST LIFECYCLE                             │
└──────────────────────────────────────────────────────────────────────────────┘

PHASE 1: INPUT ACQUISITION
───────────────────────────────────────────────────────────────────────────────
[User]
   │
   ├──► Voice Input ──► [Microphone] ──► [Wake Detector] ──► [STT Engine]
   │                                                              │
   └──► Text Input ──► [Keyboard Listener] ─────────────────────┐ │
                                                                 │ │
                                                                 ▼ ▼
                                                    ┌────────────────────┐
                                                    │  INPUT NORMALIZER  │
                                                    │  (Local Client)    │
                                                    └─────────┬──────────┘
                                                              │
PHASE 2: INTENT UNDERSTANDING                                 │
───────────────────────────────────────────────────────────────│───────────────
                                                              ▼
                              ┌────────────────────────────────────────────┐
                              │         CLOUD: INTENT ENGINE               │
                              │  ┌──────────────────────────────────────┐  │
                              │  │ 1. Tokenization & Preprocessing      │  │
                              │  │ 2. Entity Extraction                 │  │
                              │  │ 3. Intent Classification             │  │
                              │  │ 4. Ambiguity Detection               │  │
                              │  │ 5. Confidence Scoring                │  │
                              │  └──────────────────────────────────────┘  │
                              └─────────────────┬──────────────────────────┘
                                                │
                                   ┌────────────▼────────────┐
                                   │  Intent Confidence < τ? │
                                   └────────────┬────────────┘
                                          │           │
                                     YES  │           │  NO
                                          ▼           ▼
                              ┌─────────────────┐  ┌─────────────────┐
                              │ REQUEST CLARIF. │  │ PROCEED TO PLAN │
                              │ (Return to User)│  │                 │
                              └─────────────────┘  └────────┬────────┘
                                                            │
PHASE 3: PLANNING & REASONING                               │
───────────────────────────────────────────────────────────────│───────────────
                                                            ▼
                    ┌──────────────────────────────────────────────────────┐
                    │              CLOUD: PLANNER AGENT                    │
                    │                                                      │
                    │  ┌────────────────────────────────────────────────┐  │
                    │  │  INPUT:                                        │  │
                    │  │   • Structured Intent                          │  │
                    │  │   • User Context (from Memory Service)         │  │
                    │  │   • Tool Registry (available actions)          │  │
                    │  │   • Past Approval/Denial Patterns              │  │
                    │  └────────────────────────────────────────────────┘  │
                    │                         │                            │
                    │                         ▼                            │
                    │  ┌────────────────────────────────────────────────┐  │
                    │  │  REASONING STEPS:                              │  │
                    │  │   1. Goal Decomposition                        │  │
                    │  │   2. Subtask Identification                    │  │
                    │  │   3. Tool Mapping (action selection)           │  │
                    │  │   4. Dependency Graph Construction             │  │
                    │  │   5. Risk Classification per Action            │  │
                    │  │   6. Ordering & Parallelization                │  │
                    │  └────────────────────────────────────────────────┘  │
                    │                         │                            │
                    │                         ▼                            │
                    │  ┌────────────────────────────────────────────────┐  │
                    │  │  OUTPUT: ACTION PLAN                           │  │
                    │  │   • Ordered list of Action Nodes               │  │
                    │  │   • Each node contains:                        │  │
                    │  │     - action_type (from registry)              │  │
                    │  │     - parameters (validated schema)            │  │
                    │  │     - risk_level (LOW/MEDIUM/HIGH/CRITICAL)    │  │
                    │  │     - requires_confirmation (boolean)          │  │
                    │  │     - rollback_strategy (if applicable)        │  │
                    │  │     - dependencies (node references)           │  │
                    │  └────────────────────────────────────────────────┘  │
                    └──────────────────────────┬───────────────────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │    PLAN SYNTHESIZER            │
                              │    • Schema Validation         │
                              │    • Action Registry Check     │
                              │    • Cryptographic Signing     │
                              └───────────────┬────────────────┘
                                              │
                                   [Signed Action Plan]
                                              │
PHASE 4: SECURE TRANSMISSION                  │
───────────────────────────────────────────────│───────────────────────────────
                                              ▼
                              ┌────────────────────────────────┐
                              │       SECURE CHANNEL           │
                              │  • mTLS Encryption             │
                              │  • Plan Integrity Signature    │
                              │  • Replay Attack Prevention    │
                              │  • Rate Limiting               │
                              └───────────────┬────────────────┘
                                              │
PHASE 5: LOCAL VALIDATION                     │
───────────────────────────────────────────────│───────────────────────────────
                                              ▼
              ┌─────────────────────────────────────────────────────────────┐
              │                LOCAL: EXECUTOR AGENT                        │
              │                                                             │
              │  ┌───────────────────────────────────────────────────────┐  │
              │  │  PLAN VALIDATION CHECKS:                              │  │
              │  │   1. Signature Verification (reject if invalid)       │  │
              │  │   2. Schema Conformance (reject unknown actions)      │  │
              │  │   3. Action Registry Whitelist Check                  │  │
              │  │   4. Parameter Bounds Validation                      │  │
              │  │   5. Timestamp Freshness (prevent replay)             │  │
              │  └───────────────────────────────────────────────────────┘  │
              │                          │                                  │
              │              ┌───────────▼───────────┐                      │
              │              │   Validation Pass?    │                      │
              │              └───────────┬───────────┘                      │
              │                    │           │                            │
              │              FAIL  │           │  PASS                      │
              │                    ▼           ▼                            │
              │  ┌─────────────────────┐  ┌─────────────────────────────┐   │
              │  │ REJECT PLAN         │  │ PROCEED TO PERMISSION CHECK │   │
              │  │ Log Security Event  │  │                             │   │
              │  └─────────────────────┘  └──────────────┬──────────────┘   │
              └──────────────────────────────────────────┼──────────────────┘
                                                         │
PHASE 6: PERMISSION & CONSENT                            │
───────────────────────────────────────────────────────────│───────────────────
                                                         ▼
              ┌─────────────────────────────────────────────────────────────┐
              │               LOCAL: PERMISSION ENGINE                      │
              │                                                             │
              │   FOR EACH ACTION NODE:                                     │
              │   ┌───────────────────────────────────────────────────────┐ │
              │   │  1. POLICY LOOKUP                                     │ │
              │   │     • Check local policy store                        │ │
              │   │     • Match action_type + parameters to rules         │ │
              │   │                                                       │ │
              │   │  2. RISK EVALUATION                                   │ │
              │   │     • LOW: Auto-approve if policy allows              │ │
              │   │     • MEDIUM: Check prior approval patterns           │ │
              │   │     • HIGH: Always require explicit confirmation      │ │
              │   │     • CRITICAL: Require MFA + confirmation            │ │
              │   │                                                       │ │
              │   │  3. CONSENT COLLECTION (if required)                  │ │
              │   │     • Display action description to user              │ │
              │   │     • Show affected resources                         │ │
              │   │     • Await explicit APPROVE/DENY                     │ │
              │   │     • Timeout → Deny                                  │ │
              │   │                                                       │ │
              │   │  4. DECISION LOGGING                                  │ │
              │   │     • Record decision + rationale                     │ │
              │   │     • Update approval history (for memory sync)       │ │
              │   └───────────────────────────────────────────────────────┘ │
              │                          │                                  │
              │              ┌───────────▼───────────┐                      │
              │              │   All Actions Approved?│                     │
              │              └───────────┬───────────┘                      │
              │                    │           │                            │
              │              NO    │           │  YES                       │
              │                    ▼           ▼                            │
              │  ┌─────────────────────┐  ┌─────────────────────────────┐   │
              │  │ ABORT PLAN          │  │ PROCEED TO EXECUTION        │   │
              │  │ Notify Cloud        │  │                             │   │
              │  │ Store Denial Reason │  │                             │   │
              │  └─────────────────────┘  └──────────────┬──────────────┘   │
              └──────────────────────────────────────────┼──────────────────┘
                                                         │
PHASE 7: EXECUTION                                       │
───────────────────────────────────────────────────────────│───────────────────
                                                         ▼
              ┌─────────────────────────────────────────────────────────────┐
              │               LOCAL: OS INTERFACE LAYER                     │
              │                                                             │
              │   EXECUTION LOOP (respecting dependency order):             │
              │   ┌───────────────────────────────────────────────────────┐ │
              │   │  FOR EACH ACTION NODE (topologically sorted):         │ │
              │   │                                                       │ │
              │   │  1. PRE-EXECUTION SNAPSHOT                            │ │
              │   │     • Capture rollback state if reversible            │ │
              │   │     • Record pre-conditions                           │ │
              │   │                                                       │ │
              │   │  2. EXECUTE ACTION                                    │ │
              │   │     • Dispatch to appropriate OS handler              │ │
              │   │     • File ops → File System API                      │ │
              │   │     • App control → Process Control                   │ │
              │   │     • Input sim → Input Simulation                    │ │
              │   │     • Commands → Shell Executor                       │ │
              │   │                                                       │ │
              │   │  3. RESULT CAPTURE                                    │ │
              │   │     • Success: Record output                          │ │
              │   │     • Failure: Capture error details                  │ │
              │   │                                                       │ │
              │   │  4. CONTINUATION DECISION                             │ │
              │   │     • Success → Next action                           │ │
              │   │     • Recoverable Error → Retry (max 3)               │ │
              │   │     • Fatal Error → Halt + Rollback                   │ │
              │   └───────────────────────────────────────────────────────┘ │
              └──────────────────────────────────────────┬──────────────────┘
                                                         │
PHASE 8: VERIFICATION                                    │
───────────────────────────────────────────────────────────│───────────────────
                                                         ▼
              ┌─────────────────────────────────────────────────────────────┐
              │               LOCAL: EXECUTOR AGENT                         │
              │                                                             │
              │   POST-EXECUTION VERIFICATION:                              │
              │   ┌───────────────────────────────────────────────────────┐ │
              │   │  1. OUTCOME VALIDATION                                │ │
              │   │     • Check expected post-conditions                  │ │
              │   │     • Verify file states, process status, etc.        │ │
              │   │                                                       │ │
              │   │  2. RESULT ASSEMBLY                                   │ │
              │   │     • Aggregate action outcomes                       │ │
              │   │     • Prepare execution summary                       │ │
              │   │                                                       │ │
              │   │  3. USER NOTIFICATION                                 │ │
              │   │     • Display completion status                       │ │
              │   │     • Report any partial failures                     │ │
              │   └───────────────────────────────────────────────────────┘ │
              └──────────────────────────────────────────┬──────────────────┘
                                                         │
PHASE 9: MEMORY UPDATE                                   │
───────────────────────────────────────────────────────────│───────────────────
                                                         ▼
              ┌─────────────────────────────────────────────────────────────┐
              │               BIDIRECTIONAL MEMORY SYNC                     │
              │                                                             │
              │   LOCAL → CLOUD (via Secure Channel):                       │
              │   ┌───────────────────────────────────────────────────────┐ │
              │   │  • Interaction summary (sanitized)                    │ │
              │   │  • Approval/Denial decisions (for pattern learning)   │ │
              │   │  • Execution outcome (success/failure metadata)       │ │
              │   │  • User feedback (if provided)                        │ │
              │   │                                                       │ │
              │   │  EXCLUDED from sync:                                  │ │
              │   │  • File contents                                      │ │
              │   │  • Credentials or secrets                             │ │
              │   │  • Raw input audio                                    │ │
              │   └───────────────────────────────────────────────────────┘ │
              │                                                             │
              │   CLOUD: MEMORY SERVICE                                     │
              │   ┌───────────────────────────────────────────────────────┐ │
              │   │  • Update user preference embeddings                  │ │
              │   │  • Store interaction summary                          │ │
              │   │  • Update approval pattern model                      │ │
              │   │  • Maintain session continuity data                   │ │
              │   └───────────────────────────────────────────────────────┘ │
              └─────────────────────────────────────────────────────────────┘
```

---

### 4.2 Data Flow Summary Table

| Phase | Location | Input | Process | Output |
|-------|----------|-------|---------|--------|
| 1. Input Acquisition | Local | Voice/Text | Wake detection, STT, normalization | Normalized text |
| 2. Intent Understanding | Cloud | Normalized text | NLU, entity extraction, classification | Structured Intent |
| 3. Planning | Cloud | Intent + Context | Goal decomposition, tool selection | Action Plan |
| 4. Transmission | Network | Signed Action Plan | mTLS encryption, integrity check | Delivered Plan |
| 5. Validation | Local | Received Plan | Signature verify, schema check | Validated Plan |
| 6. Permission | Local | Validated Plan | Policy eval, consent collection | Approved Actions |
| 7. Execution | Local | Approved Actions | OS operations | Execution Results |
| 8. Verification | Local | Results | Outcome validation | Verified Results |
| 9. Memory Update | Cloud | Sanitized summary | Embedding, storage | Updated Memory |

---

## 5. Security, Trust, and Isolation Boundaries

### 5.1 Trust Model Definition

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                            TRUST BOUNDARY DIAGRAM                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   ┌────────────────────────────────────────────────────────────────────┐    ║
║   │                    TRUSTED EXECUTION DOMAIN                         │    ║
║   │                      (Local Client Machine)                         │    ║
║   │   ┌──────────────────────────────────────────────────────────────┐ │    ║
║   │   │                    USER TRUST ZONE                           │ │    ║
║   │   │  • User input devices                                        │ │    ║
║   │   │  • Consent UI                                                │ │    ║
║   │   │  • Audit log viewer                                          │ │    ║
║   │   └──────────────────────────────────────────────────────────────┘ │    ║
║   │                              │                                      │    ║
║   │   ┌──────────────────────────▼───────────────────────────────────┐ │    ║
║   │   │               EXECUTOR TRUST ZONE                            │ │    ║
║   │   │  • Permission Engine (Policy enforcement)                    │ │    ║
║   │   │  • Plan Validator (Schema + signature check)                 │ │    ║
║   │   │  • State Manager (Agent state FSM)                           │ │    ║
║   │   │  • Audit Logger (Tamper-evident logging)                     │ │    ║
║   │   └──────────────────────────────────────────────────────────────┘ │    ║
║   │                              │                                      │    ║
║   │   ┌──────────────────────────▼───────────────────────────────────┐ │    ║
║   │   │               SANDBOXED EXECUTION ZONE                       │ │    ║
║   │   │  • OS Interface Layer (Restricted privileges)                │ │    ║
║   │   │  • Process isolation per action type                         │ │    ║
║   │   │  • Resource quotas (CPU, memory, disk)                       │ │    ║
║   │   └──────────────────────────────────────────────────────────────┘ │    ║
║   └────────────────────────────────────────────────────────────────────┘    ║
║                                   │                                          ║
║                    ═══════════════╪═══════════════                           ║
║                      NETWORK TRUST BOUNDARY                                  ║
║                    ═══════════════╪═══════════════                           ║
║                                   │                                          ║
║   ┌────────────────────────────────▼───────────────────────────────────┐    ║
║   │                   UNTRUSTED ADVISORY DOMAIN                        │    ║
║   │                         (Cloud Services)                           │    ║
║   │                                                                    │    ║
║   │   ┌──────────────────────────────────────────────────────────────┐│    ║
║   │   │               CLOUD PLANNER ZONE                             ││    ║
║   │   │  • Suggests actions (NEVER executes)                         ││    ║
║   │   │  • Generates plans (validated locally)                       ││    ║
║   │   │  • Stores memory (non-sensitive only)                        ││    ║
║   │   │  • Has NO visibility into execution results                  ││    ║
║   │   └──────────────────────────────────────────────────────────────┘│    ║
║   └────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### 5.2 Cloud Trust Specification

#### 5.2.1 What the Cloud IS Trusted To Do

| Capability | Justification | Verification Method |
|------------|---------------|---------------------|
| Generate action plans | Core reasoning capability | Plans validated locally before execution |
| Store user preferences | Personalization requirement | Only sanitized, non-sensitive data synced |
| Classify intent | NLU processing | Local fallback for ambiguous results |
| Retrieve context | Memory-augmented reasoning | Read-only access to embeddings |
| Suggest tool sequences | Planning optimization | Suggestions validated against local registry |

#### 5.2.2 What the Cloud MUST NEVER Be Allowed To Do

| Prohibited Capability | Risk | Enforcement Mechanism |
|-----------------------|------|------------------------|
| Execute OS commands | Remote code execution | No execution API exposed; all actions local-only |
| Access file contents | Data exfiltration | Files never transmitted; only metadata in plans |
| Bypass permission checks | Unauthorized action | Permission Engine runs locally, cannot be overridden |
| Modify local policies | Privilege escalation | Policy store is local-only, signed updates required |
| Forge action signatures | Plan tampering | Public key pinned in local client |
| Access credentials | Credential theft | Secrets never included in memory sync |
| Control input devices directly | Unauthorized input | Input simulation gated by Permission Engine |
| Disable audit logging | Cover tracks | Audit logger is write-only, append-only locally |

---

### 5.3 Local Client Enforcement Responsibilities

| Enforcement Point | Description | Implementation |
|-------------------|-------------|----------------|
| **Plan Signature Verification** | Every plan must be cryptographically signed | Ed25519 signature; reject if invalid |
| **Schema Validation** | Only pre-registered action types accepted | JSON Schema validation; reject unknown actions |
| **Parameter Sanitization** | All parameters bounds-checked | Type checking, path canonicalization, injection prevention |
| **Permission Gating** | Every action checked against policy | Policy engine evaluates before dispatch |
| **Execution Sandboxing** | OS operations run with minimal privileges | Least-privilege process isolation |
| **Audit Logging** | All decisions and actions logged | Tamper-evident, append-only log |
| **Rate Limiting** | Prevent runaway execution | Max actions per minute; cool-down periods |

---

### 5.4 Permission Checkpoints

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      PERMISSION CHECKPOINT MATRIX                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CHECKPOINT 1: Plan Reception                                                │
│  ├─ Verify: Signature, Timestamp, Schema                                     │
│  └─ Fail Action: Reject plan, log security event                             │
│                                                                              │
│  CHECKPOINT 2: Action-Level Policy Check                                     │
│  ├─ Verify: Action type in whitelist, parameters valid                       │
│  └─ Fail Action: Skip action, continue or abort based on criticality         │
│                                                                              │
│  CHECKPOINT 3: Risk-Based Consent                                            │
│  ├─ LOW Risk: Auto-approve if policy permits                                 │
│  ├─ MEDIUM Risk: Check approval history, prompt if uncertain                 │
│  ├─ HIGH Risk: Always require explicit user confirmation                     │
│  └─ CRITICAL Risk: Require MFA + explicit confirmation                       │
│                                                                              │
│  CHECKPOINT 4: Pre-Execution Verification                                    │
│  ├─ Verify: Resources exist, preconditions met                               │
│  └─ Fail Action: Abort action, report to user                                │
│                                                                              │
│  CHECKPOINT 5: Post-Execution Validation                                     │
│  ├─ Verify: Expected outcomes achieved                                       │
│  └─ Fail Action: Trigger rollback if available                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.5 Data Minimization Strategy

| Data Type | Storage Location | Retention | Sync Policy |
|-----------|------------------|-----------|-------------|
| Raw audio input | Local only | Session duration | Never synced |
| Transcribed text | Local cache | 24 hours | Hash only (for dedup) |
| File contents | Local only | Never stored | Never synced |
| File paths | Local only | Session duration | Generalized patterns only |
| Credentials/secrets | Local secure store | User-managed | Never synced |
| Action plans | Local cache | 7 days | Plan metadata only |
| Execution results | Local audit log | 90 days | Success/fail status only |
| User preferences | Cloud memory | Indefinite | Sanitized summaries |
| Approval patterns | Cloud memory | 1 year | Decision + action type (no params) |

---

### 5.6 Attack Surface Analysis

| Attack Vector | Threat | Mitigation |
|---------------|--------|------------|
| **Malicious plan injection** | Attacker injects unauthorized actions | Signature verification, schema validation |
| **Cloud compromise** | Attacker controls cloud planner | Local validation; cloud cannot execute |
| **Man-in-the-middle** | Plan modification in transit | mTLS, signed plans, certificate pinning |
| **Replay attacks** | Re-execution of old plans | Timestamp validation, nonce checking |
| **Prompt injection** | Manipulating planner via input | Intent sanitization, output validation |
| **Local privilege escalation** | Executor gains elevated access | Sandboxed execution, least privilege |
| **Memory poisoning** | Corrupting cloud memory | Memory integrity checks, anomaly detection |
| **Denial of service** | Overwhelming local client | Rate limiting, resource quotas |
| **Social engineering** | Tricking user into approving dangerous actions | Clear action descriptions, risk warnings |

---

## 6. Agent Operational States

### 6.1 State Machine Definition

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SAARTHI STATE MACHINE                                │
└──────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   SLEEP     │
                              │  (Dormant)  │
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
              [Wake Word]    [Scheduled Wake]   [System Event]
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                    ┌────────►│  LISTENING  │◄────────┐
                    │         │  (Passive)  │         │
                    │         └──────┬──────┘         │
                    │                │                │
                    │          [User Input]           │
                    │                │                │
              [Timeout]              ▼          [Task Complete]
              [Cancel]        ┌─────────────┐   [Plan Rejected]
                    │         │   ACTIVE    │         │
                    │         │ (Operating) │         │
                    │         └──────┬──────┘         │
                    │                │                │
                    │                ▼                │
                    │    ┌───────────────────────┐    │
                    │    │    SUB-STATES         │    │
                    │    │  ┌─────────────────┐  │    │
                    │    │  │   PLANNING      │  │    │
                    │    │  │ (Cloud engaged) │  │    │
                    │    │  └────────┬────────┘  │    │
                    │    │           │           │    │
                    │    │           ▼           │    │
                    │    │  ┌─────────────────┐  │    │
                    │    │  │   CONFIRMING    │  │    │
                    │    │  │ (Awaiting user) │  │    │
                    │    │  └────────┬────────┘  │    │
                    │    │           │           │    │
                    │    │           ▼           │    │
                    │    │  ┌─────────────────┐  │    │
                    │    │  │   EXECUTING     │  │    │
                    │    │  │ (OS operations) │  │    │
                    │    │  └────────┬────────┘  │    │
                    │    │           │           │    │
                    │    │           ▼           │    │
                    │    │  ┌─────────────────┐  │    │
                    │    │  │   VERIFYING     │  │    │
                    │    │  │ (Post-checks)   │  │    │
                    │    │  └─────────────────┘  │    │
                    │    └───────────────────────┘    │
                    │                │                │
                    └────────────────┴────────────────┘
                                     │
                              [Sleep Command]
                              [Extended Idle]
                              [System Suspend]
                                     │
                                     ▼
                              ┌─────────────┐
                              │   SLEEP     │
                              └─────────────┘


EMERGENCY TRANSITIONS (from any state):
──────────────────────────────────────────
    [Emergency Stop] ──► SAFE_STOP ──► Rollback ──► SLEEP
    [Critical Error] ──► ERROR ──► Recovery ──► LISTENING
    [Security Event] ──► LOCKDOWN ──► Auth Required ──► SLEEP
```

---

### 6.2 State Specifications

| State | Active Components | Resource Usage | Network | Allowed Transitions |
|-------|-------------------|----------------|---------|---------------------|
| **SLEEP** | Wake detector only | Minimal (< 1% CPU) | None | → LISTENING |
| **LISTENING** | Input Gateway, Wake detector | Low (< 5% CPU) | None | → ACTIVE, → SLEEP |
| **ACTIVE:PLANNING** | Full cloud connection | Medium | Active | → CONFIRMING, → LISTENING |
| **ACTIVE:CONFIRMING** | Consent UI, Permission Engine | Low | Idle | → EXECUTING, → LISTENING |
| **ACTIVE:EXECUTING** | OS Interface, Executor | High | Idle | → VERIFYING, → ERROR |
| **ACTIVE:VERIFYING** | Executor, Logger | Medium | Sync | → LISTENING, → ERROR |
| **ERROR** | Logger, Recovery Handler | Variable | Optional | → LISTENING, → SLEEP |
| **SAFE_STOP** | Rollback Handler, Logger | High | None | → SLEEP |
| **LOCKDOWN** | Auth Handler only | Minimal | None | → SLEEP (after auth) |

---

### 6.3 Transition Triggers

| Trigger | From State(s) | To State | Condition |
|---------|---------------|----------|-----------|
| Wake word detected | SLEEP | LISTENING | Audio matches wake phrase |
| Scheduled task | SLEEP | LISTENING | Cron trigger fires |
| User text input | LISTENING | ACTIVE:PLANNING | Non-empty input received |
| User voice input | LISTENING | ACTIVE:PLANNING | STT produces valid text |
| Plan received | ACTIVE:PLANNING | ACTIVE:CONFIRMING | Valid signed plan |
| All actions approved | ACTIVE:CONFIRMING | ACTIVE:EXECUTING | Permission Engine approves |
| User denies | ACTIVE:CONFIRMING | LISTENING | User rejects action |
| Execution complete | ACTIVE:EXECUTING | ACTIVE:VERIFYING | All actions dispatched |
| Verification pass | ACTIVE:VERIFYING | LISTENING | Outcomes validated |
| Idle timeout (30s) | LISTENING | SLEEP | No input received |
| Idle timeout (5m) | ACTIVE:CONFIRMING | LISTENING | No user response |
| Cancel command | ACTIVE:* | LISTENING | User says "cancel" |
| Stop command | ANY | SAFE_STOP | User says "stop everything" |
| Critical failure | ACTIVE:EXECUTING | ERROR | Unrecoverable error |
| Security violation | ANY | LOCKDOWN | Policy breach detected |

---

## 7. Memory Architecture

### 7.1 Memory System Design

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SAARTHI MEMORY ARCHITECTURE                          │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLOUD MEMORY LAYER                               │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      VECTOR MEMORY STORE                              │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ USER PREFERENCES│  │ INTERACTION     │  │ APPROVAL        │       │  │
│  │  │ EMBEDDINGS      │  │ SUMMARIES       │  │ PATTERNS        │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ • App prefs     │  │ • Session logs  │  │ • Action→Decision│      │  │
│  │  │ • Workflow style│  │ • Task outcomes │  │ • Risk→Response  │      │  │
│  │  │ • Time patterns │  │ • Error history │  │ • Context→Choice │      │  │
│  │  │ • Language style│  │ • Feedback      │  │ • Frequency data │      │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                       │  │
│  │  METADATA:                                                            │  │
│  │  • User ID (anonymized)                                               │  │
│  │  • Embedding vectors (1536-dim)                                       │  │
│  │  • Timestamps, TTL                                                    │  │
│  │  • Access frequency                                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SESSION CONTEXT CACHE                            │  │
│  │  • Current conversation history (ephemeral)                           │  │
│  │  • Active task state                                                  │  │
│  │  • Retrieved context for current query                                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                           [Secure Sync Protocol]
                           (Sanitized data only)
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LOCAL MEMORY LAYER                               │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      LOCAL POLICY STORE                               │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ PERMISSION      │  │ ACTION          │  │ USER OVERRIDES  │       │  │
│  │  │ POLICIES        │  │ WHITELIST       │  │                 │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ • Risk levels   │  │ • Allowed types │  │ • Always allow  │       │  │
│  │  │ • Consent rules │  │ • Param bounds  │  │ • Always deny   │       │  │
│  │  │ • Path restrictions│ │ • Rate limits │  │ • Ask every time│       │  │
│  │  │ • Time windows  │  │ • Dependencies  │  │ • Trust levels  │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      LOCAL EXECUTION CACHE                            │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ PENDING ACTIONS │  │ ROLLBACK DATA   │  │ AUDIT LOG       │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │ • Queued plans  │  │ • Pre-snapshots │  │ • All decisions │       │  │
│  │  │ • Partial state │  │ • Undo commands │  │ • All actions   │       │  │
│  │  │ • Retry queue   │  │ • State diffs   │  │ • Outcomes      │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SECURE CREDENTIAL STORE                          │  │
│  │  • Encrypted at rest (OS keychain integration)                        │  │
│  │  • Never synced to cloud                                              │  │
│  │  • Accessed only by Permission Engine                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 7.2 Read/Write Ownership Matrix

| Memory Type | Cloud Read | Cloud Write | Local Read | Local Write |
|-------------|------------|-------------|------------|-------------|
| User Preferences | ✅ | ✅ | ❌ (via cloud) | ❌ |
| Interaction Summaries | ✅ | ✅ | ❌ | ❌ |
| Approval Patterns | ✅ | ✅ | ❌ (via cloud) | ❌ |
| Session Context | ✅ | ✅ | ❌ | ❌ |
| Permission Policies | ❌ | ❌ | ✅ | ✅ |
| Action Whitelist | ❌ | ❌ | ✅ | ✅ (admin) |
| User Overrides | ❌ | ❌ | ✅ | ✅ |
| Pending Actions | ❌ | ❌ | ✅ | ✅ |
| Rollback Data | ❌ | ❌ | ✅ | ✅ |
| Audit Log | ❌ | ❌ | ✅ | ✅ (append) |
| Credentials | ❌ | ❌ | ✅ (restricted) | ✅ |

---

### 7.3 Memory Sync Protocol

```
LOCAL → CLOUD SYNC (Post-Execution):
────────────────────────────────────

1. SANITIZATION
   Input:  Raw execution data
   Output: Sanitized summary
   Rules:
   • Remove all file paths → Replace with generalized patterns
   • Remove all file contents → Never include
   • Remove all credentials → Never include
   • Remove PII → Hash or generalize
   • Keep: Action type, outcome, duration, error category

2. AGGREGATION
   • Batch multiple actions into single summary
   • Compute approval/denial ratios
   • Extract behavioral patterns

3. TRANSMISSION
   • Encrypt with session key
   • Sign with device attestation
   • Transmit over mTLS channel

4. STORAGE
   • Cloud stores as embeddings
   • TTL applied based on data type
   • Old data aged out or summarized


CLOUD → LOCAL SYNC (On-Demand):
───────────────────────────────

1. QUERY
   • Local requests relevant context
   • Specifies query intent (not raw data)

2. RETRIEVAL
   • Cloud performs vector similarity search
   • Returns relevant preference/pattern data

3. CACHING
   • Local caches retrieved data ephemerally
   • Cache expires after session
```

---

## 8. Failure, Safety, and Recovery Strategy

### 8.1 Failure Mode Analysis

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        FAILURE MODE TAXONOMY                                 │
└──────────────────────────────────────────────────────────────────────────────┘

CATEGORY A: CLOUD FAILURES
──────────────────────────────────────────────────────────────────────────────

A1. Cloud Unavailable (Network/Service Down)
    ├─ Detection: Connection timeout (5s), health check failure
    ├─ Impact: No planning capability
    ├─ Response:
    │   ├─ Transition to DEGRADED mode
    │   ├─ Notify user: "Cloud unavailable, limited functionality"
    │   ├─ Enable LOCAL-ONLY operations (pre-approved, cached)
    │   └─ Retry connection with exponential backoff (max 5 min)
    └─ Recovery: Auto-resume when connection restored

A2. Cloud Latency (Slow Response)
    ├─ Detection: Response time > 10s
    ├─ Impact: Poor user experience
    ├─ Response:
    │   ├─ Display progress indicator
    │   ├─ Allow user to cancel
    │   └─ Cache successful plans for similar future queries
    └─ Recovery: Automatic

A3. Cloud Error (Invalid Response)
    ├─ Detection: Malformed JSON, schema validation failure
    ├─ Impact: Plan cannot be processed
    ├─ Response:
    │   ├─ Log error with request ID
    │   ├─ Notify user: "Planning failed, please try again"
    │   └─ Retry once with same input
    └─ Recovery: Retry or user reformulates


CATEGORY B: PLANNING FAILURES
──────────────────────────────────────────────────────────────────────────────

B1. Hallucinated Actions (Non-existent tool/action)
    ├─ Detection: Action type not in local registry
    ├─ Impact: Plan contains invalid actions
    ├─ Response:
    │   ├─ Remove invalid actions from plan
    │   ├─ If remaining plan is viable → proceed with warning
    │   ├─ If remaining plan is empty → reject entirely
    │   └─ Log for model feedback
    └─ Recovery: Automatic filtering

B2. Invalid Parameters (Out of bounds, wrong type)
    ├─ Detection: Schema validation failure
    ├─ Impact: Action cannot be executed as specified
    ├─ Response:
    │   ├─ Attempt parameter coercion if safe
    │   ├─ If coercion fails → skip action
    │   └─ Notify user of skipped action
    └─ Recovery: Automatic with notification

B3. Impossible Plan (Circular dependencies, missing prerequisites)
    ├─ Detection: Dependency graph validation failure
    ├─ Impact: Plan cannot be executed in any order
    ├─ Response:
    │   ├─ Reject entire plan
    │   ├─ Notify user: "Plan is not executable"
    │   └─ Request clarification or reformulation
    └─ Recovery: User reformulates

B4. Overly Risky Plan (Too many CRITICAL actions)
    ├─ Detection: Risk score exceeds threshold
    ├─ Impact: Plan may cause significant damage
    ├─ Response:
    │   ├─ Require explicit acknowledgment of all risks
    │   ├─ Suggest breaking into smaller plans
    │   └─ Allow user to proceed with full consent
    └─ Recovery: User decision


CATEGORY C: PERMISSION FAILURES
──────────────────────────────────────────────────────────────────────────────

C1. User Denies Action
    ├─ Detection: User selects "Deny" in consent UI
    ├─ Impact: Specific action will not execute
    ├─ Response:
    │   ├─ Mark action as DENIED
    │   ├─ Check if dependent actions should also be skipped
    │   ├─ Continue with remaining plan if viable
    │   └─ Record denial in approval history
    └─ Recovery: Inform user of partial execution

C2. User Denies Entire Plan
    ├─ Detection: User selects "Cancel All" or denies critical action
    ├─ Impact: No actions will execute
    ├─ Response:
    │   ├─ Abort plan execution
    │   ├─ Return to LISTENING state
    │   └─ Record denial pattern
    └─ Recovery: User can retry with modified request

C3. Consent Timeout
    ├─ Detection: No user response within timeout (60s for HIGH, 30s for MEDIUM)
    ├─ Impact: Action remains in pending state
    ├─ Response:
    │   ├─ Treat as implicit DENY
    │   ├─ Notify user: "Action timed out, not executed"
    │   └─ Return to LISTENING state
    └─ Recovery: User can retry

C4. Policy Violation
    ├─ Detection: Action violates local policy rules
    ├─ Impact: Action blocked regardless of user consent
    ├─ Response:
    │   ├─ Reject action with policy reason
    │   ├─ Log policy enforcement event
    │   └─ Notify user: "Action blocked by policy"
    └─ Recovery: Admin can modify policy if appropriate


CATEGORY D: EXECUTION FAILURES
──────────────────────────────────────────────────────────────────────────────

D1. Action Fails (OS error, resource not found)
    ├─ Detection: OS API returns error
    ├─ Impact: Specific action did not complete
    ├─ Response:
    │   ├─ Capture error details
    │   ├─ Attempt retry if error is transient (max 3)
    │   ├─ If persistent → mark action FAILED
    │   ├─ Check if dependent actions should be skipped
    │   └─ Continue or abort based on criticality
    └─ Recovery: Partial plan completion with report

D2. Partial Execution (Some actions succeed, some fail)
    ├─ Detection: Mixed success/failure in action results
    ├─ Impact: System in partially modified state
    ├─ Response:
    │   ├─ Report completed vs failed actions
    │   ├─ Offer rollback for completed actions if reversible
    │   ├─ Do NOT continue with dependent actions of failed ones
    │   └─ Present user with options
    └─ Recovery: User chooses rollback, retry, or accept partial

D3. Action Hangs (No response within timeout)
    ├─ Detection: Action execution exceeds timeout (30s default, configurable)
    ├─ Impact: System blocked on unresponsive action
    ├─ Response:
    │   ├─ Attempt graceful cancellation
    │   ├─ If cancellation fails → force terminate
    │   ├─ Mark action as TIMEOUT
    │   └─ Proceed based on criticality
    └─ Recovery: Automatic with notification

D4. Cascading Failure (One failure causes others)
    ├─ Detection: Multiple consecutive failures
    ├─ Impact: Plan execution becomes unstable
    ├─ Response:
    │   ├─ Halt plan execution immediately
    │   ├─ Enter SAFE_STOP state
    │   ├─ Initiate rollback of completed actions
    │   └─ Notify user of system halt
    └─ Recovery: Full rollback, return to LISTENING


CATEGORY E: SYSTEM FAILURES
──────────────────────────────────────────────────────────────────────────────

E1. Local Client Crash
    ├─ Detection: Process monitor detects termination
    ├─ Impact: All state lost, pending actions abandoned
    ├─ Response:
    │   ├─ Watchdog restarts client
    │   ├─ Load persisted state from disk
    │   ├─ Resume pending actions if flagged as resumable
    │   └─ Notify user of restart
    └─ Recovery: Automatic restart with state recovery

E2. Disk Full
    ├─ Detection: Write operation fails with ENOSPC
    ├─ Impact: Cannot persist state, logs, or cache
    ├─ Response:
    │   ├─ Halt non-critical operations
    │   ├─ Attempt emergency log rotation
    │   ├─ Notify user of critical storage issue
    │   └─ Continue in degraded mode (no persistence)
    └─ Recovery: User frees space

E3. Memory Exhaustion
    ├─ Detection: Allocation failure, OOM signals
    ├─ Impact: Client instability
    ├─ Response:
    │   ├─ Trigger emergency garbage collection
    │   ├─ Drop non-essential caches
    │   ├─ If still failing → graceful shutdown
    │   └─ Notify user
    └─ Recovery: Restart with reduced memory footprint
```

---

### 8.2 Safe-Stop Protocol

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          SAFE-STOP PROTOCOL                                  │
└──────────────────────────────────────────────────────────────────────────────┘

TRIGGER CONDITIONS:
───────────────────
• User issues stop command ("STOP", "HALT", "EMERGENCY STOP")
• Cascading failure detected (3+ consecutive action failures)
• Security violation detected
• Critical system resource exhaustion
• Watchdog timeout (no heartbeat for 30s)

PROTOCOL STEPS:
───────────────

┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: IMMEDIATE HALT                                          [< 100ms] │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Set agent state to SAFE_STOP                                             │
│  • Cancel all pending action dispatches                                      │
│  • Terminate any in-flight OS operations                                     │
│  • Close cloud connection                                                    │
│  • Disable input processing                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: STATE CAPTURE                                           [< 500ms] │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Snapshot current execution state                                          │
│  • Record all completed actions                                              │
│  • Record all in-progress actions (with status)                              │
│  • Record all pending actions (not started)                                  │
│  • Persist to disk immediately                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: ROLLBACK ASSESSMENT                                       [< 1s]  │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Identify completed actions with rollback data                             │
│  • Prioritize rollback by risk level (CRITICAL first)                        │
│  • Check rollback feasibility                                                │
│  • Generate rollback plan                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: ROLLBACK EXECUTION                                   [Variable]    │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Execute rollback actions in reverse order                                 │
│  • Verify each rollback succeeded                                            │
│  • If rollback fails: log and continue (best effort)                         │
│  • Record rollback outcomes                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: AUDIT & NOTIFY                                          [< 500ms] │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Write comprehensive audit log entry                                       │
│  • Include: trigger reason, state at halt, rollback results                  │
│  • Notify user with summary                                                  │
│  • Display: what was done, what was undone, current state                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: TRANSITION TO SLEEP                                     [< 100ms] │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Clear all volatile state                                                  │
│  • Release all resources                                                     │
│  • Transition to SLEEP state                                                 │
│  • Await next wake trigger                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 8.3 Rollback Strategies by Action Type

| Action Type | Rollback Strategy | Feasibility | Notes |
|-------------|-------------------|-------------|-------|
| **File Create** | Delete created file | HIGH | Verify file was created by us |
| **File Modify** | Restore from pre-snapshot | HIGH | Requires snapshot taken before modify |
| **File Delete** | Restore from recycle/backup | MEDIUM | May require OS recovery features |
| **File Move** | Move back to original | HIGH | Record original path |
| **App Launch** | Terminate process | HIGH | Track PID |
| **App Close** | Cannot restore | NONE | Inform user; no automatic rollback |
| **Keyboard Input** | Cannot undo | NONE | Best effort: Ctrl+Z if applicable |
| **Mouse Click** | Cannot undo | NONE | No rollback possible |
| **Shell Command** | Command-specific | VARIABLE | Some commands have inverses |
| **System Setting** | Restore previous value | HIGH | Record previous state |

---

### 8.4 Recovery Procedures

```
PROCEDURE: RECOVERY FROM CRASH
─────────────────────────────────────────────────────────────────────────────

1. STARTUP SEQUENCE
   ├─ Load persisted state from disk
   ├─ Check state integrity (checksum validation)
   └─ If corrupt → Start fresh with notification

2. PENDING ACTION ANALYSIS
   ├─ Check for incomplete executions
   ├─ Classify as:
   │   ├─ RESUMABLE: Action can be re-executed safely
   │   ├─ COMPLETED: Action finished before crash
   │   └─ UNKNOWN: Cannot determine; require user decision
   └─ Present findings to user

3. USER DECISION POINT
   ├─ Option A: Resume pending actions
   ├─ Option B: Rollback completed actions
   ├─ Option C: Abandon and start fresh
   └─ Option D: Review each action individually

4. EXECUTION
   ├─ Apply user's chosen recovery path
   ├─ Log recovery actions
   └─ Transition to LISTENING state


PROCEDURE: RECOVERY FROM CLOUD UNAVAILABILITY
─────────────────────────────────────────────────────────────────────────────

1. DETECTION
   ├─ Initial connection failure
   └─ Health check failures

2. DEGRADED MODE ACTIVATION
   ├─ Notify user of limited functionality
   ├─ Enable cached/pre-approved operations only
   └─ Disable features requiring cloud:
       ├─ Complex planning
       ├─ Memory retrieval
       └─ New tool selection

3. RECONNECTION ATTEMPTS
   ├─ Exponential backoff: 1s, 2s, 4s, 8s, ... (max 5 min)
   ├─ Health endpoint check
   └─ Full reconnection on success

4. RECOVERY
   ├─ Restore full functionality
   ├─ Sync any queued memory updates
   └─ Notify user of restored connection
```

---

## 9. Observability and Auditability

### 9.1 Logging Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          LOGGING SUBSYSTEM                                   │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL AUDIT LOG                                   │
│                                                                             │
│  PROPERTIES:                                                                │
│  • Append-only (no modification or deletion)                                │
│  • Tamper-evident (chained hashes)                                          │
│  • Encrypted at rest                                                        │
│  • Rotation: Daily, with 90-day retention                                   │
│                                                                             │
│  LOG ENTRY SCHEMA:                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  {                                                                   │   │
│  │    "timestamp": "ISO-8601",                                          │   │
│  │    "event_type": "DECISION|ACTION|SYSTEM|SECURITY",                  │   │
│  │    "session_id": "UUID",                                             │   │
│  │    "sequence_num": 12345,                                            │   │
│  │    "prev_hash": "SHA-256 of previous entry",                         │   │
│  │    "agent_state": "ACTIVE:EXECUTING",                                │   │
│  │    "event_data": {                                                   │   │
│  │      "action_type": "file_create",                                   │   │
│  │      "parameters": { ... },  // Sanitized                            │   │
│  │      "outcome": "SUCCESS|FAILURE|DENIED|TIMEOUT",                    │   │
│  │      "duration_ms": 150,                                             │   │
│  │      "error": null | { "code": "...", "message": "..." }             │   │
│  │    },                                                                │   │
│  │    "permission_context": {                                           │   │
│  │      "policy_matched": "policy-id",                                  │   │
│  │      "risk_level": "MEDIUM",                                         │   │
│  │      "user_consent": "APPROVED|DENIED|AUTO"                          │   │
│  │    },                                                                │   │
│  │    "hash": "SHA-256 of this entry"                                   │   │
│  │  }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

LOGGED EVENTS:
──────────────
• State transitions (all)
• Cloud plan receipts
• Permission decisions (all)
• Action executions (all)
• Rollback operations
• Security events
• System errors
• Recovery procedures
```

---

### 9.2 Metrics and Monitoring

| Metric Category | Metrics | Purpose |
|-----------------|---------|---------|
| **Performance** | Plan latency (p50, p95, p99), Execution duration, Cloud RTT | SLA monitoring |
| **Reliability** | Success rate, Failure rate by type, Rollback frequency | Health assessment |
| **Security** | Permission denials, Policy violations, Invalid plan rejections | Threat detection |
| **Usage** | Actions per hour, Unique intents, State time distribution | Capacity planning |
| **Resource** | CPU usage, Memory usage, Disk usage, Network bandwidth | Resource management |

---

### 9.3 Audit Capabilities

| Audit Question | Data Source | Query Method |
|----------------|-------------|--------------|
| What actions were performed in session X? | Local Audit Log | Filter by session_id |
| Why was action Y denied? | Local Audit Log | Check permission_context |
| What was the system state at time T? | Local Audit Log | Reconstruct from log chain |
| Who approved action Z? | Local Audit Log | Check user_consent field |
| What cloud plans were received today? | Local Audit Log | Filter event_type=DECISION |
| Were there any security violations? | Local Audit Log | Filter event_type=SECURITY |

---

## 10. Appendix

### 10.1 Action Schema Definition

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SAARTHI Action Plan Schema",
  "type": "object",
  "required": ["plan_id", "timestamp", "signature", "actions"],
  "properties": {
    "plan_id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "signature": {
      "type": "string",
      "description": "Ed25519 signature of plan contents"
    },
    "intent_summary": {
      "type": "string",
      "maxLength": 500
    },
    "actions": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/action"
      }
    }
  },
  "$defs": {
    "action": {
      "type": "object",
      "required": ["action_id", "action_type", "risk_level"],
      "properties": {
        "action_id": {
          "type": "string",
          "format": "uuid"
        },
        "action_type": {
          "type": "string",
          "enum": [
            "file_create", "file_read", "file_modify", "file_delete", "file_move",
            "app_launch", "app_close", "app_focus",
            "keyboard_type", "keyboard_shortcut",
            "mouse_click", "mouse_move",
            "shell_execute",
            "clipboard_copy", "clipboard_paste",
            "notification_show",
            "system_setting_modify"
          ]
        },
        "parameters": {
          "type": "object"
        },
        "risk_level": {
          "type": "string",
          "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        },
        "requires_confirmation": {
          "type": "boolean",
          "default": true
        },
        "rollback_strategy": {
          "type": "string",
          "enum": ["SNAPSHOT_RESTORE", "INVERSE_COMMAND", "NONE"]
        },
        "dependencies": {
          "type": "array",
          "items": {
            "type": "string",
            "format": "uuid"
          }
        },
        "timeout_ms": {
          "type": "integer",
          "default": 30000
        }
      }
    }
  }
}
```

---

### 10.2 Risk Classification Matrix

| Action Type | Default Risk | Escalation Conditions |
|-------------|--------------|----------------------|
| file_read | LOW | Sensitive paths → MEDIUM |
| file_create | MEDIUM | System directories → HIGH |
| file_modify | MEDIUM | Config files → HIGH; System files → CRITICAL |
| file_delete | HIGH | Multiple files → CRITICAL |
| app_launch | LOW | Unknown apps → MEDIUM; Admin apps → HIGH |
| shell_execute | HIGH | Sudo/admin → CRITICAL |
| keyboard_type | MEDIUM | Password fields → HIGH |
| system_setting_modify | CRITICAL | Always CRITICAL |

---

### 10.3 Glossary

| Term | Definition |
|------|------------|
| **Planner Agent** | Cloud-based component responsible for reasoning, planning, and generating action graphs |
| **Executor Agent** | Local component responsible for validating and executing approved actions |
| **Action Graph** | Directed acyclic graph representing a sequence of actions with dependencies |
| **Permission Engine** | Local component that enforces policies and collects user consent |
| **Vector Memory** | Embedding-based storage for user preferences and interaction patterns |
| **Safe-Stop** | Emergency protocol that halts all operations and initiates rollback |
| **Rollback** | Reverting completed actions to their pre-execution state |
| **mTLS** | Mutual TLS; both client and server authenticate each other |
| **Action Registry** | Whitelist of allowed action types and their schemas |

---

### 10.4 Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-19 | Principal AI Systems Architect | Initial release |

---

**END OF DOCUMENT**
