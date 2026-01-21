#!/usr/bin/env python3
"""
SAARTHI Voice - SIMPLIFIED VERSION
===================================

Dead-simple voice input without complex state machines.
Just: Record → Transcribe → Respond

NO complex pipelines, NO state machines, NO threading issues!
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print()
print("╔════════════════════════════════════════════════════════════╗")
print("║          SAARTHI VOICE (SIMPLE & WORKING)                  ║")
print("╚════════════════════════════════════════════════════════════╝")
print()

# Minimal imports
import sounddevice as sd
import numpy as np
import whisper
import time

# Create assistant
from saarthi_executor.integrated_assistant import create_assistant
print("🔧 Loading assistant...")
assistant = create_assistant(enable_tts=True)
print("   ✓ Ready")

# Load Whisper TINY model
print("🎤 Loading Whisper TINY model...")
model = whisper.load_model("tiny")
print("   ✓ Ready")

print()
print("=" * 60)
print("✅ SAARTHI READY!")
print("=" * 60)
print()

def record_audio(duration=5, sample_rate=16000):
    """Record audio from microphone."""
    print(f"🎙️  Recording for {duration} seconds...")
    print("   SPEAK NOW!")
    
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32'
    )
    sd.wait()  # Wait for recording to complete
    
    print("   ✓ Recording complete")
    return audio.flatten()

def transcribe(audio):
    """Transcribe audio using Whisper."""
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
    elapsed = time.time() - start
    
    text = result['text'].strip()
    print(f"   ✓ Done in {elapsed:.1f}s")
    
    return text

def process_command(text):
    """Process command with assistant."""
    print(f"\n📝 You said: \"{text}\"")
    print(f"   Length: {len(text)} chars")
    print(f"   Repr: {repr(text)}")
    print("🤔 Processing...\n")
    
    response = assistant.process(text)
    
    print(f"💬 SAARTHI: {response.text}")
    if response.action_executed:
        print(f"   ⚡ Action: {response.action_type}")
    print()

# Main loop
print("HOW TO USE:")
print("  1. Press Enter when ready to speak")
print("  2. Speak for ~3-5 seconds")
print("  3. Wait for transcription")
print("  4. Get response!")
print()

session = 0
try:
    while True:
        session += 1
        print(f"[Session {session}]")
        
        input("Press Enter to record (or Ctrl+C to quit)...")
        
        try:
            # Record
            audio = record_audio(duration=5)
            
            # Transcribe  
            text = transcribe(audio)
            
            if not text:
                print("❌ No speech detected\n")
                continue
            
            # Process
            process_command(text)
            
        except Exception as e:
            print(f"❌ Error: {e}\n")
            continue
        
        print("─" * 60 + "\n")

except KeyboardInterrupt:
    print("\n\n👋 Goodbye!\n")
