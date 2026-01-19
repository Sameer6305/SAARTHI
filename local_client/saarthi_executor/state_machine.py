"""
State Machine
=============

Manages the operational states of the SAARTHI local executor.

States:
- SLEEP: No execution, no listening
- LISTENING: Waiting for actions, no execution
- ACTIVE: Executing a confirmed action

All state transitions are explicit and logged.
"""

import logging
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ExecutorState(Enum):
    """Operational states of the executor."""
    
    SLEEP = auto()      # Inactive, not processing anything
    LISTENING = auto()  # Waiting for incoming actions
    ACTIVE = auto()     # Executing a user-confirmed action


@dataclass
class StateTransition:
    """Record of a state transition for audit."""
    
    from_state: ExecutorState
    to_state: ExecutorState
    timestamp: datetime
    reason: str
    triggered_by: str  # "user" or "system"


@dataclass 
class StateMachine:
    """
    State machine for the SAARTHI local executor.
    
    SECURITY: All transitions are logged and auditable.
    """
    
    current_state: ExecutorState = ExecutorState.SLEEP
    transition_history: list[StateTransition] = field(default_factory=list)
    _state_change_callbacks: list[Callable[[ExecutorState, ExecutorState], None]] = field(
        default_factory=list
    )
    
    # Valid transitions (explicit allowlist)
    VALID_TRANSITIONS: dict[ExecutorState, list[ExecutorState]] = field(
        default_factory=lambda: {
            ExecutorState.SLEEP: [ExecutorState.LISTENING],
            ExecutorState.LISTENING: [ExecutorState.SLEEP, ExecutorState.ACTIVE],
            ExecutorState.ACTIVE: [ExecutorState.LISTENING, ExecutorState.SLEEP],
        }
    )
    
    def can_transition_to(self, new_state: ExecutorState) -> bool:
        """Check if transition to new_state is valid from current state."""
        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        return new_state in valid_targets
    
    def transition_to(
        self,
        new_state: ExecutorState,
        reason: str,
        triggered_by: str = "system"
    ) -> bool:
        """
        Attempt to transition to a new state.
        
        Returns True if successful, False if invalid transition.
        All transitions are logged.
        """
        if not self.can_transition_to(new_state):
            logger.warning(
                "Invalid state transition attempted",
                extra={
                    "from_state": self.current_state.name,
                    "to_state": new_state.name,
                    "reason": reason,
                }
            )
            return False
        
        old_state = self.current_state
        
        # Record transition
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.utcnow(),
            reason=reason,
            triggered_by=triggered_by,
        )
        self.transition_history.append(transition)
        
        # Update state
        self.current_state = new_state
        
        logger.info(
            "State transition",
            extra={
                "from_state": old_state.name,
                "to_state": new_state.name,
                "reason": reason,
                "triggered_by": triggered_by,
            }
        )
        
        # Notify callbacks
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
        
        return True
    
    def register_state_change_callback(
        self,
        callback: Callable[[ExecutorState, ExecutorState], None]
    ) -> None:
        """Register a callback for state changes."""
        self._state_change_callbacks.append(callback)
    
    def is_sleeping(self) -> bool:
        """Check if in SLEEP state."""
        return self.current_state == ExecutorState.SLEEP
    
    def is_listening(self) -> bool:
        """Check if in LISTENING state."""
        return self.current_state == ExecutorState.LISTENING
    
    def is_active(self) -> bool:
        """Check if in ACTIVE state."""
        return self.current_state == ExecutorState.ACTIVE
    
    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)."""
        if not self.transition_history:
            return 0.0
        
        last_transition = self.transition_history[-1]
        return (datetime.utcnow() - last_transition.timestamp).total_seconds()
    
    def get_recent_transitions(self, count: int = 10) -> list[StateTransition]:
        """Get the most recent state transitions."""
        return self.transition_history[-count:]
    
    # Convenience methods for common transitions
    
    def wake_up(self, reason: str = "User activated") -> bool:
        """Transition from SLEEP to LISTENING."""
        return self.transition_to(
            ExecutorState.LISTENING,
            reason=reason,
            triggered_by="user"
        )
    
    def go_to_sleep(self, reason: str = "User requested sleep") -> bool:
        """Transition to SLEEP state."""
        return self.transition_to(
            ExecutorState.SLEEP,
            reason=reason,
            triggered_by="user"
        )
    
    def begin_execution(self, action_id: str) -> bool:
        """Transition to ACTIVE state for action execution."""
        return self.transition_to(
            ExecutorState.ACTIVE,
            reason=f"Executing action: {action_id}",
            triggered_by="system"
        )
    
    def finish_execution(self, success: bool) -> bool:
        """Transition back to LISTENING after execution."""
        status = "completed" if success else "failed"
        return self.transition_to(
            ExecutorState.LISTENING,
            reason=f"Execution {status}",
            triggered_by="system"
        )
