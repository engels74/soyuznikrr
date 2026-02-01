"""InvitationRepository for invitation data access operations.

Provides specialized repository methods for Invitation entities,
including lookup by code, filtering active invitations, and
managing invitation usage. Extends the generic Repository base
class with Invitation-specific queries.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import override

from sqlalchemy import select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.invitation import Invitation
from zondarr.repositories.base import Repository


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
