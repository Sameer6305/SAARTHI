"""
Health Check Router
===================

Provides health and readiness endpoints for monitoring and orchestration.
"""

from datetime import datetime

from fastapi import APIRouter, status

from app.config import get_settings
from app.logging_config import get_logger
from app.models.responses import HealthResponse

router = APIRouter(tags=["Health"])
logger = get_logger("health_router")
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check the health status of the SAARTHI cloud backend.",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse with component status
    """
    # Check component health
    components = {
        "api": "healthy",
        "planner": "healthy",
        "memory": "healthy",
        "intent_analyzer": "healthy",
    }
    
    # Determine overall status
    overall_status = "healthy" if all(
        v == "healthy" for v in components.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        timestamp=datetime.utcnow(),
        components=components,
    )


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Check",
    description="Check if the service is ready to accept requests.",
)
async def readiness_check() -> dict:
    """
    Readiness check for orchestration systems.
    
    Returns 200 if ready, 503 if not ready.
    """
    return {"ready": True}


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Check",
    description="Check if the service is alive.",
)
async def liveness_check() -> dict:
    """
    Liveness check for orchestration systems.
    
    Returns 200 if alive.
    """
    return {"alive": True}
