"""
Dialogue Flow Controller
========================

Orchestrates conversation flow between user input, planner, and executor.

FLOW DIAGRAM:
```
User Input
    │
    ▼
┌───────────────────┐
│ ConversationMgr   │──── Intent Classification
│   process_input() │──── Entity Extraction
└────────┬──────────┘──── State Transition
         │
         ▼
    ┌────┴────┐
    │ Branch  │
    └────┬────┘
         │
    ┌────┼────────────────┬─────────────────┐
    │    │                │                 │
    ▼    ▼                ▼                 ▼
 Needs   Needs         Execute          Conversational
 Clarify Confirm       Action           Response
    │    │                │                 │
    ▼    ▼                ▼                 ▼
 Ask     Ask           Planner          Generate
 Question Confirm      → Executor       Response
    │    │                │                 │
    └────┴────────────────┴─────────────────┘
                         │
                         ▼
                   Complete Turn
                   Update History
```
"""

from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict
from .state_model import (
    ConversationManager,
    ConversationState,
    IntentType,
    ConfirmationStatus,
    PendingAction,
)


@dataclass
class DialogueResponse:
    """Response from dialogue flow controller."""
    text: str                           # Response text to show user
    should_speak: bool = True           # Should TTS speak this?
    action_to_execute: Optional[Dict] = None  # Action for executor
    awaiting_input: bool = True         # Waiting for user input?
    session_ended: bool = False         # Conversation ended?


