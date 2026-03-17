"""
Application configuration using Pydantic Settings
"""

from typing import Dict, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Plane Configuration
    plane_base_url: str = "http://plane-api:8000"
    plane_api_key: str = ""
    plane_workspace_slug: str = ""
    plane_webhook_secret: str = ""

    # Plane Project ID (UUID)
    plane_project_id: str = ""

    # State name mapping (Plane state names → workflow triggers)
    # These map your Plane state names to workflow actions
    state_developing: str = "In Progress"
    state_integrating: str = "Integrating"
    state_testing: str = "Testing"
    state_to_publish: str = "To Publish"
    state_done: str = "Done"

    # Application Settings
    debug: bool = False
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Redis Configuration
    redis_url: str = "redis://redis:6379"
    redis_enabled: bool = True

    # Cache Configuration (in seconds)
    cache_ttl_states: int = 3600  # 1 hour - state name→UUID mapping

    # API Configuration
    api_timeout: int = 30
    max_retries: int = 3

    # CORS Configuration
    backend_cors_origins: list[str] = []

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()
