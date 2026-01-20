"""
Task Service
============

Orchestrates the complete task lifecycle:
1. Task creation
2. Intent analysis
3. Plan generation
4. Status tracking

This is the primary service that coordinates other services.
"""

import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.logging_config import get_logger
from app.models.domain import IntentAnalysis, Plan, TaskState, TaskStatus
from app.models.memory import MemoryEntryType
from app.models.responses import PlanStep, StatusResponse, TaskResponse
from app.services.intent_analyzer import get_intent_analyzer
from app.services.memory_service import get_memory_service
from app.services.planner_service import get_planner_service
from app.services.error_handling import (
    DEFAULT_TIMEOUTS,
    InputValidator,
    IntentValidationResult,
    PlanningTimeoutError,
    SafeError,
    create_planning_failed_error,
    create_service_error,
    create_timeout_error,
    get_input_validator,
    validate_intent_confidence,
    validate_intent_is_actionable,
    with_timeout,
)

logger = get_logger("task_service")
settings = get_settings()


class TaskService:
    """
    Orchestrates task lifecycle and coordinates between services.
    
    ARCHITECTURE:
    - Central coordinator for Planner-Executor pattern
    - Maintains task state in memory
    - No execution logic (execution happens on local client)
    
    ERROR HANDLING:
    - Hard timeouts on all planning phases
    - Input validation before processing
    - Intent validation before planning
    - No partial plans returned
    - All failures logged and visible
    """
    
    # Timeout configuration
    PLANNING_TIMEOUT_SECONDS = 15.0  # Hard cap for entire planning
    INTENT_TIMEOUT_SECONDS = 5.0     # Intent analysis timeout
    PLAN_GEN_TIMEOUT_SECONDS = 10.0  # Plan generation timeout
    
    def __init__(self) -> None:
        """Initialize the task service."""
        # Task state store: task_id -> TaskState
        self._tasks: dict[str, TaskState] = {}
        
        # Get service dependencies
        self._intent_analyzer = get_intent_analyzer()
        self._planner = get_planner_service()
        self._memory = get_memory_service()
        self._input_validator = get_input_validator()
        
        logger.info(
            "task_service_initialized",
            planning_timeout=self.PLANNING_TIMEOUT_SECONDS,
            intent_timeout=self.INTENT_TIMEOUT_SECONDS,
        )
    
    async def create_task(
        self,
        input_text: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> TaskResponse:
        """
        Create a new task from user input.
        
        This method:
        1. Validates input (rejects invalid/ambiguous)
        2. Creates task state
        3. Analyzes intent with TIMEOUT
        4. Validates intent (rejects low confidence/unsupported)
        5. Generates execution plan with TIMEOUT
        6. Returns task info to caller
        
        SECURITY:
        - input_text is NOT stored (only abstracted intent)
        - All processing is on abstracted data
        
        ERROR HANDLING:
        - Input validation rejects empty/gibberish/malicious input
        - Intent validation rejects ambiguous/unsupported requests
        - Hard timeouts prevent runaway processing
        - All failures return clean error responses
        """
        task_id = f"task_{uuid4().hex[:16]}"
        effective_session_id = session_id or f"sess_{uuid4().hex[:16]}"
        planning_start_time = time.monotonic()
        
        logger.info(
            "task_creation_started",
            task_id=task_id,
            session_id=effective_session_id,
            has_context=context is not None,
        )
        
        # =====================================================================
        # PHASE 0: INPUT VALIDATION (Before creating task state)
        # =====================================================================
        validation_result = self._input_validator.validate(input_text)
        
        if not validation_result.is_valid:
            logger.warning(
                "input_validation_failed",
                task_id=task_id,
                reason=validation_result.rejection_reason,
            )
            
            error = validation_result.error
            return TaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED.value,
                message=error.user_message if error else "Invalid input",
                created_at=datetime.utcnow(),
                error_code=error.internal_code if error else "VALIDATION_FAILED",
            )
        
        # Use sanitized input
        sanitized_input = validation_result.sanitized_input or input_text
        
        # Create initial task state
        task = TaskState(
            task_id=task_id,
            session_id=effective_session_id,
            status=TaskStatus.CREATED,
        )
        
        self._tasks[task_id] = task
        
        try:
            # =================================================================
            # PHASE 1: INTENT ANALYSIS (With Timeout)
            # =================================================================
            task.update_status(TaskStatus.ANALYZING, "Starting intent analysis")
            
            try:
                intent = self._analyze_intent_with_timeout(sanitized_input)
            except PlanningTimeoutError as e:
                logger.error(
                    "intent_analysis_timeout",
                    task_id=task_id,
                    timeout=e.timeout_seconds,
                    elapsed=e.elapsed_seconds,
                )
                task.update_status(TaskStatus.FAILED, "Intent analysis timed out")
                error = create_timeout_error("intent_analysis", e.timeout_seconds, e.elapsed_seconds)
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message,
                    created_at=task.created_at,
                    error_code=error.internal_code,
                )
            
            task.intent = intent
            
            # =================================================================
            # PHASE 1b: INTENT VALIDATION
            # =================================================================
            # Check confidence
            confidence_check = validate_intent_confidence(
                intent.confidence_score,
                intent.intent_category,
            )
            if not confidence_check.is_valid:
                logger.warning(
                    "intent_low_confidence",
                    task_id=task_id,
                    confidence=intent.confidence_score,
                    reason=confidence_check.rejection_reason,
                )
                task.update_status(TaskStatus.FAILED, "Intent unclear")
                error = confidence_check.error
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message if error else "Intent unclear",
                    created_at=task.created_at,
                    error_code=error.internal_code if error else "INTENT_UNCLEAR",
                )
            
            # Check if actionable
            actionable_check = validate_intent_is_actionable(
                intent.intent_category,
                intent.requires_tools,
            )
            if not actionable_check.is_valid:
                logger.info(
                    "intent_not_actionable",
                    task_id=task_id,
                    category=intent.intent_category,
                    reason=actionable_check.rejection_reason,
                )
                task.update_status(TaskStatus.FAILED, "Request not actionable")
                error = actionable_check.error
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message if error else "Cannot act on this request",
                    created_at=task.created_at,
                    error_code=error.internal_code if error else "NOT_ACTIONABLE",
                )
            
            # Store abstracted intent in STM (NOT raw input)
            self._memory.create_stm_entry(
                task_id=task_id,
                session_id=effective_session_id,
                entry_type=MemoryEntryType.INTENT_SUMMARY,
                content={
                    "intent_category": intent.intent_category,
                    "intent_summary": intent.intent_summary,
                    "confidence": intent.confidence_score,
                    "risk_level": intent.estimated_risk.value,
                },
                source="user_input",
            )
            
            # Check if clarification is needed
            if intent.clarification_needed:
                task.update_status(
                    TaskStatus.AWAITING_CONFIRMATION,
                    "Clarification needed from user",
                )
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message="Clarification needed: " + "; ".join(intent.clarification_questions),
                    created_at=task.created_at,
                    intent_summary=intent.intent_summary,
                )
            
            # =================================================================
            # PHASE 2: PLAN GENERATION (With Timeout)
            # =================================================================
            # Check total planning time budget
            elapsed_so_far = time.monotonic() - planning_start_time
            remaining_time = self.PLANNING_TIMEOUT_SECONDS - elapsed_so_far
            
            if remaining_time <= 0:
                logger.error(
                    "planning_total_timeout",
                    task_id=task_id,
                    elapsed=elapsed_so_far,
                    budget=self.PLANNING_TIMEOUT_SECONDS,
                )
                task.update_status(TaskStatus.FAILED, "Planning timed out")
                error = create_timeout_error("planning", self.PLANNING_TIMEOUT_SECONDS, elapsed_so_far)
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message,
                    created_at=task.created_at,
                    error_code=error.internal_code,
                )
            
            task.update_status(TaskStatus.PLANNING, "Generating execution plan")
            
            try:
                plan = self._generate_plan_with_timeout(task_id, intent)
            except PlanningTimeoutError as e:
                logger.error(
                    "plan_generation_timeout",
                    task_id=task_id,
                    timeout=e.timeout_seconds,
                    elapsed=e.elapsed_seconds,
                )
                task.update_status(TaskStatus.PLANNING_FAILED, "Plan generation timed out")
                error = create_timeout_error("plan_generation", e.timeout_seconds, e.elapsed_seconds)
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message,
                    created_at=task.created_at,
                    error_code=error.internal_code,
                    intent_summary=intent.intent_summary,
                )
            
            # Validate plan
            is_valid, issues = self._planner.validate_plan(plan)
            if not is_valid:
                logger.error(
                    "plan_validation_failed",
                    task_id=task_id,
                    issues=issues,
                )
                task.update_status(TaskStatus.PLANNING_FAILED, f"Plan validation failed: {issues}")
                task.failure_reason = f"Plan validation failed: {issues}"
                error = create_planning_failed_error(str(issues))
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message=error.user_message,
                    created_at=task.created_at,
                    intent_summary=intent.intent_summary,
                    error_code=error.internal_code,
                )
            
            task.plan = plan
            task.update_status(TaskStatus.PLANNING_COMPLETE, "Plan generated successfully")
            
            # Store task state in STM
            self._memory.create_stm_entry(
                task_id=task_id,
                session_id=effective_session_id,
                entry_type=MemoryEntryType.TASK_STATE,
                content={
                    "task_id": task_id,
                    "plan_id": plan.plan_id,
                    "step_count": plan.total_steps,
                    "risk_level": plan.estimated_risk.value,
                },
                source="system_derived",
            )
            
            # Determine next status
            if plan.requires_any_confirmation:
                task.update_status(
                    TaskStatus.AWAITING_CONFIRMATION,
                    "Plan requires user confirmation",
                )
            else:
                task.update_status(
                    TaskStatus.READY_FOR_EXECUTION,
                    "Plan ready for execution",
                )
            
            logger.info(
                "task_creation_complete",
                task_id=task_id,
                status=task.status.value,
                step_count=plan.total_steps,
                requires_confirmation=plan.requires_any_confirmation,
            )
            
            return TaskResponse(
                task_id=task_id,
                status=task.status.value,
                message=self._get_status_message(task.status),
                created_at=task.created_at,
                intent_summary=intent.intent_summary,
                step_count=plan.total_steps,
            )
            
        except Exception as e:
            # Fail closed on any error
            logger.error(
                "task_creation_failed",
                task_id=task_id,
                error=str(e),
                exc_info=True,
            )
            task.update_status(TaskStatus.FAILED, f"Task creation failed: {str(e)}")
            task.failure_reason = str(e)
            
            # Create safe error for user
            error = create_service_error(str(e))
            
            return TaskResponse(
                task_id=task_id,
                status=task.status.value,
                message=error.user_message,
                created_at=task.created_at,
                error_code=error.internal_code,
            )
    
    # =========================================================================
    # TIMEOUT-WRAPPED METHODS
    # =========================================================================
    
    @with_timeout(timeout_seconds=5.0, phase_name="intent_analysis")
    def _analyze_intent_with_timeout(self, input_text: str) -> IntentAnalysis:
        """
        Analyze intent with timeout protection.
        
        TIMEOUT: 5 seconds
        ON TIMEOUT: Raises PlanningTimeoutError
        """
        return self._intent_analyzer.analyze(input_text)
    
    @with_timeout(timeout_seconds=10.0, phase_name="plan_generation")
    def _generate_plan_with_timeout(
        self,
        task_id: str,
        intent: IntentAnalysis,
    ) -> Plan:
        """
        Generate plan with timeout protection.
        
        TIMEOUT: 10 seconds
        ON TIMEOUT: Raises PlanningTimeoutError
        """
        return self._planner.generate_plan(task_id, intent)
    
    async def get_task_status(self, task_id: str) -> Optional[StatusResponse]:
        """
        Get the current status of a task.
        
        This is idempotent and safe (read-only).
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            logger.warning("task_not_found", task_id=task_id)
            return None
        
        # Convert plan steps to response format
        plan_steps = None
        if task.plan:
            plan_steps = [
                PlanStep(
                    step_id=s.step_id,
                    step_number=s.step_number,
                    description=s.description,
                    step_type=s.step_type.value,
                    tool_id=s.tool_id,
                    risk_level=s.risk_level.value,
                    requires_confirmation=s.requires_confirmation,
                )
                for s in task.plan.steps
            ]
        
        return StatusResponse(
            task_id=task_id,
            status=task.status.value,
            planning_complete=task.status in [
                TaskStatus.PLANNING_COMPLETE,
                TaskStatus.AWAITING_CONFIRMATION,
                TaskStatus.READY_FOR_EXECUTION,
                TaskStatus.CONFIRMED,
            ],
            awaiting_confirmation=task.status == TaskStatus.AWAITING_CONFIRMATION,
            ready_for_execution=task.status == TaskStatus.READY_FOR_EXECUTION,
            failed=task.status in [
                TaskStatus.FAILED,
                TaskStatus.PLANNING_FAILED,
                TaskStatus.EXECUTION_FAILED,
            ],
            failure_reason=task.failure_reason,
            plan_steps=plan_steps,
            current_step=task.current_step_index + 1 if task.current_step_index > 0 else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    
    async def confirm_task(self, task_id: str) -> Optional[StatusResponse]:
        """
        Confirm a task that is awaiting confirmation.
        
        This moves the task to READY_FOR_EXECUTION status.
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            logger.warning("task_not_found_for_confirmation", task_id=task_id)
            return None
        
        if task.status != TaskStatus.AWAITING_CONFIRMATION:
            logger.warning(
                "invalid_confirmation_attempt",
                task_id=task_id,
                current_status=task.status.value,
            )
            return await self.get_task_status(task_id)
        
        task.update_status(TaskStatus.CONFIRMED, "User confirmed task")
        task.update_status(TaskStatus.READY_FOR_EXECUTION, "Ready for executor")
        
        logger.info("task_confirmed", task_id=task_id)
        
        return await self.get_task_status(task_id)
    
    async def reject_task(self, task_id: str, reason: Optional[str] = None) -> Optional[StatusResponse]:
        """
        Reject a task that is awaiting confirmation.
        
        This cancels the task.
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            logger.warning("task_not_found_for_rejection", task_id=task_id)
            return None
        
        if task.status != TaskStatus.AWAITING_CONFIRMATION:
            logger.warning(
                "invalid_rejection_attempt",
                task_id=task_id,
                current_status=task.status.value,
            )
            return await self.get_task_status(task_id)
        
        task.update_status(TaskStatus.REJECTED, reason or "User rejected task")
        task.update_status(TaskStatus.CANCELLED, "Task cancelled by user")
        
        # Clear STM for this task
        self._memory.clear_stm_for_task(task_id)
        
        logger.info("task_rejected", task_id=task_id, reason=reason)
        
        return await self.get_task_status(task_id)
    
    async def get_plan(self, task_id: str) -> Optional[Plan]:
        """
        Get the execution plan for a task.
        
        This is used by the executor client to retrieve the plan.
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            return None
        
        return task.plan
    
    async def get_intent(self, task_id: str) -> Optional[IntentAnalysis]:
        """
        Get the analyzed intent for a task.
        
        This is used for parameter extraction when converting to actions.
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            return None
        
        return task.intent
    
    async def update_execution_status(
        self,
        task_id: str,
        step_id: str,
        success: bool,
        error_message: Optional[str] = None,
    ) -> Optional[StatusResponse]:
        """
        Update task status based on execution feedback from client.
        
        This is called by the executor client to report progress.
        """
        task = self._tasks.get(task_id)
        
        if task is None:
            return None
        
        if success:
            task.completed_steps.append(step_id)
            task.current_step_index += 1
            
            # Check if all steps complete
            if task.plan and task.current_step_index >= task.plan.total_steps:
                task.update_status(TaskStatus.EXECUTION_COMPLETE, "All steps completed")
                task.update_status(TaskStatus.COMPLETED, "Task completed successfully")
                
                # Clear STM for completed task
                self._memory.clear_stm_for_task(task_id)
        else:
            task.failed_step = step_id
            task.failure_reason = error_message
            task.update_status(TaskStatus.EXECUTION_FAILED, error_message)
            task.update_status(TaskStatus.FAILED, error_message)
        
        task.updated_at = datetime.utcnow()
        
        return await self.get_task_status(task_id)
    
    def _get_status_message(self, status: TaskStatus) -> str:
        """Get human-readable message for status."""
        messages = {
            TaskStatus.CREATED: "Task created",
            TaskStatus.ANALYZING: "Analyzing intent...",
            TaskStatus.PLANNING: "Generating execution plan...",
            TaskStatus.PLANNING_COMPLETE: "Plan ready",
            TaskStatus.PLANNING_FAILED: "Planning failed",
            TaskStatus.AWAITING_CONFIRMATION: "Awaiting your confirmation",
            TaskStatus.CONFIRMED: "Confirmed, preparing for execution",
            TaskStatus.REJECTED: "Task rejected",
            TaskStatus.READY_FOR_EXECUTION: "Ready for execution",
            TaskStatus.EXECUTING: "Executing...",
            TaskStatus.EXECUTION_COMPLETE: "Execution complete",
            TaskStatus.EXECUTION_FAILED: "Execution failed",
            TaskStatus.COMPLETED: "Task completed successfully",
            TaskStatus.FAILED: "Task failed",
            TaskStatus.CANCELLED: "Task cancelled",
        }
        return messages.get(status, "Unknown status")


# Singleton instance
_task_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """Get the singleton task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
