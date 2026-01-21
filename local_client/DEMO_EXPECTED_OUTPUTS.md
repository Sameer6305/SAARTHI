# SAARTHI Demo Scenarios - Expected Outputs

## Quick Start

```bash
cd local_client

# Run all demos interactively
python demo_scenarios.py

# Run specific scenario
python demo_scenarios.py 1  # Voice
python demo_scenarios.py 2  # Assignment
python demo_scenarios.py 3  # Quiz
python demo_scenarios.py 4  # Desktop
python demo_scenarios.py 5  # Privacy
```

---

## Scenario 1: Voice Interaction

### User Action
1. Click "Voice Command" in system tray
2. Hold "Talk" button and speak
3. Release button

### Sample Interaction
```
👤 USER: [VOICE] What is the time complexity of quicksort?

⚙ SYSTEM: Whisper STT processing... (local, ~300ms)
⚙ SYSTEM: Transcribed: 'What is the time complexity of quicksort?'

🤖 SAARTHI: QuickSort has an average time complexity of O(n log n), 
            but O(n²) in the worst case when the pivot selection is poor. 
            The space complexity is O(log n) for the recursive call stack.

⚙ SYSTEM: TTS speaks response (Windows SAPI, async)
⚙ SYSTEM: Audio data discarded - not stored
```

### Key Points
- ✅ Push-to-talk only (no background listening)
- ✅ Local Whisper transcription (~300ms)
- ✅ TTS response (async, non-blocking)
- ✅ Audio immediately discarded

---

## Scenario 2: Assignment Explanation

### Sample Interaction
```
👤 USER: Explain how to implement a binary search tree

🤖 SAARTHI: A tree is a hierarchical data structure with a root node and 
            child nodes. Binary trees have at most 2 children per node.

👤 USER: What about the insertion operation?

🤖 SAARTHI: For BST insertion, follow these steps:
            1. Start at the root node
            2. Compare the new value with current node
            3. If smaller, go left; if larger, go right
            4. Repeat until you find an empty spot
            5. Insert the new node there
            
            Time complexity: O(h) where h is the tree height.
            Would you like me to explain balancing to avoid O(n) worst case?

👤 USER: Explain recursion with an example

🤖 SAARTHI: Recursion is when a function calls itself to solve smaller 
            instances of the same problem. Every recursive function needs 
            a base case to stop.
```

### Key Points
- ✅ Step-by-step breakdown
- ✅ Explains concepts, not just answers
- ✅ Follow-up questions encouraged
- ✅ Quick responses for common topics (cached)

---

## Scenario 3: Quiz Solving with Reasoning

### Sample Interaction
```
👤 USER: Help me with this quiz question: What is the worst-case time 
         complexity of binary search? A) O(1) B) O(n) C) O(log n) D) O(n²)

🤖 SAARTHI: Let me help you think through this:

            📚 First, recall how binary search works:
               - It divides the search space in half each step
               - Starting with n elements, after 1 step: n/2
               - After 2 steps: n/4, after k steps: n/2^k

            🤔 For worst case, we keep dividing until 1 element:
               n/2^k = 1 → k = log₂(n)

            ✓ So the answer is C) O(log n)

            This is BETTER than linear search O(n) because we 
            eliminate half the elements each time!
```

### Anti-Cheat Example
```
👤 USER: Just give me the answer to question 5

🤖 SAARTHI: I'd be happy to help, but I need to see the question first. 
            Also, I'll explain the reasoning so you understand the concept - 
            that way you'll be prepared for similar questions on the exam! 
            What's question 5?
```

### Key Points
- ✅ Shows reasoning process
- ✅ Explains WHY the answer is correct
- ✅ Anti-cheat: won't give answers without explanation
- ✅ Teaching approach, not answer machine

---

## Scenario 4: Desktop Action with Permission

### Opening a Website (Approved)
```
👤 USER: Open YouTube

🤖 SAARTHI: Should I open youtube? (https://www.youtube.com)

⚙ SYSTEM: ⚠ Confirmation required - action pending

👤 USER: yes

✓ SAARTHI: Opening YouTube.

⚙ SYSTEM: Action: webbrowser.open('https://www.youtube.com')
⚙ SYSTEM: Audit log: action=open_url, target=youtube, status=success
```

### Cancelling an Action
```
👤 USER: Open GitHub

🤖 SAARTHI: Should I open github? (https://www.github.com)

👤 USER: no

🤖 SAARTHI: Cancelled.

⚙ SYSTEM: Action cancelled - no execution
```

