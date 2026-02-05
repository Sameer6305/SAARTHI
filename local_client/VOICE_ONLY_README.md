# SAARTHI Voice-Only Assistant

## How to Run

```bash
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client
python voice_only.py
```

## How to Use

### Quick Start:
1. **Run** `python voice_only.py`
2. **Find tray icon** in system tray (bottom-right, near clock)
3. **Right-click** → **Enable Assistant**
4. **HOLD Ctrl+Space** while speaking
5. **RELEASE** to process your command

### Interaction Flow:
```
┌─────────────────────────────────────────────────────────────┐
│                    VOICE-ONLY FLOW                          │
│                                                             │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐  │
│  │ Ctrl+   │───▶│ RECORD   │───▶│TRANSCRIBE│───▶│RESPOND│  │
│  │ Space   │    │ (mic)    │    │ (Whisper)│    │(TTS)  │  │
│  └─────────┘    └──────────┘    └──────────┘    └───────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Tray Menu (Right-click):
| Option | Description |
|--------|-------------|
| Status: ... | Shows current state |
| ✓ Enable Assistant | Start listening for Ctrl+Space |
| ✗ Disable Assistant | Stop listening |
| Exit | Quit application |

### States:
| State | Tray Color | Description |
|-------|------------|-------------|
| Disabled | Gray | Not listening to hotkey |
| Enabled (Ready) | Green | Ready for Ctrl+Space |
| Recording | Red | Currently capturing voice |
| Processing | Yellow | Transcribing/thinking |

## Test Commands (Voice)

Try saying these while holding Ctrl+Space:

### Conversational:
- "Hello"
- "How are you?"
- "What's your name?"

### Desktop Actions:
- "Open YouTube"
- "Open Google"
- "Open my desktop"

### Student Q&A:
- "Explain binary search"
- "What is a linked list?"
- "Tell me about DBMS normalization"

### Knowledge:
- "What is the capital of France?"
- "Who is the president of the United States?"

## Security Guarantees

✅ **Mic access ONLY during Ctrl+Space hold**
✅ **Mic immediately released on key release**
✅ **No audio stored on disk**
✅ **No background listening**
✅ **Permission gate for all actions**
✅ **All events logged for audit**

## Log File

Security events are logged to:
```
~/.saarthi/logs/security.log
```

## Troubleshooting

### Hotkey not working?
- Make sure assistant is **Enabled** (green tray icon)
- Try running as Administrator (some apps block global hotkeys)
- Install pynput: `pip install pynput`

### No transcription?
- Speak clearly while holding Ctrl+Space
- Check microphone is connected and working
- First run may take a moment to load Whisper model

### Tray icon not visible?
- Check "hidden icons" area in system tray
- Click the ^ arrow near the clock

## Run Tests

```bash
python test_voice_only.py
```

## Files Created

| File | Purpose |
|------|---------|
| voice_only.py | Main entry point (voice-only) |
| saarthi_executor/minimal_tray.py | Minimal tray (no dialogs) |
| saarthi_executor/hotkey_voice.py | Ctrl+Space hold-to-talk |
| saarthi_executor/hardened_pipeline.py | Safe voice pipeline |
| saarthi_executor/voice_security.py | Security logging |
| test_voice_only.py | Bug audit tests |

## What Was Removed

❌ Voice command dialog from tray
❌ Text input options
❌ Tray-based recording logic
❌ Toggle voice mode (replaced with hold-to-talk)
❌ CLI text mode

## What Was Preserved

✅ Agentic planner–executor logic
✅ Student features (DSA, OS, DBMS explanations)
✅ Document / resume analysis
✅ Permission system
✅ Safety guardrails
✅ TTS responses
✅ Desktop actions (open browser, etc.)
