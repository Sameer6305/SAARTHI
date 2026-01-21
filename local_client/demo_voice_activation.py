"""
Voice Activation Demo
=====================

Test different voice activation methods.

Run: python demo_voice_activation.py

Choose from:
1. HOTKEY (F5) - Press F5 to toggle
2. DOUBLE-TAP - Double-tap Ctrl to toggle
3. CLAP - Clap twice to toggle (requires pyaudio)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def demo_hotkey():
    """Demo hotkey activation."""
    print("\n" + "="*50)
    print("  HOTKEY ACTIVATION DEMO")
    print("="*50)
    print("\nPress F5 to start/stop voice")
    print("Press Escape to cancel")
    print("Press Ctrl+C to exit demo\n")
    
    try:
        from saarthi_executor.voice.activation_methods import HotkeyActivation
        
        def on_start():
            print("\n🎤 LISTENING... (speak now)")
            print("   Press F5 again to stop\n")
        
        def on_stop():
            print("\n✓ STOPPED - Processing your voice...\n")
            # Here you would process the audio
            time.sleep(0.5)
            print("   (Voice would be transcribed here)\n")
        
        def on_cancel():
            print("\n❌ CANCELLED\n")
        
        activator = HotkeyActivation(
            hotkey="f5",
            on_start=on_start,
            on_stop=on_stop,
            on_cancel=on_cancel,
        )
        
        if activator.start():
            print("✓ Ready! Press F5 to talk.\n")
            
            # Keep running
            while True:
                time.sleep(0.1)
        else:
            print("Failed to start hotkey listener")
            
    except KeyboardInterrupt:
        print("\nDemo ended.")
    except ImportError:
        print("\n⚠ Install keyboard library:")
        print("  pip install keyboard")
        print("\nNote: May require admin privileges on Windows.")


def demo_double_tap():
    """Demo double-tap activation."""
    print("\n" + "="*50)
    print("  DOUBLE-TAP ACTIVATION DEMO")
    print("="*50)
    print("\nDouble-tap Ctrl key to start/stop voice")
    print("Press Ctrl+C to exit demo\n")
    
    try:
        from saarthi_executor.voice.activation_methods import DoubleTapActivation
        
        def on_start():
            print("\n🎤 LISTENING... (speak now)")
            print("   Double-tap Ctrl again to stop\n")
        
        def on_stop():
            print("\n✓ STOPPED - Processing...\n")
        
        activator = DoubleTapActivation(
            key="ctrl",
            window_ms=400,
            on_start=on_start,
            on_stop=on_stop,
        )
        
        if activator.start():
            print("✓ Ready! Double-tap Ctrl to talk.\n")
            
            while True:
                time.sleep(0.1)
        else:
            print("Failed to start double-tap listener")
            
    except KeyboardInterrupt:
        print("\nDemo ended.")
    except ImportError:
        print("\n⚠ Install keyboard library:")
        print("  pip install keyboard")


def demo_clap():
    """Demo clap detection."""
    print("\n" + "="*50)
    print("  CLAP DETECTION DEMO")
    print("="*50)
    print("\nClap twice to start/stop voice")
    print("Press Ctrl+C to exit demo\n")
    
    try:
        from saarthi_executor.voice.activation_methods import ClapActivation
        
        def on_start():
            print("\n👏 CLAP DETECTED - LISTENING...")
            print("   Clap twice again to stop\n")
        
        def on_stop():
            print("\n👏 CLAP DETECTED - STOPPED\n")
        
        activator = ClapActivation(
            threshold=0.5,  # Adjust based on your mic
            clap_count=2,
            window_ms=1000,
            on_start=on_start,
            on_stop=on_stop,
        )
        
        if activator.start():
            print("✓ Ready! Clap twice to talk.\n")
            print("Tip: If not detecting, try clapping louder")
            print("     or adjust the threshold (0.3-0.8)\n")
            
            while True:
                time.sleep(0.1)
        else:
            print("Failed to start clap detection")
            
    except KeyboardInterrupt:
        print("\nDemo ended.")
    except ImportError:
        print("\n⚠ Install pyaudio:")
        print("  pip install pyaudio")


def demo_unified():
    """Demo unified manager with method switching."""
    print("\n" + "="*50)
    print("  UNIFIED ACTIVATION MANAGER DEMO")
    print("="*50)
    print("\nTest all methods!")
    print("Press 1 for Hotkey (F5)")
    print("Press 2 for Double-tap (Ctrl)")
    print("Press 3 for Clap detection")
    print("Press Q to quit\n")
    
    try:
        from saarthi_executor.voice.activation_methods import (
            VoiceActivationManager,
            ActivationMethod,
        )
        
        def on_start():
            print("\n🎤 LISTENING...\n")
        
        def on_stop():
            print("\n✓ STOPPED\n")
        
        manager = VoiceActivationManager(
            method=ActivationMethod.HOTKEY,
            on_start=on_start,
            on_stop=on_stop,
        )
        
        if manager.start():
            print(f"✓ Current method: {manager.current_method.value}\n")
            
            import keyboard
            
            def switch_to_hotkey():
                manager.set_method(ActivationMethod.HOTKEY)
                print(f"\n→ Switched to HOTKEY (F5)\n")
            
            def switch_to_doubletap():
                manager.set_method(ActivationMethod.DOUBLE_TAP)
                print(f"\n→ Switched to DOUBLE-TAP (Ctrl)\n")
            
            def switch_to_clap():
                manager.set_method(ActivationMethod.CLAP)
                print(f"\n→ Switched to CLAP\n")
            
            keyboard.add_hotkey('1', switch_to_hotkey)
            keyboard.add_hotkey('2', switch_to_doubletap)
            keyboard.add_hotkey('3', switch_to_clap)
            
            while True:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\nDemo ended.")
        manager.stop()


def main():
    """Main demo selector."""
    print("\n" + "="*50)
    print("  VOICE ACTIVATION METHODS")
    print("="*50)
    print("""
Choose activation method to demo:

  1. HOTKEY (F5)      - Press F5 to toggle [RECOMMENDED]
  2. DOUBLE-TAP       - Double-tap Ctrl to toggle
  3. CLAP DETECTION   - Clap twice to toggle
  4. UNIFIED MANAGER  - Test all methods

  Q. Quit
""")
    
    choice = input("Enter choice (1-4): ").strip().lower()
    
    if choice == '1':
        demo_hotkey()
    elif choice == '2':
        demo_double_tap()
    elif choice == '3':
        demo_clap()
    elif choice == '4':
        demo_unified()
    elif choice == 'q':
        print("Goodbye!")
    else:
        print("Invalid choice. Running hotkey demo...")
        demo_hotkey()


if __name__ == "__main__":
    main()
