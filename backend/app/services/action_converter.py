"""
Action Conversion Service
=========================

Converts plan steps into executable actions for the local client.

ARCHITECTURE:
- Takes Plan (from Planner) as input
- Produces ExecutableAction list (for Executor) as output
- Maps tool_id to action_type
- Extracts parameters from intent/step context
- Generates signatures for verification

SECURITY:
- Only produces allowlisted action types
- Validates all parameters before output
- Generates cryptographic signatures
"""

import re
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.logging_config import get_logger
from app.models.actions import (
    ActionParameters,
    ActionResponse,
    ActionRiskLevel,
    ActionType,
    ExecutableAction,
    generate_action_signature,
)
from app.models.domain import Plan, PlanStepDomain, RiskLevel, StepType

logger = get_logger("action_converter")
settings = get_settings()


# Mapping from tool_id to action_type
TOOL_TO_ACTION_MAP: dict[str, ActionType] = {
    "browser.navigate": ActionType.OPEN_BROWSER_URL,
    "browser.open": ActionType.OPEN_BROWSER_URL,
    "media.control": ActionType.PLAY_MEDIA_FILE,
    "media.play": ActionType.PLAY_MEDIA_FILE,
    "file.read": ActionType.READ_FILE_WITH_PICKER,
    "file.execute": ActionType.READ_FILE_WITH_PICKER,  # Read-only for safety
}

# Risk level mapping
RISK_LEVEL_MAP: dict[RiskLevel, ActionRiskLevel] = {
    RiskLevel.NONE: ActionRiskLevel.NONE,
    RiskLevel.LOW: ActionRiskLevel.LOW,
    RiskLevel.MEDIUM: ActionRiskLevel.MEDIUM,
    RiskLevel.HIGH: ActionRiskLevel.HIGH,
    RiskLevel.CRITICAL: ActionRiskLevel.HIGH,  # Cap at HIGH for actions
}


