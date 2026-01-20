# SAARTHI Voice Module - Privacy & Safety Design

## Executive Summary

The SAARTHI voice module provides **optional, fully local** voice support as a **convenience layer only**. Voice input is treated identically to text input with **no special privileges**.

---

## Privacy Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRIVACY BOUNDARY                                 │
│                     (Everything inside is LOCAL)                         │
│                                                                          │
│  ┌─────────┐    ┌─────────────┐    ┌──────────┐    ┌────────────────┐  │
│  │   MIC   │───▶│ Audio Buffer│───▶│ Whisper  │───▶│ Plain Text     │  │
│  │(on PTT) │    │ (memory only)│    │ (local)  │    │ (same as typed)│  │
│  └─────────┘    └─────────────┘    └──────────┘    └────────────────┘  │
│       │               │                 │                   │            │
│       │               ▼                 │                   ▼            │
│       │         [DISCARDED]             │          Normal Pipeline       │
│       │         immediately             │          (no special trust)    │
│       │                                 │                                │
│  └────┴─────────────────────────────────┴───────────────────────────────┘
│                                                                          │
│  ❌ NO cloud services                                                    │
│  ❌ NO audio storage                                                     │
│  ❌ NO always-on listening                                               │
│  ❌ NO wake words                                                        │
│  ❌ NO telemetry                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Audio Pipeline Flow

### Step-by-Step Processing

```
STEP 1: User Action Required
────────────────────────────────
• User PRESSES push-to-talk button
• Recording indicator VISIBLE
• Mic activated ONLY during press

         │
         ▼

STEP 2: Audio Capture (Memory Only)
────────────────────────────────────
• Audio stored in RAM buffer
• No disk writes
• Max 30 seconds enforced
• Visible recording indicator

         │
         ▼

STEP 3: User Releases Button
────────────────────────────────
• Recording stops IMMEDIATELY
• No trailing capture
• Audio in buffer only

         │
         ▼

STEP 4: Local STT (Whisper)
────────────────────────────────
• 100% local processing
• CPU-compatible (no GPU required)
• 30-second timeout
• Confidence score calculated

         │
         ▼

STEP 5: Audio Buffer CLEARED
────────────────────────────────
• Buffer overwritten with zeros
• Memory released
• NO audio persistence
• Only text remains

         │
         ▼

STEP 6: Text Validation
────────────────────────────────
• Low confidence? → User confirmation dialog
• User can edit transcription
• Cancel = discard completely

         │
         ▼

STEP 7: Normal Agent Pipeline
────────────────────────────────
• Text treated EXACTLY like typed input
• Same intent analysis
• Same permission checks
• Same execution rules
• NO voice-specific privileges

         │
         ▼

STEP 8: Optional TTS Response
────────────────────────────────
• ONLY speaks approved content
• Text already shown to user
• Local TTS (Windows SAPI/Piper)
• User can disable
```

---

## Discard Points

| Point | What's Discarded | When |
|-------|------------------|------|
| Recording cancelled | All audio | Immediately |
| Recording too short | All audio | < 0.5 seconds |
| STT complete | Audio buffer | After transcription |
| Low confidence rejection | Everything | User cancels |
| Pipeline rejection | Text | Any validation failure |

---

## Permission & Consent Model

### Microphone Access

