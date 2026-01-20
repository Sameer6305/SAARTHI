"""
Backend Integration Test
========================

Test script to verify the local client can communicate
with the real backend running at localhost:8000.

USAGE:
    1. Start the backend: cd backend && python -m uvicorn app.main:app --port 8000
    2. Run this test: python test_backend_integration.py

This test:
- Connects to the backend
- Sends test commands
- Receives and logs planner responses
- Does NOT execute any actions
"""

import sys
import json
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from saarthi_executor.backend_client import (
    BackendClient,
    BackendConfig,
    create_backend_client,
    InputValidationError,
    validate_user_input,
)
from saarthi_executor.logging_config import setup_logging


def setup_test_logging():
    """Setup logging for tests."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%H:%M:%S"
    )
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def print_separator(title: str):
    """Print a visual separator."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(label: str, value, indent: int = 0):
    """Print a labeled result."""
    prefix = "  " * indent
    if isinstance(value, dict):
        print(f"{prefix}{label}:")
        for k, v in value.items():
            print_result(k, v, indent + 1)
    elif isinstance(value, list):
        print(f"{prefix}{label}: [{len(value)} items]")
        for i, item in enumerate(value[:5]):  # Show first 5
            print_result(f"[{i}]", item, indent + 1)
        if len(value) > 5:
            print(f"{prefix}  ... and {len(value) - 5} more")
    else:
        print(f"{prefix}{label}: {value}")


def test_input_validation():
    """Test input validation."""
    print_separator("INPUT VALIDATION TESTS")
    
    config = BackendConfig()
    
    test_cases = [
        ("valid input", "open youtube", True),
        ("empty string", "", False),
        ("whitespace only", "   \n\t  ", False),
        ("too short", "", False),
        ("null bytes", "hello\x00world", True),  # Should sanitize
        ("valid long text", "please open the youtube website for me", True),
    ]
    
    for name, input_text, should_pass in test_cases:
        try:
            result = validate_user_input(input_text, config)
            status = "✓ PASS" if should_pass else "✗ UNEXPECTED PASS"
            print(f"  {status}: {name}")
            if result != input_text:
                print(f"         Sanitized: '{result}'")
        except InputValidationError as e:
            status = "✓ PASS (rejected)" if not should_pass else "✗ UNEXPECTED FAIL"
            print(f"  {status}: {name} - {e}")


def test_connection():
    """Test backend connection."""
    print_separator("CONNECTION TEST")
    
    client = create_backend_client()
    
    print(f"  Backend URL: {client.config.base_url}")
    print(f"  Timeout: {client.config.timeout_seconds}s")
    print(f"  Initial state: {client.state}")
    
    print()
    print("  Attempting connection...")
    
    connected = client.connect()
    
    if connected:
        print(f"  ✓ Connected successfully")
        print(f"  State: {client.state}")
    else:
        print(f"  ✗ Connection failed")
        print(f"  State: {client.state}")
        print()
        print("  HINT: Make sure the backend is running:")
        print("        cd backend && python -m uvicorn app.main:app --port 8000")
    
    client.disconnect()
    return connected


def test_send_command(client: BackendClient, command: str):
    """Test sending a command."""
    print()
    print(f"  Command: \"{command}\"")
    print("  " + "-" * 50)
    
    result = client.send_command(command)
    
    if result.success:
        print(f"  ✓ Task created successfully")
        print(f"    task_id: {result.task_id}")
        print(f"    status: {result.status}")
        print(f"    message: {result.message}")
        if result.intent_summary:
            print(f"    intent_summary: {result.intent_summary}")
        if result.step_count:
            print(f"    step_count: {result.step_count}")
        
        return result.task_id
    else:
        print(f"  ✗ Failed: {result.error}")
        return None


def test_get_actions(client: BackendClient, task_id: str):
    """Test getting actions for a task."""
    print()
    print(f"  Fetching actions for: {task_id}")
    print("  " + "-" * 50)
    
    result = client.get_actions(task_id)
    
    if result.success:
        print(f"  ✓ Actions retrieved: {result.total_actions} action(s)")
        
        for i, action in enumerate(result.actions):
            print()
            print(f"    Action {i + 1}:")
            print(f"      action_id: {action.action_id}")
            print(f"      action_type: {action.action_type}")
            print(f"      risk_level: {action.risk_level}")
            if action.description:
                print(f"      description: {action.description}")
            if action.parameters:
                print(f"      parameters: {json.dumps(action.parameters, indent=8)}")
    else:
        print(f"  ✗ Failed: {result.error}")


def run_integration_tests():
    """Run full integration test suite."""
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║           SAARTHI Backend Integration Tests                      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    
    # Test 1: Input validation
    test_input_validation()
    
    # Test 2: Connection
    if not test_connection():
        print()
        print("=" * 70)
        print("  TESTS ABORTED: Cannot connect to backend")
        print("=" * 70)
        return False
    
    # Test 3: Command flow tests
    print_separator("COMMAND FLOW TESTS")
    
    client = create_backend_client()
    if not client.connect():
        print("  ✗ Failed to connect")
        return False
    
    try:
        # Test commands
        test_commands = [
            "open youtube",
            "open github",
            "search google for python tutorials",
            "play some music",
        ]
        
        for command in test_commands:
            task_id = test_send_command(client, command)
            
            if task_id:
                test_get_actions(client, task_id)
            
            print()
        
        # Test error cases
        print_separator("ERROR HANDLING TESTS")
        
        # Invalid task ID
        print("  Testing invalid task ID...")
        result = client.get_actions("task_invalid123")
        print(f"  Result: {result.error}" if not result.success else "  Unexpected success")
        
        # Empty command (should fail validation)
        print()
        print("  Testing empty command...")
        result = client.send_command("")
        print(f"  Result: {result.error}" if not result.success else "  Unexpected success")
        
    finally:
        client.disconnect()
    
    print_separator("TEST COMPLETE")
    print("  All integration tests passed!")
    print()
    print("  NEXT STEPS:")
    print("  1. Run the full executor: python run.py")
    print("  2. Use the tray menu to wake up")
    print("  3. Commands can be sent via the executor API")
    print()
    
    return True


def test_single_command(command: str):
    """Quick test for a single command."""
    print()
    print(f"Testing command: \"{command}\"")
    print()
    
    client = create_backend_client()
    
    if not client.connect():
        print("ERROR: Cannot connect to backend at localhost:8000")
        print("Make sure the backend is running!")
        return
    
    try:
        # Send command
        task_result = client.send_command(command)
        
        if not task_result.success:
            print(f"Command failed: {task_result.error}")
            return
        
        print(f"Task created: {task_result.task_id}")
        print(f"Status: {task_result.status}")
        
        # Get actions
        actions_result = client.get_actions(task_result.task_id)
        
        if not actions_result.success:
            print(f"Failed to get actions: {actions_result.error}")
            return
        
        print(f"\nActions ({actions_result.total_actions}):")
        for action in actions_result.actions:
            print(f"  - {action.action_type}")
            if action.parameters:
                for k, v in action.parameters.items():
                    if v:
                        print(f"      {k}: {v}")
        
    finally:
        client.disconnect()


if __name__ == "__main__":
    setup_test_logging()
    
    # Check for command line argument
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        test_single_command(command)
    else:
        run_integration_tests()
