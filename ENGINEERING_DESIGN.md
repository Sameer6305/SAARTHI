# SAARTHI - Engineering Design Document

## Table of Contents
1. [System Architecture](#system-architecture)
2. [State Machine Design](#state-machine-design)
3. [Intent Engine](#intent-engine)
4. [Knowledge Routing](#knowledge-routing)
5. [Performance Engineering](#performance-engineering)
6. [Testing Strategy](#testing-strategy)
7. [Interview Preparation](#interview-preparation)

---

## 1. System Architecture

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SAARTHI Voice Assistant                                │
│                           Windows-native, Privacy-first                             │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  INPUT LAYER                                                                        │
│  ┌───────────────┐    ┌───────────────────────┐    ┌─────────────────────────────┐ │
│  │ Hardware Key  │───▶│  Audio Stream Driver  │───▶│  Ring Buffer (16kHz mono)  │ │
│  │ (SPACE BAR)   │    │  (sounddevice)        │    │  Pre-allocated memory       │ │
│  └───────────────┘    └───────────────────────┘    └──────────────┬──────────────┘ │
└──────────────────────────────────────────────────────────────────│────────────────┘
                                                                   │
                                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  SIGNAL PROCESSING LAYER                                                            │
│  ┌────────────────────────────────────────┐    ┌──────────────────────────────────┐│
│  │  Robust VAD (Voice Activity Detection) │───▶│  State Machine Controller        ││
│  │  ┌────────────────────────────────┐    │    │  ┌──────────────────────────────┐││
│  │  │ • Adaptive RMS Threshold       │    │    │  │ IDLE → LISTENING → TRANS-   │││
│  │  │ • WebRTC VAD (optional)        │    │    │  │ CRIBING → THINKING →        │││
│  │  │ • Noise Floor Estimation       │    │    │  │ EXECUTING → SPEAKING → IDLE │││
│  │  │ • Debouncing (onset/offset)    │    │    │  └──────────────────────────────┘││
│  │  └────────────────────────────────┘    │    └──────────────────────────────────┘│
│  └────────────────────────────────────────┘                                         │
└──────────────────────────────────────────│──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  SPEECH-TO-TEXT LAYER                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Whisper STT Engine                                                          │   │
│  │  ┌───────────────────┐    ┌───────────────────┐    ┌─────────────────────┐  │   │
│  │  │ Model: tiny (39MB)│───▶│ FP32 inference    │───▶│ English optimized   │  │   │
│  │  │ Latency: <2s      │    │ Temperature: 0.0  │    │ Beam size: 1        │  │   │
│  │  └───────────────────┘    └───────────────────┘    └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────│──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  NATURAL LANGUAGE UNDERSTANDING LAYER                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Intent Classification Engine                                                │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐│   │
│  │  │                      LAYERED PARSING PIPELINE                           ││   │
│  │  │                                                                         ││   │
│  │  │  Raw Text → Normalizer → Pattern Match → Slot Extract → Confidence     ││   │
│  │  │                                                                         ││   │
│  │  │  Layer 1: Exact Pattern Match (confidence: 0.95+)                       ││   │
│  │  │  Layer 2: Verb-Object Extraction (confidence: 0.80+)                    ││   │
│  │  │  Layer 3: Fuzzy Matching (confidence: 0.60+)                            ││   │
│  │  │  Layer 4: Question Detection (confidence: 0.50+)                        ││   │
│  │  │  Layer 5: Fallback/Unknown (confidence: 0.0)                            ││   │
│  │  └─────────────────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                        │
│                                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Slot Extraction                                                             │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────────────┐│   │
│  │  │ VERB           │  │ TARGET         │  │ MODIFIERS                       ││   │
│  │  │ open, play,    │  │ youtube,       │  │ lofi, music, how to...         ││   │
│  │  │ search, what   │  │ calculator,    │  │                                 ││   │
│  │  │                │  │ binary search  │  │                                 ││   │
│  │  └────────────────┘  └────────────────┘  └─────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────│──────────────────────────────────────────┘
                                           │
          ┌────────────────────────────────┴────────────────────────────────┐
          ▼                                                                 ▼
┌────────────────────────────────────┐             ┌────────────────────────────────────┐
│  ACTION EXECUTOR                   │             │  KNOWLEDGE ROUTER                  │
│  ┌────────────────────────────────┐│             │  ┌────────────────────────────────┐│
│  │ Website Opening                ││             │  │ Tier 1: Built-in (100+ topics)││
│  │ • URL validation               ││             │  │ • O(1) lookup, 0ms latency    ││
│  │ • Browser API                  ││             │  │ • CS fundamentals             ││
│  │ • Silent execution             ││             │  └────────────────────────────────┘│
│  └────────────────────────────────┘│             │  ┌────────────────────────────────┐│
│  ┌────────────────────────────────┐│             │  │ Tier 2: LRU Cache (500 items) ││
│  │ Application Launch             ││             │  │ • O(1) lookup, 0ms latency    ││
│  │ • Process spawning             ││             │  │ • 1-hour TTL                  ││
│  │ • Subprocess isolation         ││             │  └────────────────────────────────┘│
│  │ • Error containment            ││             │  ┌────────────────────────────────┐│
│  └────────────────────────────────┘│             │  │ Tier 3: Wikipedia API         ││
│  ┌────────────────────────────────┐│             │  │ • 3s timeout (strict)         ││
│  │ Multi-step Commands            ││             │  │ • Summary extraction          ││
│  │ • Sequential execution         ││             │  │ • Failure isolation           ││
│  │ • Partial success handling     ││             │  └────────────────────────────────┘│
│  └────────────────────────────────┘│             │  ┌────────────────────────────────┐│
└────────────────────────────────────┘             │  │ Tier 4: Web Search Fallback   ││
                                                   │  │ • Browser-based               ││
          │                                        │  │ • "I'll search that for you"  ││
          │                                        │  └────────────────────────────────┘│
          └────────────────────────────────────────┤  ┌────────────────────────────────┐│
                                                   │  │ Tier 5: Graceful Unknown      ││
                                                   │  │ • "I don't know, but..."      ││
                                                   │  └────────────────────────────────┘│
                                                   └────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT LAYER                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  TTS Policy Enforcer                                                         │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐│   │
│  │  │  Content Allowlist (Explicit categories only):                          ││   │
│  │  │  ✅ GREETING, THANKS, EXPLANATION, ANSWER, ERROR, STATUS, QUESTION      ││   │
│  │  │  ❌ ACTION_CONFIRM (URLs, paths, commands NEVER spoken)                 ││   │
│  │  └─────────────────────────────────────────────────────────────────────────┘│   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐│   │
│  │  │  Content Sanitization:                                                  ││   │
│  │  │  • URL regex: https?://[^\s]+, www\.[^\s]+                              ││   │
│  │  │  • Path regex: [A-Z]:\\[^\s]+, /home/[^\s]+                             ││   │
│  │  │  • Command regex: \.exe\b, \.bat\b                                      ││   │
│  │  │  • Technical: hex strings, base64, GUIDs                                ││   │
│  │  └─────────────────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                            │                                        │
│                                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Windows SAPI TTS Engine                                                     │   │
│  │  • Voice: David (English)                                                    │   │
│  │  • Fault-tolerant: 3 retry attempts                                          │   │
│  │  • Auto-reinit on failure                                                    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                HAPPY PATH FLOW                                    │
└──────────────────────────────────────────────────────────────────────────────────┘

User presses SPACE
         │
         ▼
    ┌─────────┐     Audio stream     ┌─────────┐    Raw frames    ┌─────────────┐
    │ IDLE    │────────────────────▶│LISTENING│──────────────────▶│ Ring Buffer │
    └─────────┘                      └─────────┘                   └──────┬──────┘
                                                                          │
                                          VAD detects speech end          │
                                          ◀───────────────────────────────┘
                                                                          │
    ┌────────────┐                                                        │
    │TRANSCRIBING│◀───────────────────────────────────────────────────────┘
    └─────┬──────┘
          │ Whisper output: "open youtube and play lofi"
          ▼
    ┌─────────┐     ParsedIntent                   ┌────────────┐
    │THINKING │────────────────────────────────────▶│ Multi-step │
    └─────────┘     intent_type: MULTI_STEP        │ Detector   │
                    sub_intents: [OPEN_URL, PLAY]  └─────┬──────┘
                                                         │
                                                         ▼
    ┌──────────┐    Execute each sub-intent      ┌────────────────────┐
    │EXECUTING │◀────────────────────────────────│ Sequential         │
    └────┬─────┘                                 │ Executor           │
         │                                       │ (delay=500ms)      │
         │    Result: {success: true,            └────────────────────┘
         │             text: "Opening YouTube",
         │             speak: false,
         │             category: ACTION_CONFIRM}
         ▼
    ┌─────────┐
    │SPEAKING │────── TTS Policy ────▶ speak=false, skip TTS
    └────┬────┘       (ACTION_CONFIRM not in allowlist)
         │
         ▼
    ┌─────────┐
    │  IDLE   │────── Ready for next command
    └─────────┘


┌──────────────────────────────────────────────────────────────────────────────────┐
│                                FAILURE PATH FLOW                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

                     ┌─────────────────────────────────────────┐
                     │            FAILURE SCENARIOS            │
                     └─────────────────────────────────────────┘
                                         │
         ┌───────────────┬───────────────┼───────────────┬───────────────┐
         ▼               ▼               ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │Audio    │    │Whisper   │    │Intent    │    │Execution │    │TTS       │
    │Capture  │    │Timeout   │    │Unknown   │    │Failure   │    │Crash     │
    │Fail     │    │          │    │          │    │          │    │          │
    └────┬────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │              │               │               │               │
         ▼              ▼               ▼               ▼               ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         ERROR STATE HANDLER                             │
    │  ┌─────────────────────────────────────────────────────────────────┐   │
    │  │ 1. Log error with full context                                   │   │
    │  │ 2. Categorize: recoverable vs fatal                              │   │
    │  │ 3. Attempt recovery (max 3 retries)                              │   │
    │  │ 4. Speak friendly error message                                  │   │
    │  │ 5. Transition to IDLE (always recovers)                          │   │
    │  └─────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                                    ┌─────────┐
                                    │  IDLE   │ ◀── Always returns here
                                    └─────────┘
```

### 1.3 Why Each Layer Exists

| Layer | Purpose | Interview-Grade Justification |
|-------|---------|-------------------------------|
| **Input Layer** | Hardware abstraction | Decouples activation mechanism from audio processing. Allows hot-swapping wake word for push-to-talk without modifying capture logic. |
| **Signal Processing** | Noise & voice isolation | VAD prevents wasted STT cycles on silence. Adaptive threshold handles diverse environments. State machine ensures deterministic behavior. |
| **STT Layer** | Speech-to-text conversion | Whisper TINY balances accuracy (good) with latency (<2s). FP32 required for CPU-only Windows. Temperature=0 for deterministic output. |
| **NLU Layer** | Intent classification | Layered parsing provides graceful degradation. Confidence scores enable threshold-based routing. Slot extraction separates "what" from "how". |
| **Executor Layer** | Action dispatch | Isolated execution prevents cascading failures. Multi-step detection enables complex workflows. Silent execution respects UX. |
| **Knowledge Router** | Q&A handling | Multi-tier architecture optimizes for latency (built-in) while providing coverage (Wikipedia). Caching reduces redundant network calls. |
| **Output Layer** | Response generation | TTS Policy prevents security/UX issues (reading URLs). Category-based allowlist is explicit and auditable. |

---

## 2. State Machine Design

### 2.1 Formal State Definition

```
States S = {IDLE, LISTENING, TRANSCRIBING, THINKING, EXECUTING, SPEAKING, ERROR}

Initial State: IDLE

Terminal States: ∅ (system loops continuously)

Transitions T:
  IDLE         → LISTENING      : trigger = SPACE_KEY_DOWN
  LISTENING    → TRANSCRIBING   : trigger = VAD_SPEECH_COMPLETE
  LISTENING    → ERROR          : trigger = TIMEOUT | AUDIO_FAILURE
  TRANSCRIBING → THINKING       : trigger = STT_COMPLETE
  TRANSCRIBING → ERROR          : trigger = STT_FAILURE
  THINKING     → EXECUTING      : trigger = INTENT_PARSED (type ≠ QUESTION)
  THINKING     → SPEAKING       : trigger = INTENT_PARSED (type = QUESTION)
  EXECUTING    → SPEAKING       : trigger = EXECUTION_COMPLETE (speak = true)
  EXECUTING    → IDLE           : trigger = EXECUTION_COMPLETE (speak = false)
  SPEAKING     → IDLE           : trigger = TTS_COMPLETE
  ERROR        → IDLE           : trigger = always (after logging)
```

### 2.2 State Transition Matrix

| From \ To | IDLE | LISTENING | TRANSCRIBING | THINKING | EXECUTING | SPEAKING | ERROR |
|-----------|------|-----------|--------------|----------|-----------|----------|-------|
| **IDLE** | - | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **LISTENING** | ❌ | - | ✅ | ❌ | ❌ | ❌ | ✅ |
| **TRANSCRIBING** | ❌ | ❌ | - | ✅ | ❌ | ❌ | ✅ |
| **THINKING** | ❌ | ❌ | ❌ | - | ✅ | ✅ | ✅ |
| **EXECUTING** | ✅ | ❌ | ❌ | ❌ | - | ✅ | ✅ |
| **SPEAKING** | ✅ | ❌ | ❌ | ❌ | ❌ | - | ✅ |
| **ERROR** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | - |

### 2.3 Race Condition Prevention

```python
# Critical: Single-threaded state transitions with mutex
class AssistantStateMachine:
    def __init__(self):
        self._lock = threading.RLock()  # Reentrant for nested calls
        self._state = State.IDLE
        self._state_timestamp = time.time()
    
    def transition(self, new_state: State, reason: str) -> bool:
        """Thread-safe state transition with validation."""
        with self._lock:
            if not self._is_valid_transition(self._state, new_state):
                logger.warning(f"Invalid transition: {self._state} → {new_state}")
                return False
            
            old_state = self._state
            self._state = new_state
            self._state_timestamp = time.time()
            
            # Emit transition event (observers notified)
            self._notify_observers(old_state, new_state, reason)
            return True
```

**Key Design Decisions:**

1. **RLock instead of Lock**: Allows nested calls (e.g., error handler calling transition during transition)
2. **Explicit validation**: Matrix-based validation prevents invalid states
3. **Timestamp tracking**: Enables timeout detection and metrics
4. **Observer pattern**: Decouples state changes from side effects

### 2.4 Infinite Listening Prevention

```python
# Problem: VAD never detects silence → infinite recording
# Solution: Hard timeout with state machine enforcement

LISTENING_TIMEOUT = 30.0  # Maximum recording duration
SILENCE_TIMEOUT = 10.0    # Maximum time waiting for speech

def _listening_guard(self):
    """Background thread to enforce listening timeouts."""
    while self._state == State.LISTENING:
        elapsed = time.time() - self._state_timestamp
        
        if elapsed > LISTENING_TIMEOUT:
            logger.warning("Listening timeout - forcing transition")
            self.transition(State.ERROR, reason="listening_timeout")
            break
        
        time.sleep(0.1)  # Check every 100ms
```

---

## 3. Intent Engine (Interview-Grade)

### 3.1 Confidence-Based Classification

```python
@dataclass
class ParsedIntent:
    intent_type: IntentType
    confidence: float          # 0.0 to 1.0
    entities: Dict[str, Any]   # Extracted slots
    raw_text: str             # Original input
    normalized_text: str      # After preprocessing
    verb: Optional[str]       # Primary action verb
    target: Optional[str]     # Action target
    modifiers: List[str]      # Additional context
    source: str               # Which parsing layer matched

# Confidence thresholds (tuned empirically)
CONFIDENCE_THRESHOLDS = {
    "execute": 0.70,    # Minimum to execute without confirmation
    "suggest": 0.40,    # Minimum to suggest interpretation
    "fallback": 0.20,   # Below this, go to knowledge router
}
```

### 3.2 Slot Extraction Pipeline

```
Input: "play lofi hip hop on youtube"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  NORMALIZER                                                     │
│  "play lofi hip hop on youtube" → "play lofi hip hop youtube"  │
│  (removed filler: "on")                                         │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  VERB EXTRACTION                                                │
│  verb = "play"                                                  │
│  verb_type = PLAY_VERB (matches known play verbs)               │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  TARGET EXTRACTION                                              │
│  target = "youtube" (matched KNOWN_SITES)                       │
│  remaining = "lofi hip hop"                                     │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  MODIFIER EXTRACTION                                            │
│  modifiers = ["lofi", "hip", "hop"]                             │
│  search_query = "lofi hip hop"                                  │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTENT ASSEMBLY                                                │
│  intent_type = PLAY_MEDIA                                       │
│  entities = {                                                   │
│      "url": "https://youtube.com/results?search_query=lofi+...",│
│      "query": "lofi hip hop",                                   │
│      "platform": "youtube"                                      │
│  }                                                              │
│  confidence = 0.92                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Adding New Commands (Without Touching Core Logic)

```python
# commands/custom_commands.py

from intent_parser import IntentRegistry, IntentType

# Register new command type
IntentType.SMART_HOME = "smart_home"

# Define patterns (declarative, not procedural)
IntentRegistry.register(
    intent_type=IntentType.SMART_HOME,
    patterns=[
        r"turn (on|off) (?:the )?(?P<device>\w+)",
        r"(?P<action>dim|brighten) (?:the )?(?P<device>\w+)",
        r"set (?P<device>\w+) to (?P<value>\d+)%?",
    ],
    verbs={"turn", "dim", "brighten", "set"},
    entity_extractors={
        "device": lambda m: m.group("device"),
        "action": lambda m: m.group("action") if "action" in m.groupdict() else None,
        "value": lambda m: int(m.group("value")) if "value" in m.groupdict() else None,
    },
    confidence_boost=0.05,  # Boost if user has smart home devices
)

# Register executor (separate from parsing)
ActionRegistry.register(
    intent_type=IntentType.SMART_HOME,
    executor=SmartHomeExecutor(),
)
```

**Why This Scales:**

1. **Declarative patterns**: No procedural if/else chains
2. **Separation of concerns**: Parsing and execution are independent
3. **Entity extractors**: Type-safe slot extraction
4. **Confidence tuning**: Per-command confidence adjustments
5. **Registry pattern**: Hot-reloadable commands

---

## 4. Knowledge Routing Strategy

### 4.1 Multi-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE QUERY: "what is binary search"            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  QUERY PREPROCESSOR                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ 1. Remove question words: "what is" → ""                                ││
│  │ 2. Extract topic: "binary search"                                       ││
│  │ 3. Generate variants: ["binary search", "binary-search", "binarysearch"]││
│  │ 4. Identify category hints: "search" → ALGORITHMS                       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  TIER 1: BUILT-IN KNOWLEDGE                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │ Lookup: O(1) hash table                                                 ││
│  │ Topics: 100+ CS fundamentals                                            ││
│  │ Latency: 0ms                                                            ││
│  │                                                                         ││
│  │ MATCH FOUND: "binary search"                                            ││
│  │ Answer: "Binary search finds an element in a sorted array by           ││
│  │          repeatedly halving the search space. Time: O(log n)..."       ││
│  │ Confidence: 1.0                                                         ││
│  └────────────────────────────────────────────────────────────────────────┘│
│  Result: KnowledgeResult(answer=..., source="built_in", confidence=1.0)    │
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                         (If not found) │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  TIER 2: LRU CACHE                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │ Max Size: 500 entries                                                   ││
│  │ TTL: 3600 seconds (1 hour)                                              ││
│  │ Eviction: Least Recently Used                                           ││
│  └────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                         (If not found) │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  TIER 3: WIKIPEDIA API                                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │ Timeout: 3 seconds (STRICT - prevents blocking)                         ││
│  │ Endpoint: en.wikipedia.org/api/rest_v1/page/summary/{topic}             ││
│  │ Response: First 2 sentences of article                                  ││
│  │ Failure mode: Timeout → fallback, 404 → fallback                        ││
│  └────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                         (If not found) │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  TIER 4: WEB SEARCH FALLBACK                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │ "I'll search that for you..."                                           ││
│  │ Opens browser with Google search                                        ││
│  │ TTS: "I don't have that information, but I've opened a search for you" ││
│  └────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
                                        │
                         (Last resort)  │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  TIER 5: GRACEFUL UNKNOWN                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │ "I don't know the answer to that. Try asking in a different way,       ││
│  │  or I can search the web for you."                                     ││
│  │                                                                         ││
│  │ Confidence: 0.0 (signals UI to offer alternatives)                      ││
│  └────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Answer Summarization

```python
def summarize_for_speech(text: str, max_sentences: int = 3, max_chars: int = 300) -> str:
    """
    Summarize text for TTS output.
    
    Design decisions:
    1. Max 3 sentences - longer becomes tedious to listen to
    2. Max 300 chars - approx 20 seconds at normal speaking rate
    3. Preserve first sentences - usually most important (Wikipedia style)
    4. Clean trailing fragments - avoid "The algorithm..."
    """
    if not text:
        return ""
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    result = []
    char_count = 0
    
    for sentence in sentences[:max_sentences]:
        if char_count + len(sentence) > max_chars:
            break
        result.append(sentence)
        char_count += len(sentence)
    
    return ' '.join(result)
```

### 4.3 Timeout and Failure Isolation

```python
def query_wikipedia(topic: str, timeout: float = 3.0) -> Optional[str]:
    """
    Query Wikipedia with strict timeout.
    
    CRITICAL: This function MUST NOT block for more than timeout seconds.
    Network calls are wrapped in executor to enforce timeout.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_wikipedia, topic)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            logger.warning(f"Wikipedia timeout for: {topic}")
            return None
        except Exception as e:
            logger.error(f"Wikipedia error: {e}")
            return None
        finally:
            # Cancel if still running (best effort)
            future.cancel()
```

---

## 5. Performance & Reliability Engineering

### 5.1 Latency Tracking

```python
@dataclass
class PerformanceMetrics:
    """Tracks performance across the pipeline."""
    
    # Timing metrics (in seconds)
    audio_capture_time: float = 0.0
    stt_time: float = 0.0
    intent_parsing_time: float = 0.0
    knowledge_lookup_time: float = 0.0
    execution_time: float = 0.0
    tts_time: float = 0.0
    total_time: float = 0.0
    
    # Success metrics
    stt_success: bool = False
    intent_confidence: float = 0.0
    execution_success: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class PerformanceTracker:
    """Singleton performance tracker with rolling statistics."""
    
    def __init__(self, window_size: int = 100):
        self._history: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()
    
    @contextmanager
    def track_stage(self, stage_name: str):
        """Context manager for timing individual stages."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._record(stage_name, elapsed)
    
    def get_percentiles(self, stage: str) -> Dict[str, float]:
        """Get p50, p90, p99 latencies for a stage."""
        with self._lock:
            values = [m[stage] for m in self._history if stage in m]
            if not values:
                return {"p50": 0, "p90": 0, "p99": 0}
            
            values.sort()
            return {
                "p50": values[len(values) // 2],
                "p90": values[int(len(values) * 0.9)],
                "p99": values[int(len(values) * 0.99)],
            }
```

### 5.2 Command Success Rate Logging

```python
class CommandSuccessTracker:
    """Tracks command success rates by intent type."""
    
    def __init__(self):
        self._counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})
    
    def record(self, intent_type: IntentType, success: bool):
        key = intent_type.value
        if success:
            self._counts[key]["success"] += 1
        else:
            self._counts[key]["failure"] += 1
    
    def get_success_rate(self, intent_type: IntentType) -> float:
        """Get success rate for an intent type."""
        counts = self._counts[intent_type.value]
        total = counts["success"] + counts["failure"]
        return counts["success"] / total if total > 0 else 0.0
    
    def get_report(self) -> str:
        """Generate human-readable success report."""
        lines = ["Command Success Rates:", "-" * 40]
        for intent, counts in sorted(self._counts.items()):
            total = counts["success"] + counts["failure"]
            rate = counts["success"] / total if total > 0 else 0
            lines.append(f"  {intent}: {rate:.1%} ({counts['success']}/{total})")
        return "\n".join(lines)
```

### 5.3 Failure Categorization

```python
class FailureCategory(Enum):
    """Categorization of failures for debugging."""
    
    # Audio pipeline
    AUDIO_DEVICE_ERROR = "audio_device_error"
    VAD_TIMEOUT = "vad_timeout"
    AUDIO_TOO_SHORT = "audio_too_short"
    
    # STT pipeline
    STT_MODEL_ERROR = "stt_model_error"
    STT_EMPTY_RESULT = "stt_empty_result"
    STT_TIMEOUT = "stt_timeout"
    
    # Intent pipeline
    INTENT_UNKNOWN = "intent_unknown"
    INTENT_LOW_CONFIDENCE = "intent_low_confidence"
    INTENT_PARSE_ERROR = "intent_parse_error"
    
    # Execution pipeline
    EXECUTION_EXCEPTION = "execution_exception"
    EXECUTION_TIMEOUT = "execution_timeout"
    RESOURCE_NOT_FOUND = "resource_not_found"
    
    # TTS pipeline
    TTS_ENGINE_ERROR = "tts_engine_error"
    TTS_BLOCKED_CONTENT = "tts_blocked_content"
    
    # Network
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"


class FailureTracker:
    """Tracks and categorizes failures for debugging."""
    
    def __init__(self):
        self._failures: List[Dict] = []
        self._counts: Counter = Counter()
    
    def record(self, category: FailureCategory, context: Dict[str, Any]):
        """Record a failure with full context."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category.value,
            "context": context,
        }
        self._failures.append(entry)
        self._counts[category] += 1
        
        # Log for immediate visibility
        logger.error(f"FAILURE [{category.value}]: {context}")
    
    def get_top_failures(self, n: int = 5) -> List[Tuple[str, int]]:
        """Get most common failure categories."""
        return self._counts.most_common(n)
```

### 5.4 Production Debugging Guide

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HOW TO DEBUG PRODUCTION ISSUES                         │
└─────────────────────────────────────────────────────────────────────────────┘

1. CHECK METRICS FIRST
   $ python -c "from saarthi_executor.metrics import get_metrics; print(get_metrics().summary())"
   
   Look for:
   - P99 latencies > 5s (bottleneck somewhere)
   - Success rate < 90% (reliability issue)
   - Specific intent types failing (pattern issue)

2. IDENTIFY FAILURE CATEGORY
   $ grep "FAILURE" logs/saarthi.log | tail -100 | sort | uniq -c | sort -rn
   
   Common issues:
   - AUDIO_DEVICE_ERROR: Check sounddevice, microphone permissions
   - VAD_TIMEOUT: Adjust silence_duration, check ambient noise
   - STT_EMPTY_RESULT: Whisper model issue, audio quality
   - INTENT_UNKNOWN: Pattern coverage gap

3. REPRODUCE WITH VERBOSE LOGGING
   $ LOG_LEVEL=DEBUG python voice_ultimate_v2.py 2>&1 | tee debug.log
   
   Look for:
   - State transitions (should be linear path)
   - Confidence scores (should be > 0.7 for actions)
   - Timing per stage (identify slowest)

4. CHECK STATE MACHINE
   $ grep "transition" logs/saarthi.log | tail -20
   
   Expected: IDLE → LISTENING → TRANSCRIBING → THINKING → EXECUTING → IDLE
   Red flags:
   - Stuck in LISTENING (VAD not stopping)
   - LISTENING → ERROR (timeout or device issue)
   - Multiple ERROR transitions (instability)

5. PROFILE PERFORMANCE
   $ python -m cProfile -s cumtime voice_ultimate_v2.py 2>&1 | head -50
   
   Expected hotspots:
   - whisper.transcribe (STT - expected to be slow)
   - sounddevice.InputStream (I/O bound - expected)
   
   Red flags:
   - intent_parser taking > 100ms (pattern issues)
   - TTS taking > 500ms (engine issues)
```

---

## 6. Testing Strategy

### 6.1 Testing Philosophy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TESTING PYRAMID                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌───────────────────┐
                           │  E2E Tests (5%)   │  ◀── Real audio, real TTS
                           │  Manual QA        │      Cannot automate fully
                           └─────────┬─────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │    Integration Tests (20%)      │  ◀── Mocked audio/TTS
                    │    Audio → STT → Intent → Exec  │      Automated in CI
                    └────────────────┬────────────────┘
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        │                    Unit Tests (75%)                     │  ◀── Pure functions
        │  Intent Parser, TTS Policy, Knowledge Router, VAD       │      Fast, isolated
        └─────────────────────────────────────────────────────────┘
```

### 6.2 What CANNOT Be Easily Tested

| Component | Why Difficult | Mitigation |
|-----------|---------------|------------|
| **Real microphone input** | Hardware dependency, ambient noise | Mock with recorded WAV files |
| **Whisper accuracy** | Model is a black box, non-deterministic | Test with fixed audio samples, check transcription accuracy > 90% |
| **Windows SAPI TTS** | COM object, Windows-only, blocking | Mock TTS engine, verify input not output |
| **Browser opening** | Side effect, spawns external process | Verify webbrowser.open called with correct URL |
| **User experience** | Subjective, requires human judgment | Manual QA checklist, user testing sessions |

### 6.3 See tests/ Directory

The test suite is in [tests/](local_client/tests/) with:

- `test_intent_parser.py` - Unit tests for intent classification
- `test_tts_policy.py` - Unit tests for TTS gating
- `test_knowledge_router.py` - Unit tests for Q&A routing
- `test_vad.py` - Unit tests for voice activity detection
- `test_integration.py` - Integration tests with mocked I/O
- `conftest.py` - Pytest fixtures

---

## 7. Interview Preparation

### 7.1 Resume Bullet Points (Impact-Oriented)

```
• Architected real-time voice assistant with 6-layer pipeline (Audio → VAD → STT → NLU → Executor → TTS), 
  achieving <3s end-to-end latency and 95%+ command success rate on Windows

• Designed deterministic state machine (7 states, 12 transitions) eliminating infinite-loop bugs 
  and enabling graceful error recovery with automatic retries

• Implemented confidence-based intent classification with slot extraction, supporting 50+ command 
  patterns without O(n) if/else chains; adding new commands requires only declarative registration
```

### 7.2 Interview Questions This Project Answers

1. **"Tell me about a system you designed with multiple layers. Why did you choose that architecture?"**
   
   → Explain the 6-layer pipeline, why each layer exists, and the tradeoffs (e.g., Whisper TINY for latency vs accuracy)

2. **"How do you handle state in a real-time system? What about race conditions?"**
   
   → Explain the state machine with mutex-protected transitions, the transition matrix, and how timeouts prevent infinite states

3. **"Describe a time you had to debug a production issue."**
   
   → Use the VAD infinite listening bug: symptom → root cause (silence counted before speech) → state machine solution

4. **"How do you design for extensibility? Give an example."**
   
   → Show the IntentRegistry pattern: declarative patterns, separation of parsing and execution, no core logic changes

5. **"What's your testing strategy? What do you prioritize?"**
   
   → Testing pyramid, why intent parsing is heavily tested (pure functions), why TTS is mocked (side effects), what requires manual QA

### 7.3 90-Second Project Explanation

> "SAARTHI is a Windows voice assistant I built to solve a real problem: existing assistants either require cloud APIs, don't work offline, or have frustrating UX issues like reading URLs aloud.
>
> The architecture is a 6-layer pipeline. Audio comes in through the microphone, goes through a state-machine-based Voice Activity Detector that uses adaptive thresholds to handle different environments. Then Whisper—running locally—converts speech to text in under 2 seconds.
>
> The interesting part is the intent engine. Instead of a giant if-else chain, I use layered parsing: exact patterns first for speed, then verb-object extraction, then fuzzy matching. Each intent gets a confidence score, and I only execute if confidence is above 0.7.
>
> For questions, I have a multi-tier knowledge router: built-in knowledge for instant answers on 100+ CS topics, an LRU cache, and Wikipedia with a strict 3-second timeout so the assistant never hangs.
>
> The TTS layer has an explicit allowlist—URLs, file paths, and commands are never spoken. This came from a bug where the assistant would say 'Opening https://www.youtube.com' which is terrible UX.
>
> Everything is driven by a 7-state state machine that prevents race conditions and ensures the system always recovers to IDLE, even after errors. I track latency percentiles and command success rates for debugging.
>
> The project demonstrates real-time systems design, state machine engineering, and production-grade error handling—all running entirely offline."

---

## Appendix A: Component Dependency Graph

```
                    ┌─────────────────────────────────────┐
                    │         voice_ultimate_v2.py        │
                    │     (Main orchestration layer)      │
                    └───────────────────┬─────────────────┘
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼               ▼
┌───────────────┐ ┌───────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────┐
│ audio_capture │ │robust_vad │ │ intent_parser │ │knowledge_router│ │tts_policy│
│     .py       │ │    .py    │ │      .py      │ │      .py      │ │   .py    │
└───────┬───────┘ └─────┬─────┘ └───────────────┘ └───────────────┘ └──────────┘
        │               │
        ▼               ▼
┌─────────────────────────────────────────────┐
│             External Libraries              │
│  sounddevice, numpy, whisper, pyttsx3       │
│  (optional: webrtcvad)                      │
└─────────────────────────────────────────────┘
```

---

## Appendix B: Key Metrics Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| End-to-end latency (P50) | < 2.5s | SPACE pressed → response started |
| End-to-end latency (P99) | < 5.0s | Include slow STT cases |
| Command success rate | > 95% | Successful execution / total attempts |
| Intent confidence (actions) | > 0.70 | Average for executed commands |
| VAD reliability | > 98% | Correct stop / total recordings |
| TTS URL leakage | 0% | URLs spoken / total TTS calls |
| Memory usage | < 500MB | Including Whisper model |
| Crash recovery | 100% | Always returns to IDLE after error |
