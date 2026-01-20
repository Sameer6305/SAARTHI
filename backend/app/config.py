"""
Application Configuration
=========================

Centralized configuration using Pydantic Settings.
All secrets and environment-specific values are loaded from environment variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All sensitive values MUST be provided via environment variables.
    Defaults are provided only for non-sensitive development settings.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # === Application Identity ===
    app_name: str = "SAARTHI Cloud Backend"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    
    # === Server Configuration ===
    host: str = "0.0.0.0"
    port: int = 8000
    
    # === Security Settings ===
    # In production, these would be set via environment variables
    api_key_header: str = "X-API-Key"
    cors_origins: list[str] = ["http://localhost:3000"]
    
    # === Memory Configuration ===
    stm_max_entries_per_task: int = 100
    stm_entry_max_size_bytes: int = 10240  # 10KB
    ltm_max_results_per_query: int = 10
    
    # === Planner Configuration ===
    planner_max_steps: int = 20
    planner_timeout_seconds: float = 30.0
    
    # === Action Configuration ===
    action_expiry_minutes: int = 5  # Actions expire after 5 minutes
    max_actions_per_task: int = 10  # Maximum actions per task
    
    # === Request Timeouts ===
    request_timeout_seconds: float = 60.0  # Overall request timeout
    intent_analysis_timeout_seconds: float = 10.0
    plan_generation_timeout_seconds: float = 20.0
    
    # === Rate Limiting ===
    rate_limit_requests_per_minute: int = 60
    rate_limit_tasks_per_minute: int = 30
    
    # === Security ===
    secret_key: str = ""  # MUST be set in production via environment variable
    
    # === Logging Configuration ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    
    Using lru_cache ensures settings are loaded once and reused.
    """
    return Settings()
