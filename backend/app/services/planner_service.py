"""
Planner Service
===============

Generates structured execution plans from analyzed intents.

ARCHITECTURE NOTES:
- Planner generates JSON plans ONLY
- No execution logic
- Plans are deterministic and auditable
- Output is sent to local Executor for actual execution

SECURITY INVARIANTS:
- No OS commands
- No subprocess calls
- No dynamic code execution
- Output is pure JSON structure
"""

import time
from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.logging_config import get_logger
from app.models.domain import (
    IntentAnalysis,
    Plan,
    PlanStepDomain,
    RiskLevel,
    StepType,
)

logger = get_logger("planner_service")
settings = get_settings()


class PlannerService:
    """
    Generates execution plans from analyzed intents.
    
    The Planner follows the specification in PLANNER_EXECUTOR.md:
    - Produces JSON-only output
    - Deterministic step generation
    - Risk-aware confirmation requirements
    - No execution, only planning
    """
    
    # Step templates by intent category
    STEP_TEMPLATES: dict[str, list[dict]] = {
        "file_operation": [
            {
                "description": "Identify target file or folder",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Verify access permissions",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "file.check_permissions",
                "risk_level": RiskLevel.LOW,
            },
            {
                "description": "Execute file operation",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "file.execute",
                "risk_level": RiskLevel.MEDIUM,
            },
            {
                "description": "Verify operation result",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "file.verify",
                "risk_level": RiskLevel.NONE,
            },
        ],
        "app_control": [
            {
                "description": "Identify target application",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Check application availability",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "app.check",
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Execute application control",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "app.control",
                "risk_level": RiskLevel.LOW,
            },
        ],
        "browser_action": [
            {
                "description": "Identify target URL or search query",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Open or navigate browser",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "browser.navigate",
                "risk_level": RiskLevel.LOW,
            },
        ],
        "system_operation": [
            {
                "description": "Analyze system operation request",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Confirm system operation with user",
                "step_type": StepType.USER_CONFIRMATION_REQUIRED,
                "risk_level": RiskLevel.HIGH,
                "requires_confirmation": True,
            },
            {
                "description": "Execute system operation",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "system.execute",
                "risk_level": RiskLevel.HIGH,
            },
        ],
        "communication": [
            {
                "description": "Identify communication target and content",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Prepare message content",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "comm.prepare",
                "risk_level": RiskLevel.LOW,
            },
            {
                "description": "Confirm message before sending",
                "step_type": StepType.USER_CONFIRMATION_REQUIRED,
                "risk_level": RiskLevel.MEDIUM,
                "requires_confirmation": True,
            },
            {
                "description": "Send communication",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "comm.send",
                "risk_level": RiskLevel.MEDIUM,
            },
        ],
        "media_control": [
            {
                "description": "Identify media target",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Execute media control",
                "step_type": StepType.TOOL_REQUIRED,
                "tool_id": "media.control",
                "risk_level": RiskLevel.NONE,
            },
        ],
        "information_request": [
            {
                "description": "Process information request",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
            {
                "description": "Provide response to user",
                "step_type": StepType.INFORMATIONAL,
                "risk_level": RiskLevel.NONE,
            },
        ],
    }
    
    def __init__(self) -> None:
        """Initialize the planner service."""
        self._version = "1.0.0"
        logger.info("planner_service_initialized", version=self._version)
    
    def generate_plan(
        self,
        task_id: str,
        intent: IntentAnalysis,
    ) -> Plan:
        """
        Generate an execution plan from analyzed intent.
        
        SECURITY:
        - Output is pure JSON (Plan model)
        - No execution logic
        - Deterministic based on intent
        
        Args:
            task_id: The task identifier
            intent: Analyzed intent from IntentAnalyzer
        
        Returns:
            Plan object ready for Executor
        """
        start_time = time.time()
        
        plan_id = f"plan_{uuid4().hex[:16]}"
        
        logger.info(
            "plan_generation_started",
            task_id=task_id,
            plan_id=plan_id,
            intent_category=intent.intent_category,
        )
        
        # Get step templates for this intent category
        templates = self.STEP_TEMPLATES.get(
            intent.intent_category,
            self.STEP_TEMPLATES["information_request"],
        )
        
        # Generate plan steps
        steps = self._generate_steps(
            task_id=task_id,
            intent=intent,
            templates=templates,
        )
        
        # Validate step count
        if len(steps) > settings.planner_max_steps:
            logger.warning(
                "plan_step_limit_exceeded",
                task_id=task_id,
                step_count=len(steps),
                max_steps=settings.planner_max_steps,
            )
            steps = steps[:settings.planner_max_steps]
        
        # Calculate overall risk (max of all step risks)
        overall_risk = self._calculate_overall_risk(steps, intent.estimated_risk)
        
        # Check if any step requires confirmation
        requires_confirmation = any(s.requires_confirmation for s in steps)
        
        generation_time_ms = (time.time() - start_time) * 1000
        
        plan = Plan(
            plan_id=plan_id,
            task_id=task_id,
            intent_summary=intent.intent_summary,  # Already abstracted
            steps=steps,
            total_steps=len(steps),
            estimated_risk=overall_risk,
            requires_any_confirmation=requires_confirmation,
            planner_version=self._version,
            generation_time_ms=generation_time_ms,
        )
        
        logger.info(
            "plan_generation_complete",
            task_id=task_id,
            plan_id=plan_id,
            step_count=len(steps),
            overall_risk=overall_risk.value,
            requires_confirmation=requires_confirmation,
            generation_time_ms=round(generation_time_ms, 2),
        )
        
        return plan
    
    def _generate_steps(
        self,
        task_id: str,
        intent: IntentAnalysis,
        templates: list[dict],
    ) -> list[PlanStepDomain]:
        """Generate plan steps from templates."""
        steps = []
        
        for i, template in enumerate(templates, start=1):
            step_id = f"{task_id}_step_{i}"
            
            # Determine if this step needs confirmation
            requires_confirmation = template.get("requires_confirmation", False)
            
            # Escalate confirmation requirement based on overall risk
            if intent.estimated_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                if template.get("step_type") == StepType.TOOL_REQUIRED:
                    requires_confirmation = True
            
            # Get risk level from template, potentially escalated
            risk_level = template.get("risk_level", RiskLevel.LOW)
            if intent.estimated_risk == RiskLevel.CRITICAL:
                risk_level = RiskLevel.CRITICAL
            
            step = PlanStepDomain(
                step_id=step_id,
                step_number=i,
                step_type=template["step_type"],
                description=template["description"],
                tool_id=template.get("tool_id"),
                tool_parameters=self._generate_tool_params(intent, template),
                risk_level=risk_level,
                requires_confirmation=requires_confirmation,
                preconditions=[f"{task_id}_step_{i-1}"] if i > 1 else [],
                on_failure="abort" if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else "skip",
                max_retries=0 if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else 1,
            )
            
            steps.append(step)
        
        return steps
    
    def _generate_tool_params(
        self,
        intent: IntentAnalysis,
        template: dict,
    ) -> Optional[dict]:
        """
        Generate tool parameters based on intent.
        
        NOTE: In production, this would be more sophisticated,
        potentially using LLM to extract specific parameters.
        """
        if template.get("step_type") != StepType.TOOL_REQUIRED:
            return None
        
        tool_id = template.get("tool_id", "")
        
        # Basic parameter structure (abstracted)
        params = {
            "intent_category": intent.intent_category,
            "confidence": intent.confidence_score,
            "entities": intent.detected_entities,
        }
        
        return params
    
    def _calculate_overall_risk(
        self,
        steps: list[PlanStepDomain],
        intent_risk: RiskLevel,
    ) -> RiskLevel:
        """Calculate overall plan risk as max of all risks."""
        risk_order = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        
        max_step_risk = max(
            (risk_order.index(s.risk_level) for s in steps),
            default=0,
        )
        
        intent_risk_idx = risk_order.index(intent_risk)
        
        return risk_order[max(max_step_risk, intent_risk_idx)]
    
    def validate_plan(self, plan: Plan) -> tuple[bool, list[str]]:
        """
        Validate a plan for consistency and safety.
        
        Returns (is_valid, list_of_issues).
        """
        issues = []
        
        # Check step count
        if plan.total_steps == 0:
            issues.append("Plan has no steps")
        
        if plan.total_steps > settings.planner_max_steps:
            issues.append(f"Plan exceeds max steps ({settings.planner_max_steps})")
        
        # Check step numbering
        for i, step in enumerate(plan.steps, start=1):
            if step.step_number != i:
                issues.append(f"Step numbering mismatch at position {i}")
        
        # Check precondition validity
        step_ids = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for precond in step.preconditions:
                if precond not in step_ids:
                    issues.append(f"Invalid precondition {precond} in step {step.step_id}")
        
        # Check risk consistency
        if plan.estimated_risk == RiskLevel.CRITICAL:
            # Critical plans must have confirmation
            if not plan.requires_any_confirmation:
                issues.append("Critical risk plan must require confirmation")
        
        return len(issues) == 0, issues


# Singleton instance
_planner_service: Optional[PlannerService] = None


def get_planner_service() -> PlannerService:
    """Get the singleton planner service instance."""
    global _planner_service
    if _planner_service is None:
        _planner_service = PlannerService()
    return _planner_service
