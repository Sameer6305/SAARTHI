"""
Main Executor Application
=========================

The main SAARTHI local execution client.

This is the entry point that ties everything together:
- State machine
- Tray application  
- Permission manager
- Action validators
- Action handlers
- Cloud communication
- VOICE INPUT (PRIMARY interaction method)

VOICE INPUT:
- Push-to-talk ONLY (no background listening)
- Voice treated as UNTRUSTED input (same as text)
- Same permission flow, same allowlist, same logging
- Local Whisper STT (no cloud)
- Audio exists only in memory
"""

import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from saarthi_executor.state_machine import StateMachine, ExecutorState
from saarthi_executor.validator import ActionValidator, ValidationResult
from saarthi_executor.permission_manager import PermissionManager, PermissionDecision as LegacyPermissionDecision
from saarthi_executor.permission_enforcer import (
    PermissionEnforcer,
    PermissionDecision,
    create_permission_enforcer,
    ACTION_ALLOWLIST,
)
from saarthi_executor.action_handlers import ActionHandlerRegistry, ActionResult
from saarthi_executor.cloud_client import CloudClient, MockCloudClient, CloudConfig
from saarthi_executor.backend_client import (
    BackendClient,
    BackendConfig,
    create_backend_client,
    TaskCreationResult,
    ActionsResult,
    ConnectionState,
)
from saarthi_executor.tray_app import (
    TrayIcon,
    DialogRequest,
    CommandDialogRequest,
    VoiceDialogRequest,
    VoiceSettingsRequest,
    ExitRequest,
)
from saarthi_executor.command_dialog import (
    CommandDialog,
    DialogResult,
    CommandResult,
    show_command_dialog,
)
from saarthi_executor.voice_command_dialog import (
    VoiceCommandDialog,
    VoiceDialogResult,
    VoiceCommandResult,
    show_voice_command_dialog,
)
from saarthi_executor.voice.integration import VoiceIntegration
from saarthi_executor.voice.config import VoiceConfig
from saarthi_executor.logging_config import setup_logging, security_logger

# NEW: Integrated assistant with conversational loop, student tools, TTS
from saarthi_executor.integrated_assistant import IntegratedAssistant, create_assistant

logger = logging.getLogger(__name__)


