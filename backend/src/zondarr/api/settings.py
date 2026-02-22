"""Settings controller for application-level configuration.

Provides endpoints for managing CSRF origin and other application settings.
All endpoints require authentication (not in AUTH_EXCLUDE_PATHS).
"""

from collections.abc import Mapping, Sequence

from litestar import Controller, get, put
from litestar.di import Provide
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.api.schemas import CsrfOriginResponse, CsrfOriginUpdate
from zondarr.config import Settings
from zondarr.core.exceptions import ValidationError
from zondarr.repositories.app_setting import AppSettingRepository
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
    ) -> CsrfOriginResponse:
        """Update the CSRF origin in the database."""
        # Check if locked by env var
        _, is_locked = await settings_service.get_csrf_origin()
        if is_locked:
            raise ValidationError(
                "CSRF origin is set via CSRF_ORIGIN environment variable and cannot be changed through the API",
                field_errors={"csrf_origin": ["Locked by environment variable"]},
            )

        await settings_service.set_csrf_origin(data.csrf_origin)
        origin, locked = await settings_service.get_csrf_origin()
        return CsrfOriginResponse(csrf_origin=origin, is_locked=locked)
