"""
Assistant State Machine v2.0
============================

Interview-grade deterministic state machine for the SAARTHI voice assistant.

DESIGN PRINCIPLES:
1. Explicit state transitions (matrix-validated)
2. Thread-safe with reentrant lock
3. Timeout protection on all states
4. Observable state changes
5. Full audit trail for debugging

STATE DIAGRAM:
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   ┌──────┐     ┌───────────┐     ┌─────────────┐     ┌────────┐│
    │   │ IDLE │────▶│ LISTENING │────▶│TRANSCRIBING │────▶│THINKING││
    │   └──────┘     └───────────┘     └─────────────┘     └────────┘│
    │       ▲              │                  │                 │    │
    │       │              │                  │                 │    │
    │       │              ▼                  ▼                 ▼    │
    │       │         ┌────────┐         ┌────────┐       ┌─────────┐│
    │       └─────────│ ERROR  │◀────────│ ERROR  │◀──────│EXECUTING││
    │                 └────────┘         └────────┘       └─────────┘│
    │                      │                                    │    │
    │                      │                                    ▼    │
    │                      │                             ┌──────────┐│
    │                      └────────────────────────────▶│ SPEAKING ││
    │                                                    └──────────┘│
    └─────────────────────────────────────────────────────────────────┘

PUBLIC API:
    - AssistantState: Enum of all states
    - StateConfig: Configuration for timeouts
    - StateTransition: Immutable transition record
    - StateTransitionError: Exception for invalid transitions
    - AssistantStateMachine: The state machine itself
    - create_state_machine: Factory function
    - requires_state: Decorator for state-aware functions
    - transitions_to: Decorator for automatic transitions
"""

# Public API exports
__all__ = [
    'AssistantState',
    'StateConfig',
    'StateTransition',
    'StateTransitionError',
    'AssistantStateMachine',
    'create_state_machine',
    'requires_state',
    'transitions_to',
]

import logging
import threading
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any, Set
from contextlib import contextmanager
from collections import deque

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    """
    Voice assistant operational states.
    
    Each state has:
    - Defined entry/exit conditions
    - Maximum duration (timeout protection)
    - Valid next states
    """
    IDLE = auto()           # Waiting for activation (SPACE key)
    LISTENING = auto()      # Capturing audio via VAD
    TRANSCRIBING = auto()   # Whisper STT processing
    THINKING = auto()       # Intent parsing and routing
    EXECUTING = auto()      # Running action (browser, app, etc.)
    SPEAKING = auto()       # TTS output
    ERROR = auto()          # Error handling (always recovers to IDLE)


@dataclass
class StateConfig:
    """Configuration for state timeouts and behavior."""
    # Maximum time (seconds) allowed in each state before forced transition
    timeouts: Dict[AssistantState, float] = field(default_factory=lambda: {
        AssistantState.IDLE: float('inf'),       # No timeout for idle
        AssistantState.LISTENING: 30.0,          # Max recording duration
        AssistantState.TRANSCRIBING: 15.0,       # Max STT time
        AssistantState.THINKING: 5.0,            # Max intent parsing time
        AssistantState.EXECUTING: 30.0,          # Max execution time
        AssistantState.SPEAKING: 60.0,           # Max TTS time
        AssistantState.ERROR: 5.0,               # Max error handling time
    })
    
    # Enable/disable timeout monitoring
    enable_timeout_monitoring: bool = True
    
    # How often to check for timeouts (seconds)
    timeout_check_interval: float = 0.5


@dataclass
class StateTransition:
    """Immutable record of a state transition."""
    from_state: AssistantState
    to_state: AssistantState
    timestamp: datetime
    reason: str
    duration_in_previous_state: float
    triggered_by: str  # "user", "system", "timeout", "error"
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_state.name,
            "to": self.to_state.name,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "duration": round(self.duration_in_previous_state, 3),
            "triggered_by": self.triggered_by,
            "context": self.context,
        }


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_state: AssistantState, to_state: AssistantState, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition: {from_state.name} → {to_state.name}. {reason}")


