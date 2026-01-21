#!/usr/bin/env python3
"""
SAARTHI Voice Mode
==================

SIMPLEST way to use voice with SAARTHI.

Press F5 to start speaking, press F5 again to stop.
Or just use Tray mode with "Voice Command" option.

Usage:
    python voice_mode.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print()
print("╔════════════════════════════════════════════════════════════╗")
print("║          SAARTHI Voice Mode - 3 Options                    ║")
print("╠════════════════════════════════════════════════════════════╣")
print("║                                                            ║")
print("║  OPTION 1: TRAY MODE (Recommended)                         ║")
print("║  ────────────────────────────────────────────────────────  ║")
print("║    python main.py --tray                                   ║")
print("║                                                            ║")
print("║    → System tray icon appears                              ║")
print("║    → Right-click → 'Voice Command'                         ║")
print("║    → Click to start, speak, click to stop                  ║")
print("║                                                            ║")
print("║  OPTION 2: VOICE HOTKEY (F5)                               ║")
print("║  ────────────────────────────────────────────────────────  ║")
print("║    python main.py --voice                                  ║")
print("║                                                            ║")
print("║    → Press F5 to toggle voice recording                    ║")
print("║    → Works anywhere, even outside the app                  ║")
print("║                                                            ║")
print("║  OPTION 3: PUSH-TO-TALK IN TRAY                            ║")
print("║  ────────────────────────────────────────────────────────  ║")
print("║    Using run.py (the original way):                        ║")
print("║    python run.py                                           ║")
print("║                                                            ║")
print("║    → System tray icon appears                              ║")
print("║    → Right-click → 'Voice Command'                         ║")
print("║    → Dialog opens, click 'Start Recording', speak, click   ║")
print("║      'Stop Recording'                                      ║")
print("║                                                            ║")
print("╚════════════════════════════════════════════════════════════╝")
print()
print("Which option would you like to use?")
print()
print("1. Tray Mode (Recommended)")
print("2. Voice Hotkey (F5)")
print("3. Run.py (Original)")
print()

choice = input("Enter 1, 2, or 3: ").strip()

if choice == "1":
    print("\nStarting Tray Mode...")
    print("Look for the SAARTHI icon in your system tray!")
    print()
    import os
    os.system("python main.py --tray")
    
elif choice == "2":
    print("\nStarting Voice Hotkey Mode...")
    print("Press F5 anywhere to start/stop voice recording!")
    print()
    import os
    os.system("python main.py --voice")
    
elif choice == "3":
    print("\nStarting Original Tray Mode (run.py)...")
    print("Look for the SAARTHI icon in your system tray!")
    print()
    import os
    os.system("python run.py")
    
else:
    print("\nInvalid choice. Run this script again.")
