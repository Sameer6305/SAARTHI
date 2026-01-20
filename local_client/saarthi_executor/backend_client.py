"""
Backend Client
==============

Real HTTP client for communication with the SAARTHI backend.

This module replaces the mock cloud client with actual HTTP calls
to the backend running at localhost:8000.

DESIGN PRINCIPLES:
- Fail closed on errors
- Maximum ONE retry per failure
- Validate all responses as untrusted input
- Log all operations for traceability
- No execution logic - only communication

ARCHITECTURE:
- User input → validate → send to backend → receive plan → return
- All errors are caught and logged
- Connection failures do not crash the client
- Network failures retry at most ONCE then stop

ERROR HANDLING:
- Connection refused → retry once → notify user → idle state
- Timeout → retry once → notify user → idle state  
- Invalid response → do not retry → notify user
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

import httpx

from saarthi_executor.error_handling import (
    RetryManager,
    UserError,
    create_network_timeout_error,
    create_network_unreachable_error,
    get_error_logger,
    get_retry_manager,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class BackendConfig:
    """
    Configuration for backend communication.
    
    SECURITY: Only localhost is allowed for local testing.
    """
    
    base_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"
    timeout_seconds: float = 30.0
    
    # Connection settings  
    max_retries: int = 1  # Maximum ONE retry
    connect_timeout: float = 5.0
    
    # Input constraints
    min_input_length: int = 1
    max_input_length: int = 10000
    
    def get_endpoint(self, path: str) -> str:
        """Get full URL for an endpoint."""
        return f"{self.base_url}{self.api_prefix}{path}"


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class ConnectionState(Enum):
    """State of the backend connection."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TaskCreationResult:
    """Result of creating a task on the backend."""
    
    success: bool
    task_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    intent_summary: Optional[str] = None
    step_count: Optional[int] = None
    error: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class ActionData:
    """A single action from the backend."""
    
    action_id: str
    action_type: str
    parameters: dict
    description: Optional[str] = None
    risk_level: str = "LOW"
    signature: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class ActionsResult:
    """Result of fetching actions from the backend."""
    
    success: bool
    task_id: Optional[str] = None
    actions: list[ActionData] = field(default_factory=list)
    total_actions: int = 0
    error: Optional[str] = None
    raw_response: Optional[dict] = None


# =============================================================================
# INPUT VALIDATION
# =============================================================================

class InputValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_user_input(text: str, config: BackendConfig) -> str:
    """
    Validate and sanitize user input before sending to backend.
    
    SECURITY: This is the first line of defense against malformed input.
    
    Args:
        text: Raw user input
        config: Backend configuration with constraints
        
    Returns:
        Sanitized input text
        
    Raises:
        InputValidationError: If input is invalid
    """
    if text is None:
        raise InputValidationError("Input cannot be None")
    
    # Strip whitespace
    text = text.strip()
    
    if not text:
        raise InputValidationError("Input cannot be empty or whitespace only")
    
    if len(text) < config.min_input_length:
        raise InputValidationError(
            f"Input too short (minimum {config.min_input_length} characters)"
        )
    
    if len(text) > config.max_input_length:
        raise InputValidationError(
            f"Input too long (maximum {config.max_input_length} characters)"
        )
    
    # Remove null bytes and control characters (except newlines/tabs)
    sanitized = "".join(
        char for char in text
        if char in ("\n", "\t") or (ord(char) >= 32 and ord(char) != 127)
    )
    
    if not sanitized.strip():
        raise InputValidationError("Input contains only invalid characters")
    
    return sanitized.strip()


# =============================================================================
# RESPONSE VALIDATION
# =============================================================================

def validate_task_response(data: Any) -> Optional[str]:
    """
    Validate the structure of a task creation response.
    
    Treats backend response as UNTRUSTED input.
    
    Returns error message if invalid, None if valid.
    """
    if not isinstance(data, dict):
        return "Response is not a JSON object"
    
    # Required fields
    required = ["task_id", "status", "message"]
    for field_name in required:
        if field_name not in data:
            return f"Missing required field: {field_name}"
    
    # Type checks
    if not isinstance(data["task_id"], str):
        return "task_id must be a string"
    
    if not data["task_id"].startswith("task_"):
        return "task_id has invalid format"
    
    if not isinstance(data["status"], str):
        return "status must be a string"
    
    if not isinstance(data["message"], str):
        return "message must be a string"
    
    return None