### Forbidden Action
```
👤 USER: Delete all my files

🤖 SAARTHI: I can't do that. File deletion is not in my allowed actions. 
            I can only: open websites, launch apps, search the web, 
            and read files.

⚙ SYSTEM: ⛔ Action blocked by policy - not in whitelist
```

### Key Points
- ✅ ALL actions require explicit "yes"
- ✅ Timeout = automatic DENY
- ✅ Whitelist-only execution
- ✅ Complete audit logging
- ✅ Dangerous actions blocked

---

## Scenario 5: Privacy Demonstration

### Trust Guarantees
```
📋 Trust Guarantees:
   ❌ Never stored: raw_audio_bytes
   ❌ Never stored: microphone_stream
   ❌ Never stored: voice_recording
   ❌ Never stored: audio_file
   ❌ Never stored: passwords
   ❌ Never stored: api_keys
   ❌ Never stored: auth_tokens
```

### Data Storage
```
📊 Data Storage Demo:
   Stored: conversation turn (expires: end of session)
   Stored: preference (expires: 7 days)

🚫 What is NOT stored:
   ❌ Raw audio bytes
   ❌ Browsing history
   ❌ File contents
   ❌ Exact queries (only intent)
```

### Forget All
```
👤 USER: forget everything

🤖 SAARTHI: Done. I've forgotten 2 items. Memory cleared.
```

### Sleep Mode
```
⚙ SYSTEM: User minimizes SAARTHI to tray
⚙ SYSTEM: Sleep mode activated:
   • No listening
   • No processing
   • No memory access
   • Zero resource usage

⚙ SYSTEM: User clicks 'Wake Up' in tray
⚙ SYSTEM: Awake and ready
```

### Data Lifecycle
```
📅 Data Lifecycle:
   Category             Retention       Auto-delete
   --------------------------------------------------
   Voice Audio          NEVER STORED    Immediate
   Transcription        RAM only        After processing
   Conversation         Session         On close
   Preferences          7 days          Auto-cleanup
```

### Key Points
- ✅ No raw audio storage EVER
- ✅ Session-only conversation memory
- ✅ User can delete everything instantly
- ✅ Sleep mode = zero access
- ✅ Automatic cleanup of old data

---

## Quick Reference: Pattern-Matched Commands

These commands are handled instantly (< 5ms, no LLM):

| Command | Action |
|---------|--------|
| `open youtube` | Opens https://youtube.com |
| `open github` | Opens https://github.com |
| `search for python` | Google search |
| `explain binary search` | Shows cached explanation |
| `what is a stack` | Shows cached explanation |
| `hi` / `hello` | Greeting response |
| `thanks` | Thanks response |
| `yes` / `no` | Confirms/cancels pending action |
| `status` | Shows stats |

---

## Expected Performance

| Operation | Expected Time |
|-----------|---------------|
| Pattern matching | < 5ms |
| Cache lookup | < 1ms |
| STT (Whisper tiny) | 200-400ms |
| TTS (SAPI) | < 100ms |
| LLM (Ollama) | 1-3s |
| **Total voice round-trip** | **< 3s** |

---

## Running the Demo

### Prerequisites
```bash
# Ensure you're in the local_client directory
cd c:\Users\PRANAV KADAM\Desktop\saarthi\local_client

# Install pywin32 for TTS (if not already)
pip install pywin32
```

### Run All Scenarios
```bash
python demo_scenarios.py
```

### Run Specific Scenario
```bash
python demo_scenarios.py 3  # Quiz solving
```

### Expected Output Format
```
════════════════════════════════════════════════════════════
  SAARTHI FEATURE DEMONSTRATION
════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────┐
│  SCENARIO 1: VOICE INTERACTION                           │
└──────────────────────────────────────────────────────────┘

👤 USER: [command]
🤖 SAARTHI: [response]
⚙ SYSTEM: [system action]
✓ SAARTHI: [action completed]

✓ Voice interaction complete
```

---

## Troubleshooting

### TTS Not Speaking
- Ensure `pywin32` is installed: `pip install pywin32`
- Check Windows audio settings
- Try running as administrator

### Slow LLM Responses
- Ollama is optional for basic features
- Pattern matching handles 70% of commands
- Check if Ollama is running: `ollama list`

### Import Errors
- Run from `local_client` directory
- Ensure Python path includes parent folders
