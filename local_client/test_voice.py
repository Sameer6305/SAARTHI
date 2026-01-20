"""
Voice Module Test Script
========================

Tests the voice components without requiring full executor.

Usage:
    python test_voice.py [component]
    
Components:
    capture  - Test audio capture
    stt      - Test speech-to-text
    tts      - Test text-to-speech
    pipeline - Test full pipeline
    all      - Test everything
"""

import sys
import time


def test_capture():
    """Test push-to-talk audio capture."""
    print("\n" + "="*60)
    print("TESTING: Audio Capture (Push-to-Talk)")
    print("="*60)
    
    try:
        from saarthi_executor.voice.audio_capture import PushToTalkCapture, CaptureState
        
        def on_state_change(state: CaptureState):
            print(f"  State: {state.value}")
        
        capture = PushToTalkCapture(
            sample_rate=16000,
            max_duration=10.0,
            min_duration=0.5,
            on_state_change=on_state_change,
        )
        
        print(f"\n✓ Audio available: {capture.is_available}")
        
        if not capture.is_available:
            print("✗ No microphone detected - skipping capture test")
            return False
        
        print("\nPress ENTER to start recording (will record for 3 seconds)...")
        input()
        
        print("🎤 Recording... (speak now)")
        capture.start_recording()
        
        time.sleep(3)
        
        print("⏹ Stopping...")
        result = capture.stop_recording()
        
        print(f"\n✓ Capture success: {result.success}")
        print(f"✓ Duration: {result.duration_seconds:.2f}s")
        
        if result.audio:
            print(f"✓ Audio samples: {len(result.audio.data)}")
            result.clear()
            print("✓ Audio buffer cleared")
        
        return result.success
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Install with: pip install sounddevice numpy")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_stt():
    """Test local Whisper STT."""
    print("\n" + "="*60)
    print("TESTING: Speech-to-Text (Local Whisper)")
    print("="*60)
    
    try:
        from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
        from saarthi_executor.voice.config import WhisperModel
        
        print("\nLoading Whisper model (tiny)...")
        print("  This may take a moment on first run (downloads ~75MB)")
        
        stt = LocalWhisperSTT(
            model_name=WhisperModel.TINY,
            device="cpu",
        )
        
        start = time.time()
        loaded = stt.load_model()
        elapsed = time.time() - start
        
        print(f"\n✓ Model loaded: {loaded} ({elapsed:.1f}s)")
        
        if not loaded:
            print("✗ Failed to load model")
            return False
        
        # Test with captured audio
        from saarthi_executor.voice.audio_capture import PushToTalkCapture
        
        capture = PushToTalkCapture()
        
        if not capture.is_available:
            print("✗ No microphone - cannot test STT with real audio")
            return loaded  # Model loaded at least
        
        print("\nPress ENTER to record and transcribe...")
        input()
        
        print("🎤 Recording for 3 seconds...")
        capture.start_recording()
        time.sleep(3)
        result = capture.stop_recording()
        
        if not result.success or not result.audio:
            print("✗ Capture failed")
            return False
        
        print("⏳ Transcribing...")
        transcription = stt.transcribe_and_clear(result.audio)
        
        print(f"\n✓ Status: {transcription.status.value}")
        print(f"✓ Text: '{transcription.text}'")
        print(f"✓ Confidence: {transcription.confidence:.2%}")
        print(f"✓ Processing time: {transcription.processing_seconds:.2f}s")
        print(f"✓ Needs confirmation: {transcription.needs_confirmation}")
        
        return transcription.success
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Install with: pip install openai-whisper")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tts():
    """Test local TTS."""
    print("\n" + "="*60)
    print("TESTING: Text-to-Speech (Windows SAPI)")
    print("="*60)
    
    try:
        from saarthi_executor.voice.tts_local import WindowsSapiTTS
        
        tts = WindowsSapiTTS(volume=80)
        
        print(f"\n✓ TTS available: {tts.is_available}")
        
        if not tts.is_available:
            print("✗ Windows SAPI not available")
            return False
        
        voices = tts.get_voices()
        print(f"✓ Available voices: {len(voices)}")
        for v in voices[:3]:  # Show first 3
            print(f"    - {v}")
        
        print("\nSpeaking test message...")
        result = tts.speak("Hello! This is SAARTHI speaking. Voice features are working correctly.")
        
        print(f"\n✓ Speech success: {result.success}")
        print(f"✓ Duration: {result.duration_seconds:.2f}s")
        
        return result.success
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Install with: pip install pyttsx3")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_pipeline():
    """Test full voice pipeline."""
    print("\n" + "="*60)
    print("TESTING: Full Voice Pipeline")
    print("="*60)
    
    try:
        from saarthi_executor.voice.pipeline import VoicePipeline, VoicePipelineState
        from saarthi_executor.voice.config import VoiceConfig
        
        def on_state_change(state: VoicePipelineState):
            print(f"  Pipeline state: {state.value}")
        
        def on_recording(is_recording: bool):
            if is_recording:
                print("  🎤 Recording started")
            else:
                print("  ⏹ Recording stopped")
        
        config = VoiceConfig(
            enabled=True,
            confirm_ambiguous=True,
            show_recording_indicator=False,  # Disable for test
        )
        
        pipeline = VoicePipeline(
            config=config,
            on_state_change=on_state_change,
            on_recording_state=on_recording,
        )
        
        status = pipeline.get_status()
        print(f"\n✓ Pipeline status: {status}")
        
        if not status.get('capture_available'):
            print("✗ No microphone available")
            return False
        
        print("\nPress ENTER to test push-to-talk...")
        input()
        
        print("🎤 Starting recording (3 seconds)...")
        pipeline.start_listening()
        time.sleep(3)
        
        result = pipeline.stop_listening()
        
        print(f"\n✓ Success: {result.success}")
        print(f"✓ Text: '{result.text}'")
        print(f"✓ Confidence: {result.confidence:.2%}")
        print(f"✓ Needs confirmation: {result.needs_confirmation}")
        
        if result.success and result.text:
            print("\nSpeaking response...")
            pipeline.speak(f"You said: {result.text}")
        
        pipeline.disable()
        print("\n✓ Pipeline disabled and cleaned up")
        
        return result.success
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              SAARTHI Voice Module - Test Suite                    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  This tests the optional voice components:                        ║
║  • Audio Capture (push-to-talk)                                  ║
║  • Speech-to-Text (local Whisper)                                ║
║  • Text-to-Speech (Windows SAPI)                                 ║
║  • Full Pipeline                                                  ║
║                                                                   ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    component = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    results = {}
    
    if component in ("capture", "all"):
        results["capture"] = test_capture()
    
    if component in ("stt", "all"):
        results["stt"] = test_stt()
    
    if component in ("tts", "all"):
        results["tts"] = test_tts()
    
    if component in ("pipeline", "all"):
        results["pipeline"] = test_pipeline()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
