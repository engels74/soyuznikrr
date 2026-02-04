"""InvitationRepository for invitation data access operations.

Provides specialized repository methods for Invitation entities,
including lookup by code, filtering active invitations, and
managing invitation usage. Extends the generic Repository base
class with Invitation-specific queries.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, override

from sqlalchemy import func, select
from sqlalchemy.sql import Select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.invitation import Invitation
from zondarr.repositories.base import Repository

# Type alias for valid sort fields
SortField = Literal["created_at", "expires_at", "use_count"]
SortOrder = Literal["asc", "desc"]


class InvitationRepository(Repository[Invitation]):
    """Repository for Invitation entity operations.

    Extends the generic Repository with Invitation-specific queries
    such as lookup by code, filtering active invitations, and
    managing invitation usage counts.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[Invitation]:
        """Return the Invitation model class.

        Returns:
            The Invitation SQLAlchemy model class.
        """
        return Invitation

    async def get_by_code(self, code: str) -> Invitation | None:
        """Retrieve an invitation by its unique code.

        Args:
            code: The unique invitation code to look up.

        Returns:
            The Invitation if found, None otherwise.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(Invitation).where(Invitation.code == code)
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get invitation by code",
                operation="get_by_code",
                original=e,
            ) from e

    async def get_active(self) -> Sequence[Invitation]:
        """Retrieve all active invitations.

        Returns invitations that are:
        - Enabled (enabled=True)
        - Not expired (expires_at is None or in the future)
        - Not exhausted (max_uses is None or use_count < max_uses)

        Returns:
            A sequence of active Invitation entities.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            now = datetime.now(UTC)
            result = await self.session.scalars(
                select(Invitation).where(
                    Invitation.enabled == True,  # noqa: E712
                    (Invitation.expires_at == None) | (Invitation.expires_at > now),  # noqa: E711
                    (Invitation.max_uses == None)  # noqa: E711
                    | (Invitation.use_count < Invitation.max_uses),
                )
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get active invitations",
                operation="get_active",
                original=e,
            ) from e

    async def increment_use_count(self, invitation: Invitation) -> Invitation:
        """Increment the use count of an invitation.

        Atomically increments the use_count field by 1.

        Args:
            invitation: The invitation to update.

        Returns:
            The updated Invitation with incremented use_count.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            invitation.use_count += 1
            await self.session.flush()
            return invitation
        except Exception as e:
            raise RepositoryError(
                "Failed to increment invitation use count",
                operation="increment_use_count",
                original=e,
            ) from e

    async def disable(self, invitation: Invitation) -> Invitation:
        """Disable an invitation.

        Sets the enabled flag to False, preventing further redemptions.

        Args:
            invitation: The invitation to disable.

        Returns:
            The updated Invitation with enabled=False.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            invitation.enabled = False
            await self.session.flush()
            return invitation
        except Exception as e:
            raise RepositoryError(
                "Failed to disable invitation",
                operation="disable",
                original=e,
            ) from e

    async def get_expired(self, now: datetime) -> Sequence[Invitation]:
        """Retrieve all expired but still enabled invitations.

        Returns invitations where expires_at is in the past and enabled=True.
        Used by the background expiration task to find invitations that need
        to be disabled.

        Args:
            now: The current timestamp to compare against expires_at.

        Returns:
            A sequence of expired Invitation entities that are still enabled.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(Invitation).where(
                    Invitation.enabled == True,  # noqa: E712
                    Invitation.expires_at != None,  # noqa: E711
                    Invitation.expires_at < now,
                )
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get expired invitations",
                operation="get_expired",
                original=e,
            ) from e

    async def update(self, invitation: Invitation) -> Invitation:
        """Persist changes to an invitation.

        Flushes any pending changes to the invitation entity to the database.

        Args:
            invitation: The invitation with updated fields.

        Returns:
            The updated Invitation entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.flush()
            return invitation
        except Exception as e:
            raise RepositoryError(
                "Failed to update invitation",
                operation="update",
                original=e,
            ) from e

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        enabled: bool | None = None,
        expired: bool | None = None,
        sort_by: SortField = "created_at",
        sort_order: SortOrder = "desc",
    ) -> tuple[Sequence[Invitation], int]:
        """Retrieve invitations with pagination, filtering, and sorting.

        Supports filtering by enabled status and expiration status,
        with configurable sorting and pagination.

        Args:
            page: Page number (1-indexed). Defaults to 1.
            page_size: Number of items per page. Defaults to 50.
            enabled: Filter by enabled status. None means no filter.
            expired: Filter by expiration status. None means no filter.
                True = only expired, False = only non-expired.
            sort_by: Field to sort by. One of: created_at, expires_at, use_count.
            sort_order: Sort direction. One of: asc, desc.

        Returns:
            A tuple of (items, total_count) where items is the page of
            Invitation entities and total_count is the total matching records.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            # Build base query with filters
            base_query = self._build_filtered_query(enabled=enabled, expired=expired)

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

            # Execute query
            result = await self.session.scalars(paginated_query)
            items = result.all()

            return items, total
        except Exception as e:
            raise RepositoryError(
                "Failed to list paginated invitations",
                operation="list_paginated",
                original=e,
            ) from e

    def _build_filtered_query(
        self,
        *,
        enabled: bool | None = None,
        expired: bool | None = None,
    ) -> Select[tuple[Invitation]]:
        """Build a filtered query for invitations.

        Args:
            enabled: Filter by enabled status. None means no filter.
            expired: Filter by expiration status. None means no filter.

        Returns:
            A SQLAlchemy Select statement with filters applied.
        """
        query = select(Invitation)

        # Filter by enabled status
        if enabled is not None:
            query = query.where(Invitation.enabled == enabled)

        # Filter by expiration status
        if expired is not None:
            now = datetime.now(UTC)
            if expired:
                # Only expired: expires_at is not None AND expires_at <= now
                query = query.where(
                    Invitation.expires_at != None,  # noqa: E711
                    Invitation.expires_at <= now,
                )
            else:
                # Only non-expired: expires_at is None OR expires_at > now
                query = query.where(
                    (Invitation.expires_at == None) | (Invitation.expires_at > now)  # noqa: E711
                )

        return query

    def _get_sort_column(self, sort_by: SortField):
        """Get the SQLAlchemy column for sorting.

        Args:
            sort_by: The field name to sort by.

        Returns:
            The corresponding SQLAlchemy column.
        """
        sort_columns = {
            "created_at": Invitation.created_at,
            "expires_at": Invitation.expires_at,
            "use_count": Invitation.use_count,
        }
        return sort_columns[sort_by]

    @override
    async def delete(self, entity: Invitation) -> None:
        """Delete an invitation from the database.

        Removes the invitation without cascading to User records.
        Users created from this invitation retain their invitation_id
        reference but the invitation itself is removed.

        Args:
            entity: The invitation to delete.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.delete(entity)
            await self.session.flush()
        except Exception as e:
            raise RepositoryError(
                "Failed to delete invitation",
                operation="delete",
                original=e,
            ) from e
