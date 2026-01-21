"""
Simple Voice Test - No Tray, Just Voice
========================================

Test voice input without tray complications.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print()
print("="*60)
print("SIMPLE VOICE TEST")
print("="*60)
print()
print("Initializing voice...")

from saarthi_executor.voice.integration import VoiceIntegration
from saarthi_executor.integrated_assistant import create_assistant

# Callback when voice is transcribed
def handle_voice(text: str):
    print(f"\n>>> You said: \"{text}\"")
    
    # Process with assistant
    response = assistant.process(text)
    
    print(f">>> SAARTHI: {response.text}\n")
    
    if response.action_executed:
        print(f"    [Action executed: {response.action_type}]")

# Create voice integration
voice = VoiceIntegration(on_voice_input=handle_voice)

# Create assistant
assistant = create_assistant(enable_tts=True)

# Initialize
print("Initializing...")
if not voice.initialize():
    print("ERROR: Voice initialization failed")
    sys.exit(1)

print("Voice ready!")
print()
print("="*60)
print("HOW TO USE:")
print("="*60)
print()
print("  1. Click 'Start Recording' button")
print("  2. SPEAK your command")
print("  3. Click 'Stop Recording'")
print("  4. Wait for transcription")
print("  5. SAARTHI responds!")
print()
print("  Try saying:")
print("    - 'hi'")
print("    - 'open youtube'")
print("    - 'yes' (to confirm)")
print("    - 'explain binary search'")
print()
print("="*60)
print()

input("Press Enter to open voice dialog...")

from saarthi_executor.voice_command_dialog import show_voice_command_dialog

def start_recording():
    print("[Recording started]")
    return voice.start_push_to_talk()

def stop_recording():
    print("[Recording stopped, transcribing...]")
    result = voice.stop_push_to_talk()
    if result:
        text, confidence = result
        print(f"[Transcribed: \"{text}\" (confidence: {confidence:.2f})]")
    return result

def send_text(text):
    print(f"[Sending: \"{text}\"]")
    handle_voice(text)
    return {"success": True}

def cancel():
    print("[Cancelled]")
    voice.cancel_recording()

try:
    while True:
        result = show_voice_command_dialog(
            on_start_recording=start_recording,
            on_stop_recording=stop_recording,
            on_send_text=send_text,
            on_cancel_recording=cancel,
        )
        
        if result:
            print(f"\nDialog result: {result.result.value}")
            if result.transcribed_text:
                print(f"Text: {result.transcribed_text}")
        
        again = input("\nTry again? (y/n): ").strip().lower()
        if again != 'y':
            break

except KeyboardInterrupt:
    print("\nExiting...")

voice.cleanup()
print("\nDone!")
