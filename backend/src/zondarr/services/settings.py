"""Settings service for managing application settings.

Implements the env-var-overrides-DB pattern: environment variable values
take precedence over database values and are marked as "locked".
"""

from zondarr.config import Settings
from zondarr.models.app_setting import AppSetting
from zondarr.repositories.app_setting import AppSettingRepository

# Database keys for settings
CSRF_ORIGIN_KEY = "csrf_origin"


class SettingsService:
    """Service for managing application-level settings.

    Follows the env-var-overrides-DB pattern: if a setting is defined
    via environment variable, it takes precedence and is marked as locked.

    Attributes:
        repository: The AppSettingRepository for data access.
        settings: Optional application Settings for env var checks.
    """

    repository: AppSettingRepository
    settings: Settings | None

    def __init__(
        self,
        repository: AppSettingRepository,
        /,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings

    async def get_csrf_origin(self) -> tuple[str | None, bool]:
        """Get the CSRF origin setting.

        Checks environment variable first (via Settings), then falls back
        to the database value.

        Returns:
            A tuple of (origin_value, is_locked).
            is_locked is True when the value comes from an environment variable.
        """
        # Env var takes precedence
        if self.settings is not None and self.settings.csrf_origin:
            return self.settings.csrf_origin, True

        # Fall back to DB
        setting = await self.repository.get_by_key(CSRF_ORIGIN_KEY)
        if setting is not None and setting.value:
            return setting.value, False

        return None, False

    async def set_csrf_origin(self, origin: str | None) -> AppSetting:
        """Set the CSRF origin in the database.

        Args:
            origin: The origin URL to set, or None to clear.

        Returns:
            The created or updated AppSetting.
        """
        return await self.repository.upsert(CSRF_ORIGIN_KEY, origin)
