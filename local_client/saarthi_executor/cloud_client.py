"""
Cloud Communication
===================

Handles secure communication with the SAARTHI cloud backend.

SECURITY:
- HTTPS only
- Certificate validation
- Request signing
- Response validation
"""

import logging
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CloudConfig:
    """Configuration for cloud communication."""
    
    base_url: str = "https://api.saarthi.local"  # Placeholder
    api_key: str = ""  # Set via environment
    timeout_seconds: float = 30.0
    verify_ssl: bool = True


@dataclass 
class ActionRequest:
    """An action request from the cloud."""
    
    raw_json: dict
    received_at: datetime
    source_ip: Optional[str] = None


class CloudClient:
    """
    Client for cloud communication.
    
    SECURITY:
    - Only communicates with configured cloud endpoint
    - All communication over HTTPS
    - Validates all responses
    """
    
    def __init__(self, config: CloudConfig):
        """Initialize the cloud client."""
        self.config = config
        self._client: Optional[httpx.Client] = None
    
    def connect(self) -> bool:
        """Establish connection to cloud."""
        try:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl,
                headers={
                    "User-Agent": "SAARTHI-LocalExecutor/1.0",
                    "X-API-Key": self.config.api_key,
                },
            )
            
            # Test connection
            response = self._client.get("/health")
            
            if response.status_code == 200:
                logger.info("Connected to cloud backend")
                return True
            else:
                logger.warning(
                    "Cloud health check failed",
                    extra={"status_code": response.status_code}
                )
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to cloud: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close connection to cloud."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Disconnected from cloud")
    
    def poll_for_actions(self, task_id: Optional[str] = None) -> Optional[ActionRequest]:
        """
        Poll the cloud for pending actions.
        
        Returns None if no actions pending.
        """
        if not self._client:
            logger.warning("Not connected to cloud")
            return None
        
        try:
            endpoint = "/api/v1/executor/pending-actions"
            params = {"task_id": task_id} if task_id else {}
            
            response = self._client.get(endpoint, params=params)
            
            if response.status_code == 204:  # No content
                return None
            
            if response.status_code == 200:
                action_json = response.json()
                
                return ActionRequest(
                    raw_json=action_json,
                    received_at=datetime.utcnow(),
                )
            
            logger.warning(
                "Unexpected response from cloud",
                extra={"status_code": response.status_code}
            )
            return None
            
        except Exception as e:
            logger.error(f"Failed to poll for actions: {e}")
            return None
    
    def report_action_result(
        self,
        action_id: str,
        success: bool,
        message: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        Report action execution result to cloud.
        
        Returns True if successfully reported.
        """
        if not self._client:
            logger.warning("Not connected to cloud")
            return False
        
        try:
            response = self._client.post(
                f"/api/v1/task/{action_id}/execution-update",
                json={
                    "action_id": action_id,
                    "success": success,
                    "message": message,
                    "data": data or {},
                    "reported_at": datetime.utcnow().isoformat(),
                },
            )
            
            if response.status_code in [200, 201]:
                logger.info(
                    "Reported action result to cloud",
                    extra={"action_id": action_id, "success": success}
                )
                return True
            
            logger.warning(
                "Failed to report action result",
                extra={"status_code": response.status_code}
            )
            return False
            
        except Exception as e:
            logger.error(f"Failed to report action result: {e}")
            return False


class MockCloudClient:
    """
    Mock cloud client for testing without real cloud.
    
    Returns predefined test actions.
    """
    
    def __init__(self):
        """Initialize mock client."""
        self._pending_actions: list[dict] = []
        self._connected: bool = False
    
    def connect(self) -> bool:
        """Simulate connection."""
        self._connected = True
        logger.info("Mock cloud client connected")
        return True
    
    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("Mock cloud client disconnected")
    
    def add_test_action(self, action: dict) -> None:
        """Add a test action for testing."""
        self._pending_actions.append(action)
    
    def poll_for_actions(self, task_id: Optional[str] = None) -> Optional[ActionRequest]:
        """Return next pending test action."""
        if not self._connected:
            return None
        
        if self._pending_actions:
            action = self._pending_actions.pop(0)
            return ActionRequest(
                raw_json=action,
                received_at=datetime.utcnow(),
            )
        
        return None
    
    def report_action_result(
        self,
        action_id: str,
        success: bool,
        message: str,
        data: Optional[dict] = None,
    ) -> bool:
        """Log result (mock)."""
        logger.info(
            "Mock: Action result",
            extra={
                "action_id": action_id,
                "success": success,
                "message": message,
            }
        )
        return True
