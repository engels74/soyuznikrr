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
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.di import Provide
from litestar.exceptions import HTTPException as LitestarHTTPException
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin, SwaggerRenderPlugin
from litestar.openapi.spec import Components, SecurityScheme, Tag
from litestar.plugins.structlog import StructlogConfig, StructlogPlugin

from zondarr.api.auth import AuthController
from zondarr.api.errors import (
    authentication_error_handler,
    external_service_error_handler,
    internal_error_handler,
    litestar_http_exception_handler,
    not_found_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.api.invitations import InvitationController
from zondarr.api.join import JoinController
from zondarr.api.oauth import OAuthController
from zondarr.api.providers import ProviderController
from zondarr.api.servers import ServerController
from zondarr.api.users import UserController
from zondarr.api.wizards import WizardController
from zondarr.config import Settings, load_settings
from zondarr.core.auth import create_jwt_auth
from zondarr.core.database import db_lifespan, provide_db_session
from zondarr.core.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from zondarr.core.tasks import background_tasks_lifespan
from zondarr.media.providers import register_all_providers
from zondarr.media.registry import registry


def provide_settings(state: State) -> Settings:
    """Extract Settings from app state for DI injection."""
    return state.settings  # pyright: ignore[reportAny]


def _create_openapi_config() -> OpenAPIConfig:
    """Create OpenAPI configuration for the application.

    Generates tags dynamically from registered providers.

    Returns:
        Configured OpenAPIConfig instance.
    """
    # Base tags
    tags = [
        Tag(name="Authentication", description="Admin authentication"),
        Tag(name="Health", description="Health check endpoints"),
        Tag(name="Media Servers", description="Media server management"),
        Tag(name="Invitations", description="Invitation management"),
        Tag(name="Join", description="Public invitation redemption"),
        Tag(name="OAuth", description="OAuth authentication flows"),
        Tag(name="Providers", description="Provider metadata"),
        Tag(name="Users", description="User and identity management"),
        Tag(name="Wizards", description="Wizard management for onboarding flows"),
    ]

    return OpenAPIConfig(
        title="Zondarr API",
        version="0.1.0",
        description="Unified invitation and user management for media servers",
        path="/docs",
        tags=tags,
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


def _create_cors_config(settings: Settings) -> CORSConfig | None:
    """Create CORS configuration if origins are specified.

    Returns:
        CORSConfig if cors_origins is non-empty, None otherwise.
    """
    if not settings.cors_origins:
        return None
    return CORSConfig(
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
        max_age=3600,
    )


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
    # Register all providers before loading settings
    # (settings loading reads env vars from provider metadata)
    register_all_providers()

    if settings is None:
        settings = load_settings()

    registry.set_settings(settings)

    # Collect route handlers dynamically from providers
    route_handlers: list[type] = [
        AuthController,
        HealthController,
        InvitationController,
        JoinController,
        OAuthController,
        ProviderController,
        ServerController,
        UserController,
        WizardController,
    ]

    for desc in registry.get_all_descriptors():
        if desc.route_handlers:
            route_handlers.extend(desc.route_handlers)

    # Create JWT cookie auth
    jwt_auth = create_jwt_auth(settings)

    return Litestar(
        route_handlers=route_handlers,
        lifespan=[db_lifespan, background_tasks_lifespan],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_db_session),
            "settings": Provide(provide_settings, sync_to_thread=False),
        },
        on_app_init=[jwt_auth.on_app_init],
        cors_config=_create_cors_config(settings),
        openapi_config=_create_openapi_config(),
        plugins=[
            StructlogPlugin(config=_create_structlog_config()),
        ],
        exception_handlers={
            AuthenticationError: authentication_error_handler,
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
            ExternalServiceError: external_service_error_handler,
            LitestarHTTPException: litestar_http_exception_handler,
            Exception: internal_error_handler,
        },
        debug=settings.debug,
    )


# Default application instance for Granian deployment
# Usage: granian zondarr.app:app --interface asgi
app = create_app()
