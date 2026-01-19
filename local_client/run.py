"""
SAARTHI Local Executor - Runner Script
======================================

Simple entry point to run the local executor.

Usage:
    python run.py
    
The executor will:
1. Start in SLEEP state
2. Show a system tray icon
3. Right-click the icon to wake up
4. When LISTENING, it will process incoming actions
"""

import sys
from pathlib import Path

# Add the local_client directory to path
sys.path.insert(0, str(Path(__file__).parent))

from saarthi_executor.executor import main

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              SAARTHI Local Execution Client                      ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  SECURITY:                                                       ║
║  • All actions require YOUR permission                           ║
║  • Only allowed actions: open URL, play media, read files        ║
║  • NO shell commands, NO file deletion, NO monitoring            ║
║                                                                  ║
║  CONTROLS:                                                       ║
║  • Right-click the tray icon to control                          ║
║  • "Wake Up" to start listening for actions                      ║
║  • "Go to Sleep" to pause                                        ║
║  • "Exit" to quit                                                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    main()
