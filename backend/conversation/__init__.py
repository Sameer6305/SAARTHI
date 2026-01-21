"""
Conversation Package
====================

Provides multi-turn conversational interaction for SAARTHI.

Components:
- state_model: Conversation state machine and context management
- dialogue_flow: Dialogue controller with clarification and confirmation
- integration: Planner-Executor integration layer

Usage:
```python
from conversation import IntegratedAssistant, ActionType

# Create assistant
assistant = IntegratedAssistant()

# Register action handlers
async def open_url_handler(url: str, site_name: str = "") -> dict:
    import webbrowser
    webbrowser.open(url)
    return {"opened": url}

assistant.register_action(ActionType.OPEN_URL, open_url_handler)

# Process conversation
response = await assistant.process("open youtube")
# Response: "I'll open YouTube in your browser. Should I proceed?"

response = await assistant.process("yes")
# Response: "Done! Opened YouTube."
```
"""

from .state_model import (
    ConversationManager,
    ConversationState,
    ConversationContext,
    IntentType,
    ConfirmationStatus,
    Turn,
    PendingAction,
)

from .dialogue_flow import (
    DialogueFlowController,
    DialogueResponse,
)

from .integration import (
    IntegratedAssistant,
    Planner,
    Executor,
    ActionPlan,
    ActionType,
)

__all__ = [
    # State model
    "ConversationManager",
    "ConversationState", 
    "ConversationContext",
    "IntentType",
    "ConfirmationStatus",
    "Turn",
    "PendingAction",
    
    # Dialogue flow
    "DialogueFlowController",
    "DialogueResponse",
    
    # Integration
    "IntegratedAssistant",
    "Planner",
    "Executor",
    "ActionPlan",
    "ActionType",
]
