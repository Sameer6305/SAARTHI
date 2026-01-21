#!/usr/bin/env python3
"""
SAARTHI Feature Demo
=====================

Interactive demo showcasing all SAARTHI features:
1. Voice Interaction
2. Assignment Explanation
3. Quiz Solving with Reasoning
4. Desktop Action with Permission
5. Privacy Demonstration

Run: python demo_scenarios.py

Each scenario can be run independently or all together.
"""

import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'═'*60}{Colors.END}\n")

def print_scenario(num: int, title: str):
    """Print scenario title."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}┌{'─'*58}┐{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}│  SCENARIO {num}: {title:<44}│{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}└{'─'*58}┘{Colors.END}\n")

def print_user(text: str):
    """Print user input."""
    print(f"{Colors.BLUE}👤 USER:{Colors.END} {text}")

def print_saarthi(text: str, action: bool = False):
    """Print SAARTHI response."""
    icon = "✓" if action else "🤖"
    color = Colors.GREEN if action else Colors.YELLOW
    print(f"{color}{icon} SAARTHI:{Colors.END} {text}")

def print_system(text: str):
    """Print system message."""
    print(f"{Colors.RED}⚙ SYSTEM:{Colors.END} {text}")

def pause(seconds: float = 0.5):
    """Pause for effect."""
    time.sleep(seconds)


# =============================================================================
# SCENARIO 1: VOICE INTERACTION
# =============================================================================

def demo_voice_interaction():
    """
    Demonstrate voice interaction flow.
    
    FEATURES SHOWN:
    - Push-to-talk activation
    - Local Whisper transcription
    - Natural language understanding
    - TTS response
    """
    print_scenario(1, "VOICE INTERACTION")
    
    print("""
    This scenario demonstrates the voice interaction flow.
    Voice input is the PRIMARY interaction method.
    
    FLOW:
    1. User presses talk button (push-to-talk)
    2. Audio captured locally
    3. Whisper transcribes locally (no cloud)
    4. Assistant processes command
    5. TTS speaks response
    6. Audio immediately discarded (privacy)
    """)
    
    pause(1)
    
    # Simulate voice interaction
    print_system("User clicks 'Voice Command' in system tray")
    pause(0.5)
    
    print_system("Voice dialog opens - 'Hold to Talk' button visible")
    pause(0.5)
    
    print_system("User holds button and speaks...")
    print_user("[VOICE] What is the time complexity of quicksort?")
    pause(0.5)
    
    print_system("Whisper STT processing... (local, ~300ms)")
    pause(0.3)
    
    print_system("Transcribed: 'What is the time complexity of quicksort?'")
    pause(0.3)
    
    print_saarthi(
        "QuickSort has an average time complexity of O(n log n), "
        "but O(n²) in the worst case when the pivot selection is poor. "
        "The space complexity is O(log n) for the recursive call stack."
    )
    
    print_system("TTS speaks response (Windows SAPI, async)")
    pause(0.5)
    
    print_system("Audio data discarded - not stored")
    
    print(f"\n{Colors.GREEN}✓ Voice interaction complete{Colors.END}")
    
    return True


# =============================================================================
# SCENARIO 2: ASSIGNMENT EXPLANATION
# =============================================================================

def demo_assignment_explanation():
    """
    Demonstrate assignment explanation with step-by-step breakdown.
    
    FEATURES SHOWN:
    - Topic detection
    - Concept breakdown
    - Step-by-step explanation
    - Teaching approach (not just answers)
    """
    print_scenario(2, "ASSIGNMENT EXPLANATION")
    
    print("""
    This scenario shows how SAARTHI helps with assignments.
    
    PRINCIPLE: Teach, don't cheat
    - Explain concepts before solutions
    - Show reasoning
    - Guide understanding
    """)
    
    pause(1)
    
    # Import assistant
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # Scenario: Student asks about DSA topic
    print_user("Explain how to implement a binary search tree")
    pause(0.3)
    
    response = assistant.process("explain how to implement a binary search tree")
    print_saarthi(response.text)
    pause(0.5)
    
    # Follow-up question
    print_user("What about the insertion operation?")
    pause(0.3)
    
    # Simulate LLM response for complex topic
    print_saarthi(
        "For BST insertion, follow these steps:\n"
        "1. Start at the root node\n"
        "2. Compare the new value with current node\n"
        "3. If smaller, go left; if larger, go right\n"
        "4. Repeat until you find an empty spot\n"
        "5. Insert the new node there\n\n"
        "Time complexity: O(h) where h is the tree height.\n"
        "Would you like me to explain balancing to avoid O(n) worst case?"
    )
    pause(0.5)
    
    # Another topic
    print_user("Explain recursion with an example")
    pause(0.3)
    
    response = assistant.process("explain recursion")
    print_saarthi(response.text)
    
    print(f"\n{Colors.GREEN}✓ Assignment explanation complete{Colors.END}")
    
    return True


# =============================================================================
# SCENARIO 3: QUIZ SOLVING WITH REASONING
# =============================================================================

def demo_quiz_solving():
    """
    Demonstrate quiz help with reasoning (not just answers).
    
    FEATURES SHOWN:
    - Question analysis
    - Step-by-step reasoning
    - Teaching approach
    - Anti-cheating detection
    """
    print_scenario(3, "QUIZ SOLVING WITH REASONING")
    
    print("""
    This scenario shows quiz assistance.
    
    APPROACH:
    - Analyze the question first
    - Show reasoning process
    - Explain why the answer is correct
    - Never just give answers without explanation
    """)
    
    pause(1)
    
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # MCQ Question
    print_user(
        "Help me with this quiz question: "
        "What is the worst-case time complexity of binary search? "
        "A) O(1) B) O(n) C) O(log n) D) O(n²)"
    )
    pause(0.3)
    
    print_saarthi(
        "Let me help you think through this:\n\n"
        "📚 First, recall how binary search works:\n"
        "   - It divides the search space in half each step\n"
        "   - Starting with n elements, after 1 step: n/2\n"
        "   - After 2 steps: n/4, after k steps: n/2^k\n\n"
        "🤔 For worst case, we keep dividing until 1 element:\n"
        "   n/2^k = 1 → k = log₂(n)\n\n"
        "✓ So the answer is C) O(log n)\n\n"
        "This is BETTER than linear search O(n) because we eliminate "
        "half the elements each time!"
    )
    pause(0.5)
    
    # Another question - testing anti-cheat
    print_user("Just give me the answer to question 5")
    pause(0.3)
    
    print_saarthi(
        "I'd be happy to help, but I need to see the question first. "
        "Also, I'll explain the reasoning so you understand the concept - "
        "that way you'll be prepared for similar questions on the exam! "
        "What's question 5?"
    )
    pause(0.5)
    
    # Conceptual question
    print_user("Why is hash table lookup O(1)?")
    pause(0.3)
    
    response = assistant.process("explain hash table")
    print_saarthi(response.text)
    
    print(f"\n{Colors.GREEN}✓ Quiz solving demonstration complete{Colors.END}")
    
    return True


# =============================================================================
# SCENARIO 4: DESKTOP ACTION WITH PERMISSION
# =============================================================================

def demo_desktop_action():
    """
    Demonstrate desktop action with confirmation.
    
    FEATURES SHOWN:
    - Action classification
    - Confirmation prompt
    - User approval required
    - Safe execution
    - Audit logging
    """
    print_scenario(4, "DESKTOP ACTION WITH PERMISSION")
    
    print("""
    This scenario shows safe desktop action execution.
    
    SAFETY RULES:
    - ALL actions require explicit confirmation
    - Only whitelisted actions allowed
    - No shell commands, no file deletion
    - Complete audit logging
    """)
    
    pause(1)
    
    from saarthi_executor.integrated_assistant import IntegratedAssistant
    
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    # User requests action
    print_user("Open YouTube")
    pause(0.3)
    
    response = assistant.process("open youtube")
    print_saarthi(response.text)
    
    print_system("⚠ Confirmation required - action pending")
    pause(0.5)
    
    # Show what would happen on confirm
    print(f"\n{Colors.YELLOW}--- If user says 'yes' ---{Colors.END}")
    
    print_user("yes")
    pause(0.3)
    
    # Don't actually open - just simulate
    print_saarthi("Opening YouTube.", action=True)
    print_system("Action: webbrowser.open('https://www.youtube.com')")
    print_system("Audit log: action=open_url, target=youtube, status=success")
    
    # Reset for cancel demo
    assistant = IntegratedAssistant(enable_tts=False)
    assistant.initialize()
    
    print(f"\n{Colors.YELLOW}--- Alternative: user cancels ---{Colors.END}")
    
    print_user("Open GitHub")
    response = assistant.process("open github")
    print_saarthi(response.text)
    
    print_user("no")
    response = assistant.process("no")
    print_saarthi(response.text)
    
    print_system("Action cancelled - no execution")
    
    # Forbidden action
    print(f"\n{Colors.YELLOW}--- Forbidden action attempt ---{Colors.END}")
    
    print_user("Delete all my files")
    pause(0.3)
    
    print_saarthi(
        "I can't do that. File deletion is not in my allowed actions. "
        "I can only: open websites, launch apps, search the web, and read files."
    )
    print_system("⛔ Action blocked by policy - not in whitelist")
    
    print(f"\n{Colors.GREEN}✓ Desktop action demonstration complete{Colors.END}")
    
    return True


# =============================================================================
# SCENARIO 5: PRIVACY DEMONSTRATION
# =============================================================================

def demo_privacy():
    """
    Demonstrate privacy features.
    
    FEATURES SHOWN:
    - No raw audio storage
    - Session-only memory
    - User-controlled deletion
    - Sleep mode (zero access)
    - Data lifecycle
    """
    print_scenario(5, "PRIVACY DEMONSTRATION")
    
    print("""
    This scenario demonstrates privacy guarantees.
    
    TRUST GUARANTEES:
    - No raw audio ever stored
    - No browsing history tracked
    - Minimal memory (session only)
    - User can delete anytime
    - Sleep = zero access
    """)
    
    pause(1)
    
    # Import privacy manager
    from saarthi_executor.privacy_model import (
        PrivacyManager, 
        DataCategory, 
        TrustGuarantees,
        DataLifecycle,
    )
    
    privacy = PrivacyManager()
    
    # Show trust guarantees
    print(f"\n{Colors.CYAN}📋 Trust Guarantees:{Colors.END}")
    for item in TrustGuarantees.NEVER_STORE:
        print(f"   ❌ Never stored: {item}")
    pause(0.5)
    
    # Demonstrate data storage
    print(f"\n{Colors.CYAN}📊 Data Storage Demo:{Colors.END}")
    
    # Store some data
    privacy.store(DataCategory.CONVERSATION, {
        "user": "explain binary search",
        "assistant": "Binary search is...",
    })
    print("   Stored: conversation turn (expires: end of session)")
    
    privacy.store(DataCategory.PREFERENCE, {
        "voice_enabled": True,
        "tts_speed": 0.9,
    })
    print("   Stored: preference (expires: 7 days)")
    
    # Show what's NOT stored
    print(f"\n{Colors.CYAN}🚫 What is NOT stored:{Colors.END}")
    print("   ❌ Raw audio bytes")
    print("   ❌ Browsing history")
    print("   ❌ File contents")
    print("   ❌ Exact queries (only intent)")
    
    pause(0.5)
    
    # Demonstrate forget all
    print(f"\n{Colors.CYAN}🗑 User-Controlled Deletion:{Colors.END}")
    print_user("forget everything")
    pause(0.3)
    
    deleted = privacy.forget_all()
    print_saarthi(f"Done. I've forgotten {deleted} items. Memory cleared.")
    
    # Demonstrate sleep mode
    print(f"\n{Colors.CYAN}😴 Sleep Mode:{Colors.END}")
    print_system("User minimizes SAARTHI to tray")
    pause(0.3)
    
    privacy.enter_sleep_mode()
    print_system("Sleep mode activated:")
    print("   • No listening")
    print("   • No processing")
    print("   • No memory access")
    print("   • Zero resource usage")
    
    pause(0.5)
    
    print_system("User clicks 'Wake Up' in tray")
    privacy.exit_sleep_mode()
    print_system("Awake and ready")
    
    # Show data lifecycle
    print(f"\n{Colors.CYAN}📅 Data Lifecycle:{Colors.END}")
    lifecycle = DataLifecycle()
    
    print(f"   {'Category':<20} {'Retention':<15} {'Auto-delete'}")
    print(f"   {'-'*50}")
    print(f"   {'Voice Audio':<20} {'NEVER STORED':<15} Immediate")
    print(f"   {'Transcription':<20} {'RAM only':<15} After processing")
    print(f"   {'Conversation':<20} {'Session':<15} On close")
    print(f"   {'Preferences':<20} {'7 days':<15} Auto-cleanup")
    
    print(f"\n{Colors.GREEN}✓ Privacy demonstration complete{Colors.END}")
    
    return True


# =============================================================================
# FULL DEMO
# =============================================================================

def run_full_demo():
    """Run all demo scenarios."""
    print_header("SAARTHI FEATURE DEMONSTRATION")
    
    print("""
    Welcome to the SAARTHI feature demo!
    
    This demo showcases all major features:
    
    1. 🎤 Voice Interaction
    2. 📚 Assignment Explanation
    3. ❓ Quiz Solving with Reasoning
    4. 🖥️ Desktop Action with Permission
    5. 🔒 Privacy Demonstration
    
    Press Enter to start each scenario...
    """)
    
    scenarios = [
        ("Voice Interaction", demo_voice_interaction),
        ("Assignment Explanation", demo_assignment_explanation),
        ("Quiz Solving", demo_quiz_solving),
        ("Desktop Actions", demo_desktop_action),
        ("Privacy", demo_privacy),
    ]
    
    results = []
    
    for name, func in scenarios:
        input(f"\n{Colors.BOLD}Press Enter to run: {name}...{Colors.END}")
        try:
            success = func()
            results.append((name, success))
        except Exception as e:
            print(f"{Colors.RED}Error in {name}: {e}{Colors.END}")
            results.append((name, False))
    
    # Summary
    print_header("DEMO COMPLETE")
    
    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    for name, success in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if success else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    print(f"\n{Colors.BOLD}Total: {passed}/{len(results)} scenarios completed{Colors.END}")


def run_single_demo(scenario: int):
    """Run a single demo scenario."""
    demos = {
        1: ("Voice Interaction", demo_voice_interaction),
        2: ("Assignment Explanation", demo_assignment_explanation),
        3: ("Quiz Solving", demo_quiz_solving),
        4: ("Desktop Actions", demo_desktop_action),
        5: ("Privacy", demo_privacy),
    }
    
    if scenario not in demos:
        print(f"Unknown scenario: {scenario}")
        print("Available: 1-5")
        return
    
    name, func = demos[scenario]
    print_header(f"DEMO: {name}")
    func()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            scenario = int(sys.argv[1])
            run_single_demo(scenario)
        except ValueError:
            print("Usage: python demo_scenarios.py [scenario_number]")
            print("  No argument: Run all scenarios")
            print("  1: Voice Interaction")
            print("  2: Assignment Explanation")
            print("  3: Quiz Solving")
            print("  4: Desktop Actions")
            print("  5: Privacy")
    else:
        run_full_demo()