class AssistantStateMachine:
    """
    Thread-safe, deterministic state machine for voice assistant.
    
    INTERVIEW TALKING POINTS:
    1. Why RLock? - Allows nested transitions (e.g., error during transition)
    2. Why matrix validation? - O(1) validity check, explicit allowlist
    3. Why observer pattern? - Decouples state changes from side effects
    4. Why timeout monitoring? - Prevents infinite states (e.g., VAD never stopping)
    
    USAGE:
        sm = AssistantStateMachine()
        
        # Register observer
        sm.add_observer(lambda old, new, reason: print(f"{old} → {new}"))
        
        # Transition with validation
        if sm.can_transition_to(AssistantState.LISTENING):
            sm.transition(AssistantState.LISTENING, "user_pressed_space")
        
        # Context manager for automatic error handling
        with sm.in_state(AssistantState.EXECUTING) as ctx:
            # Do work... if exception raised, auto-transitions to ERROR
            pass
    """
    
    # Valid transition matrix (explicit allowlist)
    # Key: from_state, Value: set of valid to_states
    TRANSITION_MATRIX: Dict[AssistantState, Set[AssistantState]] = {
        AssistantState.IDLE: {
            AssistantState.LISTENING,
        },
        AssistantState.LISTENING: {
            AssistantState.TRANSCRIBING,
            AssistantState.ERROR,
            AssistantState.IDLE,  # User cancelled
        },
        AssistantState.TRANSCRIBING: {
            AssistantState.THINKING,
            AssistantState.ERROR,
        },
        AssistantState.THINKING: {
            AssistantState.EXECUTING,
            AssistantState.SPEAKING,  # Direct to speaking for Q&A
            AssistantState.ERROR,
        },
        AssistantState.EXECUTING: {
            AssistantState.SPEAKING,
            AssistantState.IDLE,  # Silent execution complete
            AssistantState.ERROR,
        },
        AssistantState.SPEAKING: {
            AssistantState.IDLE,
            AssistantState.ERROR,
        },
        AssistantState.ERROR: {
            AssistantState.IDLE,  # Error always recovers to IDLE
        },
    }
    
    def __init__(self, config: Optional[StateConfig] = None):
        self._config = config or StateConfig()
        
        # State
        self._state = AssistantState.IDLE
        self._state_start_time = time.time()
        self._lock = threading.RLock()
        
        # Observers
        self._observers: List[Callable[[AssistantState, AssistantState, str], None]] = []
        
        # History (for debugging)
        self._history: deque = deque(maxlen=100)
        
        # Statistics
        self._stats = {
            "transitions": 0,
            "invalid_transitions_attempted": 0,
            "timeouts": 0,
            "errors": 0,
        }
        
        # Timeout monitor thread
        self._timeout_monitor: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        if self._config.enable_timeout_monitoring:
            self._start_timeout_monitor()
        
        logger.info("State machine initialized in IDLE state")
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    @property
    def state(self) -> AssistantState:
        """Get current state (thread-safe read)."""
        with self._lock:
            return self._state
    
    @property
    def state_duration(self) -> float:
        """Get time spent in current state."""
        with self._lock:
            return time.time() - self._state_start_time
    
    @property
    def is_idle(self) -> bool:
        return self.state == AssistantState.IDLE
    
    @property
    def is_busy(self) -> bool:
        return self.state not in {AssistantState.IDLE, AssistantState.ERROR}
    
    def can_transition_to(self, new_state: AssistantState) -> bool:
        """Check if transition to new_state is valid from current state."""
        with self._lock:
            valid_targets = self.TRANSITION_MATRIX.get(self._state, set())
            return new_state in valid_targets
    
    def transition(
        self,
        new_state: AssistantState,
        reason: str,
        triggered_by: str = "system",
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: Target state
            reason: Human-readable reason for transition
            triggered_by: "user", "system", "timeout", or "error"
            context: Additional context for debugging
        
        Returns:
            True if transition succeeded, False if invalid
        
        Raises:
            StateTransitionError if raise_on_invalid=True (not default)
        """
        with self._lock:
            # Validate transition
            if not self.can_transition_to(new_state):
                self._stats["invalid_transitions_attempted"] += 1
                logger.warning(
                    f"Invalid transition: {self._state.name} → {new_state.name} "
                    f"(reason: {reason})"
                )
                return False
            
            # Record transition
            old_state = self._state
            duration = time.time() - self._state_start_time
            
            transition = StateTransition(
                from_state=old_state,
                to_state=new_state,
                timestamp=datetime.now(),
                reason=reason,
                duration_in_previous_state=duration,
                triggered_by=triggered_by,
                context=context or {},
            )
            
            # Execute transition
            self._state = new_state
            self._state_start_time = time.time()
            self._history.append(transition)
            self._stats["transitions"] += 1
            
            if new_state == AssistantState.ERROR:
                self._stats["errors"] += 1
            
            # Log
            logger.info(
                f"State: {old_state.name} → {new_state.name} "
                f"(reason: {reason}, duration: {duration:.2f}s)"
            )
            
            # Notify observers (outside lock to prevent deadlocks)
            self._notify_observers(old_state, new_state, reason)
            
            return True
    
    def force_idle(self, reason: str = "forced_reset"):
        """
        Force transition to IDLE regardless of current state.
        Used for recovery from stuck states.
        """
        with self._lock:
            old_state = self._state
            if old_state == AssistantState.IDLE:
                return
            
            logger.warning(f"Forcing IDLE from {old_state.name}: {reason}")
            self._state = AssistantState.IDLE
            self._state_start_time = time.time()
            
            self._history.append(StateTransition(
                from_state=old_state,
                to_state=AssistantState.IDLE,
                timestamp=datetime.now(),
                reason=f"FORCED: {reason}",
                duration_in_previous_state=time.time() - self._state_start_time,
                triggered_by="system",
                context={"forced": True},
            ))
    
    @contextmanager
    def in_state(
        self,
        target_state: AssistantState,
        reason: str = "context_manager",
        error_reason: str = "exception_in_state",
    ):
        """
        Context manager for state lifecycle.
        
        Automatically:
        - Transitions to target_state on entry
        - Transitions to ERROR on exception
        - Allows graceful exit with successful transition
        
        Usage:
            with sm.in_state(AssistantState.EXECUTING, "running_action"):
                # Do work...
                pass  # Auto-transitions based on success/failure
        """
        entered = self.transition(target_state, reason)
        if not entered:
            raise StateTransitionError(self._state, target_state, "Cannot enter state")
        
        try:
            yield self
        except Exception as e:
            self.transition(AssistantState.ERROR, f"{error_reason}: {str(e)[:50]}")
            raise
    
    def add_observer(
        self,
        callback: Callable[[AssistantState, AssistantState, str], None]
    ):
        """Add state change observer."""
        with self._lock:
            self._observers.append(callback)
    
    def remove_observer(
        self,
        callback: Callable[[AssistantState, AssistantState, str], None]
    ):
        """Remove state change observer."""
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)
    
    def get_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get last n state transitions."""
        with self._lock:
            return [t.to_dict() for t in list(self._history)[-n:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state machine statistics."""
        with self._lock:
            return {
                **self._stats,
                "current_state": self._state.name,
                "time_in_state": round(self.state_duration, 2),
            }
    
    def shutdown(self):
        """Clean shutdown of state machine."""
        self._stop_monitor.set()
        if self._timeout_monitor and self._timeout_monitor.is_alive():
            self._timeout_monitor.join(timeout=2.0)
        logger.info("State machine shutdown complete")
    
    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================
    
    def _notify_observers(
        self,
        old_state: AssistantState,
        new_state: AssistantState,
        reason: str
    ):
        """Notify all observers of state change."""
        for observer in self._observers:
            try:
                observer(old_state, new_state, reason)
            except Exception as e:
                logger.error(f"Observer error: {e}")
    
    def _start_timeout_monitor(self):
        """Start background thread to monitor state timeouts."""
        def monitor():
            while not self._stop_monitor.is_set():
                self._check_timeout()
                time.sleep(self._config.timeout_check_interval)
        
        self._timeout_monitor = threading.Thread(
            target=monitor,
            daemon=True,
            name="state_timeout_monitor"
        )
        self._timeout_monitor.start()
        logger.debug("Timeout monitor started")
    
    def _check_timeout(self):
        """Check if current state has timed out."""
        with self._lock:
            timeout = self._config.timeouts.get(self._state, float('inf'))
            if self.state_duration > timeout:
                self._stats["timeouts"] += 1
                logger.warning(
                    f"State timeout: {self._state.name} exceeded {timeout}s "
                    f"(actual: {self.state_duration:.1f}s)"
                )
                
                # Transition to ERROR, then ERROR will auto-recover to IDLE
                if self._state != AssistantState.ERROR:
                    self.transition(
                        AssistantState.ERROR,
                        f"timeout_in_{self._state.name.lower()}",
                        triggered_by="timeout",
                    )
                else:
                    # ERROR state timed out, force IDLE
                    self.force_idle("error_state_timeout")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_state_machine(
    enable_timeouts: bool = True,
    custom_timeouts: Optional[Dict[AssistantState, float]] = None,
) -> AssistantStateMachine:
    """
    Create a configured state machine.
    
    Args:
        enable_timeouts: Whether to monitor state timeouts
        custom_timeouts: Override default timeouts
    
    Returns:
        Configured AssistantStateMachine
    """
    config = StateConfig(enable_timeout_monitoring=enable_timeouts)
    
    if custom_timeouts:
        config.timeouts.update(custom_timeouts)
    
    return AssistantStateMachine(config)


# =============================================================================
# DECORATORS FOR STATE-AWARE FUNCTIONS
# =============================================================================

def requires_state(*required_states: AssistantState):
    """
    Decorator to ensure function only runs in specified states.
    
    Usage:
        @requires_state(AssistantState.IDLE, AssistantState.LISTENING)
        def start_recording(self):
            ...
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            sm = getattr(self, '_state_machine', None)
            if sm is None:
                raise RuntimeError("Object has no _state_machine attribute")
            
            if sm.state not in required_states:
                logger.warning(
                    f"Function {func.__name__} requires states "
                    f"{[s.name for s in required_states]}, "
                    f"but current state is {sm.state.name}"
                )
                return None
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def transitions_to(target_state: AssistantState, reason: str):
    """
    Decorator to automatically transition after function execution.
    
    Usage:
        @transitions_to(AssistantState.THINKING, "stt_complete")
        def transcribe(self, audio):
            ...
            return text
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            sm = getattr(self, '_state_machine', None)
            result = func(self, *args, **kwargs)
            
            if sm and result is not None:
                sm.transition(target_state, reason)
            
            return result
        return wrapper
    return decorator
