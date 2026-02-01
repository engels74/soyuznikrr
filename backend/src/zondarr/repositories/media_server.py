"""MediaServer repository for data access operations.

Provides specialized repository methods for MediaServer entities,
including filtering by enabled status. Extends the generic Repository
base class with MediaServer-specific queries.
"""

from collections.abc import Sequence
from typing import override
from uuid import UUID

from sqlalchemy import select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.media_server import Library, MediaServer
from zondarr.repositories.base import Repository


class MediaServerRepository(Repository[MediaServer]):
    """Repository for MediaServer entity operations.

    Extends the generic Repository with MediaServer-specific queries
    such as filtering by enabled status.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[MediaServer]:
        """Return the MediaServer model class.

        Returns:
            The MediaServer SQLAlchemy model class.
        """
        return MediaServer

    async def get_enabled(self) -> Sequence[MediaServer]:
        """Retrieve all enabled media servers.

        Returns only media servers where enabled=True, useful for
        operations that should only target active servers.

        Returns:
            A sequence of enabled MediaServer entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(MediaServer).where(MediaServer.enabled == True)  # noqa: E712
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get enabled media servers",
                operation="get_enabled",
                original=e,
            ) from e

    async def get_by_ids(self, ids: Sequence[UUID], /) -> Sequence[MediaServer]:
        """Retrieve media servers by their IDs.

        Args:
            ids: Sequence of UUIDs to look up (positional-only).

        Returns:
            A sequence of MediaServer entities matching the provided IDs.

        Raises:
            RepositoryError: If the database operation fails.
        """
        if not ids:
            return []

        try:
            result = await self.session.scalars(
                select(MediaServer).where(MediaServer.id.in_(ids))
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get media servers by IDs",
                operation="get_by_ids",
                original=e,
            ) from e

    async def get_enabled_by_ids(self, ids: Sequence[UUID], /) -> Sequence[MediaServer]:
        """Retrieve enabled media servers by their IDs.

        Args:
            ids: Sequence of UUIDs to look up (positional-only).

        Returns:
            A sequence of enabled MediaServer entities matching the provided IDs.

        Raises:
            RepositoryError: If the database operation fails.
        """
        if not ids:
            return []

        try:
            result = await self.session.scalars(
                select(MediaServer).where(
                    MediaServer.id.in_(ids),
                    MediaServer.enabled == True,  # noqa: E712
                )
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get enabled media servers by IDs",
                operation="get_enabled_by_ids",
                original=e,
            ) from e

    async def get_libraries_by_ids(
        self, library_ids: Sequence[UUID], /
    ) -> Sequence[Library]:
        """Retrieve libraries by their IDs.

        Args:
            library_ids: Sequence of library UUIDs to look up (positional-only).

        Returns:
            A sequence of Library entities matching the provided IDs.

        Raises:
            RepositoryError: If the database operation fails.
        """
        if not library_ids:
            return []

        try:
            result = await self.session.scalars(
                select(Library).where(Library.id.in_(library_ids))
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get libraries by IDs",
                operation="get_libraries_by_ids",
                original=e,
            ) from e
