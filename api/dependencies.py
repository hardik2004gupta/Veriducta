"""FastAPI dependency injection providers."""

from config.settings import Settings, get_settings


def get_app_settings() -> Settings:
    """Provide the application Settings instance as a FastAPI dependency."""
    return get_settings()
