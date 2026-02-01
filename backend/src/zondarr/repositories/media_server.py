"""MediaServer repository for data access operations.

Provides specialized repository methods for MediaServer entities,
including filtering by enabled status. Extends the generic Repository
base class with MediaServer-specific queries.
"""

from collections.abc import Sequence
from typing import override

from sqlalchemy import select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.media_server import MediaServer
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
