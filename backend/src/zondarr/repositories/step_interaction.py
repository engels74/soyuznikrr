"""StepInteractionRepository for step interaction data access operations.

Provides specialized repository methods for StepInteraction entities.
Extends the generic Repository base class with StepInteraction-specific queries.
"""

from collections.abc import Sequence
from typing import override
from uuid import UUID

from sqlalchemy import select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.wizard import StepInteraction
from zondarr.repositories.base import Repository


class StepInteractionRepository(Repository[StepInteraction]):
    """Repository for StepInteraction entity operations.

    Extends the generic Repository with StepInteraction-specific queries
    such as fetching interactions by step ID.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[StepInteraction]:
        """Return the StepInteraction model class.

        Returns:
            The StepInteraction SQLAlchemy model class.
        """
        return StepInteraction

    async def get_by_step_id(self, step_id: UUID, /) -> Sequence[StepInteraction]:
        """Retrieve all interactions for a step, ordered by display_order.

        Args:
            step_id: The UUID of the step (positional-only).

        Returns:
            A sequence of StepInteraction entities ordered by display_order.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(StepInteraction)
                .where(StepInteraction.step_id == step_id)
                .order_by(StepInteraction.display_order)
            )
            return result.all()
        except Exception as e:
            raise RepositoryError(
                "Failed to get interactions by step_id",
                operation="get_by_step_id",
                original=e,
            ) from e

    async def update(self, interaction: StepInteraction, /) -> StepInteraction:
        """Persist changes to a step interaction.

        Flushes any pending changes to the interaction entity to the database.

        Args:
            interaction: The interaction with updated fields (positional-only).

        Returns:
            The updated StepInteraction entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.flush()
            return interaction
        except Exception as e:
            raise RepositoryError(
                "Failed to update step interaction",
                operation="update",
                original=e,
            ) from e
