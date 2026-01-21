#!/usr/bin/env python3
"""
SAARTHI Voice Mode - WORKING VERSION
=====================================

This is the SIMPLEST way to use voice with SAARTHI.
No tray complications, just pure voice + assistant.

Press Enter → Dialog opens → Click 'Start Recording' → Speak → Click 'Stop' → Get response!
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

print()
print("╔════════════════════════════════════════════════════════════╗")
print("║          SAARTHI VOICE MODE (Working)                      ║")
print("╠════════════════════════════════════════════════════════════╣")
print("║  This is the reliable way to use voice!                    ║")
print("║                                                            ║")
print("║  How it works:                                             ║")
print("║  1. Press Enter                                            ║")
print("║  2. Voice dialog opens                                     ║")
print("║  3. Click 'Start Recording'                                ║")
print("║  4. SPEAK your command                                     ║")
print("║  5. Click 'Stop Recording'                                 ║")
print("║  6. SAARTHI transcribes and responds!                      ║")
print("║                                                            ║")
print("║  Try commands like:                                        ║")
print("║    - 'hi'                                                  ║")
print("║    - 'open youtube'                                        ║")
print("║    - 'yes' (to confirm actions)                            ║")
print("║    - 'explain binary search'                               ║")
print("║    - 'search for python tutorials'                         ║")
print("╚════════════════════════════════════════════════════════════╝")
print()

print("🔧 Initializing SAARTHI...")

# Import components
from saarthi_executor.voice.integration import VoiceIntegration
from saarthi_executor.integrated_assistant import create_assistant
from saarthi_executor.voice_command_dialog import show_voice_command_dialog

# Create assistant (with TTS)
assistant = create_assistant(enable_tts=True)
print("   ✓ Assistant ready")

# Create voice integration
def on_voice_input(text: str):
    """Called when voice is transcribed."""
    print(f"\n📝 Transcribed: \"{text}\"")
    print("🤔 Processing...\n")
    
    # Process through assistant
    response = assistant.process(text)
    
    # Show response
    print(f"💬 SAARTHI: {response.text}")
    
    if response.action_executed:
        print(f"   ⚡ Action: {response.action_type}")
    
    if response.needs_clarification:
        print(f"   ❓ Needs clarification")
    
    print()

voice = VoiceIntegration(on_voice_input=on_voice_input)

# Initialize voice
print("🎤 Initializing voice...")
if not voice.initialize():
    print("❌ Voice initialization failed!")
    print("   Make sure you have a microphone connected.")
    sys.exit(1)

print("   ✓ Voice ready")
print()
print("=" * 60)
print("✅ SAARTHI IS READY!")
print("=" * 60)
print()

# Voice dialog callbacks
def start_recording():
    """Start recording voice."""
    success = voice.start_push_to_talk()
    if success:
        print("🎙️  RECORDING... (speak now)")
    else:
        print("❌ Failed to start recording")
    return success

def stop_recording():
    """Stop recording and transcribe."""
    print("⏹️  Stopping recording...")
    result = voice.stop_push_to_talk()
    
    if result:
        text, confidence = result
        print(f"✓ Transcribed with {confidence*100:.0f}% confidence")
        return result
    else:
        print("❌ No speech detected or transcription failed")
        return None

def send_text(text):
    """Send text to assistant."""
    on_voice_input(text)
    return {"success": True}

def cancel():
    """Cancel recording."""
    print("❌ Recording cancelled")
    voice.cancel_recording()

# Main loop
session_count = 0

try:
    while True:
        session_count += 1
        print(f"[Session {session_count}]")
        
        input("Press Enter to open voice dialog (or Ctrl+C to quit)...")
        
        print("\n→ Opening voice dialog...")
        print("  Click 'Start Recording', speak, then click 'Stop Recording'\n")
        
        # Show voice dialog
        result = show_voice_command_dialog(
            on_start_recording=start_recording,
            on_stop_recording=stop_recording,
            on_send_text=send_text,
            on_cancel_recording=cancel,
        )
        
        if result:
            print(f"✓ Dialog completed: {result.result.value}")
            if result.transcribed_text:
                print(f"  Text: \"{result.transcribed_text}\"")
        
        print("\n" + "─" * 60 + "\n")

except KeyboardInterrupt:
    print("\n\n🛑 Shutting down...")

# Cleanup
voice.cleanup()
assistant.cleanup()

print("\n👋 Goodbye!\n")
