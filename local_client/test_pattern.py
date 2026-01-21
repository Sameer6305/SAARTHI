#!/usr/bin/env python3
"""Quick test for pattern matching."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from saarthi_executor.integrated_assistant import create_assistant

# Create assistant
assistant = create_assistant(enable_tts=False)

# Test cases
test_inputs = [
    "open youtube",
    "hello open youtube",
    "hi open youtube", 
    "hey open youtube",
    "Hello, open YouTube.",
    "hello open youtube",  # with comma
]

print("Testing Pattern Matching")
print("=" * 60)

for text in test_inputs:
    print(f"\nInput: '{text}'")
    response = assistant.process(text)
    print(f"Response: {response.text}")
    print(f"Confirmation needed: {assistant.confirmation_manager.pending_action is not None}")

print("\n" + "=" * 60)
