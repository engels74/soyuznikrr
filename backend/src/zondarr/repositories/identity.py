"""IdentityRepository for identity data access operations.

Provides specialized repository methods for Identity entities,
including update operations, eager loading with users, and cascade
deletion logic. Extends the generic Repository base class with
Identity-specific functionality.
"""

from typing import override
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from zondarr.core.exceptions import RepositoryError
from zondarr.models.identity import Identity
from zondarr.repositories.base import Repository


class IdentityRepository(Repository[Identity]):
    """Repository for Identity entity operations.

    Extends the generic Repository with Identity-specific operations
    such as update, eager loading with users, and cascade deletion.
    Inherits get_by_id, get_all, create, and delete from the base
    Repository class.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[Identity]:
        """Return the Identity model class.

        Returns:
            The Identity SQLAlchemy model class.
        """
        return Identity

    async def update(self, identity: Identity) -> Identity:
        """Update an existing identity.

        Flushes changes to the database to persist modifications
        made to the identity entity.

        Args:
            identity: The identity entity with updated values.

        Returns:
            The updated Identity entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.flush()
            return identity
        except Exception as e:
            raise RepositoryError(
                "Failed to update identity",
                operation="update",
                original=e,
            ) from e

    async def get_with_users(self, identity_id: UUID, /) -> Identity | None:
        """Retrieve an identity with all linked users eagerly loaded.

        Uses selectinload to eagerly fetch all User records associated
        with the identity in a single query, avoiding N+1 query issues.

        Validates: Requirement 17.2 - WHEN returning user details THEN
        the System SHALL include the parent Identity with all linked Users.

        Args:
            identity_id: The UUID of the identity to retrieve (positional-only).

        Returns:
            The Identity with users loaded if found, None otherwise.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(Identity)
                .where(Identity.id == identity_id)
                .options(selectinload(Identity.users))
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get identity with users",
                operation="get_with_users",
                original=e,
            ) from e

    async def delete_if_no_users(self, identity_id: UUID, /) -> bool:
        """Delete an identity only if it has no remaining users.

        Checks if the identity has any linked User records. If no users
        exist, the identity is deleted. This implements the cascade logic
        for cleaning up orphaned identities.

        Validates: Requirement 19.5 - WHEN the last User for an Identity
        is deleted THEN the System SHALL also delete the Identity.

        Args:
            identity_id: The UUID of the identity to check and delete
                (positional-only).

        Returns:
            True if the identity was deleted, False if it still has users
            or was not found.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            # Get identity with users to check count
            identity = await self.get_with_users(identity_id)
            if identity is None:
                return False

            # Only delete if no users remain
            if len(identity.users) == 0:
                await self.session.delete(identity)
                await self.session.flush()
                return True

            return False
        except RepositoryError:
            # Re-raise RepositoryError from get_with_users
            raise
        except Exception as e:
            raise RepositoryError(
                "Failed to delete identity if no users",
                operation="delete_if_no_users",
                original=e,
            ) from e
