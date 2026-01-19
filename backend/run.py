"""
SAARTHI Cloud Backend - Runner Script
======================================

Simple entry point to run the FastAPI application.

Usage:
    python run.py

For development with auto-reload:
    Set DEBUG=true in environment or .env file
"""

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                    SAARTHI Cloud Backend                         ║
╠══════════════════════════════════════════════════════════════════╣
║  Version:     {settings.app_version:<50} ║
║  Environment: {settings.environment:<50} ║
║  Host:        {settings.host:<50} ║
║  Port:        {str(settings.port):<50} ║
║  Debug:       {str(settings.debug):<50} ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
