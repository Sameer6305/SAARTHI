"""
SAARTHI Cloud Backend - Main Application
=========================================

FastAPI application for the SAARTHI Planner-Executor AI system.

This is the CLOUD SIDE ONLY. All execution happens on the local client.

SECURITY INVARIANTS:
- No OS commands
- No subprocess calls
- No dynamic code execution
- No filesystem writes
- No tool execution logic
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging_config import configure_logging, get_logger
from app.models.responses import ErrorResponse
from app.routers import health_router, tasks_router

# Configure logging before anything else
configure_logging()
logger = get_logger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    
    # Initialize services (they're lazy-loaded, but we can warm them up)
    from app.services.task_service import get_task_service
    from app.services.memory_service import get_memory_service
    
    get_task_service()
    get_memory_service()
    
    logger.info("application_started")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    # Cleanup memory
    memory_service = get_memory_service()
    memory_service.cleanup_expired_stm()
    
    logger.info("application_stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
## SAARTHI Cloud Backend

A privacy-preserving, Planner-Executor based AI assistant backend.

### Architecture

- **Cloud Side**: Intent analysis, planning, memory management (this service)
- **Local Client**: OS-level execution, tool invocation (separate service)

### Security

- No OS commands executed in cloud
- No raw user data stored
- All memory is abstracted
- Explicit permission model

### Endpoints

- `POST /api/v1/task` - Create task from text input
- `POST /api/v1/voice` - Create task from transcribed speech
- `GET /api/v1/status/{task_id}` - Get task status
- `POST /api/v1/task/{task_id}/confirm` - Confirm pending task
- `POST /api/v1/task/{task_id}/reject` - Reject pending task
- `GET /api/v1/task/{task_id}/plan` - Get execution plan
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# =============================================================================
# MIDDLEWARE
# =============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.utcnow()
    
    # Generate request ID
    request_id = request.headers.get("X-Request-ID", f"req_{id(request)}")
    
    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    
    response = await call_next(request)
    
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    
    return response


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    
    Returns a clean error response without exposing internal details.
    """
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=str(exc.errors()),
    )
    
    # Extract user-friendly error messages
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        error_messages.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="validation_error",
            message="; ".join(error_messages),
            timestamp=datetime.utcnow(),
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    SECURITY: Never expose stack traces or internal details.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred. Please try again later.",
            timestamp=datetime.utcnow(),
        ).model_dump(mode="json"),
    )


# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(health_router)
app.include_router(tasks_router)


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint - returns basic service info."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
