"""Settings controller for application-level configuration.

Provides endpoints for managing CSRF origin and other application settings.
All endpoints require authentication.
"""

from collections.abc import Mapping, Sequence
from urllib.parse import urlparse

from litestar import Controller, Request, get, post, put
from litestar.datastructures import State
from litestar.di import Provide
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.api.schemas import (
    CsrfOriginResponse,
    CsrfOriginTestRequest,
    CsrfOriginTestResponse,
    CsrfOriginUpdate,
)
from zondarr.config import Settings
from zondarr.core.exceptions import ValidationError
from zondarr.repositories.admin import AdminAccountRepository
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.onboarding import OnboardingService
from zondarr.services.settings import SettingsService


async def provide_app_setting_repository(session: AsyncSession) -> AppSettingRepository:
    """Create AppSettingRepository from injected session."""
    return AppSettingRepository(session)


async def provide_settings_service(
    app_setting_repository: AppSettingRepository,
    settings: Settings,
) -> SettingsService:
    """Create SettingsService from injected dependencies."""
    return SettingsService(app_setting_repository, settings=settings)


class SettingsController(Controller):
    """Controller for application settings endpoints."""

    path: str = "/api/v1/settings"
    tags: Sequence[str] | None = ["Settings"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "app_setting_repository": Provide(provide_app_setting_repository),
        "settings_service": Provide(provide_settings_service),
    }

    @get(
        "/csrf-origin",
        summary="Get CSRF origin setting",
        description="Returns the current CSRF origin and whether it is locked by an environment variable.",
    )
    async def get_csrf_origin(
        self,
        settings_service: SettingsService,
    ) -> CsrfOriginResponse:
        """Get the current CSRF origin configuration."""
        origin, is_locked = await settings_service.get_csrf_origin()
        return CsrfOriginResponse(csrf_origin=origin, is_locked=is_locked)

    @put(
        "/csrf-origin",
        summary="Update CSRF origin setting",
        description="Set or clear the CSRF origin. Fails if the value is locked by an environment variable.",
    )
    async def update_csrf_origin(
        self,
        data: CsrfOriginUpdate,
        settings_service: SettingsService,
        app_setting_repository: AppSettingRepository,
        session: AsyncSession,
    ) -> CsrfOriginResponse:
        """Update the CSRF origin in the database."""
        # Check if locked by env var
        _, is_locked = await settings_service.get_csrf_origin()
        if is_locked:
            raise ValidationError(
                "CSRF origin is set via CSRF_ORIGIN environment variable and cannot be changed through the API",
                field_errors={"csrf_origin": ["Locked by environment variable"]},
            )

        _ = await settings_service.set_csrf_origin(data.csrf_origin)
        onboarding_service = OnboardingService(
            admin_repo=AdminAccountRepository(session),
            app_setting_repo=app_setting_repository,
        )
        _ = await onboarding_service.complete_security_step()
        origin, locked = await settings_service.get_csrf_origin()
        return CsrfOriginResponse(csrf_origin=origin, is_locked=locked)

    @post(
        "/csrf-origin/test",
        summary="Test CSRF origin against browser",
        description="Compares the provided origin against the request's Origin header to verify they match.",
    )
    async def test_csrf_origin(
        self,
        data: CsrfOriginTestRequest,
        request: Request[object, object, State],
    ) -> CsrfOriginTestResponse:
        """Test whether the provided CSRF origin matches the browser's actual Origin header."""
        request_origin = self._extract_request_origin(request)
        if request_origin is None:
            return CsrfOriginTestResponse(
                success=False,
                message=(
                    "Could not determine your browser's origin. No Origin or Referer "
                    "header was sent. If you are using a proxy, ensure it forwards "
                    "Origin and Referer headers."
                ),
                request_origin=None,
            )

        # Normalize both origins: lowercase, strip trailing slashes
        normalized_provided = data.origin.lower().rstrip("/")
        normalized_request = request_origin.lower().rstrip("/")

        if normalized_provided == normalized_request:
            return CsrfOriginTestResponse(
                success=True,
                message="Origin matches — CSRF protection will work correctly.",
                request_origin=request_origin,
            )

        return CsrfOriginTestResponse(
            success=False,
            message=f"Origin mismatch: you entered '{data.origin}' but your browser sent '{request_origin}'.",
            request_origin=request_origin,
        )

    @staticmethod
    def _extract_request_origin(request: Request[object, object, State]) -> str | None:
        """Extract the origin from the request's Origin or Referer header."""
        origin = request.headers.get("origin")
        if origin and origin.lower() != "null":
            return origin

        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.hostname:
                host = parsed.hostname
                if ":" in host:
                    host = f"[{host}]"
                default_ports = {"http": 80, "https": 443}
                port_suffix = (
                    f":{parsed.port}"
                    if parsed.port and parsed.port != default_ports.get(parsed.scheme)
                    else ""
                )
                return f"{parsed.scheme}://{host}{port_suffix}"

        return None