```
┌─────────────────────────────────────────────────────────────────┐
│                    MICROPHONE CONSENT FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Voice is DISABLED by default                                │
│     └── User must explicitly enable in settings                 │
│                                                                  │
│  2. First enable shows explanation:                             │
│     "Voice features require microphone access.                  │
│      Recording only happens when you press the talk button.     │
│      No audio is stored. All processing is local."              │
│                                                                  │
│  3. Each recording requires button PRESS:                       │
│     └── No automatic activation                                 │
│     └── No wake words                                           │
│     └── No background listening                                 │
│                                                                  │
│  4. Recording state is ALWAYS visible:                          │
│     └── Red floating indicator: "🎤 RECORDING"                  │
│     └── Tray icon state change                                  │
│     └── Click indicator to cancel                               │
│                                                                  │
│  5. Voice can be disabled anytime:                              │
│     └── Settings menu                                           │
│     └── Tray menu option                                        │
│     └── Takes effect immediately                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Recording State Communication

| State | Visual Indicator | Tray Icon | Action Available |
|-------|------------------|-----------|------------------|
| Voice Disabled | None | Normal | Enable in settings |
| Voice Ready | None | 🟢 dot | Press PTT button |
| Recording | 🔴 "RECORDING" floating | 🔴 pulse | Release to transcribe |
| Processing | 🟠 "PROCESSING" floating | 🟠 | Wait |
| Confirming | Dialog box | Normal | Accept/Edit/Cancel |
| Speaking | 🔊 indicator | Normal | Click to stop |

### Revocation

```
User can ALWAYS:
├── Cancel recording mid-capture (click indicator or ESC)
├── Reject transcription in confirmation dialog
├── Disable voice entirely (Settings → Voice → Disable)
├── Uninstall voice dependencies (removes capability)
└── Delete voice config file (resets to disabled)
```

---

## Failure Handling

### Graceful Degradation to Text-Only

```
┌────────────────────────────────────────────────────────────────────┐
│                      FAILURE HANDLING MATRIX                        │
├─────────────────────────┬──────────────────────────────────────────┤
│ Failure                 │ Response                                  │
├─────────────────────────┼──────────────────────────────────────────┤
│ No microphone           │ • Show error: "No microphone detected"   │
│                         │ • Disable voice button                    │
│                         │ • Text input remains available            │
├─────────────────────────┼──────────────────────────────────────────┤
│ Mic access denied       │ • Show: "Microphone access required"     │
│                         │ • Offer to open Windows settings          │
│                         │ • Fall back to text                       │
├─────────────────────────┼──────────────────────────────────────────┤
│ Whisper load failure    │ • Show: "Speech recognition unavailable" │
│                         │ • Offer to download model                 │
│                         │ • Fall back to text                       │
├─────────────────────────┼──────────────────────────────────────────┤
│ STT timeout (>30s)      │ • Cancel transcription                   │
│                         │ • Show: "Processing took too long"        │
│                         │ • Discard audio                           │
├─────────────────────────┼──────────────────────────────────────────┤
│ Low confidence (<30%)   │ • Treat as "no speech detected"          │
│                         │ • Discard silently                        │
│                         │ • User can try again                      │
├─────────────────────────┼──────────────────────────────────────────┤
│ Medium confidence       │ • Show confirmation dialog               │
│ (30-60%)                │ • User can edit or cancel                │
│                         │ • Proceed only with explicit OK           │
├─────────────────────────┼──────────────────────────────────────────┤
│ TTS failure             │ • Log warning                            │
│                         │ • Text response still shown               │
│                         │ • Continue without speech                 │
├─────────────────────────┼──────────────────────────────────────────┤
│ 5+ consecutive failures │ • Auto-disable voice                     │
│                         │ • Show: "Voice disabled due to errors"   │
│                         │ • Require manual re-enable                │
├─────────────────────────┼──────────────────────────────────────────┤
│ Any unknown error       │ • Log full error                         │
│                         │ • Discard audio                           │
│                         │ • Fall back to text                       │
│                         │ • NEVER proceed with partial data         │
└─────────────────────────┴──────────────────────────────────────────┘
```

### Critical Invariant

```
╔════════════════════════════════════════════════════════════════════╗
║                                                                     ║
║   SILENCE OR FAILURE MUST NEVER TRIGGER AN ACTION                  ║
║                                                                     ║
║   • No speech detected → No action                                 ║
║   • Error during processing → No action                            ║
║   • Low confidence → Confirmation required or no action            ║
║   • Timeout → No action                                            ║
║   • User cancels → No action                                       ║
║                                                                     ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Integration Architecture

### Module Structure