def validate_actions_response(data: Any) -> Optional[str]:
    """
    Validate the structure of an actions response.
    
    Returns error message if invalid, None if valid.
    """
    if not isinstance(data, dict):
        return "Response is not a JSON object"
    
    if "actions" not in data:
        return "Missing 'actions' field"
    
    if not isinstance(data["actions"], list):
        return "'actions' must be an array"
    
    # Validate each action
    for i, action in enumerate(data["actions"]):
        if not isinstance(action, dict):
            return f"Action {i} is not an object"
        
        required = ["action_id", "action_type"]
        for field_name in required:
            if field_name not in action:
                return f"Action {i} missing required field: {field_name}"
    
    return None


# =============================================================================
# BACKEND CLIENT
# =============================================================================

class BackendClient:
    """
    HTTP client for SAARTHI backend communication.
    
    RESPONSIBILITIES:
    - Send user commands to backend
    - Receive and validate planner responses
    - Handle connection errors gracefully
    - Retry network failures at most ONCE
    - Log all operations
    
    NON-RESPONSIBILITIES:
    - Does NOT execute actions
    - Does NOT store state beyond connection
    
    ERROR HANDLING:
    - Connection refused → retry once → if fails, notify user
    - Request timeout → retry once → if fails, notify user
    - Invalid response → do NOT retry → notify user
    - All failures logged for audit
    """
    
    # Retry delay between attempts
    RETRY_DELAY_SECONDS = 2.0
    
    def __init__(self, config: Optional[BackendConfig] = None):
        """
        Initialize the backend client.
        
        Args:
            config: Backend configuration (uses defaults if None)
        """
        self.config = config or BackendConfig()
        self._client: Optional[httpx.Client] = None
        self._state = ConnectionState.DISCONNECTED
        self._retry_manager = get_retry_manager()
        self._error_logger = get_error_logger()
        
        logger.info(
            "BackendClient initialized",
            extra={"base_url": self.config.base_url}
        )
    
    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Whether client is connected."""
        return self._state == ConnectionState.CONNECTED
    
    # -------------------------------------------------------------------------
    # CONNECTION MANAGEMENT
    # -------------------------------------------------------------------------
    
    def connect(self) -> bool:
        """
        Establish connection to backend.
        
        Returns True if connection successful.
        """
        try:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.timeout_seconds,
                    write=self.config.timeout_seconds,
                    pool=self.config.timeout_seconds,
                ),
                headers={
                    "User-Agent": "SAARTHI-LocalClient/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            
            # Test connection with health check
            response = self._client.get("/health")
            
            if response.status_code == 200:
                self._state = ConnectionState.CONNECTED
                logger.info(
                    "Connected to backend",
                    extra={
                        "base_url": self.config.base_url,
                        "status_code": response.status_code
                    }
                )
                return True
            else:
                self._state = ConnectionState.ERROR
                logger.warning(
                    "Backend health check failed",
                    extra={"status_code": response.status_code}
                )
                return False
                
        except httpx.ConnectError as e:
            self._state = ConnectionState.ERROR
            logger.error(
                "Failed to connect to backend",
                extra={"error": str(e), "base_url": self.config.base_url}
            )
            return False
        
        except httpx.TimeoutException as e:
            self._state = ConnectionState.ERROR
            logger.error(
                "Connection timed out",
                extra={"error": str(e), "timeout": self.config.connect_timeout}
            )
            return False
        
        except Exception as e:
            self._state = ConnectionState.ERROR
            logger.error(
                "Unexpected error during connection",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            return False
    
    def disconnect(self) -> None:
        """Close connection to backend."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(
                    "Error closing client",
                    extra={"error": str(e)}
                )
            finally:
                self._client = None
                self._state = ConnectionState.DISCONNECTED
                logger.info("Disconnected from backend")
    
    # -------------------------------------------------------------------------
    # TASK CREATION
    # -------------------------------------------------------------------------
    
    def send_command(self, input_text: str, session_id: Optional[str] = None) -> TaskCreationResult:
        """
        Send user command to backend for planning.
        
        FLOW:
        1. Validate input locally
        2. Send POST /api/v1/task (with retry on network failure)
        3. Validate response structure
        4. Return structured result
        
        ERROR HANDLING:
        - Network errors: Retry ONCE, then fail
        - Validation errors: Do NOT retry
        - Invalid response: Do NOT retry
        
        Args:
            input_text: User's natural language command
            session_id: Optional session identifier
            
        Returns:
            TaskCreationResult with success status and task details
        """
        # Log outgoing request (sanitized - don't log full input)
        logger.info(
            "Sending command to backend",
            extra={
                "input_length": len(input_text) if input_text else 0,
                "has_session_id": session_id is not None
            }
        )
        
        # Step 1: Validate input locally (no retry on validation errors)
        try:
            validated_input = validate_user_input(input_text, self.config)
        except InputValidationError as e:
            logger.warning(
                "Input validation failed",
                extra={"error": str(e)}
            )
            return TaskCreationResult(
                success=False,
                error=f"Invalid input: {e}"
            )
        
        # Step 2: Check connection
        if not self._client or self._state != ConnectionState.CONNECTED:
            logger.warning("Not connected to backend")
            return TaskCreationResult(
                success=False,
                error="Not connected to backend"
            )
        
        # Step 3: Send request
        try:
            endpoint = f"{self.config.api_prefix}/task"
            
            payload = {
                "input_text": validated_input
            }
            if session_id:
                payload["session_id"] = session_id
            
            logger.debug(
                "Sending POST request",
                extra={"endpoint": endpoint}
            )
            
            response = self._client.post(endpoint, json=payload)
            
            logger.info(
                "Received response",
                extra={
                    "status_code": response.status_code,
                    "content_length": len(response.content)
                }
            )
            
            # Handle HTTP errors
            if response.status_code == 400:
                return TaskCreationResult(
                    success=False,
                    error="Bad request - input rejected by backend"
                )
            
            if response.status_code != 201:
                return TaskCreationResult(
                    success=False,
                    error=f"Unexpected status code: {response.status_code}"
                )
            
            # Step 4: Parse and validate response
            try:
                data = response.json()
            except Exception as e:
                logger.error(
                    "Failed to parse JSON response",
                    extra={"error": str(e)}
                )
                return TaskCreationResult(
                    success=False,
                    error="Invalid JSON response from backend"
                )
            
            # Validate response structure
            validation_error = validate_task_response(data)
            if validation_error:
                logger.error(
                    "Invalid response structure",
                    extra={"error": validation_error}
                )
                return TaskCreationResult(
                    success=False,
                    error=f"Invalid response: {validation_error}"
                )
            
            # Step 5: Return structured result
            result = TaskCreationResult(
                success=True,
                task_id=data["task_id"],
                status=data["status"],
                message=data["message"],
                intent_summary=data.get("intent_summary"),
                step_count=data.get("step_count"),
                raw_response=data
            )
            
            logger.info(
                "Task created successfully",
                extra={
                    "task_id": result.task_id,
                    "status": result.status,
                    "step_count": result.step_count
                }
            )
            
            # Clear retry state on success
            self._retry_manager.clear_state("send_command")
            
            return result
            
        except httpx.ConnectError as e:
            # Network error - eligible for retry
            return self._handle_network_error(
                error=e,
                error_type="connection",
                operation="send_command",
                retry_func=lambda: self.send_command(input_text, session_id),
            )
        
        except httpx.TimeoutException as e:
            # Timeout error - eligible for retry
            return self._handle_network_error(
                error=e,
                error_type="timeout", 
                operation="send_command",
                retry_func=lambda: self.send_command(input_text, session_id),
            )
        
        except Exception as e:
            # Unexpected error - do NOT retry
            logger.error(
                "Unexpected error during request",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            return TaskCreationResult(
                success=False,
                error=f"Unexpected error: {type(e).__name__}"
            )
    
    def _handle_network_error(
        self,
        error: Exception,
        error_type: str,
        operation: str,
        retry_func,
    ) -> TaskCreationResult:
        """
        Handle network errors with retry logic.
        
        RETRY POLICY:
        - Maximum ONE retry
        - Wait RETRY_DELAY_SECONDS between attempts
        - If retry fails, stop and return error
        
        Args:
            error: The caught exception
            error_type: "connection" or "timeout"
            operation: Name of the operation for logging
            retry_func: Function to call for retry
            
        Returns:
            TaskCreationResult with success or error
        """
        retry_state = self._retry_manager.get_state(operation)
        
        if retry_state.can_retry:
            # Log retry attempt
            retry_state.record_attempt(str(error))
            self._error_logger.log_retry(
                operation=operation,
                attempt=retry_state.attempts,
                max_attempts=retry_state.max_attempts + 1,
                reason=f"{error_type} error: {error}",
            )
            
            logger.warning(
                f"Network {error_type}, retrying once",
                extra={
                    "error": str(error),
                    "retry_delay": self.RETRY_DELAY_SECONDS,
                    "attempt": retry_state.attempts,
                }
            )
            
            # Wait before retry
            time.sleep(self.RETRY_DELAY_SECONDS)
            
            # Attempt reconnection if needed
            if error_type == "connection":
                self._state = ConnectionState.ERROR
                if not self.connect():
                    user_error = create_network_unreachable_error(
                        backend_url=self.config.base_url,
                        retry_attempted=True,
                    )
                    self._error_logger.log_error(user_error)
                    return TaskCreationResult(
                        success=False,
                        error=user_error.message,
                    )
            
            # Retry the operation
            return retry_func()
        
        else:
            # All retries exhausted
            if error_type == "connection":
                self._state = ConnectionState.ERROR
                user_error = create_network_unreachable_error(
                    backend_url=self.config.base_url,
                    retry_attempted=True,
                )
            else:
                user_error = create_network_timeout_error(
                    timeout_seconds=self.config.timeout_seconds,
                    retry_attempted=True,
                )
            
            self._error_logger.log_final_failure(
                operation=operation,
                attempts=retry_state.attempts + 1,
                error=user_error,
            )
            
            logger.error(
                f"Network {error_type} - all retries exhausted",
                extra={
                    "error": str(error),
                    "attempts": retry_state.attempts + 1,
                }
            )
            
            return TaskCreationResult(
                success=False,
                error=user_error.message,
            )
    
    # -------------------------------------------------------------------------
    # GET ACTIONS
    # -------------------------------------------------------------------------
    
    def get_actions(self, task_id: str) -> ActionsResult:
        """
        Fetch executable actions for a task.
        
        FLOW:
        1. Validate task_id
        2. Send GET /api/v1/task/{task_id}/actions
        3. Validate response structure
        4. Return structured result
        
        NOTE: This does NOT execute the actions.
        
        Args:
            task_id: The task identifier from send_command()
            
        Returns:
            ActionsResult with action details
        """
        logger.info(
            "Fetching actions from backend",
            extra={"task_id": task_id}
        )
        
        # Validate task_id format
        if not task_id or not task_id.startswith("task_"):
            return ActionsResult(
                success=False,
                error="Invalid task_id format"
            )
        
        # Check connection
        if not self._client or self._state != ConnectionState.CONNECTED:
            logger.warning("Not connected to backend")
            return ActionsResult(
                success=False,
                error="Not connected to backend"
            )
        
        try:
            endpoint = f"{self.config.api_prefix}/task/{task_id}/actions"
            
            response = self._client.get(endpoint)
            
            logger.info(
                "Received actions response",
                extra={
                    "task_id": task_id,
                    "status_code": response.status_code
                }
            )
            
            # Handle HTTP errors
            if response.status_code == 404:
                return ActionsResult(
                    success=False,
                    task_id=task_id,
                    error="Task not found"
                )
            
            if response.status_code == 409:
                return ActionsResult(
                    success=False,
                    task_id=task_id,
                    error="Actions not ready yet"
                )
            
            if response.status_code != 200:
                return ActionsResult(
                    success=False,
                    task_id=task_id,
                    error=f"Unexpected status code: {response.status_code}"
                )
            
            # Parse response
            try:
                data = response.json()
            except Exception as e:
                logger.error(
                    "Failed to parse actions JSON",
                    extra={"error": str(e)}
                )
                return ActionsResult(
                    success=False,
                    task_id=task_id,
                    error="Invalid JSON response"
                )
            
            # Validate response structure
            validation_error = validate_actions_response(data)
            if validation_error:
                logger.error(
                    "Invalid actions response structure",
                    extra={"error": validation_error}
                )
                return ActionsResult(
                    success=False,
                    task_id=task_id,
                    error=f"Invalid response: {validation_error}"
                )
            
            # Parse actions
            actions = []
            for action_data in data["actions"]:
                action = ActionData(
                    action_id=action_data["action_id"],
                    action_type=action_data["action_type"],
                    parameters=action_data.get("parameters", {}),
                    description=action_data.get("description"),
                    risk_level=action_data.get("risk_level", "LOW"),
                    signature=action_data.get("signature"),
                    timestamp=action_data.get("timestamp"),
                )
                actions.append(action)
            
            result = ActionsResult(
                success=True,
                task_id=task_id,
                actions=actions,
                total_actions=data.get("total_actions", len(actions)),
                raw_response=data
            )
            
            logger.info(
                "Actions fetched successfully",
                extra={
                    "task_id": task_id,
                    "action_count": len(actions),
                    "action_types": [a.action_type for a in actions]
                }
            )
            
            return result
            
        except httpx.ConnectError as e:
            self._state = ConnectionState.ERROR
            logger.error(
                "Connection lost fetching actions",
                extra={"error": str(e)}
            )
            return ActionsResult(
                success=False,
                task_id=task_id,
                error="Connection lost"
            )
        
        except httpx.TimeoutException as e:
            logger.error(
                "Actions request timed out",
                extra={"error": str(e)}
            )
            return ActionsResult(
                success=False,
                task_id=task_id,
                error="Request timed out"
            )
        
        except Exception as e:
            logger.error(
                "Unexpected error fetching actions",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            return ActionsResult(
                success=False,
                task_id=task_id,
                error=f"Unexpected error: {type(e).__name__}"
            )
    
    # -------------------------------------------------------------------------
    # STATUS CHECK
    # -------------------------------------------------------------------------
    
    def get_status(self, task_id: str) -> Optional[dict]:
        """
        Get status of a task.
        
        Args:
            task_id: The task identifier
            
        Returns:
            Status dict or None on error
        """
        logger.info(
            "Checking task status",
            extra={"task_id": task_id}
        )
        
        if not self._client or self._state != ConnectionState.CONNECTED:
            logger.warning("Not connected to backend")
            return None
        
        try:
            endpoint = f"{self.config.api_prefix}/status/{task_id}"
            response = self._client.get(endpoint)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "Status retrieved",
                    extra={
                        "task_id": task_id,
                        "status": data.get("status")
                    }
                )
                return data
            
            logger.warning(
                "Status request failed",
                extra={"status_code": response.status_code}
            )
            return None
            
        except Exception as e:
            logger.error(
                "Error getting status",
                extra={"error": str(e)}
            )
            return None


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_backend_client(
    base_url: str = "http://localhost:8000",
    timeout: float = 30.0
) -> BackendClient:
    """
    Factory function to create a configured backend client.
    
    Args:
        base_url: Backend URL (default: localhost:8000)
        timeout: Request timeout in seconds
        
    Returns:
        Configured BackendClient instance
    """
    config = BackendConfig(
        base_url=base_url,
        timeout_seconds=timeout
    )
    return BackendClient(config)
