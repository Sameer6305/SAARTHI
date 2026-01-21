#!/usr/bin/env python3
"""
SAARTHI Voice Professional
==========================

Production-ready voice assistant with:
- WebRTC Voice Activity Detection (industry-standard VAD)
- Global hotkey (works even when window not focused)
- Audio feedback beeps
- Command history
- No confirmations for known commands
- Continuous operation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import sounddevice as sd
import numpy as np
import whisper
import time
import threading
import json
from collections import deque
from pynput import keyboard
import winsound

# WebRTC VAD for professional voice activity detection
try:
    import webrtcvad
    HAS_WEBRTC_VAD = True
except ImportError:
    HAS_WEBRTC_VAD = False
    print("⚠️  WebRTC VAD not installed. Using basic VAD.")
    print("   For better voice detection: pip install webrtcvad")

from saarthi_executor.integrated_assistant import create_assistant

print()
print("=" * 70)
print("🎯 SAARTHI VOICE PROFESSIONAL")
print("=" * 70)
print()

# Configuration
CONFIG_FILE = Path(__file__).parent / "voice_config.json"
DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+space",  # More professional than F9
    "sample_rate": 16000,
    "silence_duration": 1.2,  # Seconds of silence to stop
    "max_recording": 30,  # Max recording duration
    "vad_aggressiveness": 2,  # 0-3, higher = more aggressive
    "audio_feedback": True,  # Beep sounds
    "save_history": True,
}

def load_config():
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            # Merge with defaults
            return {**DEFAULT_CONFIG, **config}
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

CONFIG = load_config()

# Load Whisper
print("🎤 Loading Whisper TINY model...")
model = whisper.load_model("tiny")
print("   ✓ Model ready")

# Create assistant
print("🤖 Creating assistant (NO confirmations)...")
assistant = create_assistant(enable_tts=True)
print("   ✓ Assistant ready")

# Command history
history_file = Path(__file__).parent / "command_history.json"
command_history = deque(maxlen=100)

def load_history():
    """Load command history."""
    global command_history
    if history_file.exists():
        with open(history_file) as f:
            data = json.load(f)
            command_history = deque(data, maxlen=100)

def save_history():
    """Save command history."""
    if CONFIG["save_history"]:
        with open(history_file, 'w') as f:
            json.dump(list(command_history), f, indent=2)

if CONFIG["save_history"]:
    load_history()

print()
print("=" * 70)
print("✅ SAARTHI READY!")
print("=" * 70)
print()
print("CONTROLS:")
print(f"  • Press {CONFIG['hotkey'].upper()} to start listening")
print("  • Speak your command")
print("  • Automatic silence detection stops recording")
print("  • Actions execute immediately (no confirmations)")
print()
print("Press ESC to exit")
print("=" * 70)
print()


class ProfessionalVAD:
    """Voice Activity Detection using WebRTC VAD or fallback."""
    
    def __init__(self, sample_rate=16000, aggressiveness=2):
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        
        if HAS_WEBRTC_VAD:
            self.vad = webrtcvad.Vad(aggressiveness)
            self.method = "WebRTC"
        else:
            self.vad = None
            self.method = "Threshold"
            self.threshold = 0.01
    
    def is_speech(self, frame):
        """Check if frame contains speech."""
        if self.vad:
            # WebRTC VAD requires 16-bit PCM
            pcm = (frame * 32767).astype(np.int16).tobytes()
            # Frame must be 10, 20, or 30ms
            frame_len = len(pcm) // 2  # 16-bit = 2 bytes per sample
            duration_ms = (frame_len * 1000) // self.sample_rate
            
            if duration_ms in [10, 20, 30]:
                try:
                    return self.vad.is_speech(pcm, self.sample_rate)
                except:
                    pass
        
        # Fallback: threshold-based
        volume = np.sqrt(np.mean(frame**2))
        return volume > self.threshold


class SmartRecorder:
    """Smart audio recorder with VAD."""
    
    def __init__(self, sample_rate=16000, silence_duration=1.2, max_duration=30):
        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.vad = ProfessionalVAD(sample_rate, CONFIG["vad_aggressiveness"])
        
        self.is_recording = False
        self.audio_buffer = []
        self.silence_time = 0
        self.has_speech = False
        
        print(f"   ✓ Using {self.vad.method} VAD")
    
    def audio_callback(self, indata, frames, time_info, status):
        """Process audio stream."""
        if not self.is_recording:
            return
        
        frame = indata.copy().flatten()
        self.audio_buffer.append(frame)
        
        # Check for speech
        is_speech = self.vad.is_speech(frame)
        
        if is_speech:
            self.has_speech = True
            self.silence_time = 0
        elif self.has_speech:
            # Count silence only after we've detected speech
            self.silence_time += frames / self.sample_rate
        
        # Stop if too much silence
        if self.silence_time >= self.silence_duration:
            self.is_recording = False
    
    def record(self):
        """Record audio with smart VAD."""
        self.audio_buffer = []
        self.silence_time = 0
        self.has_speech = False
        self.is_recording = True
        
        # Audio feedback - start beep
        if CONFIG["audio_feedback"]:
            threading.Thread(target=lambda: winsound.Beep(800, 100), daemon=True).start()
        
        print("🎙️  LISTENING... (speak now)")
        
        # Start recording stream
        stream = sd.InputStream(
            callback=self.audio_callback,
            channels=1,
            samplerate=self.sample_rate,
            dtype='float32',
            blocksize=int(self.sample_rate * 0.03),  # 30ms frames
        )
        
        start_time = time.time()
        with stream:
            while self.is_recording:
                time.sleep(0.05)
                
                # Timeout
                if time.time() - start_time > self.max_duration:
                    print("   ⏱️  Max duration reached")
                    break
        
        duration = time.time() - start_time
        
        # Audio feedback - stop beep
        if CONFIG["audio_feedback"]:
            threading.Thread(target=lambda: winsound.Beep(600, 100), daemon=True).start()
        
        print(f"   ✓ Recorded {duration:.1f}s")
        
        if self.audio_buffer:
            return np.concatenate(self.audio_buffer)
        return None


recorder = SmartRecorder(
    CONFIG["sample_rate"],
    CONFIG["silence_duration"],
    CONFIG["max_recording"]
)


def transcribe(audio):
    """Transcribe audio."""
    if audio is None or len(audio) < CONFIG["sample_rate"] * 0.3:
        return None
    
    print("🔄 Transcribing...")
    start = time.time()
    
    result = model.transcribe(
        audio,
        language="en",
        fp16=False,
        verbose=False,
        temperature=0.0,
        best_of=1,
        beam_size=1,
    )
    
    text = result['text'].strip()
    elapsed = time.time() - start
    print(f"   ✓ Done in {elapsed:.1f}s")
    
    return text if text else None


def execute_command(text):
    """Execute command immediately."""
    print(f"📝 \"{text}\"")
    
    # Save to history
    command_history.append({
        "text": text,
        "timestamp": time.time(),
    })
    
    print("⚡ Executing...")
    
    # Process
    response = assistant.process(text)
    
    # Auto-confirm if needed
    if "should i" in response.text.lower():
        print("   🔄 Auto-confirming...")
        response = assistant.process("yes")
    
    print(f"💬 {response.text}")
    if response.action_executed:
        print(f"   ✅ {response.action_type}")
    print()


listening_active = False

def on_activate():
    """Hotkey pressed."""
    global listening_active
    
    if listening_active:
        return
    
    listening_active = True
    print("\n" + "─" * 70)
    
    try:
        # Record
        audio = recorder.record()
        
        if audio is None:
            print("❌ No audio\n")
            return
        
        # Transcribe
        text = transcribe(audio)
        
        if not text:
            print("❌ No speech\n")
            return
        
        # Execute
        execute_command(text)
        
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
    
    finally:
        listening_active = False
        print("─" * 70)
        print(f"Ready! Press {CONFIG['hotkey'].upper()}...")
        print()


# Parse hotkey
def parse_hotkey(hotkey_str):
    """Parse hotkey string like 'ctrl+shift+space'."""
    parts = hotkey_str.lower().split('+')
    keys = []
    
    for part in parts:
        part = part.strip()
        if part == 'ctrl':
            keys.append(keyboard.Key.ctrl)
        elif part == 'shift':
            keys.append(keyboard.Key.shift)
        elif part == 'alt':
            keys.append(keyboard.Key.alt)
        elif part == 'space':
            keys.append(keyboard.Key.space)
        elif len(part) == 1:
            keys.append(keyboard.KeyCode.from_char(part))
        else:
            # Try to get from Key enum
            try:
                keys.append(getattr(keyboard.Key, part))
            except AttributeError:
                print(f"⚠️  Unknown key: {part}")
    
    return keys


# Hotkey management
hotkey_combo = parse_hotkey(CONFIG["hotkey"])
current_keys = set()

def on_press(key):
    """Key pressed."""
    current_keys.add(key)
    
    # Check if hotkey combo is pressed
    if all(k in current_keys for k in hotkey_combo):
        on_activate()

def on_release(key):
    """Key released."""
    try:
        current_keys.discard(key)
    except KeyError:
        pass
    
    # Exit on ESC
    if key == keyboard.Key.esc:
        print("\n👋 Goodbye!")
        save_history()
        return False


print(f"🎯 Ready! Press {CONFIG['hotkey'].upper()} to speak...")
print()

# Start listener
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

save_history()
