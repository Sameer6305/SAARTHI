"""
Test SAARTHI Integrated Assistant
=================================

Quick test to verify the integrated assistant works correctly.

Run: python test_integration.py
"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

def test_pattern_matching():
    """Test pattern matching (no LLM needed)."""
    print("\n" + "="*60)
    print("TEST: Pattern Matching")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import PatternMatcher
    
    matcher = PatternMatcher()
    
    test_cases = [
        ("open youtube", "open_url", {"site": "youtube"}),
        ("go to github", "open_url", {"site": "github"}),
        ("search for python tutorials", "search_web", {"query": "python tutorials"}),
        ("hi", "greeting", {}),
        ("hello saarthi", "greeting", {}),
        ("thanks", "thanks", {}),
        ("yes", "confirm_yes", {"value": True}),
        ("no", "confirm_no", {"value": False}),
        ("explain binary search", "explain", {"topic": "binary search"}),
        ("what is a linked list", "explain", {"topic": "a linked list"}),
        ("status", "status", {}),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_intent, expected_entities_subset in test_cases:
        result = matcher.match(text)
        
        if result is None:
            print(f"  ✗ '{text}' → No match (expected {expected_intent})")
            failed += 1
            continue
        
        if result.intent_name == expected_intent:
            # Check entities
            entities_match = all(
                result.entities.get(k) == v 
                for k, v in expected_entities_subset.items()
            )
            
            if entities_match:
                print(f"  ✓ '{text}' → {result.intent_name}")
                passed += 1
            else:
                print(f"  ✗ '{text}' → entities mismatch: {result.entities}")
                failed += 1
        else:
            print(f"  ✗ '{text}' → {result.intent_name} (expected {expected_intent})")
            failed += 1
    
    print(f"\nPattern matching: {passed}/{passed+failed} tests passed")
    return failed == 0


def test_response_cache():
    """Test response caching."""
    print("\n" + "="*60)
    print("TEST: Response Cache")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import ResponseCache
    
    cache = ResponseCache(max_size=10, ttl_seconds=60)
    
    # Test set and get
    cache.set("test query", "test response")
    result = cache.get("test query")
    
    if result == "test response":
        print("  ✓ Cache set/get works")
    else:
        print(f"  ✗ Cache get returned: {result}")
        return False
    
    # Test case insensitivity
    result2 = cache.get("TEST QUERY")
    if result2 == "test response":
        print("  ✓ Cache is case-insensitive")
    else:
        print(f"  ✗ Case-insensitive failed: {result2}")
        return False
    
    # Test miss
    miss = cache.get("nonexistent")
    if miss is None:
        print("  ✓ Cache miss returns None")
    else:
        print(f"  ✗ Cache miss returned: {miss}")
        return False
    
    print("\nCache tests passed!")
    return True


def test_assistant_conversation():
    """Test assistant conversational flow."""
    print("\n" + "="*60)
    print("TEST: Assistant Conversation")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    # Create assistant without TTS (for testing)
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # Test greeting
    response = assistant.process("hello")
    print(f"  User: 'hello'")
    print(f"  SAARTHI: '{response.text}'")
    
    if "hello" in response.text.lower() or "hey" in response.text.lower() or "hi" in response.text.lower() or "how can i help" in response.text.lower():
        print("  ✓ Greeting response correct")
    else:
        print("  ✗ Unexpected greeting response")
        return False
    
    # Test status
    response = assistant.process("status")
    print(f"\n  User: 'status'")
    print(f"  SAARTHI: '{response.text}'")
    
    if "running" in response.text.lower() or "pattern" in response.text.lower():
        print("  ✓ Status response correct")
    else:
        print("  ✗ Unexpected status response")
        return False
    
    print("\nConversation tests passed!")
    return True


def test_confirmation_flow():
    """Test action confirmation flow."""
    print("\n" + "="*60)
    print("TEST: Confirmation Flow")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    # Create assistant without TTS
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # Try to open YouTube - should ask for confirmation
    response = assistant.process("open youtube")
    print(f"  User: 'open youtube'")
    print(f"  SAARTHI: '{response.text}'")
    
    # Should have pending action
    if assistant.has_pending_action():
        print("  ✓ Action pending confirmation")
    else:
        print("  ✗ No pending action")
        return False
    
    # Cancel the action
    response = assistant.process("no")
    print(f"\n  User: 'no'")
    print(f"  SAARTHI: '{response.text}'")
    
    if not assistant.has_pending_action():
        print("  ✓ Action cancelled")
    else:
        print("  ✗ Action still pending after cancel")
        return False
    
    print("\nConfirmation flow tests passed!")
    return True


def test_student_tools():
    """Test student tool responses."""
    print("\n" + "="*60)
    print("TEST: Student Tools")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    # Create assistant without TTS
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # Test explanation
    response = assistant.process("explain binary search")
    print(f"  User: 'explain binary search'")
    print(f"  SAARTHI: '{response.text[:100]}...'")
    
    if "binary" in response.text.lower() and ("search" in response.text.lower() or "sorted" in response.text.lower() or "log" in response.text.lower()):
        print("  ✓ Binary search explanation provided")
    else:
        print("  ✗ Explanation seems incorrect")
        return False
    
    # Test another topic
    response = assistant.process("what is a stack")
    print(f"\n  User: 'what is a stack'")
    print(f"  SAARTHI: '{response.text[:100]}...'")
    
    if "stack" in response.text.lower() or "lifo" in response.text.lower() or "push" in response.text.lower():
        print("  ✓ Stack explanation provided")
    else:
        print("  ✗ Explanation seems incorrect")
        return False
    
    print("\nStudent tool tests passed!")
    return True


def test_tts_initialization():
    """Test TTS can be initialized."""
    print("\n" + "="*60)
    print("TEST: TTS Initialization")
    print("="*60)
    
    from saarthi_executor.integrated_assistant import SimpleTTS
    
    tts = SimpleTTS()
    
    if tts.initialize():
        print("  ✓ TTS initialized (Windows SAPI)")
        
        # Try speaking (non-blocking)
        tts.speak("Test complete", async_mode=True)
        print("  ✓ TTS speak called (async)")
        
        # Give it a moment
        import time
        time.sleep(0.5)
        
        tts.stop()
        print("  ✓ TTS stopped")
        
        return True
    else:
        print("  ⚠ TTS initialization failed (may not have pywin32)")
        return True  # Not a failure, just unavailable


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("SAARTHI INTEGRATION TESTS")
    print("="*60)
    
    results = []
    
    results.append(("Pattern Matching", test_pattern_matching()))
    results.append(("Response Cache", test_response_cache()))
    results.append(("Conversation", test_assistant_conversation()))
    results.append(("Confirmation Flow", test_confirmation_flow()))
    results.append(("Student Tools", test_student_tools()))
    results.append(("TTS", test_tts_initialization()))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
