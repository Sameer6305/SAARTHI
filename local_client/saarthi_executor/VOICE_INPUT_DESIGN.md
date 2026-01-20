# SAARTHI Voice Input Design Document

## Overview

Voice input is the **PRIMARY** user interaction method for SAARTHI local client. This document describes the design, implementation, and security guarantees.

## Design Principles

### 1. PUSH-TO-TALK ONLY
- ❌ **No** wake words ("Hey SAARTHI")
- ❌ **No** background listening
- ❌ **No** always-on microphone
- ✅ User must **explicitly** press and hold button to record
- ✅ Recording stops **immediately** on button release

### 2. LOCAL PROCESSING ONLY
- ❌ **No** cloud speech-to-text
- ❌ **No** audio transmitted over network
- ✅ Whisper STT runs **100% locally** on CPU
- ✅ Audio **never** leaves the device

### 3. AUDIO IN MEMORY ONLY
- ❌ **No** audio saved to disk
- ❌ **No** audio caching
- ✅ Audio exists **only** in RAM during processing
- ✅ Audio buffer **cleared immediately** after transcription

### 4. VOICE = UNTRUSTED INPUT
- ✅ Voice goes through **SAME** permission flow as text
- ✅ Voice goes through **SAME** allowlist checks
- ✅ Voice goes through **SAME** audit logging
- ❌ **No** special trust for voice input
- ❌ **No** bypass of security gates

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SAARTHI Voice Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│  │   TRAY MENU  │ ──► │  VOICE CMD   │ ──► │  PUSH-TO-TALK    │ │
│  │ 🎤 Voice Cmd │     │   DIALOG     │     │   RECORDING      │ │
│  │  (PRIMARY)   │     │              │     │                  │ │
│  └──────────────┘     └──────────────┘     └────────┬─────────┘ │
│                                                      │           │
│                                                      ▼           │
│                       ┌──────────────────────────────────────┐  │
│                       │         AUDIO CAPTURE                │  │
│                       │   • Memory buffer only               │  │
│                       │   • Max 30 seconds                   │  │
│                       │   • 16kHz sample rate                │  │
│                       └────────────────┬─────────────────────┘  │
│                                        │                        │
│                                        ▼                        │
│                       ┌──────────────────────────────────────┐  │
│                       │      LOCAL WHISPER STT               │  │
│                       │   • 100% offline                     │  │
│                       │   • CPU-compatible                   │  │
│                       │   • Audio cleared after use          │  │
│                       └────────────────┬─────────────────────┘  │
│                                        │                        │
│                                        ▼                        │
│                       ┌──────────────────────────────────────┐  │
│                       │      TRANSCRIBED TEXT                │  │
│                       │   • May be edited by user            │  │
│                       │   • Low confidence = confirm         │  │
│                       └────────────────┬─────────────────────┘  │
│                                        │                        │
│                                        ▼                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │               SAME PIPELINE AS TEXT INPUT                  │ │
│  │   • Backend client → Planner                               │ │
│  │   • Actions → Allowlist check                              │ │
│  │   • Permission dialog (user must ALLOW)                    │ │
│  │   • Execution (if permitted)                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## User Flow

### 1. Start Voice Command
1. User right-clicks tray icon
2. User clicks "🎤 Voice Command" (PRIMARY - bold, top of menu)
3. Voice Command Dialog opens

### 2. Push-to-Talk Recording
1. Dialog shows "🎤 Hold to Talk" button
2. User **presses and holds** the button
3. Visual indicator turns RED: "🔴 RECORDING..."
4. Tray icon turns RED to show recording state
5. User speaks their command
6. User **releases** button

### 3. Transcription
1. Button shows "⏳ Processing..."
2. Local Whisper STT processes audio
3. Audio buffer is **immediately cleared**
4. Transcribed text appears in editable field
5. Confidence level is displayed

### 4. Confirmation and Send
1. User can **edit** transcribed text if needed
2. Low confidence triggers explicit warning
3. User clicks "Send Command" to submit
4. Text goes through **same flow as typed text**

