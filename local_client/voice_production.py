#!/usr/bin/env python3
"""
SAARTHI Voice - PRODUCTION MODE
================================

Production-ready voice assistant with:
- Voice Activity Detection (auto-detects when you stop speaking)
- Hotkey activation (F5 to start listening)
- No confirmations (direct execution)
- No terminal prompts (runs in background)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import sounddevice as sd
import numpy as np
import whisper
import time
import threading
import keyboard
from collections import deque

# Create assistant WITHOUT confirmations
from saarthi_executor.integrated_assistant import create_assistant

print("=" * 70)
print("SAARTHI VOICE - PRODUCTION MODE")
print("=" * 70)
print()

# Load Whisper TINY model
print("🎤 Loading Whisper model...")
model = whisper.load_model("tiny")
print("   ✓ Model loaded")

# Create assistant with TTS but NO confirmations
print("🤖 Creating assistant...")
assistant = create_assistant(enable_tts=True)
print("   ✓ Assistant ready")

print()
print("=" * 70)
print("✅ SAARTHI IS READY!")
print("=" * 70)
print()
print("HOW TO USE:")
print("  1. Press F9 to start listening")
print("  2. Speak your command")
print("  3. Stop speaking - it will auto-detect silence")
print("  4. Get instant response and action!")
print()
print("Press Ctrl+C to exit")
print("=" * 70)
print()

# Voice Activity Detection parameters
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01  # Volume threshold for silence
SILENCE_DURATION = 1.5     # Seconds of silence before stopping
MAX_RECORDING_TIME = 30    # Maximum recording duration

class VoiceRecorder:
    """Records audio with voice activity detection."""
    
    def __init__(self):
        self.is_recording = False
        self.audio_buffer = []
        self.silence_counter = 0
        
    def audio_callback(self, indata, frames, time_info, status):
        """Called for each audio chunk."""
        if not self.is_recording:
            return
            
        # Calculate volume (RMS)
        volume = np.sqrt(np.mean(indata**2))
        
        # Store audio
        self.audio_buffer.append(indata.copy())
        
        # Check for silence
        if volume < SILENCE_THRESHOLD:
            self.silence_counter += frames / SAMPLE_RATE
        else:
            self.silence_counter = 0
            
        # Stop if too much silence
        if self.silence_counter >= SILENCE_DURATION:
            self.is_recording = False
    
    def record_with_vad(self):
        """Record until silence is detected."""
        self.audio_buffer = []
        self.silence_counter = 0
        self.is_recording = True
        
        print("🎙️  LISTENING... (speak now, will auto-stop)")
        
        # Start recording stream
        stream = sd.InputStream(
            callback=self.audio_callback,
            channels=1,
            samplerate=SAMPLE_RATE,
            dtype='float32',
        )
        
        start_time = time.time()
        with stream:
            # Wait until recording stops or timeout
            while self.is_recording:
                time.sleep(0.1)
                
                # Timeout safety
                if time.time() - start_time > MAX_RECORDING_TIME:
                    print("   ⚠️  Max recording time reached")
                    break
        
        duration = time.time() - start_time
        print(f"   ✓ Recorded {duration:.1f}s")
        
        # Combine audio chunks
        if self.audio_buffer:
            audio = np.concatenate(self.audio_buffer, axis=0).flatten()
            return audio
        return None

recorder = VoiceRecorder()

def transcribe(audio):
    """Transcribe audio using Whisper."""
    if audio is None or len(audio) < SAMPLE_RATE * 0.5:  # Too short
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

def process_and_execute(text):
    """Process command and execute immediately (NO confirmation)."""
    print(f"📝 You said: \"{text}\"")
    print("⚡ Executing...")
    
    # Process with assistant
    response = assistant.process(text)
    
    # If confirmation was requested, auto-confirm
    if "should i" in response.text.lower() or "confirm" in response.text.lower():
        print("   🔄 Auto-confirming...")
        response = assistant.process("yes")
    
    print(f"💬 {response.text}")
    if response.action_executed:
        print(f"   ✅ Action completed: {response.action_type}")
    print()

listening_active = False

def on_hotkey():
    """Called when F5 is pressed."""
    global listening_active
    
    if listening_active:
        return  # Already processing
    
    listening_active = True
    print("\n" + "─" * 70)
    
    try:
        # Record with VAD
        audio = recorder.record_with_vad()
        
        if audio is None:
            print("❌ No audio captured\n")
            return
        
        # Transcribe
        text = transcribe(audio)
        
        if not text:
            print("❌ No speech detected\n")
            return
        
        # Execute immediately
        process_and_execute(text)
        
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    finally:
        listening_active = False
        print("─" * 70)
        print("Press F9 to speak again...")
        print()

# Register hotkey
print("Registering F9 hotkey...")
keyboard.add_hotkey('f9', on_hotkey)
print("✓ Hotkey registered\n")

print("🎯 Ready! Press F9 to start speaking...")
print()

# Keep running
try:
    keyboard.wait()  # Wait forever
except KeyboardInterrupt:
    print("\n\n👋 Goodbye!")
