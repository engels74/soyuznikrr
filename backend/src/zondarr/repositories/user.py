"""UserRepository for user data access operations.

Provides specialized repository methods for User entities,
including queries by identity and media server. Extends the generic
Repository base class with User-specific functionality.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, override
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.identity import User
from zondarr.repositories.base import Repository

# Type alias for valid sort fields
UserSortField = Literal["created_at", "username", "expires_at"]
SortOrder = Literal["asc", "desc"]


class UserRepository(Repository[User]):
    """Repository for User entity operations.

    Extends the generic Repository with User-specific queries
    such as filtering by identity or media server. Inherits
    get_by_id, get_all, create, and delete from the base
    Repository class.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[User]:
        """Return the User model class.

        Returns:
            The User SQLAlchemy model class.
        """
        return User

    async def get_by_identity(self, identity_id: UUID) -> Sequence[User]:
        """Retrieve all users belonging to a specific identity.

        Args:
            identity_id: The UUID of the identity to filter by.

        Returns:
            A sequence of User entities linked to the identity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(User).where(User.identity_id == identity_id)
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get users by identity",
                operation="get_by_identity",
                original=e,
            ) from e

    async def get_by_server(self, media_server_id: UUID) -> Sequence[User]:
        """Retrieve all users on a specific media server.

        Args:
            media_server_id: The UUID of the media server to filter by.

        Returns:
            A sequence of User entities on the media server.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(User).where(User.media_server_id == media_server_id)
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get users by server",
                operation="get_by_server",
                original=e,
            ) from e

    async def get_by_external_and_server(
        self, external_user_id: str, media_server_id: UUID
    ) -> User | None:
        """Retrieve a user by external user ID and media server.

        Queries by the compound key (external_user_id, media_server_id)
        to find a specific user on a specific server.

        Args:
            external_user_id: The user's ID on the media server.
            media_server_id: The UUID of the media server.

        Returns:
            The User entity if found, None otherwise.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(User).where(
                    User.external_user_id == external_user_id,
                    User.media_server_id == media_server_id,
                )
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get user by external ID and server",
                operation="get_by_external_and_server",
                original=e,
            ) from e

    async def update(self, user: User) -> User:
        """Update an existing user.

        Flushes changes to the database to persist modifications
        made to the user entity.

        Args:
            user: The user entity with updated values.

        Returns:
            The updated User entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.flush()
            return user
        except Exception as e:
            raise RepositoryError(
                "Failed to update user",
                operation="update",
                original=e,
            ) from e

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        media_server_id: UUID | None = None,
        invitation_id: UUID | None = None,
        enabled: bool | None = None,
        expired: bool | None = None,
        sort_by: UserSortField = "created_at",
        sort_order: SortOrder = "desc",
    ) -> tuple[Sequence[User], int]:
        """Retrieve users with pagination, filtering, and sorting.

        Supports filtering by media_server_id, invitation_id, enabled status,
        and expiration status. Supports sorting by created_at, username, and
        expires_at.

        Args:
            page: Page number (1-indexed). Defaults to 1.
            page_size: Number of items per page. Defaults to 50.
            media_server_id: Filter by media server ID. None means no filter.
            invitation_id: Filter by invitation ID. None means no filter.
            enabled: Filter by enabled status. None means no filter.
            expired: Filter by expiration status. None means no filter.
                True = only expired, False = only non-expired.
            sort_by: Field to sort by. One of: created_at, username, expires_at.
            sort_order: Sort direction. One of: asc, desc.

        Returns:
            A tuple of (items, total_count) where items is the page of
            User entities and total_count is the total matching records.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            # Build base query with filters
            base_query = self._build_filtered_query(
                media_server_id=media_server_id,
                invitation_id=invitation_id,
                enabled=enabled,
                expired=expired,
            )

            # Get total count
            count_query = select(func.count()).select_from(base_query.subquery())
            total = await self.session.scalar(count_query) or 0

            # Apply sorting
            sort_column = self._get_sort_column(sort_by)
            if sort_order == "desc":
                base_query = base_query.order_by(sort_column.desc())
            else:
                base_query = base_query.order_by(sort_column.asc())

            # Apply pagination
            offset = (page - 1) * page_size
            paginated_query = base_query.offset(offset).limit(page_size)

            # Add eager loading for relationships
            paginated_query = paginated_query.options(
                selectinload(User.identity),
                selectinload(User.media_server),
                selectinload(User.invitation),
            )

            # Execute query
            result = await self.session.scalars(paginated_query)
            items = result.all()

            return items, total
        except Exception as e:
            raise RepositoryError(
                "Failed to list paginated users",
                operation="list_paginated",
                original=e,
            ) from e

    def _build_filtered_query(
        self,
        *,
        media_server_id: UUID | None = None,
        invitation_id: UUID | None = None,
        enabled: bool | None = None,
        expired: bool | None = None,
    ) -> Select[tuple[User]]:
        """Build a filtered query for users.

        Args:
            media_server_id: Filter by media server ID. None means no filter.
            invitation_id: Filter by invitation ID. None means no filter.
            enabled: Filter by enabled status. None means no filter.
            expired: Filter by expiration status. None means no filter.

        Returns:
            A SQLAlchemy Select statement with filters applied.
        """
        query = select(User)

        # Filter by media server ID
        if media_server_id is not None:
            query = query.where(User.media_server_id == media_server_id)

        # Filter by invitation ID
        if invitation_id is not None:
            query = query.where(User.invitation_id == invitation_id)

        # Filter by enabled status
        if enabled is not None:
            query = query.where(User.enabled == enabled)

        # Filter by expiration status
        if expired is not None:
            now = datetime.now(UTC)
            if expired:
                # Only expired: expires_at is not None AND expires_at <= now
                query = query.where(
                    User.expires_at != None,  # noqa: E711
                    User.expires_at <= now,
                )
            else:
                # Only non-expired: expires_at is None OR expires_at > now
                query = query.where(
                    (User.expires_at == None) | (User.expires_at > now)  # noqa: E711
                )

        return query

    def _get_sort_column(self, sort_by: UserSortField):
        """Get the SQLAlchemy column for sorting.

        Args:
            sort_by: The field name to sort by.

        Returns:
            The corresponding SQLAlchemy column.
        """
        sort_columns = {
            "created_at": User.created_at,
            "username": User.username,
            "expires_at": User.expires_at,
        }
        return sort_columns[sort_by]
