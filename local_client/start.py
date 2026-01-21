"""
SAARTHI - Complete Startup Script
==================================

This script will:
1. Check all dependencies
2. Initialize all components
3. Run SAARTHI in your chosen mode
4. Handle any errors gracefully
"""

import sys
import os
from pathlib import Path

# Ensure we're in the right directory
script_dir = Path(__file__).parent
os.chdir(script_dir)
sys.path.insert(0, str(script_dir))

print()
print("=" * 70)
print("                    SAARTHI STARTUP")
print("=" * 70)
print()

# Step 1: Check Python version
print("Step 1: Checking Python version...")
if sys.version_info < (3, 8):
    print("❌ ERROR: Python 3.8+ required")
    print(f"   You have: {sys.version}")
    sys.exit(1)
print(f"   ✓ Python {sys.version_info.major}.{sys.version_info.minor}")

# Step 2: Check dependencies
print("\nStep 2: Checking dependencies...")
missing = []
dependencies = [
    ('sounddevice', 'sounddevice'),
    ('whisper', 'openai-whisper'),
    ('pystray', 'pystray'),
    ('PIL', 'Pillow'),
    ('win32com.client', 'pywin32'),
]

for module_name, package_name in dependencies:
    try:
        __import__(module_name)
        print(f"   ✓ {package_name}")
    except ImportError:
        print(f"   ✗ {package_name} - MISSING")
        missing.append(package_name)

if missing:
    print(f"\n❌ Missing dependencies: {', '.join(missing)}")
    print("\nInstall with:")
    print(f"   pip install {' '.join(missing)}")
    
    choice = input("\nTry to install now? (y/n): ").strip().lower()
    if choice == 'y':
        print("\nInstalling...")
        os.system(f"pip install {' '.join(missing)}")
        print("\nDependencies installed! Please run this script again.")
    sys.exit(1)

# Step 3: Check microphone
print("\nStep 3: Checking microphone...")
try:
    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    if input_devices:
        print(f"   ✓ Found {len(input_devices)} input device(s)")
        default = sd.query_devices(kind='input')
        print(f"   Default: {default['name']}")
    else:
        print("   ⚠ No microphone found (voice won't work)")
except Exception as e:
    print(f"   ⚠ Could not check microphone: {e}")

# Step 4: Check Whisper model
print("\nStep 4: Checking Whisper model...")
whisper_cache = Path.home() / ".cache" / "whisper"
if whisper_cache.exists():
    models = list(whisper_cache.glob("*.pt"))
    if models:
        print(f"   ✓ Whisper model found ({models[0].name})")
    else:
        print("   ⚠ No model found (will download on first use ~140MB)")
else:
    print("   ⚠ No model found (will download on first use ~140MB)")

# Step 5: Choose mode
print("\n" + "=" * 70)
print("                    CHOOSE MODE")
print("=" * 70)
print()
print("1. VOICE MODE - Simple (Recommended) ⚡")
print("   → Press Enter, speak, get response")
print("   → No dialogs, no complications!")
print("   → Best for: Everyone!")
print()
print("2. CLI MODE (Text only)")
print("   → Type commands, get text/voice responses")
print("   → Best for: Testing, debugging, quiet environments")
print()
print("3. TRAY MODE (Background)")
print("   → System tray icon with menu")
print("   → Best for: Running in background, occasional use")
print()
print("4. CLI MODE (No TTS)")
print("   → Type commands, get text only (faster)")
print("   → Best for: Quick testing without sound")
print()

while True:
    choice = input("Enter choice (1-4): ").strip()
    if choice in ['1', '2', '3', '4']:
        break
    print("Invalid choice. Enter 1, 2, 3, or 4.")

print()
print("=" * 70)
print("                    STARTING SAARTHI")
print("=" * 70)
print()

# Run the chosen mode
if choice == '1':
    print("Starting VOICE MODE (Simple & Working)...")
    print("(Just press Enter and speak!)")
    print()
    os.system("python voice_simple.py")
    
elif choice == '2':
    print("Starting CLI MODE...")
    print()
    os.system("python main.py")
    
elif choice == '3':
    print("Starting TRAY MODE...")
    print("(Look for the icon in your system tray)")
    print()
    os.system("python main.py --tray")
    
elif choice == '4':
    print("Starting CLI MODE (No TTS)...")
    print()
    os.system("python main.py --no-tts")
