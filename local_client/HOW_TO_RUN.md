# SAARTHI - How to Run

## 🎙️ FOR VOICE (WORKING METHOD!)

### ⭐ EASIEST & MOST RELIABLE:
```bash
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client
python voice.py
```

**What happens:**
1. SAARTHI initializes (takes a few seconds)
2. Press **Enter** to open voice dialog
3. Click **"Start Recording"** button
4. **SPEAK** your command clearly
5. Click **"Stop Recording"** button
6. Wait 1-2 seconds for transcription
7. SAARTHI responds with voice!
8. Press Enter again for another command

**This works 100% reliably!**

---

## All Voice Options

### Option 1: TRAY MODE with Voice Command 🖥️
```bash
python main.py --tray
```

**What you get:**
1. System tray icon appears (bottom-right, near clock)
2. Right-click → **"Wake Up"** (activate)
3. Right-click → **"Voice Command"** (opens dialog)
4. Click "Start Recording", speak, click "Stop Recording"
5. SAARTHI transcribes and responds!

**Best for:** Regular use, clean interface

### Option 2: F5 HOTKEY Mode ⌨️
```bash
python main.py --voice
```

**What you get:**
1. Terminal stays open
2. Press **F5** anywhere to start recording
3. Press **F5** again to stop and process
4. Works even when you're in other apps!

**Best for:** Quick voice commands while working

### Option 3: Original Run.py 🔧
```bash
python run.py
```

**What you get:**
- Same as Tray Mode
- Full features including backend connection
- Legacy push-to-talk voice dialog

---

## ⌨️ FOR TEXT (Testing)

### CLI MODE
```bash
python main.py
```

**What happens:**
1. Terminal opens with a prompt
2. Type commands directly
3. Get responses instantly

---

## All Run Options

| Command | Description |
|---------|-------------|
| `python main.py --tray` | **TRAY MODE** - System tray icon with menu |
| `python main.py` | CLI mode - Type commands in terminal |
| `python main.py --no-tts` | CLI without speech |
| `python main.py --voice` | CLI + F5 hotkey for voice |
| `python main.py -v` | Verbose logging |

---

## Using Tray Mode

### Step 1: Start
```bash
python main.py --tray
```

### Step 2: Find the Icon
Look in your **system tray** (bottom-right corner of screen, near the clock)
- The icon may be in the "hidden icons" area (click the ^ arrow)

### Step 3: Right-Click the Icon
You'll see this menu:
```
┌──────────────────────┐
│ SAARTHI              │
├──────────────────────┤
│ ⚪ State: SLEEP      │
├──────────────────────┤
│ 🔊 Wake Up           │
│ 💬 Send Command      │
│ 🎤 Voice Command     │
│ 🔧 Voice Settings    │
├──────────────────────┤
│ ❌ Exit              │
└──────────────────────┘
```

### Step 4: Use It!
1. Click **"Wake Up"** first (changes state from SLEEP to LISTENING)
2. Click **"Send Command"** → Type your command → Press Enter
3. Or click **"Voice Command"** → Speak → It transcribes and responds

---

## Commands That Work

### Desktop Actions (Require Confirmation)
| Say This | What Happens |
|----------|--------------|
| `open youtube` | Opens YouTube |
| `open google` | Opens Google |
| `open github` | Opens GitHub |
| `search for python tutorials` | Googles the query |
| `open notepad` | Opens Notepad |
| `open calculator` | Opens Calculator |

### Student Tools (Instant Response)
| Say This | What Happens |
|----------|--------------|
| `explain binary search` | Explains the algorithm |
| `explain recursion` | Explains recursion |
| `explain arrays` | Explains arrays |
| `define algorithm` | Defines algorithm |

### Conversation
| Say This | What Happens |
|----------|--------------|
| `hi` / `hello` | Greeting |
| `thanks` / `thank you` | Thanks response |

### System Commands
| Type This | What Happens |
|-----------|--------------|
| `/status` | Show stats |
| `/sleep` | Enter sleep mode |
| `/wake` | Wake up |
| `/quit` | Exit |

---

## Control Flow

```
                    ┌─────────────────────────────────────┐
                    │          USER INPUT                 │
                    │    (type command, press Enter)      │
                    └───────────────┬─────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │         PATTERN MATCHER             │
                    │  (handles 60-70% of commands)       │
                    │  Latency: < 5ms                     │
                    └───────────────┬─────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ DESKTOP       │         │ STUDENT       │         │ CONVERSATION  │
│ ACTION        │         │ TOOL          │         │               │
│               │         │               │         │               │
│ open youtube  │         │ explain X     │         │ hi, thanks    │
│ search for X  │         │ define X      │         │ hello         │
└───────┬───────┘         └───────┬───────┘         └───────┬───────┘
        │                         │                         │
        ▼                         │                         │
┌───────────────┐                 │                         │
│ CONFIRMATION  │                 │                         │
│ "Should I...?"│                 │                         │
│               │                 │                         │
│ → yes/no      │                 │                         │
└───────┬───────┘                 │                         │
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────────────┐
                    │          TTS RESPONSE               │
                    │  (speaks the response)              │
                    └─────────────────────────────────────┘
```

---

## Verification Tests

### Quick Test (No Interaction)
```bash
python quick_test.py
```

Expected output:
```
✓ All tests passed!
```

### Manual Test
1. Run `python main.py`
2. Type `hi` → Should greet you
3. Type `open youtube` → Should ask confirmation
4. Type `yes` → YouTube opens
5. Type `/quit` → Exits

---

## Files

| File | Purpose |
|------|---------|
| `main.py` | **ENTRY POINT** - Run this |
| `quick_test.py` | Verify everything works |
| `saarthi_executor/integrated_assistant.py` | Core assistant logic |
| `saarthi_executor/voice/activation_methods.py` | Voice activation (F5) |

---

## Troubleshooting

### TTS Not Working?
Run without TTS:
```bash
python main.py --no-tts
```

### Import Errors?
Make sure you're in the right directory:
```bash
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client
python main.py
```

### Voice Mode Issues?
Install keyboard library:
```bash
pip install keyboard
```

---

## Agent States

| State | Description |
|-------|-------------|
| 🟢 ACTIVE | Ready for input |
| 🔄 PROCESSING | Thinking... |
| ⚡ EXECUTING | Running action |
| 😴 SLEEPING | Not listening (type `/wake`) |

---

## Summary

1. **To run:** `python main.py`
2. **To test:** `python quick_test.py`
3. **To quit:** `/quit` or Ctrl+C