class SaarthiExecutor:
    """
    Main SAARTHI local executor application.
    
    SECURITY INVARIANTS:
    - All actions require user permission
    - Only allowlisted actions can execute
    - All events are logged
    - Fail-closed on any error
    - Voice input treated IDENTICALLY to text (no special trust)
    
    ARCHITECTURE:
    - Uses BackendClient for real HTTP communication
    - Commands sent via send_command() method
    - Voice input is PRIMARY interaction method
    - Actions received but NOT executed in this integration phase
    """
    
    # Polling interval when listening (seconds)
    POLL_INTERVAL: float = 2.0
    
    # Backend configuration
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_TIMEOUT: float = 30.0
    
    def __init__(
        self, 
        use_mock_cloud: bool = False, 
        use_real_backend: bool = True,
        enable_voice: bool = True,
    ):
        """
        Initialize the executor.
        
        Args:
            use_mock_cloud: If True, use MockCloudClient (legacy)
            use_real_backend: If True, use real BackendClient for HTTP calls
            enable_voice: If True, enable voice input features
        """
        # Core components
        self._state_machine = StateMachine()
        self._validator = ActionValidator()
        self._permission_manager = PermissionManager()  # Legacy
        self._permission_enforcer = create_permission_enforcer()  # NEW: Strong enforcement
        self._action_registry = ActionHandlerRegistry()
        
        # Backend client (real HTTP integration)
        self._use_real_backend = use_real_backend
        self._backend_client: Optional[BackendClient] = None
        
        if use_real_backend:
            self._backend_client = create_backend_client(
                base_url=self.BACKEND_URL,
                timeout=self.BACKEND_TIMEOUT
            )
            logger.info(
                "BackendClient created",
                extra={"url": self.BACKEND_URL}
            )
        
        # Legacy cloud client (for backward compatibility)
        if use_mock_cloud:
            self._cloud_client = MockCloudClient()
        else:
            self._cloud_client = CloudClient(CloudConfig())
        
        # ═══════════════════════════════════════════════════════════════════
        # VOICE INTEGRATION (NEW)
        # Voice input is the PRIMARY interaction method
        # Voice is treated IDENTICALLY to text input - no special trust
        # ═══════════════════════════════════════════════════════════════════
        self._enable_voice = enable_voice
        self._voice_integration: Optional[VoiceIntegration] = None
        
        if enable_voice:
            self._voice_integration = VoiceIntegration(
                on_voice_input=self._handle_voice_text,
            )
            logger.info("Voice integration created")
        
        # ═══════════════════════════════════════════════════════════════════
        # INTEGRATED ASSISTANT (NEW)
        # Handles: Conversational loop, Student tools, TTS, Safe actions
        # ═══════════════════════════════════════════════════════════════════
        self._assistant: Optional[IntegratedAssistant] = None
        
        # Tray application
        self._tray: Optional[TrayIcon] = None
        
        # Control flags
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        
        # Current session
        self._session_id: Optional[str] = None
        
        logger.info("SAARTHI Executor initialized", extra={
            "use_real_backend": use_real_backend,
            "use_mock_cloud": use_mock_cloud,
            "enable_voice": enable_voice,
        })
    
    def start(self) -> None:
        """
        Start the executor application.
        
        THREADING MODEL:
        - Main thread: Runs dialog queue loop (handles Tkinter dialogs)
        - Background thread 1: Tray icon (via run_detached)
        - Background thread 2: Action listener loop
        
        This keeps main thread free for Tkinter which requires it.
        """
        logger.info("Starting SAARTHI Executor")
        
        self._running = True
        
        # Connect to real backend
        if self._backend_client:
            if self._backend_client.connect():
                logger.info(
                    "Connected to backend successfully",
                    extra={"url": self.BACKEND_URL}
                )
            else:
                logger.warning(
                    "Could not connect to backend - ensure it's running",
                    extra={"url": self.BACKEND_URL}
                )
        
        # Connect to cloud (legacy)
        if not self._cloud_client.connect():
            logger.warning("Could not connect to cloud (will work offline)")
        
        # Initialize voice integration
        if self._voice_integration:
            if self._voice_integration.initialize():
                logger.info("Voice integration initialized successfully")
                # Pre-load STT model in background
                self._voice_integration.preload_models()
            else:
                logger.warning("Voice integration failed to initialize")
        
        # ═══════════════════════════════════════════════════════════════════
        # INITIALIZE INTEGRATED ASSISTANT
        # Conversational loop, Student tools, TTS, Safe desktop actions
        # ═══════════════════════════════════════════════════════════════════
        try:
            self._assistant = create_assistant(
                enable_tts=True,  # Local TTS (Windows SAPI/Piper)
                llm_callback=self._local_llm_callback,  # Optional local LLM
            )
            logger.info("Integrated assistant initialized with TTS")
        except Exception as e:
            logger.warning(f"Assistant initialization failed (TTS may not work): {e}")
            # Try without TTS
            try:
                self._assistant = create_assistant(enable_tts=False)
                logger.info("Integrated assistant initialized without TTS")
            except Exception as e2:
                logger.error(f"Assistant initialization completely failed: {e2}")
        
        # Start listener thread
        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name="ActionListener",
        )
        self._listener_thread.start()
        
        # Create tray icon
        # Voice Command is now the PRIMARY entry point
        self._tray = TrayIcon(
            state_machine=self._state_machine,
            on_exit=self.stop,
            on_send_command=self._show_command_dialog,
            on_voice_command=self._show_voice_command_dialog,
            on_voice_settings=self._show_voice_settings,
            is_voice_enabled=self._is_voice_enabled,
        )
        
        # Register state change logging
        self._state_machine.register_state_change_callback(
            lambda old, new: security_logger.state_transition(
                old.name, new.name, "User or system"
            )
        )
        
        # Start tray icon in BACKGROUND thread (keeps main thread free)
        self._tray.start_detached()
        
        # Start in SLEEP state, user must activate
        logger.info("Executor started - in SLEEP state")
        logger.info("Voice Command is PRIMARY interaction method")
        
        # Main thread runs the dialog queue loop (for Tkinter)
        self._run_dialog_queue_loop()
    
    def _run_dialog_queue_loop(self) -> None:
        """
        Main thread loop that processes dialog requests from the queue.
        
        This runs on the MAIN THREAD so Tkinter dialogs work correctly.
        The tray icon runs in a background thread and puts requests in the queue.
        """
        import queue as queue_module
        
        logger.info("Dialog queue loop started on main thread")
        
        while self._running:
            try:
                # Wait for a dialog request (with timeout to check _running)
                request = self._tray.dialog_queue.get(timeout=0.5)
                
                # Process the request
                if isinstance(request, CommandDialogRequest):
                    logger.info("Processing command dialog request")
                    self._show_command_dialog()
                    
                elif isinstance(request, VoiceDialogRequest):
                    logger.info("Processing voice dialog request")
                    self._show_voice_command_dialog()
                    
                elif isinstance(request, VoiceSettingsRequest):
                    logger.info("Processing voice settings request")
                    self._show_voice_settings()
                    
                elif isinstance(request, ExitRequest):
                    logger.info("Processing exit request")
                    self.stop()
                    break
                    
            except queue_module.Empty:
                # Timeout, loop again to check _running
                continue
            except Exception as e:
                logger.error(f"Error processing dialog request: {e}")
        
        logger.info("Dialog queue loop stopped")
    
    def stop(self) -> None:
        """Stop the executor application."""
        logger.info("Stopping SAARTHI Executor")
        
        self._running = False
        
        # Clean up voice integration
        if self._voice_integration:
            self._voice_integration.cleanup()
            logger.info("Voice integration cleaned up")
        
        # Clean up integrated assistant
        if self._assistant:
            self._assistant.cleanup()
            logger.info("Integrated assistant cleaned up")
        
        # Disconnect from real backend
        if self._backend_client:
            self._backend_client.disconnect()
            logger.info("Backend client disconnected")
        
        # Disconnect from cloud (legacy)
        self._cloud_client.disconnect()
        
        # Stop listener thread
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5.0)
        
        logger.info("SAARTHI Executor stopped")
    
    def _listener_loop(self) -> None:
        """
        Background loop that listens for actions when in LISTENING state.
        """
        logger.info("Listener loop started")
        
        while self._running:
            # Only poll when LISTENING
            if self._state_machine.is_listening():
                try:
                    action_request = self._cloud_client.poll_for_actions()
                    
                    if action_request:
                        self._process_action(action_request.raw_json)
                
                except Exception as e:
                    logger.error(f"Error in listener loop: {e}")
            
            time.sleep(self.POLL_INTERVAL)
        
        logger.info("Listener loop stopped")
    
    def _process_action(self, action_json: dict) -> None:
        """
        Process an incoming action with STRONG PERMISSION ENFORCEMENT.
        
        Flow:
        1. ⚠️ HARD GATE: Check if action is in allowlist (BEFORE anything else)
        2. Validate action schema
        3. Get handler
        4. ⚠️ HARD GATE: Request explicit user permission via modal dialog
        5. Execute if and ONLY if permitted
        6. Report result
        
        SECURITY: 
        - Only 'open_browser_url' and 'play_media_file' can proceed
        - All other actions are REJECTED without showing dialog
        - User must explicitly click ALLOW for each action
        - No remembered permissions, no auto-approval
        - Audit log written for every decision
        """
        action_id = action_json.get("action_id", "unknown")
        action_type = action_json.get("action_type", "unknown")
        parameters = action_json.get("parameters", {})
        description = action_json.get("description", "No description")
        
        logger.info(
            f"Processing action",
            extra={"action_id": action_id, "action_type": action_type}
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 0: HARD GATE - ACTION ALLOWLIST CHECK (BEFORE ANYTHING ELSE)
        # ═══════════════════════════════════════════════════════════════════
        if not self._permission_enforcer.is_action_allowed(action_type):
            # This action is NOT in the allowlist - REJECT WITHOUT DIALOG
            rejection_reason = f"Action '{action_type}' is not in the allowed actions list"
            
            # Log policy violation (method generates its own reason based on action type)
            self._permission_enforcer.reject_policy_violation(
                action_id=action_id,
                action_type=action_type,
            )
            
            security_logger.forbidden_action_attempted(
                action_type,
                rejection_reason,
            )
            
            # Report rejection to cloud
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=f"POLICY VIOLATION: {rejection_reason}",
            )
            
            # Notify user
            if self._tray:
                self._tray.show_notification(
                    "⛔ Action Blocked",
                    f"'{action_type}' is not permitted by security policy",
                )
            
            logger.warning(
                f"POLICY VIOLATION: Action blocked by allowlist",
                extra={
                    "action_id": action_id,
                    "action_type": action_type,
                    "allowed_actions": list(ACTION_ALLOWLIST),
                }
            )
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Validate action schema
        # ═══════════════════════════════════════════════════════════════════
        validation = self._validator.validate(action_json)
        
        if not validation.is_valid:
            security_logger.action_rejected(
                action_id,
                validation.rejection_reason or "Unknown",
                validation.rejection_rule or "UNKNOWN",
            )
            
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=f"Validation failed: {validation.rejection_reason}",
            )
            
            if self._tray:
                self._tray.show_notification(
                    "Action Rejected",
                    validation.rejection_reason or "Validation failed",
                )
            return
        
        security_logger.action_validated(action_id, action_type)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Get handler
        # ═══════════════════════════════════════════════════════════════════
        handler = self._action_registry.get_handler(action_type)
        
        if not handler:
            security_logger.forbidden_action_attempted(
                action_type,
                "No handler registered",
            )
            
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=f"Unknown action type: {action_type}",
            )
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: HARD GATE - REQUEST EXPLICIT USER PERMISSION
        # ═══════════════════════════════════════════════════════════════════
        # This shows a MODAL dialog that BLOCKS until user responds
        # User MUST click ALLOW or DENY - no auto-approval, no timeout-allow
        
        data_description = handler.get_data_description(parameters)
        risk_level = action_json.get("risk_level", "LOW")
        
        # Build target description for the dialog
        target_info = self._build_target_description(action_type, parameters)
        
        permission_decision = self._permission_enforcer.request_permission(
            action_id=action_id,
            action_type=action_type,
            description=description,
            target=target_info,
            risk_level=risk_level,
            parameters=parameters,
        )
        
        # Handle permission decision - ONLY ALLOW passes through
        if permission_decision != PermissionDecision.ALLOW:
            # Log the denial
            security_logger.permission_denied(action_id, action_type)
            
            # Build user-friendly message based on decision
            denial_messages = {
                PermissionDecision.DENY: "User explicitly denied permission",
                PermissionDecision.TIMEOUT: "Permission request timed out (60 seconds)",
                PermissionDecision.WINDOW_CLOSED: "Permission dialog was closed",
                PermissionDecision.ERROR: "Error showing permission dialog",
                PermissionDecision.REJECTED: "Action rejected by policy",
            }
            denial_reason = denial_messages.get(
                permission_decision, 
                f"Permission denied: {permission_decision.value}"
            )
            
            # Report to cloud
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=denial_reason,
            )
            
            # Notify user
            if self._tray:
                self._tray.show_notification(
                    "❌ Action Denied",
                    f"{action_type}: {denial_reason}",
                )
            
            logger.info(
                f"Permission denied for action",
                extra={
                    "action_id": action_id,
                    "action_type": action_type,
                    "decision": permission_decision.value,
                }
            )
            return
        
        # ✅ Permission GRANTED - log it
        security_logger.permission_granted(action_id, action_type)
        logger.info(
            f"✅ Permission GRANTED for action",
            extra={"action_id": action_id, "action_type": action_type}
        )
        
        # Step 4: Execute action
        # Transition to ACTIVE state
        if not self._state_machine.begin_execution(action_id):
            logger.error("Failed to transition to ACTIVE state")
            return
        
        try:
            result = handler.execute(action_id, parameters)
            
            security_logger.action_executed(
                action_id, 
                action_type, 
                result.success
            )
            
            # Report result to cloud
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=result.success,
                message=result.message,
                data=result.data,
            )
            
            # Show notification
            if self._tray:
                if result.success:
                    self._tray.show_notification(
                        "Action Completed",
                        result.message,
                    )
                else:
                    self._tray.show_notification(
                        "Action Failed",
                        result.error or result.message,
                    )
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            
            security_logger.action_executed(action_id, action_type, False)
            
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=f"Execution error: {str(e)}",
            )
        
        finally:
            # Always transition back to LISTENING
            self._state_machine.finish_execution(True)
    
    def _build_target_description(self, action_type: str, parameters: dict) -> str:
        """
        Build a user-friendly target description for the permission dialog.
        
        This extracts the key target info (URL, file path, etc.) from 
        action parameters to show the user exactly WHAT will be executed.
        
        Args:
            action_type: The action type being requested
            parameters: Action parameters dict
            
        Returns:
            Human-readable target description
        """
        if action_type == "open_browser_url":
            url = parameters.get("url", "unknown URL")
            return f"URL: {url}"
        
        elif action_type == "play_media_file":
            file_path = parameters.get("file_path", "unknown file")
            return f"File: {file_path}"
        
        else:
            # Fallback for any other action types
            # Show first parameter value or "No target specified"
            if parameters:
                first_key = list(parameters.keys())[0]
                first_value = parameters[first_key]
                return f"{first_key}: {first_value}"
            return "No target specified"
    
    def inject_test_action(self, action: dict) -> None:
        """
        Inject a test action for testing purposes.
        
        Only works with MockCloudClient.
        """
        if isinstance(self._cloud_client, MockCloudClient):
            self._cloud_client.add_test_action(action)
            logger.info("Test action injected")
    
    # =========================================================================
    # COMMAND DIALOG INTEGRATION
    # =========================================================================
    
    def _show_command_dialog(self) -> None:
        """
        Show the command input dialog.
        
        Called when user clicks "Send Command" in tray menu.
        Now runs on MAIN THREAD so Tkinter works correctly.
        """
        logger.info("Opening command dialog")
        
        try:
            # Now running on main thread, Tkinter works directly
            result = show_command_dialog(
                on_send=self._handle_dialog_send
            )
            
            if result:
                logger.info(
                    "Command dialog closed",
                    extra={
                        "result": result.result.value,
                        "task_id": result.task_id
                    }
                )
            
        except Exception as e:
            logger.error(f"Error showing command dialog: {e}")
            if self._tray:
                self._tray.show_notification(
                    "Dialog Error",
                    f"Failed to open command dialog: {e}"
                )
    
    def _handle_dialog_send(self, input_text: str) -> DialogResult:
        """
        Handle command from dialog - send to backend.
        
        This is the callback passed to the command dialog.
        Now uses INTEGRATED ASSISTANT first, then falls back to backend.
        
        Args:
            input_text: Validated user input from dialog
            
        Returns:
            DialogResult with task outcome
        """
        logger.info(
            "Handling dialog send",
            extra={"input_length": len(input_text)}
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # TRY INTEGRATED ASSISTANT FIRST (Fast, local)
        # ═══════════════════════════════════════════════════════════════════
        if self._assistant:
            try:
                response = self._assistant.process(input_text)
                
                # If assistant handled it (action executed or conversation)
                if response.action_executed or not response.needs_clarification:
                    logger.info(
                        "Assistant handled command locally",
                        extra={"action": response.action_type}
                    )
                    
                    # Show notification
                    if self._tray and response.text:
                        self._tray.show_notification(
                            "SAARTHI" if not response.action_executed else "✓ Done",
                            response.text[:100],
                        )
                    
                    return DialogResult(
                        result=CommandResult.SUCCESS,
                        task_id=f"local_{int(time.time())}",
                        status="completed",
                        message=response.text,
                    )
                    
            except Exception as e:
                logger.warning(f"Assistant failed, falling back to backend: {e}")
        
        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK TO BACKEND
        # ═══════════════════════════════════════════════════════════════════
        
        # Check backend connection
        if not self._backend_client:
            return DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error="Backend client not configured"
            )
        
        if not self._backend_client.is_connected:
            logger.info("Backend not connected, attempting to connect")
            if not self._backend_client.connect():
                return DialogResult(
                    result=CommandResult.BACKEND_ERROR,
                    error="Cannot connect to backend. Is it running at localhost:8000?"
                )
        
        # Send command to backend
        try:
            task_result = self._backend_client.send_command(
                input_text=input_text,
                session_id=self._session_id
            )
            
            if task_result.success:
                # Build success message
                message_parts = []
                if task_result.intent_summary:
                    message_parts.append(f"Intent: {task_result.intent_summary}")
                if task_result.step_count:
                    message_parts.append(f"Steps: {task_result.step_count}")
                
                return DialogResult(
                    result=CommandResult.SUCCESS,
                    task_id=task_result.task_id,
                    status=task_result.status,
                    message="\n".join(message_parts) if message_parts else None
                )
            else:
                return DialogResult(
                    result=CommandResult.BACKEND_ERROR,
                    error=task_result.error or "Backend rejected the command"
                )
                
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return DialogResult(
                result=CommandResult.BACKEND_ERROR,
                error=f"Error: {str(e)}"
            )

    # =========================================================================
    # VOICE COMMAND INTEGRATION (PRIMARY INPUT METHOD)
    # =========================================================================
    
    def _is_voice_enabled(self) -> bool:
        """Check if voice features are enabled."""
        return self._voice_integration is not None and self._voice_integration.is_enabled
    
    def _show_voice_command_dialog(self) -> None:
        """
        Show the voice command dialog (PRIMARY interaction method).
        
        Called when user clicks "Voice Command" in tray menu.
        Now runs on MAIN THREAD so Tkinter works correctly.
        
        SECURITY:
        - Voice input is treated IDENTICALLY to text input
        - Same permission flow, same allowlist, same logging
        - No special trust for voice input
        """
        logger.info("Opening voice command dialog (PRIMARY)")
        
        if not self._voice_integration:
            logger.error("Voice integration not available")
            if self._tray:
                self._tray.show_notification(
                    "Voice Not Available",
                    "Voice features are not enabled"
                )
            return
        
        # Initialize if needed
        if not self._voice_integration.is_enabled:
            logger.info("Enabling voice features")
            if not self._voice_integration.enable_voice():
                logger.error("Failed to enable voice features")
                if self._tray:
                    self._tray.show_notification(
                        "Voice Error",
                        "Failed to enable voice features"
                    )
                return
        
        try:
            # Now running on main thread, Tkinter works directly
            result = show_voice_command_dialog(
                on_start_recording=self._voice_start_recording,
                on_stop_recording=self._voice_stop_recording,
                on_send_text=self._voice_send_text,
                on_cancel_recording=self._voice_cancel_recording,
            )
            
            if result:
                logger.info(
                    "Voice command dialog closed",
                    extra={
                        "result": result.result.value,
                        "task_id": result.task_id,
                        "transcribed_text": result.transcribed_text[:50] if result.transcribed_text else None,
                    }
                )
                
        except Exception as e:
            logger.error(f"Error showing voice command dialog: {e}")
            if self._tray:
                self._tray.show_notification(
                    "Voice Dialog Error",
                    f"Failed to open voice dialog: {e}"
                )
                
        except Exception as e:
            logger.error(f"Error showing voice command dialog: {e}")
            if self._tray:
                self._tray.show_notification(
                    "Voice Dialog Error",
                    f"Failed to open voice dialog: {e}"
                )
    
    def _voice_start_recording(self) -> bool:
        """
        Start push-to-talk recording.
        
        Called when user PRESSES the talk button.
        """
        logger.info("Voice: Starting push-to-talk recording")
        
        if not self._voice_integration:
            return False
        
        success = self._voice_integration.start_push_to_talk()
        
        if success:
            # Only update tray icon if recording actually started
            if self._tray:
                self._tray.set_recording_state(True)
            
            # Log for audit
            security_logger.voice_recording_started(source="push_to_talk")
        else:
            # Make sure tray shows NOT recording on failure
            if self._tray:
                self._tray.set_recording_state(False)
        
        return success
    
    def _voice_stop_recording(self) -> Optional[tuple[str, float]]:
        """
        Stop push-to-talk recording and get transcription.
        
        Called when user RELEASES the talk button.
        
        Returns:
            (transcribed_text, confidence) or None on failure
        """
        logger.info("Voice: Stopping push-to-talk recording")
        
        # Update tray icon
        if self._tray:
            self._tray.set_recording_state(False)
        
        if not self._voice_integration:
            return None
        
        # Stop recording and get transcription
        # This is where audio is processed and immediately discarded
        text = self._voice_integration.stop_push_to_talk()
        
        if text:
            # Get confidence from voice integration (simplified)
            # In full implementation, this would come from the STT result
            confidence = 0.85  # Placeholder - will be from actual STT
            
            logger.info(
                "Voice: Transcription complete",
                extra={
                    "text_length": len(text),
                    "confidence": confidence,
                }
            )
            
            text_preview = text[:30] + "..." if len(text) > 30 else text
            security_logger.voice_transcription_complete(text_preview=text_preview)
            
            return (text, confidence)
        
        return None
    
    def _voice_cancel_recording(self) -> None:
        """Cancel push-to-talk recording."""
        logger.info("Voice: Recording cancelled")
        
        # Update tray icon
        if self._tray:
            self._tray.set_recording_state(False)
        
        if self._voice_integration:
            self._voice_integration.cancel_push_to_talk()
    
    def _voice_send_text(self, text: str) -> Optional[str]:
        """
        Send transcribed voice text to backend.
        
        This is called with the final text (after optional editing).
        Voice text goes through EXACTLY the same flow as typed text.
        
        SECURITY:
        - Voice input treated as UNTRUSTED
        - Same backend flow as text input
        - Same permission enforcement
        
        Args:
            text: Transcribed (and possibly edited) text
            
        Returns:
            task_id if successful, None on failure
        """
        logger.info(
            "Voice: Sending command to backend",
            extra={"text_length": len(text), "source": "voice"}
        )
        
        # Log for audit - voice input is treated as untrusted
        text_preview = text[:50] + "..." if len(text) > 50 else text
        security_logger.voice_command_submitted(
            source="voice_push_to_talk",
            text_preview=text_preview,
        )
        
        # Send through SAME pipeline as text input
        # No special trust, no bypass
        result = self._handle_dialog_send(text)
        
        if result.result == CommandResult.SUCCESS:
            return result.task_id
        else:
            logger.warning(
                "Voice command failed",
                extra={"error": result.error}
            )
            return None
    
    def _handle_voice_text(self, text: str) -> None:
        """
        Handle voice input text from integration callback.
        
        This is an alternative entry point for voice text.
        Now uses the INTEGRATED ASSISTANT for conversational responses.
        
        Args:
            text: Transcribed text from voice input
        """
        logger.info(
            "Voice integration callback: text received",
            extra={"text_length": len(text)}
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # USE INTEGRATED ASSISTANT (NEW)
        # Handles: Pattern matching, Student tools, TTS responses
        # ═══════════════════════════════════════════════════════════════════
        if self._assistant:
            try:
                response = self._assistant.process(text)
                
                logger.info(
                    "Assistant response",
                    extra={
                        "text": response.text[:50] if response.text else "",
                        "action_executed": response.action_executed,
                        "needs_clarification": response.needs_clarification,
                    }
                )
                
                # Show notification with response
                if self._tray and response.text:
                    self._tray.show_notification(
                        "SAARTHI" if not response.action_executed else "✓ Done",
                        response.text[:100],
                    )
                
                # TTS is handled inside assistant.process()
                return
                
            except Exception as e:
                logger.error(f"Assistant processing failed: {e}")
                # Fall through to backend
        
        # Fallback: Send through backend pipeline
        result = self.send_command(text)
        
        if result and result.success:
            logger.info(
                "Voice command processed successfully",
                extra={"task_id": result.task_id}
            )
        else:
            logger.warning("Voice command processing failed")
    
    def _show_voice_settings(self) -> None:
        """Show voice settings dialog."""
        logger.info("Opening voice settings dialog")
        
        if self._voice_integration:
            self._voice_integration.show_settings()
        else:
            if self._tray:
                self._tray.show_notification(
                    "Voice Not Available",
                    "Voice features are not enabled"
                )

    # =========================================================================
    # LOCAL LLM INTEGRATION (NEW - FREE, LOCAL)
    # =========================================================================
    
    def _local_llm_callback(self, prompt: str) -> str:
        """
        Call local LLM (Ollama) for complex understanding.
        
        FREE-ONLY STACK:
        - Uses Ollama running locally
        - Recommended models: phi3, mistral, llama2
        - No cloud, no API keys, no cost
        
        FALLBACK:
        - If Ollama not running, returns helpful message
        
        Args:
            prompt: The prompt to send to LLM
            
        Returns:
            LLM response or fallback message
        """
        import requests
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "phi3",  # Fast, small model
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 256,  # Limit response length
                        "temperature": 0.3,  # More deterministic
                    },
                },
                timeout=10.0,
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                logger.warning(f"Ollama returned status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.debug("Ollama not running (this is optional)")
        except Exception as e:
            logger.warning(f"Local LLM call failed: {e}")
        
        # Fallback - no LLM available
        return ""

    # =========================================================================
    # BACKEND INTEGRATION (NEW)
    # =========================================================================
    
    def send_command(self, input_text: str) -> Optional[TaskCreationResult]:
        """
        Send a user command to the backend for planning.
        
        This is the PRIMARY integration point for the local client.
        
        FLOW:
        1. Validate that we're connected to backend
        2. Send command via HTTP
        3. Receive task creation result
        4. Log the result
        5. Return structured result (NO execution)
        
        Args:
            input_text: User's natural language command
            
        Returns:
            TaskCreationResult with task_id and status, or None on failure
        """
        if not self._backend_client:
            logger.error("No backend client configured")
            return None
        
        if not self._backend_client.is_connected:
            logger.warning("Backend not connected, attempting reconnection")
            if not self._backend_client.connect():
                logger.error("Failed to reconnect to backend")
                if self._tray:
                    self._tray.show_notification(
                        "Connection Error",
                        "Cannot connect to backend"
                    )
                return None
        
        # Log outgoing request (sanitized)
        logger.info(
            "Sending command to backend",
            extra={
                "input_length": len(input_text),
                "session_id": self._session_id
            }
        )
        
        # Send command
        result = self._backend_client.send_command(
            input_text=input_text,
            session_id=self._session_id
        )
        
        if result.success:
            logger.info(
                "Command sent successfully",
                extra={
                    "task_id": result.task_id,
                    "status": result.status,
                    "step_count": result.step_count,
                    "intent_summary": result.intent_summary
                }
            )
            
            if self._tray:
                self._tray.show_notification(
                    "Task Created",
                    f"Task: {result.task_id}\nStatus: {result.status}"
                )
        else:
            logger.warning(
                "Command failed",
                extra={"error": result.error}
            )
            
            if self._tray:
                self._tray.show_notification(
                    "Command Failed",
                    result.error or "Unknown error"
                )
        
        return result
    
    def fetch_actions(self, task_id: str) -> Optional[ActionsResult]:
        """
        Fetch executable actions for a task from the backend.
        
        This retrieves the planner output in executor-compatible format.
        
        NOTE: This does NOT execute the actions.
        
        Args:
            task_id: Task ID from send_command()
            
        Returns:
            ActionsResult with action list, or None on failure
        """
        if not self._backend_client:
            logger.error("No backend client configured")
            return None
        
        if not self._backend_client.is_connected:
            logger.warning("Backend not connected")
            return None
        
        logger.info(
            "Fetching actions for task",
            extra={"task_id": task_id}
        )
        
        result = self._backend_client.get_actions(task_id)
        
        if result.success:
            logger.info(
                "Actions fetched successfully",
                extra={
                    "task_id": task_id,
                    "action_count": result.total_actions,
                    "action_types": [a.action_type for a in result.actions]
                }
            )
            
            # Log each action (for debugging/tracing)
            for action in result.actions:
                logger.info(
                    "Action received",
                    extra={
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "description": action.description,
                        "risk_level": action.risk_level,
                        "has_parameters": bool(action.parameters)
                    }
                )
        else:
            logger.warning(
                "Failed to fetch actions",
                extra={"task_id": task_id, "error": result.error}
            )
        
        return result
    
    def process_command(self, input_text: str) -> dict:
        """
        Full command processing flow: send command and fetch actions.
        
        This is a convenience method that combines send_command and fetch_actions.
        
        FLOW:
        1. Send command to backend
        2. If successful, fetch actions
        3. Return full result with actions
        
        NOTE: No actions are executed.
        
        Args:
            input_text: User's natural language command
            
        Returns:
            Dict with task_id, status, actions, and any errors
        """
        result = {
            "success": False,
            "task_id": None,
            "status": None,
            "actions": [],
            "error": None
        }
        
        # Step 1: Send command
        task_result = self.send_command(input_text)
        
        if not task_result or not task_result.success:
            result["error"] = task_result.error if task_result else "Failed to send command"
            return result
        
        result["task_id"] = task_result.task_id
        result["status"] = task_result.status
        
        # Step 2: Fetch actions
        actions_result = self.fetch_actions(task_result.task_id)
        
        if not actions_result or not actions_result.success:
            result["error"] = actions_result.error if actions_result else "Failed to fetch actions"
            # Still return partial success - we have task_id
            result["success"] = True  # Task was created
            return result
        
        # Full success
        result["success"] = True
        result["actions"] = [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "parameters": a.parameters,
                "description": a.description,
                "risk_level": a.risk_level
            }
            for a in actions_result.actions
        ]
        
        logger.info(
            "Command processed successfully",
            extra={
                "task_id": result["task_id"],
                "action_count": len(result["actions"])
            }
        )
        
        return result
    
    @property
    def backend_connected(self) -> bool:
        """Check if backend is connected."""
        return self._backend_client and self._backend_client.is_connected


def main():
    """Main entry point."""
    # Setup logging
    log_file = Path.home() / ".saarthi" / "executor.log"
    setup_logging(log_level="INFO", log_file=log_file)
    
    logger.info("=" * 60)
    logger.info("SAARTHI Local Executor Starting")
    logger.info("Voice Command is PRIMARY interaction method")
    logger.info("=" * 60)
    
    # Create executor with REAL backend integration and VOICE enabled
    # use_mock_cloud=False disables legacy mock
    # use_real_backend=True enables HTTP client to localhost:8000
    # enable_voice=True enables push-to-talk voice input
    executor = SaarthiExecutor(
        use_mock_cloud=False, 
        use_real_backend=True,
        enable_voice=True,
    )
    
    try:
        executor.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        executor.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        executor.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