```
local_client/
└── saarthi_executor/
    └── voice/
        ├── __init__.py         # Module definition, capability lists
        ├── config.py           # Configuration (disabled by default)
        ├── audio_capture.py    # Push-to-talk recording
        ├── stt_whisper.py      # Local Whisper STT
        ├── tts_local.py        # Windows SAPI / Piper TTS
        ├── pipeline.py         # Orchestrates the flow
        ├── ui_components.py    # Recording indicator, dialogs
        └── integration.py      # Connects to executor
```

### Integration with Existing Executor

```python
# In executor.py - voice is OPTIONAL and MODULAR

class SaarthiExecutor:
    def __init__(self, use_voice: bool = False):
        # ... existing init ...
        
        # Voice is optional - only load if requested
        self._voice = None
        if use_voice:
            from saarthi_executor.voice.integration import VoiceIntegration
            self._voice = VoiceIntegration(
                on_voice_input=self._handle_text_input  # SAME handler as text!
            )
    
    def _handle_text_input(self, text: str) -> None:
        """
        Handle input - SAME for voice and typed text.
        
        Voice input has NO special treatment.
        """
        # 1. Analyze intent
        # 2. Plan actions
        # 3. Request permissions
        # 4. Execute (if approved)
        pass
```

### Tray Menu Integration

```
SAARTHI (Right-click menu)
├── Status: LISTENING
├── ────────────────────
├── Wake Up (disabled when active)
├── Go to Sleep
├── ────────────────────
├── 🎤 Push to Talk      ← NEW: Voice button
├── Voice Settings...    ← NEW: Configure voice
├── ────────────────────
├── Test Action
├── ────────────────────
└── Exit
```

---

## Security Invariants

### Voice Input = Text Input

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRUST MODEL                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Voice Input ─────┐                                                  │
│                   │                                                  │
│                   ▼                                                  │
│               ┌───────────┐                                          │
│               │  SAME     │     Same intent analysis                 │
│               │  PIPELINE │     Same permission checks               │
│               │           │     Same execution rules                 │
│               └───────────┘     Same user consent                    │
│                   ▲                                                  │
│                   │                                                  │
│  Text Input ──────┘                                                  │
│                                                                      │
│  ════════════════════════════════════════════════════════════════   │
│                                                                      │
│  Voice CANNOT:                                                       │
│  • Bypass permission dialogs                                         │
│  • Execute without user consent                                      │
│  • Access more actions than text                                     │
│  • Skip validation steps                                             │
│  • Have elevated trust                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### What Voice CANNOT Do

| Forbidden | Reason |
|-----------|--------|
| Execute shell commands | Blocked at action level |
| Delete files | Not in allowlist |
| Bypass permissions | Same flow as text |
| Access system resources | Same restrictions as text |
| Operate silently | Visible indicator required |
| Record without button | Push-to-talk only |
| Store audio | Memory-only processing |
| Send audio to cloud | Local processing only |

---

## Testing the Voice Module

```bash
# Install voice dependencies
pip install sounddevice numpy openai-whisper pyttsx3

# Test audio capture
python -c "from saarthi_executor.voice.audio_capture import PushToTalkCapture; print(PushToTalkCapture().is_available)"

# Test STT
python -c "from saarthi_executor.voice.stt_whisper import LocalWhisperSTT; stt = LocalWhisperSTT(); print(stt.load_model())"

# Test TTS
python -c "from saarthi_executor.voice.tts_local import WindowsSapiTTS; tts = WindowsSapiTTS(); tts.speak('Hello from SAARTHI')"
```

---

## One-Minute Summary

> **SAARTHI Voice** is an optional, privacy-first voice module that adds push-to-talk 
> convenience without compromising security.
>
> **Key Points:**
> - Voice is **disabled by default**
> - Recording happens **only while button is pressed**
> - All processing is **100% local** (Whisper STT, Windows TTS)
> - Audio is **never stored** (memory-only, cleared immediately)
> - Voice input is treated **exactly like typed text**
> - No **special privileges, no bypassing permissions**
> - Visual **recording indicator always visible**
> - Graceful **fallback to text** on any failure
> - User can **disable anytime**
>
> **Voice is a helper, never a controller.**
