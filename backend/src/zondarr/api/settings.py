"""Settings controller for application-level configuration.

Provides endpoints for managing CSRF origin, sync/expiration intervals,
and system information. All endpoints require authentication.
"""

import platform
import sys
from collections.abc import Mapping, Sequence
from urllib.parse import urlparse

from litestar import Controller, Request, get, post, put
from litestar.datastructures import State
from litestar.di import Provide
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr import __version__
from zondarr.api.schemas import (
    AboutResponse,
    AllSettingsResponse,
    CsrfOriginResponse,
    CsrfOriginTestRequest,
    CsrfOriginTestResponse,
    CsrfOriginUpdate,
    ExpirationIntervalUpdate,
    SettingValue,
    SyncIntervalUpdate,
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

    @get(
        "",
        summary="Get all settings",
        description="Returns all application settings with their lock status.",
    )
    async def get_all_settings(
        self,
        settings_service: SettingsService,
    ) -> AllSettingsResponse:
        """Bundle all settings with lock status."""
        csrf_origin, csrf_locked = await settings_service.get_csrf_origin()
        sync_interval, sync_locked = await settings_service.get_sync_interval()
        exp_interval, exp_locked = await settings_service.get_expiration_interval()

        return AllSettingsResponse(
            csrf_origin=SettingValue(value=csrf_origin, is_locked=csrf_locked),
            sync_interval_seconds=SettingValue(
                value=str(sync_interval), is_locked=sync_locked
            ),
            expiration_check_interval_seconds=SettingValue(
                value=str(exp_interval), is_locked=exp_locked
            ),
        )

    @put(
        "/sync-interval",
        summary="Update sync interval",
        description="Set the media server sync interval. Fails if locked by environment variable.",
    )
    async def update_sync_interval(
        self,
        data: SyncIntervalUpdate,
        settings_service: SettingsService,
    ) -> SettingValue:
        """Update the sync interval setting."""
        _, is_locked = await settings_service.get_sync_interval()
        if is_locked:
            raise ValidationError(
                "Sync interval is set via SYNC_INTERVAL_SECONDS environment variable and cannot be changed through the API",
                field_errors={"sync_interval_seconds": ["Locked by environment variable"]},
            )
        _ = await settings_service.set_sync_interval(data.sync_interval_seconds)
        value, locked = await settings_service.get_sync_interval()
        return SettingValue(value=str(value), is_locked=locked)

    @put(
        "/expiration-interval",
        summary="Update expiration check interval",
        description="Set the invitation expiration check interval. Fails if locked by environment variable.",
    )
    async def update_expiration_interval(
        self,
        data: ExpirationIntervalUpdate,
        settings_service: SettingsService,
    ) -> SettingValue:
        """Update the expiration check interval setting."""
        _, is_locked = await settings_service.get_expiration_interval()
        if is_locked:
            raise ValidationError(
                "Expiration interval is set via EXPIRATION_CHECK_INTERVAL_SECONDS environment variable and cannot be changed through the API",
                field_errors={"expiration_check_interval_seconds": ["Locked by environment variable"]},
            )
        _ = await settings_service.set_expiration_interval(
            data.expiration_check_interval_seconds
        )
        value, locked = await settings_service.get_expiration_interval()
        return SettingValue(value=str(value), is_locked=locked)

    @get(
        "/about",
        summary="Get system information",
        description="Returns read-only system information for the about page.",
    )
    async def get_about(self, settings: Settings) -> AboutResponse:
        """Return system information."""
        db_url = settings.database_url
        if "sqlite" in db_url:
            db_engine = "SQLite"
        elif "postgresql" in db_url:
            db_engine = "PostgreSQL"
        else:
            db_engine = db_url.split("://")[0] if "://" in db_url else "Unknown"

        return AboutResponse(
            app_version=__version__,
            python_version=sys.version.split()[0],
            db_engine=db_engine,
            os_info=f"{platform.system()} {platform.release()}",
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
