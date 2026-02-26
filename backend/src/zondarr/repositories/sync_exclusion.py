"""SyncExclusionRepository for managing sync exclusion records.

Provides methods to add, query, and clean up sync exclusions that
prevent deleted users from being re-imported during background sync.
"""

from datetime import UTC, datetime, timedelta
from typing import override
from uuid import UUID

from sqlalchemy import delete, select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.sync_exclusion import SyncExclusion
from zondarr.repositories.base import Repository


class SyncExclusionRepository(Repository[SyncExclusion]):
    """Repository for SyncExclusion entity operations.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[SyncExclusion]:
        return SyncExclusion

    async def get_excluded_ids(self, media_server_id: UUID) -> set[str]:
        """Return set of excluded external_user_ids for a server.

        Args:
            media_server_id: The UUID of the media server.

        Returns:
            Set of external_user_id strings that should be excluded from sync.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(SyncExclusion.external_user_id).where(
                    SyncExclusion.media_server_id == media_server_id
                )
            )
            return set(result.all())
        except Exception as e:
            raise RepositoryError(
                "Failed to get excluded IDs",
                operation="get_excluded_ids",
                original=e,
            ) from e

    async def add_exclusion(
        self, external_user_id: str, media_server_id: UUID
    ) -> SyncExclusion:
        """Add a sync exclusion for an external user on a server.

        Args:
            external_user_id: The user's ID on the media server.
            media_server_id: The UUID of the media server.

        Returns:
            The created SyncExclusion entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        exclusion = SyncExclusion(
            external_user_id=external_user_id,
            media_server_id=media_server_id,
        )
        return await self.create(exclusion)

    async def remove_exclusion(
        self, external_user_id: str, media_server_id: UUID
    ) -> bool:
        """Remove a sync exclusion.

        Args:
            external_user_id: The user's ID on the media server.
            media_server_id: The UUID of the media server.

        Returns:
            True if an exclusion was removed, False if not found.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.execute(
                delete(SyncExclusion).where(
                    SyncExclusion.external_user_id == external_user_id,
                    SyncExclusion.media_server_id == media_server_id,
                )
            )
            await self.session.flush()
            row_count: int = result.rowcount  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
            return row_count > 0
        except Exception as e:
            raise RepositoryError(
                "Failed to remove exclusion",
                operation="remove_exclusion",
                original=e,
            ) from e

    async def cleanup_old(self, days: int = 30) -> int:
        """Remove exclusions older than N days.

        Args:
            days: Maximum age in days. Defaults to 30.

        Returns:
            Count of exclusions removed.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            result = await self.session.execute(
                delete(SyncExclusion).where(SyncExclusion.created_at < cutoff)
            )
            await self.session.flush()
            row_count: int = result.rowcount  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]
            return row_count
        except Exception as e:
            raise RepositoryError(
                "Failed to cleanup old exclusions",
                operation="cleanup_old",
                original=e,
            ) from e
