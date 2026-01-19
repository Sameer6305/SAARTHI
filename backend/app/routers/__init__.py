"""
API Routers
===========

FastAPI routers for SAARTHI cloud backend.
Each router handles a specific domain of endpoints.
"""

from app.routers.tasks import router as tasks_router
from app.routers.health import router as health_router

__all__ = [
    "tasks_router",
    "health_router",
]
