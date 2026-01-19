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
from saarthi_executor.permission_manager import PermissionManager, PermissionDecision
from saarthi_executor.action_handlers import ActionHandlerRegistry, ActionResult
from saarthi_executor.cloud_client import CloudClient, MockCloudClient, CloudConfig
from saarthi_executor.tray_app import TrayIcon
from saarthi_executor.logging_config import setup_logging, security_logger

logger = logging.getLogger(__name__)


class SaarthiExecutor:
    """
    Main SAARTHI local executor application.
    
    SECURITY INVARIANTS:
    - All actions require user permission
    - Only allowlisted actions can execute
    - All events are logged
    - Fail-closed on any error
    """
    
    # Polling interval when listening (seconds)
    POLL_INTERVAL: float = 2.0
    
    def __init__(self, use_mock_cloud: bool = True):
        """Initialize the executor."""
        # Core components
        self._state_machine = StateMachine()
        self._validator = ActionValidator()
        self._permission_manager = PermissionManager()
        self._action_registry = ActionHandlerRegistry()
        
        # Cloud client
        if use_mock_cloud:
            self._cloud_client = MockCloudClient()
        else:
            self._cloud_client = CloudClient(CloudConfig())
        
        # Tray application
        self._tray: Optional[TrayIcon] = None
        
        # Control flags
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        
        logger.info("SAARTHI Executor initialized")
    
    def start(self) -> None:
        """Start the executor application."""
        logger.info("Starting SAARTHI Executor")
        
        self._running = True
        
        # Connect to cloud
        if not self._cloud_client.connect():
            logger.warning("Could not connect to cloud (will work offline)")
        
        # Start listener thread
        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name="ActionListener",
        )
        self._listener_thread.start()
        
        # Create and start tray icon (blocks)
        self._tray = TrayIcon(
            state_machine=self._state_machine,
            on_exit=self.stop,
        )
        
        # Register state change logging
        self._state_machine.register_state_change_callback(
            lambda old, new: security_logger.state_transition(
                old.name, new.name, "User or system"
            )
        )
        
        # Start in SLEEP state, user must activate
        logger.info("Executor started - in SLEEP state")
        
        # This blocks (tray icon main loop)
        self._tray.start()
    
    def stop(self) -> None:
        """Stop the executor application."""
        logger.info("Stopping SAARTHI Executor")
        
        self._running = False
        
        # Disconnect from cloud
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
        Process an incoming action.
        
        Flow:
        1. Validate action
        2. Get handler
        3. Request permission
        4. Execute if permitted
        5. Report result
        """
        action_id = action_json.get("action_id", "unknown")
        action_type = action_json.get("action_type", "unknown")
        
        logger.info(
            f"Processing action",
            extra={"action_id": action_id, "action_type": action_type}
        )
        
        # Step 1: Validate action
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
        
        # Step 2: Get handler
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
        
        # Step 3: Request permission
        parameters = action_json.get("parameters", {})
        description = action_json.get("description", "No description")
        risk_level = action_json.get("risk_level", "LOW")
        
        data_description = handler.get_data_description(parameters)
        
        permission = self._permission_manager.request_permission(
            action_id=action_id,
            action_type=action_type,
            description=description,
            data_accessed=data_description,
            risk_level=risk_level,
        )
        
        if permission != PermissionDecision.ALLOW:
            security_logger.permission_denied(action_id, action_type)
            
            self._cloud_client.report_action_result(
                action_id=action_id,
                success=False,
                message=f"User denied permission: {permission.value}",
            )
            
            if self._tray:
                self._tray.show_notification(
                    "Action Denied",
                    f"You denied: {action_type}",
                )
            return
        
        security_logger.permission_granted(action_id, action_type)
        
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
    
    def inject_test_action(self, action: dict) -> None:
        """
        Inject a test action for testing purposes.
        
        Only works with MockCloudClient.
        """
        if isinstance(self._cloud_client, MockCloudClient):
            self._cloud_client.add_test_action(action)
            logger.info("Test action injected")


def main():
    """Main entry point."""
    # Setup logging
    log_file = Path.home() / ".saarthi" / "executor.log"
    setup_logging(log_level="INFO", log_file=log_file)
    
    logger.info("=" * 60)
    logger.info("SAARTHI Local Executor Starting")
    logger.info("=" * 60)
    
    # Create and start executor
    executor = SaarthiExecutor(use_mock_cloud=True)
    
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
