"""
Test Script for SAARTHI Local Executor
======================================

Run this to test the executor with sample actions.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Add the local_client directory to path
sys.path.insert(0, str(Path(__file__).parent))

from saarthi_executor.executor import SaarthiExecutor
from saarthi_executor.logging_config import setup_logging


def create_test_action(action_type: str, parameters: dict) -> dict:
    """Create a properly formatted test action."""
    return {
        "action_id": f"act_{'0' * 16}test{int(time.time())}",
        "action_type": action_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": "a" * 64,  # Dummy signature
        "description": f"Test action: {action_type}",
        "risk_level": "LOW",
        "parameters": parameters,
        "metadata": {
            "task_id": "task_" + "0" * 16,
            "plan_id": "plan_" + "0" * 16,
            "step_number": 1,
        }
    }


def main():
    """Run test executor with sample actions."""
    setup_logging(log_level="DEBUG")
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              SAARTHI Executor - TEST MODE                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  This will start the executor and inject test actions.           ║
║                                                                  ║
║  1. Wake up the executor (right-click tray → Wake Up)            ║
║  2. Test actions will be processed                               ║
║  3. You will be asked to approve each action                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    executor = SaarthiExecutor(use_mock_cloud=True)
    
    # Inject test actions
    print("\n📝 Injecting test actions...")
    
    # Test 1: Open URL
    executor.inject_test_action(create_test_action(
        "open_browser_url",
        {"url": "https://www.google.com"}
    ))
    print("   ✓ Added: Open Google in browser")
    
    # Test 2: Play media (will use file picker)
    executor.inject_test_action(create_test_action(
        "play_media_file",
        {"media_type": "audio"}
    ))
    print("   ✓ Added: Play audio file (you'll select one)")
    
    # Test 3: Read file (will use file picker)
    executor.inject_test_action(create_test_action(
        "read_file_with_picker",
        {
            "file_types": [".txt", ".md", ".py"],
            "purpose": "Read text file contents for analysis"
        }
    ))
    print("   ✓ Added: Read text file (you'll select one)")
    
    print("\n🚀 Starting executor...")
    print("   Right-click the tray icon and select 'Wake Up' to process actions.\n")
    
    try:
        executor.start()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        executor.stop()


if __name__ == "__main__":
    main()