class ActionConversionService:
    """
    Converts plans into executable actions.
    
    Only steps with tool_required and mapped tool_id become actions.
    Informational steps are skipped (they don't need execution).
    """
    
    def __init__(self) -> None:
        """Initialize the conversion service."""
        self._version = "1.0.0"
        logger.info("action_conversion_service_initialized", version=self._version)
    
    def convert_plan_to_actions(
        self,
        plan: Plan,
        intent_summary: str,
        detected_entities: list[str],
        target_url: Optional[str] = None,
    ) -> ActionResponse:
        """
        Convert a plan into executable actions.
        
        Args:
            plan: The execution plan from planner
            intent_summary: Summary of user intent (for description)
            detected_entities: Entities detected (for parameter extraction)
            target_url: Pre-extracted target URL for browser actions
        
        Returns:
            ActionResponse with list of executable actions
        """
        logger.info(
            "converting_plan_to_actions",
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            step_count=plan.total_steps,
            target_url=target_url,
        )
        
        actions: list[ExecutableAction] = []
        
        for step in plan.steps:
            # Only convert tool_required steps
            if step.step_type != StepType.TOOL_REQUIRED:
                logger.debug(
                    "skipping_non_tool_step",
                    step_id=step.step_id,
                    step_type=step.step_type.value,
                )
                continue
            
            # Check if we have a mapping for this tool
            if step.tool_id not in TOOL_TO_ACTION_MAP:
                logger.warning(
                    "unknown_tool_id",
                    step_id=step.step_id,
                    tool_id=step.tool_id,
                )
                continue
            
            action = self._convert_step_to_action(
                step=step,
                task_id=plan.task_id,
                intent_summary=intent_summary,
                detected_entities=detected_entities,
                target_url=target_url,
            )
            
            if action:
                actions.append(action)
        
        # Calculate expiry (5 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        response = ActionResponse(
            task_id=plan.task_id,
            execution_status="ready_for_execution",
            actions=actions,
            total_actions=len(actions),
            current_action_index=0,
            requires_confirmation=plan.requires_any_confirmation,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        
        logger.info(
            "plan_converted_to_actions",
            plan_id=plan.plan_id,
            task_id=plan.task_id,
            action_count=len(actions),
            expires_at=expires_at.isoformat(),
        )
        
        return response
    
    def _convert_step_to_action(
        self,
        step: PlanStepDomain,
        task_id: str,
        intent_summary: str,
        detected_entities: list[str],
        target_url: Optional[str] = None,
    ) -> Optional[ExecutableAction]:
        """Convert a single plan step to an executable action."""
        action_type = TOOL_TO_ACTION_MAP.get(step.tool_id)
        if not action_type:
            return None
        
        # Generate action ID
        action_id = f"act_{uuid4().hex[:24]}"
        
        # Generate timestamp
        timestamp = datetime.utcnow()
        
        # Generate signature
        signature = generate_action_signature(
            action_id=action_id,
            action_type=action_type.value,
            timestamp=timestamp.isoformat(),
        )
        
        # Extract parameters based on action type
        parameters = self._extract_parameters(
            action_type=action_type,
            intent_summary=intent_summary,
            detected_entities=detected_entities,
            step_params=step.tool_parameters or {},
            target_url=target_url,
        )
        
        # Map risk level
        risk_level = RISK_LEVEL_MAP.get(step.risk_level, ActionRiskLevel.LOW)
        
        # Create human-readable description
        description = self._create_description(
            action_type=action_type,
            intent_summary=intent_summary,
            parameters=parameters,
        )
        
        action = ExecutableAction(
            action_id=action_id,
            action_type=action_type,
            timestamp=timestamp,
            signature=signature,
            description=description,
            risk_level=risk_level,
            parameters=parameters,
            task_id=task_id,
            step_id=step.step_id,
        )
        
        logger.debug(
            "step_converted_to_action",
            step_id=step.step_id,
            action_id=action_id,
            action_type=action_type.value,
        )
        
        return action
    
    def _extract_parameters(
        self,
        action_type: ActionType,
        intent_summary: str,
        detected_entities: list[str],
        step_params: dict,
        target_url: Optional[str] = None,
    ) -> ActionParameters:
        """
        Extract action parameters from context.
        
        Uses pre-extracted values from intent analysis when available.
        """
        params = ActionParameters()
        
        if action_type == ActionType.OPEN_BROWSER_URL:
            # Use pre-extracted target_url from intent if available
            if target_url:
                params.url = target_url
            else:
                # Fallback to pattern extraction
                url = self._extract_url(intent_summary, detected_entities, step_params)
                if url:
                    params.url = url
        
        elif action_type == ActionType.PLAY_MEDIA_FILE:
            # Determine media type
            media_type = self._extract_media_type(intent_summary, step_params)
            params.media_type = media_type
        
        elif action_type == ActionType.READ_FILE_WITH_PICKER:
            # Extract file type filters
            file_types = self._extract_file_types(intent_summary, step_params)
            params.file_types = file_types
            params.read_mode = "text"
        
        return params
    
    def _extract_url(
        self,
        intent_summary: str,
        detected_entities: list[str],
        step_params: dict,
    ) -> Optional[str]:
        """Extract URL from context."""
        # Check step params first
        if "url" in step_params:
            return step_params["url"]
        
        # Common site mappings
        site_map = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "github": "https://github.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "facebook": "https://www.facebook.com",
            "linkedin": "https://www.linkedin.com",
            "reddit": "https://www.reddit.com",
            "stackoverflow": "https://stackoverflow.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://www.spotify.com",
        }
        
        # Check intent summary for known sites
        summary_lower = intent_summary.lower()
        for site, url in site_map.items():
            if site in summary_lower:
                return url
        
        # Try to extract URL pattern from intent
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        matches = re.findall(url_pattern, intent_summary)
        if matches:
            return matches[0]
        
        # Check entities
        for entity in detected_entities:
            entity_lower = entity.lower()
            for site, url in site_map.items():
                if site in entity_lower:
                    return url
        
        return None
    
    def _extract_media_type(
        self,
        intent_summary: str,
        step_params: dict,
    ) -> str:
        """Extract media type from context."""
        if "media_type" in step_params:
            return step_params["media_type"]
        
        summary_lower = intent_summary.lower()
        
        if any(word in summary_lower for word in ["video", "movie", "film", "watch"]):
            return "video"
        elif any(word in summary_lower for word in ["music", "song", "audio", "listen", "podcast"]):
            return "audio"
        elif any(word in summary_lower for word in ["image", "photo", "picture", "screenshot"]):
            return "image"
        
        return "video"  # Default to video
    
    def _extract_file_types(
        self,
        intent_summary: str,
        step_params: dict,
    ) -> list[str]:
        """Extract file type filters from context."""
        if "file_types" in step_params:
            return step_params["file_types"]
        
        summary_lower = intent_summary.lower()
        
        # Common file type mappings
        if any(word in summary_lower for word in ["document", "doc", "word"]):
            return [".docx", ".doc", ".pdf", ".txt"]
        elif any(word in summary_lower for word in ["spreadsheet", "excel", "csv"]):
            return [".xlsx", ".xls", ".csv"]
        elif any(word in summary_lower for word in ["presentation", "powerpoint", "slides"]):
            return [".pptx", ".ppt", ".pdf"]
        elif any(word in summary_lower for word in ["image", "photo", "picture"]):
            return [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
        elif any(word in summary_lower for word in ["pdf"]):
            return [".pdf"]
        elif any(word in summary_lower for word in ["code", "script", "python"]):
            return [".py", ".js", ".ts", ".java", ".cpp", ".c"]
        
        # Default: common document types
        return [".txt", ".pdf", ".docx"]
    
    def _create_description(
        self,
        action_type: ActionType,
        intent_summary: str,
        parameters: ActionParameters,
    ) -> str:
        """Create a human-readable description for user consent."""
        if action_type == ActionType.OPEN_BROWSER_URL:
            if parameters.url:
                return f"Open {parameters.url} in your default browser"
            return "Open a website in your default browser"
        
        elif action_type == ActionType.PLAY_MEDIA_FILE:
            media_type = parameters.media_type or "media"
            return f"Open a file picker to select a {media_type} file to play"
        
        elif action_type == ActionType.READ_FILE_WITH_PICKER:
            if parameters.file_types:
                types = ", ".join(parameters.file_types[:3])
                return f"Open a file picker to select a file ({types}) to read"
            return "Open a file picker to select a file to read"
        
        return f"Execute action: {intent_summary}"


# Singleton instance
_conversion_service: Optional[ActionConversionService] = None


def get_action_conversion_service() -> ActionConversionService:
    """Get the singleton action conversion service instance."""
    global _conversion_service
    if _conversion_service is None:
        _conversion_service = ActionConversionService()
    return _conversion_service
