"""
Tasks Router
============

API endpoints for task management:
- POST /task - Create new task
- POST /voice - Create task from transcribed speech
- GET /status/{task_id} - Get task status
- POST /task/{task_id}/confirm - Confirm pending task
- POST /task/{task_id}/reject - Reject pending task
- GET /task/{task_id}/plan - Get execution plan
"""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.logging_config import get_logger
from app.models.requests import TaskRequest, VoiceRequest
from app.models.responses import ErrorResponse, StatusResponse, TaskResponse
from app.services.task_service import get_task_service

router = APIRouter(prefix="/api/v1", tags=["Tasks"])
logger = get_logger("tasks_router")


@router.post(
    "/task",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Task",
    description="Create a new task from user text input.",
    responses={
        201: {"description": "Task created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
)
async def create_task(request: TaskRequest) -> TaskResponse:
    """
    Create a new task from text input.
    
    This endpoint:
    1. Validates input
    2. Analyzes intent (abstracted, not stored raw)
    3. Generates execution plan
    4. Returns task ID and initial status
    
    The task may require confirmation before execution.
    """
    # Generate correlation ID for request tracing
    correlation_id = f"req_{uuid4().hex[:12]}"
    
    logger.info(
        "task_request_received",
        correlation_id=correlation_id,
        session_id=request.session_id,
        input_length=len(request.input_text),
    )
    
    try:
        task_service = get_task_service()
        
        response = await task_service.create_task(
            input_text=request.input_text,
            session_id=request.session_id,
            context=request.context,
        )
        
        logger.info(
            "task_created",
            correlation_id=correlation_id,
            task_id=response.task_id,
            status=response.status,
        )
        
        return response
        
    except ValueError as e:
        # Input validation errors
        logger.warning(
            "task_creation_validation_error",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Unexpected errors - fail closed, don't expose details
        logger.error(
            "task_creation_error",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request",
        )


@router.post(
    "/voice",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Task from Voice",
    description="Create a new task from transcribed speech input.",
    responses={
        201: {"description": "Task created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
)
async def create_task_from_voice(request: VoiceRequest) -> TaskResponse:
    """
    Create a new task from transcribed voice input.
    
    NOTE: This accepts TRANSCRIBED TEXT, not raw audio.
    Audio processing happens on the local client.
    
    Internally, this is processed the same as text input.
    """
    correlation_id = f"req_{uuid4().hex[:12]}"
    
    logger.info(
        "voice_task_request_received",
        correlation_id=correlation_id,
        session_id=request.session_id,
        text_length=len(request.transcribed_text),
        stt_confidence=request.confidence_score,
    )
    
    try:
        task_service = get_task_service()
        
        # Process as regular text input
        response = await task_service.create_task(
            input_text=request.transcribed_text,
            session_id=request.session_id,
            context={"source": "voice", "stt_confidence": request.confidence_score},
        )
        
        logger.info(
            "voice_task_created",
            correlation_id=correlation_id,
            task_id=response.task_id,
            status=response.status,
        )
        
        return response
        
    except ValueError as e:
        logger.warning(
            "voice_task_validation_error",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "voice_task_creation_error",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request",
        )


@router.get(
    "/status/{task_id}",
    response_model=StatusResponse,
    summary="Get Task Status",
    description="Get the current status of a task.",
    responses={
        200: {"description": "Task status retrieved"},
        404: {"model": ErrorResponse, "description": "Task not found"},
    },
)
async def get_task_status(task_id: str) -> StatusResponse:
    """
    Get the current status of a task.
    
    This endpoint is:
    - Idempotent (safe to call multiple times)
    - Read-only (no side effects)
    
    Returns detailed status including:
    - Planning state
    - Confirmation requirements
    - Plan steps (if available)
    - Failure information (if failed)
    """
    logger.debug("status_request", task_id=task_id)
    
    task_service = get_task_service()
    status_response = await task_service.get_task_status(task_id)
    
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return status_response


@router.post(
    "/task/{task_id}/confirm",
    response_model=StatusResponse,
    summary="Confirm Task",
    description="Confirm a task that is awaiting user confirmation.",
    responses={
        200: {"description": "Task confirmed"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        409: {"model": ErrorResponse, "description": "Task not in confirmation state"},
    },
)
async def confirm_task(task_id: str) -> StatusResponse:
    """
    Confirm a task that is awaiting confirmation.
    
    This moves the task to READY_FOR_EXECUTION status,
    allowing the executor client to proceed.
    """
    logger.info("confirm_request", task_id=task_id)
    
    task_service = get_task_service()
    status_response = await task_service.confirm_task(task_id)
    
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    if status_response.status not in ["ready_for_execution", "confirmed"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is not awaiting confirmation (current status: {status_response.status})",
        )
    
    return status_response


@router.post(
    "/task/{task_id}/reject",
    response_model=StatusResponse,
    summary="Reject Task",
    description="Reject a task that is awaiting user confirmation.",
    responses={
        200: {"description": "Task rejected"},
        404: {"model": ErrorResponse, "description": "Task not found"},
    },
)
async def reject_task(
    task_id: str,
    reason: Optional[str] = None,
) -> StatusResponse:
    """
    Reject a task that is awaiting confirmation.
    
    This cancels the task and cleans up associated memory.
    """
    logger.info("reject_request", task_id=task_id, reason=reason)
    
    task_service = get_task_service()
    status_response = await task_service.reject_task(task_id, reason)
    
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return status_response


@router.get(
    "/task/{task_id}/plan",
    summary="Get Execution Plan",
    description="Get the execution plan for a task (for executor client).",
    responses={
        200: {"description": "Plan retrieved"},
        404: {"model": ErrorResponse, "description": "Task or plan not found"},
        409: {"model": ErrorResponse, "description": "Plan not ready"},
    },
)
async def get_task_plan(task_id: str) -> dict:
    """
    Get the execution plan for a task.
    
    This endpoint is used by the executor client to retrieve
    the plan for execution.
    
    Only returns plan if task is in READY_FOR_EXECUTION state.
    """
    logger.info("plan_request", task_id=task_id)
    
    task_service = get_task_service()
    
    # First check status
    status_response = await task_service.get_task_status(task_id)
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    if not status_response.ready_for_execution:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan not ready (current status: {status_response.status})",
        )
    
    plan = await task_service.get_plan(task_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found for task {task_id}",
        )
    
    # Return plan as JSON (Pydantic model serialization)
    return plan.model_dump(mode="json")


@router.post(
    "/task/{task_id}/execution-update",
    response_model=StatusResponse,
    summary="Update Execution Status",
    description="Update task status based on execution feedback from client.",
    responses={
        200: {"description": "Status updated"},
        404: {"model": ErrorResponse, "description": "Task not found"},
    },
)
async def update_execution_status(
    task_id: str,
    step_id: str,
    success: bool,
    error_message: Optional[str] = None,
) -> StatusResponse:
    """
    Update task status based on executor feedback.
    
    This is called by the executor client to report:
    - Step completion (success=True)
    - Step failure (success=False, error_message provided)
    """
    logger.info(
        "execution_update",
        task_id=task_id,
        step_id=step_id,
        success=success,
        error=error_message,
    )
    
    task_service = get_task_service()
    status_response = await task_service.update_execution_status(
        task_id=task_id,
        step_id=step_id,
        success=success,
        error_message=error_message,
    )
    
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return status_response