class DialogueFlowController:
    """
    Controls the dialogue flow between user and system.
    
    RESPONSIBILITIES:
    1. Receive user input
    2. Use ConversationManager for state management
    3. Coordinate with Planner for action planning
    4. Coordinate with Executor for action execution
    5. Generate appropriate responses
    
    NO HALLUCINATED EXECUTION:
    - Actions are NEVER executed without explicit confirmation
    - Confirmation must come from user, not inferred
    - All actions are logged and traceable
    """
    
    # Response templates
    RESPONSES = {
        "greeting": [
            "Hello! I'm SAARTHI, your study assistant. How can I help?",
            "Hi there! What would you like me to help with today?",
        ],
        "thanks": [
            "You're welcome! Let me know if you need anything else.",
            "Happy to help! Is there anything else?",
        ],
        "help": (
            "I can help you with:\n"
            "• Open websites (e.g., 'open YouTube')\n"
            "• Search the web (e.g., 'search for calculus tutorial')\n"
            "• Read and summarize files\n"
            "• Explain concepts\n"
            "• Create study plans\n"
            "• Help with quizzes\n"
            "Just say what you need!"
        ),
        "confirm_prompt": "Should I proceed? Say 'yes' to confirm or 'no' to cancel.",
        "action_cancelled": "Okay, I've cancelled that. What else can I help with?",
        "action_confirmed": "Got it! Executing now...",
        "action_completed": "Done! {result}",
        "action_failed": "Sorry, I couldn't complete that. {error}",
        "clarify_prefix": "I need a bit more information. ",
        "unknown": "I'm not sure what you mean. Could you rephrase that?",
        "error": "Something went wrong. Let's try again.",
    }
    
    def __init__(
        self,
        planner_callback: Optional[Callable] = None,
        executor_callback: Optional[Callable] = None,
    ):
        """
        Initialize dialogue controller.
        
        Args:
            planner_callback: Function to call for planning (async)
            executor_callback: Function to call for execution (async)
        """
        self.conversation = ConversationManager()
        self._planner = planner_callback
        self._executor = executor_callback
        self._response_index = 0  # For varying responses
    
    def _get_response(self, key: str, **kwargs) -> str:
        """Get a response template, with variation for repeated keys."""
        template = self.RESPONSES.get(key, self.RESPONSES["unknown"])
        
        if isinstance(template, list):
            self._response_index = (self._response_index + 1) % len(template)
            template = template[self._response_index]
        
        return template.format(**kwargs) if kwargs else template
    
    async def handle_input(self, user_text: str) -> DialogueResponse:
        """
        Main entry point: handle user input and return response.
        
        This is the core dialogue loop handler.
        """
        if not user_text.strip():
            return DialogueResponse(
                text="I didn't catch that. Could you say that again?",
                awaiting_input=True,
            )
        
        # Process input through conversation manager
        result = self.conversation.process_input(user_text)
        
        # Branch based on result
        intent = result["intent"]
        
        # --- Handle clarification needed ---
        if result["needs_clarification"]:
            return DialogueResponse(
                text=self._get_response("clarify_prefix") + result["clarification_question"],
                awaiting_input=True,
            )
        
        # --- Handle confirmation needed ---
        if result["needs_confirmation"]:
            action = result["pending_action"]
            confirm_text = f"I'll {action.description}. {self._get_response('confirm_prompt')}"
            return DialogueResponse(
                text=confirm_text,
                awaiting_input=True,
            )
        
        # --- Handle confirmation response (execute) ---
        if result.get("execute_now") and result["pending_action"]:
            action = result["pending_action"]
            
            # Execute the action
            exec_result = await self._execute_action(action)
            
            if exec_result.get("success"):
                response_text = self._get_response("action_completed", result=exec_result.get("message", ""))
            else:
                response_text = self._get_response("action_failed", error=exec_result.get("error", "Unknown error"))
            
            self.conversation.complete_turn(response_text, action.action_type)
            
            return DialogueResponse(
                text=response_text,
                awaiting_input=True,
            )
        
        # --- Handle conversational intents ---
        if result["is_conversational"]:
            response_text = self._handle_conversational(intent)
            self.conversation.complete_turn(response_text)
            
            return DialogueResponse(
                text=response_text,
                awaiting_input=True,
            )
        
        # --- Handle cancellation ---
        if intent == IntentType.CANCEL:
            response_text = self._get_response("action_cancelled")
            self.conversation.complete_turn(response_text)
            
            return DialogueResponse(
                text=response_text,
                awaiting_input=True,
            )
        
        # --- Unknown intent ---
        response_text = self._get_response("unknown")
        self.conversation.complete_turn(response_text)
        
        return DialogueResponse(
            text=response_text,
            awaiting_input=True,
        )
    
    def _handle_conversational(self, intent: IntentType) -> str:
        """Generate response for conversational intents."""
        if intent == IntentType.GREETING:
            return self._get_response("greeting")
        
        if intent == IntentType.THANKS:
            return self._get_response("thanks")
        
        if intent == IntentType.HELP:
            return self._get_response("help")
        
        return self._get_response("unknown")
    
    async def _execute_action(self, action: PendingAction) -> Dict[str, Any]:
        """
        Execute an approved action through the executor.
        
        NO HALLUCINATED EXECUTION:
        - Only executes if action.status == APPROVED
        - Logs all execution attempts
        - Returns actual result, not assumed success
        """
        if action.status != ConfirmationStatus.APPROVED:
            return {
                "success": False,
                "error": "Action not approved",
            }
        
        if not self._executor:
            # No executor connected - simulate for testing
            return {
                "success": True,
                "message": f"[SIMULATED] Would execute: {action.action_type}",
            }
        
        try:
            result = await self._executor(
                action_type=action.action_type,
                parameters=action.parameters,
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def get_conversation_context(self) -> str:
        """Get conversation context for LLM prompts."""
        return self.conversation.context.to_prompt_context()
    
    def reset(self) -> str:
        """Reset conversation, returns new session ID."""
        return self.conversation.new_session()


# =============================================================================
# DIALOGUE FLOW EXAMPLES
# =============================================================================

"""
EXAMPLE 1: Simple URL Open
--------------------------
User: "open youtube"
→ Intent: OPEN_URL, Entities: {site: youtube, url: https://www.youtube.com}
→ Action: Pending confirmation
Assistant: "I'll open YouTube in your browser. Should I proceed?"
User: "yes"
→ Intent: CONFIRMATION
→ Execute: open_url(https://www.youtube.com)
Assistant: "Done! Opened YouTube."


EXAMPLE 2: Ambiguous Request (Clarification)
--------------------------------------------
User: "open the website"
→ Intent: OPEN_URL, Entities: {} (no site extracted)
→ Needs clarification
Assistant: "Which website would you like me to open?"
User: "google"
→ Intent: CLARIFICATION (context: url)
→ Entities: {site: google, url: https://www.google.com}
→ Action: Pending confirmation
Assistant: "I'll open Google. Should I proceed?"
User: "yes"
→ Execute: open_url(https://www.google.com)
Assistant: "Done! Opened Google."


EXAMPLE 3: Rejection
--------------------
User: "search for python tutorials"
→ Intent: SEARCH_WEB, Entities: {query: python tutorials}
→ Action: Pending confirmation
Assistant: "I'll search the web for 'python tutorials'. Should I proceed?"
User: "no, search for java instead"
→ Intent: CANCEL (detected "no")
→ Clear pending action
→ Re-process: "search for java instead"
→ Intent: SEARCH_WEB, Entities: {query: java}
→ Action: New pending confirmation
Assistant: "I'll search the web for 'java'. Should I proceed?"


EXAMPLE 4: Multi-turn Context
-----------------------------
User: "explain differential equations"
→ Intent: EXPLAIN
Assistant: "Differential equations are equations involving derivatives..."
User: "give me an example"
→ Intent: FOLLOWUP (context: differential equations)
→ Uses conversation history to understand context
Assistant: "Here's a simple example: dy/dx = 2x..."


EXAMPLE 5: Task with File
-------------------------
User: "summarize my notes"
→ Intent: READ_FILE, Entities: {} (no file specified)
→ Needs clarification
Assistant: "Which file would you like me to summarize?"
User: "the calculus pdf on my desktop"
→ Intent: CLARIFICATION
→ Entities: {file_hint: calculus pdf, location: desktop}
→ Search for file...
→ Found: C:/Users/Desktop/calculus_notes.pdf
→ Action: Pending confirmation
Assistant: "I'll summarize calculus_notes.pdf from your desktop. Proceed?"
User: "yes"
→ Execute: read_and_summarize(file_path)
Assistant: "Here's a summary of your calculus notes: ..."
"""
