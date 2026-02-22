"""AppSettingRepository for key-value settings data access.

Does NOT extend the generic Repository[T] base class because AppSetting
uses a string primary key rather than UUID.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.core.exceptions import RepositoryError
from zondarr.models.app_setting import AppSetting


class AppSettingRepository:
    """Repository for AppSetting entity operations.

    Provides get_by_key and upsert methods for the key-value settings table.

    Attributes:
        session: The async database session for executing queries.
    """

    session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, key: str) -> AppSetting | None:
        """Retrieve a setting by its key.

        Args:
            key: The setting key to look up.

        Returns:
            The AppSetting if found, None otherwise.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(AppSetting).where(AppSetting.key == key)
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get setting by key",
                operation="get_by_key",
                original=e,
            ) from e

    async def upsert(self, key: str, value: str | None) -> AppSetting:
        """Create or update a setting.

        If a setting with the given key exists, updates its value.
        Otherwise creates a new setting.

        Args:
            key: The setting key.
            value: The setting value (nullable).

        Returns:
            The created or updated AppSetting.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            existing = await self.get_by_key(key)
            if existing is not None:
                existing.value = value
                await self.session.flush()
                return existing

            setting = AppSetting(key=key, value=value)
            self.session.add(setting)
            await self.session.flush()
            return setting
        except RepositoryError:
            raise
        except Exception as e:
            raise RepositoryError(
                "Failed to upsert setting",
                operation="upsert",
                original=e,
            ) from e
