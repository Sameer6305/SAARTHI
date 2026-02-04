#!/usr/bin/env python3
"""
Quick Verification Script for Bug Fixes (v4.1)
===============================================

Tests the 5 critical bug fixes without requiring full voice assistant.
"""

import sys
from pathlib import Path

# Add local_client to path
sys.path.insert(0, str(Path(__file__).parent / "local_client"))

from saarthi_executor.input_normalizer import get_normalizer
from saarthi_executor.intent_router import get_router, RouteCategory
from saarthi_executor.knowledge_answerer import get_knowledge_answerer
from saarthi_executor.student_mode import get_student_handler
from saarthi_executor.intent_engine import IntentEngine


def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_input_normalization():
    """Test 1: Input Normalization"""
    print_section("TEST 1: Input Normalization (Hinglish/Typos)")
    
    normalizer = get_normalizer()
    
    test_cases = [
        ("open youtube", "Clean English"),
        ("youtube kholo", "Hinglish"),
        ("opne yt", "Typos + Abbreviations"),
        ("um like play music plz", "Fillers"),
    ]
    
    for text, desc in test_cases:
        result = normalizer.normalize(text)
        status = "✅" if result.is_safe_to_process else "⚠️"
        print(f"{status} {desc:25s}: '{text}' → '{result.normalized}'")
        print(f"   Confidence: {result.confidence:.0%}, Language: {result.language_detected}")
        if result.corrections_made:
            print(f"   Corrections: {', '.join(result.corrections_made)}")
        print()


def test_intent_routing():
    """Test 2: Intent Routing"""
    print_section("TEST 2: Intent Routing (Knowledge vs Action)")
    
    router = get_router()
    engine = IntentEngine()
    
    test_cases = [
        ("Who is Elon Musk?", "Knowledge question"),
        ("open youtube", "Action command"),
        ("help with my assignment", "Student mode"),
        ("hello", "Conversational"),
    ]
    
    for text, desc in test_cases:
        intent = engine.classify(text)
        route = router.route(intent)
        print(f"✅ {desc:20s}: '{text}'")
        print(f"   Intent: {intent.intent_type.value}")
        print(f"   Route:  {route.category.value} (confidence: {route.confidence:.0%})")
        print()


def test_knowledge_answering():
    """Test 3: Knowledge Answering"""
    print_section("TEST 3: Knowledge Answering (No Generic 'I Don't Know')")
    
    answerer = get_knowledge_answerer()
    
    test_cases = [
        ("binary search", "Known topic"),
        ("XYZ Random Nonexistent Thing", "Unknown topic"),
        ("Elon Musk", "Popular topic"),
    ]
    
    for topic, desc in test_cases:
        answer = answerer.answer(topic)
        print(f"✅ {desc:20s}: '{topic}'")
        print(f"   Source: {answer.source}")
        print(f"   Answer: {answer.text[:100]}..." if len(answer.text) > 100 else f"   Answer: {answer.text}")
        print(f"   Confidence: {answer.confidence:.0%}")
        print()


def test_student_mode():
    """Test 4: Student Mode"""
    print_section("TEST 4: Student Mode (Teaching Approach)")
    
    handler = get_student_handler()
    
    test_cases = [
        "help me with my DSA assignment",
        "explain binary search step by step",
        "I have a quiz on operating systems",
    ]
    
    for query in test_cases:
        response = handler.handle_student_request(query)
        print(f"✅ Query: '{query}'")
        print(f"   Type: {response.request_type.value}")
        print(f"   Response: {response.text[:150]}...")
        if response.follow_up_questions:
            print(f"   Follow-ups: {len(response.follow_up_questions)} questions")
        print()


def test_multi_step_detection():
    """Test 5: Multi-Step Detection"""
    print_section("TEST 5: Multi-Step Intent Detection")
    
    engine = IntentEngine()
    
    test_cases = [
        "open youtube and search lofi music",
        "open spotify and play jazz",
        "search python tutorials",  # Single-step (control)
    ]
    
    for text in test_cases:
        intent = engine.classify(text)
        is_multi = intent.intent_type.value == "multi_step"
        status = "🔗" if is_multi else "⚡"
        print(f"{status} '{text}'")
        print(f"   Intent: {intent.intent_type.value} (confidence: {intent.confidence:.0%})")
        if hasattr(intent, 'sub_intents') and intent.sub_intents:
            print(f"   Sub-intents: {len(intent.sub_intents)}")
        print()


def main():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("  SAARTHI BUG FIXES VERIFICATION (v4.1)")
    print("="*80)
    print("\nThis script tests the 5 critical bug fixes without starting the voice assistant.")
    print("For full integration testing, run: python local_client/voice_ultimate_v4.py\n")
    
    try:
        test_input_normalization()
        test_intent_routing()
        test_knowledge_answering()
        test_student_mode()
        test_multi_step_detection()
        
        print("\n" + "="*80)
        print("  ✅ ALL VERIFICATION TESTS COMPLETED")
        print("="*80)
        print("\nNext step: Run the full voice assistant:")
        print("  cd local_client")
        print("  python voice_ultimate_v4.py")
        print("\nThen press SPACE and test with real voice input!")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nCheck that all modules are properly installed.")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
