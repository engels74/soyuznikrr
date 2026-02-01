"""Litestar application factory for Zondarr.

Provides:
- create_app(): Factory function for creating Litestar application instances
- app: Default application instance for Granian deployment

The application factory pattern enables:
- Dependency injection override for testing
- Configuration customization per environment
- Clean separation of concerns

Usage:
    # Production (Granian)
    granian zondarr.app:app --interface asgi

    # Testing
    from zondarr.app import create_app
    app = create_app(settings=test_settings)
"""

from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin, SwaggerRenderPlugin
from litestar.openapi.spec import Components, SecurityScheme, Tag
from litestar.plugins.structlog import StructlogConfig, StructlogPlugin

from zondarr.api.errors import (
    internal_error_handler,
    not_found_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.api.invitations import InvitationController
from zondarr.api.join import JoinController
from zondarr.api.servers import ServerController
from zondarr.config import Settings, load_settings
from zondarr.core.database import db_lifespan, provide_db_session
from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.media.clients.jellyfin import JellyfinClient
from zondarr.media.clients.plex import PlexClient
from zondarr.media.registry import registry
from zondarr.models.media_server import ServerType


def _register_media_clients() -> None:
    """Register all media client implementations in the registry.

    Called during application startup to ensure all supported server types
    have their client implementations available.
    """
    registry.register(ServerType.JELLYFIN, JellyfinClient)
    registry.register(ServerType.PLEX, PlexClient)


def _create_openapi_config() -> OpenAPIConfig:
    """Create OpenAPI configuration for the application.

    Returns:
        Configured OpenAPIConfig instance.
    """
    return OpenAPIConfig(
        title="Zondarr API",
        version="0.1.0",
        description="Unified invitation and user management for media servers",
        path="/docs",
        tags=[
            Tag(name="Health", description="Health check endpoints"),
            Tag(name="Media Servers", description="Media server management"),
            Tag(name="Invitations", description="Invitation management"),
            Tag(name="Join", description="Public invitation redemption"),
            Tag(name="Users", description="User and identity management"),
        ],
        security=[{"BearerToken": []}],
        components=Components(
            security_schemes={
                "BearerToken": SecurityScheme(
                    type="http",
                    scheme="bearer",
                    bearer_format="JWT",
                    description="JWT authentication token",
                ),
            },
        ),
        render_plugins=[
            SwaggerRenderPlugin(path="/swagger"),
            ScalarRenderPlugin(path="/scalar"),
        ],
    )


def _create_structlog_config() -> StructlogConfig:
    """Create structlog configuration for structured logging.

    Returns:
        Configured StructlogConfig instance.
    """
    return StructlogConfig()


def create_app(settings: Settings | None = None) -> Litestar:
    """Application factory for creating Litestar app instances.

    Creates a fully configured Litestar application with:
    - Database connection pool management via lifespan
    - Dependency injection for database sessions
    - Media client registry initialization
    - OpenAPI documentation with Swagger and Scalar
    - Structured logging with structlog
    - Exception handlers for domain errors

    Args:
        settings: Optional Settings instance. If not provided, settings
            are loaded from environment variables via load_settings().

    Returns:
        Configured Litestar application instance.

    Example:
        # Production usage (settings from environment)
        app = create_app()

        # Testing with custom settings
        test_settings = Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            secret_key="test-secret-key-at-least-32-chars",
        )
        app = create_app(settings=test_settings)
    """
    if settings is None:
        settings = load_settings()

    # Register media clients in the global registry
    _register_media_clients()

    return Litestar(
        route_handlers=[
            HealthController,
            InvitationController,
            JoinController,
            ServerController,
        ],
        lifespan=[db_lifespan],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_db_session),
        },
        openapi_config=_create_openapi_config(),
        plugins=[
            StructlogPlugin(config=_create_structlog_config()),
        ],
        exception_handlers={
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
            Exception: internal_error_handler,
        },
        debug=settings.debug,
    )


# Default application instance for Granian deployment
# Usage: granian zondarr.app:app --interface asgi
app = create_app()