## Security Guarantees

### Recording Safety
| Guarantee | Implementation |
|-----------|---------------|
| No background listening | `PushToTalkCapture` only records while button held |
| Visible recording state | Red indicator overlay + tray icon |
| User can cancel | Click indicator or close dialog |
| Max duration enforced | 30 second hard limit |

### Audio Privacy
| Guarantee | Implementation |
|-----------|---------------|
| No disk writes | `AudioBuffer` exists only in RAM |
| Immediate disposal | `audio.clear()` called after STT |
| Secure clear | Buffer overwritten with zeros |
| No caching | No audio stored between sessions |

### Permission Enforcement
| Guarantee | Implementation |
|-----------|---------------|
| Same allowlist | Voice text → `_handle_dialog_send()` → backend |
| Same permission dialogs | Actions require explicit ALLOW |
| Same audit logging | `security_logger` records all events |
| No voice bypass | Voice is **just text** to permission system |

## Components

### Files Modified
- [tray_app.py](saarthi_executor/tray_app.py) - Added "🎤 Voice Command" as PRIMARY menu item
- [executor.py](saarthi_executor/executor.py) - Added voice integration methods

### Files Created
- [voice_command_dialog.py](saarthi_executor/voice_command_dialog.py) - Push-to-talk dialog UI

### Existing Voice Module
- [voice/pipeline.py](saarthi_executor/voice/pipeline.py) - Voice pipeline orchestrator
- [voice/audio_capture.py](saarthi_executor/voice/audio_capture.py) - Push-to-talk capture
- [voice/stt_whisper.py](saarthi_executor/voice/stt_whisper.py) - Local Whisper STT
- [voice/integration.py](saarthi_executor/voice/integration.py) - Executor integration
- [voice/ui_components.py](saarthi_executor/voice/ui_components.py) - Recording indicator

## Configuration

Voice is **disabled by default**. User must explicitly enable.

```python
# voice/config.py
@dataclass
class VoiceConfig:
    # Master switch - OFF by default
    enabled: bool = False
    
    # STT settings
    whisper_model: WhisperModel = WhisperModel.SMALL
    max_recording_seconds: float = 30.0
    min_recording_seconds: float = 0.5
    
    # Confidence thresholds
    min_confidence: float = 0.3      # Below = reject
    ambiguous_confidence: float = 0.6 # Below = confirm
    
    # UI settings
    show_recording_indicator: bool = True
    play_feedback_sounds: bool = True
```

## Dependencies

```
# Voice Support
sounddevice==0.4.6     # Audio capture
numpy==1.26.3          # Audio processing
openai-whisper==20231117  # Local STT
pyttsx3==2.90          # TTS (optional)
```

## Error Handling

| Error | Handling |
|-------|----------|
| No microphone | Show error, disable voice button |
| Recording too short | Show "No speech detected" |
| Low confidence | Show confirmation dialog |
| STT timeout | Show error, reset to ready |
| Model not loaded | Pre-load on startup, show loading indicator |

## Audit Trail

All voice events are logged:

```
2024-XX-XX 12:00:00 - Voice recording started (source: push_to_talk)
2024-XX-XX 12:00:05 - Voice transcription complete (text_preview: "open youtube...")
2024-XX-XX 12:00:05 - Voice command submitted (source: voice_push_to_talk)
2024-XX-XX 12:00:06 - Command sent to backend (task_id: xxx)
```

## Testing Checklist

- [ ] Voice Command appears as PRIMARY (bold) in tray menu
- [ ] Push-to-talk button starts/stops recording on press/release
- [ ] Recording indicator shows RED while recording
- [ ] Tray icon turns RED while recording
- [ ] Transcription appears after release
- [ ] Low confidence shows warning
- [ ] Edited text can be sent
- [ ] Voice commands go through permission dialogs
- [ ] Audio is not saved to disk
- [ ] Voice works without internet (local Whisper)
