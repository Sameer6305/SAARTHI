# SAARTHI - Complete Setup & Run Guide

## 🚀 Quick Start (One Command)

```bash
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client
python start.py
```

This will:
1. ✓ Check all dependencies
2. ✓ Verify microphone
3. ✓ Check Whisper model
4. ✓ Let you choose mode
5. ✓ Start SAARTHI

---

## 📋 Prerequisites

### Required:
- Python 3.8 or higher
- Windows 10/11

### Will be checked/installed:
- sounddevice (audio recording)
- openai-whisper (speech-to-text)
- pystray (system tray)
- Pillow (icons)
- pywin32 (Windows TTS)

---

## 🎯 Modes Available

### 1. Voice Mode (Recommended) 🎙️
```bash
python start.py
# Choose option 1
```

**What you get:**
- Press Enter → Voice dialog opens
- Click "Start Recording" → Speak → Click "Stop"
- SAARTHI transcribes and responds with voice
- Perfect for regular use

**Commands to try:**
- "hi"
- "open youtube"
- "yes" (to confirm)
- "explain binary search"

---

### 2. CLI Mode (Text) ⌨️
```bash
python start.py
# Choose option 2
```

**What you get:**
- Type commands in terminal
- Get voice responses
- Good for testing

**Example:**
```
You > hi
SAARTHI: Hello! How can I help you today?

You > open youtube
SAARTHI: Should I open youtube?

You > yes
[YouTube opens]
```

---

### 3. Tray Mode (Background) 🖥️
```bash
python start.py
# Choose option 3
```

**What you get:**
- System tray icon (bottom-right)
- Right-click for menu
- "Wake Up" to activate
- "Send Command" for text
- "Voice Command" for speech

---

### 4. CLI Mode (No TTS) 🔇
```bash
python start.py
# Choose option 4
```

**What you get:**
- Same as CLI mode but no speech
- Faster response
- Good for quiet environments

---

## 🎬 First Time Setup

### Step 1: Install Dependencies
```bash
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client
pip install sounddevice openai-whisper pystray Pillow pywin32
```

### Step 2: Test It
```bash
python start.py
```

Choose option 1 (Voice Mode) and try saying "hi"

---

## 🧪 Testing Each Component

### Test 1: Basic Import
```bash
python quick_test.py
```
Expected: "✓ All tests passed!"

### Test 2: Voice Dialog
```bash
python test_voice_simple.py
```
Expected: Dialog opens, you can record

### Test 3: Full Voice
```bash
python voice.py
```
Expected: Full voice interaction

---

## 🔧 Common Issues & Fixes

### Issue: "ModuleNotFoundError"
**Fix:**
```bash
pip install sounddevice openai-whisper pystray Pillow pywin32
```

### Issue: "No microphone found"
**Fix:**
1. Plug in a microphone
2. Check Windows Sound settings
3. Test with: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### Issue: "Whisper model download takes forever"
**Fix:**
- First run downloads ~140MB model
- Takes 1-5 minutes depending on internet
- Only happens once
- Stored in: `%USERPROFILE%\.cache\whisper\`

### Issue: "TTS not working"
**Fix:**
Run without TTS:
```bash
python start.py
# Choose option 4 (No TTS)
```

### Issue: "Voice dialog doesn't open"
**Check:**
1. Is Python in foreground?
2. Is another window blocking it?
3. Try: `python test_voice_simple.py` to test just the dialog

### Issue: "Exit code 1"
**Debug:**
```bash
python main.py -v
```
(Verbose mode shows detailed errors)

---

## 📊 System Requirements

### Minimum:
- **CPU:** Any modern processor
- **RAM:** 4GB (8GB recommended for Whisper)
- **Disk:** 500MB (for Whisper model)
- **OS:** Windows 10/11
- **Python:** 3.8+

### For Best Performance:
- **RAM:** 8GB+
- **CPU:** Multi-core
- **SSD:** Faster model loading

---

## ✅ Verification Checklist

After running `python start.py`, verify:

- [ ] Step 1: Python version OK
- [ ] Step 2: All dependencies installed
- [ ] Step 3: Microphone detected
- [ ] Step 4: Whisper model ready
- [ ] Step 5: Mode chosen
- [ ] Step 6: SAARTHI started
- [ ] Step 7: Can interact (voice/text)
- [ ] Step 8: Gets responses
- [ ] Step 9: Actions work (with confirmation)

---

## 🎯 Quick Commands Reference

| Command | What It Does |
|---------|-------------|
| `python start.py` | Start with setup checks |
| `python voice.py` | Voice mode directly |
| `python main.py` | CLI mode directly |
| `python main.py --tray` | Tray mode directly |
| `python main.py --no-tts` | CLI without speech |
| `python quick_test.py` | Test core functions |
| `python test_voice_simple.py` | Test voice dialog |

---

## 📖 What Works Right Now

### ✅ Voice Features:
- Whisper STT (local, accurate)
- Push-to-talk dialog
- Windows SAPI TTS
- Noise cancellation
- Confidence scoring

### ✅ Assistant Features:
- Conversational responses
- Confirmation for actions
- Student tools (explain, define)
- Desktop actions (open apps, search)
- Multi-turn context
- Pattern matching (fast responses)

### ✅ Desktop Actions:
- Open websites (youtube, google, github, etc.)
- Open apps (notepad, calculator)
- Web search
- File operations (view in notepad)

### ✅ Student Tools:
- Explain algorithms
- Define terms
- Quick reference

### ✅ Privacy:
- 100% local processing
- No cloud required
- Audio never saved
- Session-only memory

---

## 🚦 What to Expect

### First Run:
- Takes 3-5 seconds to initialize
- May download Whisper model (~140MB)
- Loads TTS engine
- Initializes microphone

### Subsequent Runs:
- Starts in 2-3 seconds
- Everything cached
- Fast responses

### Voice Commands:
- Transcription: 1-2 seconds
- Response generation: < 1 second
- Total: 2-3 seconds per command

---

## 💡 Tips for Best Experience

1. **Speak Clearly:** Whisper works best with clear speech
2. **Short Commands:** "open youtube" better than long sentences
3. **Confirm Actions:** Desktop actions need "yes" to execute
4. **Use Voice Mode:** It's the most reliable
5. **Check Logs:** If issues, check terminal output

---

## 🆘 Still Having Issues?

### Get Help:
1. Run: `python start.py` (it checks everything)
2. Check the terminal output for errors
3. Try each test file individually
4. Start with simplest mode (option 4 - No TTS)

### Debug Mode:
```bash
python main.py -v
```
Shows detailed logs

---

## ✅ Success Criteria

You'll know it's working when:

1. ✓ `python start.py` runs without errors
2. ✓ You can choose a mode
3. ✓ SAARTHI starts up
4. ✓ You can interact (type or speak)
5. ✓ You get responses back
6. ✓ Actions work (with your permission)

**That's it! SAARTHI is fully operational!**
