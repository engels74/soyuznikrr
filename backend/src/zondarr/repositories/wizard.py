"""WizardRepository for wizard data access operations.

Provides specialized repository methods for Wizard entities,
including eager loading of steps, pagination, and filtering.
Extends the generic Repository base class with Wizard-specific queries.
"""

from collections.abc import Sequence
from typing import Literal, override
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from zondarr.core.exceptions import RepositoryError
from zondarr.models.wizard import Wizard, WizardStep
from zondarr.repositories.base import Repository

# Type alias for valid sort fields
SortField = Literal["created_at", "name"]
SortOrder = Literal["asc", "desc"]


class WizardRepository(Repository[Wizard]):
    """Repository for Wizard entity operations.

    Extends the generic Repository with Wizard-specific queries
    such as eager loading of steps, pagination, and filtering
    by enabled status.

    Attributes:
        session: The async database session for executing queries.
    """

    @property
    @override
    def _model_class(self) -> type[Wizard]:
        """Return the Wizard model class.

        Returns:
            The Wizard SQLAlchemy model class.
        """
        return Wizard

    async def get_with_steps(self, wizard_id: UUID, /) -> Wizard | None:
        """Retrieve a wizard by ID with all steps eagerly loaded.

        Args:
            wizard_id: The UUID of the wizard to retrieve (positional-only).

        Returns:
            The Wizard with steps if found, None otherwise.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            result = await self.session.scalars(
                select(Wizard)
                .options(
                    selectinload(Wizard.steps).selectinload(WizardStep.interactions)
                )
                .where(Wizard.id == wizard_id)
            )
            return result.first()
        except Exception as e:
            raise RepositoryError(
                "Failed to get wizard with steps",
                operation="get_with_steps",
                original=e,
            ) from e

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        enabled: bool | None = None,
        sort_by: SortField = "created_at",
        sort_order: SortOrder = "desc",
    ) -> tuple[Sequence[Wizard], int]:
        """Retrieve wizards with pagination, filtering, and sorting.

        Supports filtering by enabled status with configurable
        sorting and pagination.

        Args:
            page: Page number (1-indexed). Defaults to 1.
            page_size: Number of items per page. Defaults to 50.
            enabled: Filter by enabled status. None means no filter.
            sort_by: Field to sort by. One of: created_at, name.
            sort_order: Sort direction. One of: asc, desc.

        Returns:
            A tuple of (items, total_count) where items is the page of
            Wizard entities and total_count is the total matching records.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            # Build base query with filters
            base_query = self._build_filtered_query(enabled=enabled)

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
                "Failed to list paginated wizards",
                operation="list_paginated",
                original=e,
            ) from e

    async def update(self, wizard: Wizard, /) -> Wizard:
        """Persist changes to a wizard.

        Flushes any pending changes to the wizard entity to the database.

        Args:
            wizard: The wizard with updated fields (positional-only).

        Returns:
            The updated Wizard entity.

        Raises:
            RepositoryError: If the database operation fails.
        """
        try:
            await self.session.flush()
            return wizard
        except Exception as e:
            raise RepositoryError(
                "Failed to update wizard",
                operation="update",
                original=e,
            ) from e

    def _build_filtered_query(
        self,
        *,
        enabled: bool | None = None,
    ) -> Select[tuple[Wizard]]:
        """Build a filtered query for wizards.

        Args:
            enabled: Filter by enabled status. None means no filter.

        Returns:
            A SQLAlchemy Select statement with filters applied.
        """
        query = select(Wizard)

        # Filter by enabled status
        if enabled is not None:
            query = query.where(Wizard.enabled == enabled)

        return query

    def _get_sort_column(self, sort_by: SortField):
        """Get the SQLAlchemy column for sorting.

        Args:
            sort_by: The field name to sort by.

        Returns:
            The corresponding SQLAlchemy column.
        """
        sort_columns = {
            "created_at": Wizard.created_at,
            "name": Wizard.name,
        }
        return sort_columns[sort_by]
