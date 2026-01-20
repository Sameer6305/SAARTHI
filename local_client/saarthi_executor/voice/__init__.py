"""
SAARTHI Voice Module
====================

OPTIONAL, FULLY LOCAL voice support for SAARTHI.

PRIVACY GUARANTEES:
- Push-to-talk ONLY (no wake words, no always-on listening)
- All processing is LOCAL (Whisper STT, Windows/Piper TTS)
- No raw audio storage (memory-only during transcription)
- No cloud services
- No background recording
- Explicit user action required to record

SAFETY GUARANTEES:
- Voice input is treated identically to text input
- No special trust or elevated permissions for voice
- Voice can be disabled entirely
- Silence or failure never triggers actions
- Ambiguous input falls back to text confirmation

This module is a CONVENIENCE LAYER only.
It NEVER bypasses permissions, execution rules, or user consent.
"""

__version__ = "1.0.0"

# What voice CAN do
VOICE_CAPABILITIES = [
    "push_to_talk_stt",          # Convert speech to text on user action
    "approved_text_tts",         # Speak already-approved text
    "visual_recording_indicator", # Show when mic is active
]

# What voice will NEVER do
VOICE_FORBIDDEN = [
    "always_on_listening",
    "wake_word_detection",
    "background_recording",
    "raw_audio_storage",
    "cloud_stt",
    "cloud_tts",
    "automatic_mic_activation",
    "silent_recording",
    "audio_telemetry",
]
