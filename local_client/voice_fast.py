#!/usr/bin/env python3
"""
SAARTHI Voice Mode - FAST VERSION
==================================

Ultra-fast voice mode using TINY Whisper model.
Transcription in < 1 second!

Usage:
    python voice_fast.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.WARNING)  # Reduce log noise

print()
print("╔════════════════════════════════════════════════════════════╗")
print("║          SAARTHI VOICE MODE (FAST)                         ║")
print("╠════════════════════════════════════════════════════════════╣")
print("║  ULTRA-FAST transcription with Whisper TINY model          ║")
print("║  Transcription: < 1 second!                                ║")
print("╚════════════════════════════════════════════════════════════╝")
print()

print("🔧 Initializing SAARTHI...")

# Import components
from saarthi_executor.voice.config import VoiceConfig, WhisperModel
from saarthi_executor.voice.integration import VoiceIntegration
from saarthi_executor.integrated_assistant import create_assistant
from saarthi_executor.voice_command_dialog import show_voice_command_dialog

# Create assistant (with TTS)
assistant = create_assistant(enable_tts=True)
print("   ✓ Assistant ready")

# Callback when voice is transcribed
def on_voice_input(text: str):
    """Called when voice is transcribed."""
    print(f"\n📝 You said: \"{text}\"")
    
    # Process through assistant
    import time
    start = time.time()
    response = assistant.process(text)
    elapsed = time.time() - start
    
    # Show response
    print(f"💬 SAARTHI: {response.text}")
    print(f"   (Responded in {elapsed:.2f}s)")
    
    if response.action_executed:
        print(f"   ⚡ Action: {response.action_type}")
    
    print()

# Create FAST config with TINY model
fast_config = VoiceConfig(
    enabled=True,
    whisper_model=WhisperModel.TINY,  # FASTEST model
    stt_timeout_seconds=10.0,  # Shorter timeout
    min_confidence=0.2,  # Lower threshold
)

# Create voice integration with fast config
voice = VoiceIntegration(on_voice_input=on_voice_input)
voice._config = fast_config  # Override with fast config

# Initialize voice
print("🎤 Initializing FAST voice (Whisper TINY)...")
if not voice.initialize():
    print("❌ Voice initialization failed!")
    sys.exit(1)

print("   ✓ Voice ready (Whisper TINY loaded)")
print()
print("=" * 60)
print("✅ SAARTHI IS READY! (FAST MODE)")
print("=" * 60)
print()
print("Whisper TINY model:")
print("  - Transcription: < 1 second")
print("  - Accuracy: ~90% (good for simple commands)")
print("  - Memory: Low (~75MB)")
print()

# Voice dialog callbacks
def start_recording():
    """Start recording voice."""
    success = voice.start_push_to_talk()
    if success:
        print("🎙️  RECORDING...")
    return success

def stop_recording():
    """Stop recording and transcribe."""
    print("⏹️  Transcribing... (this will be fast!)")
    import time
    start = time.time()
    
    result = voice.stop_push_to_talk()
    
    if result:
        text, confidence = result
        elapsed = time.time() - start
        print(f"✓ Done in {elapsed:.2f}s! (confidence: {confidence*100:.0f}%)")
        return result
    else:
        print("❌ No speech detected")
        return None

def send_text(text):
    """Send text to assistant."""
    on_voice_input(text)
    return {"success": True}

def cancel():
    """Cancel recording."""
    voice.cancel_recording()

# Main loop
session_count = 0

try:
    while True:
        session_count += 1
        print(f"\n[Session {session_count}]")
        
        input("Press Enter to speak (or Ctrl+C to quit)...")
        
        print()
        
        # Show voice dialog
        result = show_voice_command_dialog(
            on_start_recording=start_recording,
            on_stop_recording=stop_recording,
            on_send_text=send_text,
            on_cancel_recording=cancel,
        )
        
        if result and result.transcribed_text:
            print(f"✓ Session complete")
        
        print("─" * 60)

except KeyboardInterrupt:
    print("\n\n🛑 Shutting down...")

# Cleanup
voice.cleanup()
assistant.cleanup()

print("\n👋 Goodbye!\n")
