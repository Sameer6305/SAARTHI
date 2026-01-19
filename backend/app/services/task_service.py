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

from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.config import get_settings
from app.logging_config import get_logger
from app.models.domain import Plan, TaskState, TaskStatus
from app.models.memory import MemoryEntryType
from app.models.responses import PlanStep, StatusResponse, TaskResponse
from app.services.intent_analyzer import get_intent_analyzer
from app.services.memory_service import get_memory_service
from app.services.planner_service import get_planner_service

logger = get_logger("task_service")
settings = get_settings()


class TaskService:
    """
    Orchestrates task lifecycle and coordinates between services.
    
    ARCHITECTURE:
    - Central coordinator for Planner-Executor pattern
    - Maintains task state in memory
    - No execution logic (execution happens on local client)
    """
    
    def __init__(self) -> None:
        """Initialize the task service."""
        # Task state store: task_id -> TaskState
        self._tasks: dict[str, TaskState] = {}
        
        # Get service dependencies
        self._intent_analyzer = get_intent_analyzer()
        self._planner = get_planner_service()
        self._memory = get_memory_service()
        
        logger.info("task_service_initialized")
    
    async def create_task(
        self,
        input_text: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> TaskResponse:
        """
        Create a new task from user input.
        
        This method:
        1. Creates task state
        2. Analyzes intent (abstracted)
        3. Generates execution plan
        4. Returns task info to caller
        
        SECURITY:
        - input_text is NOT stored (only abstracted intent)
        - All processing is on abstracted data
        """
        task_id = f"task_{uuid4().hex[:16]}"
        effective_session_id = session_id or f"sess_{uuid4().hex[:16]}"
        
        logger.info(
            "task_creation_started",
            task_id=task_id,
            session_id=effective_session_id,
            has_context=context is not None,
        )
        
        # Create initial task state
        task = TaskState(
            task_id=task_id,
            session_id=effective_session_id,
            status=TaskStatus.CREATED,
        )
        
        self._tasks[task_id] = task
        
        try:
            # Phase 1: Intent Analysis
            task.update_status(TaskStatus.ANALYZING, "Starting intent analysis")
            
            intent = self._intent_analyzer.analyze(input_text)
            task.intent = intent
            
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
            
            # Phase 2: Plan Generation
            task.update_status(TaskStatus.PLANNING, "Generating execution plan")
            
            plan = self._planner.generate_plan(task_id, intent)
            
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
                return TaskResponse(
                    task_id=task_id,
                    status=task.status.value,
                    message="Planning failed due to validation errors",
                    created_at=task.created_at,
                    intent_summary=intent.intent_summary,
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
            
            return TaskResponse(
                task_id=task_id,
                status=task.status.value,
                message="Task creation failed",
                created_at=task.created_at,
            )
    
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
