"""WizardController for wizard management endpoints.

Provides REST endpoints for wizard CRUD operations:
- POST /api/v1/wizards - Create a new wizard
- GET /api/v1/wizards - List wizards with pagination
- GET /api/v1/wizards/{id} - Get wizard details with steps
- PATCH /api/v1/wizards/{id} - Update a wizard
- DELETE /api/v1/wizards/{id} - Delete a wizard
- POST /api/v1/wizards/{id}/steps - Create a step
- PATCH /api/v1/wizards/{id}/steps/{step_id} - Update a step
- DELETE /api/v1/wizards/{id}/steps/{step_id} - Delete a step
- POST /api/v1/wizards/{id}/steps/{step_id}/reorder - Reorder a step
- POST /api/v1/wizards/{id}/steps/{step_id}/interactions - Add interaction
- PATCH /api/v1/wizards/{id}/steps/{step_id}/interactions/{iid} - Update interaction
- DELETE /api/v1/wizards/{id}/steps/{step_id}/interactions/{iid} - Remove interaction
- POST /api/v1/wizards/validate-step - Validate step completion (public)

Uses Litestar Controller pattern with dependency injection for services.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from litestar.types import AnyCallable
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.models.wizard import Wizard
from zondarr.repositories.step_interaction import StepInteractionRepository
from zondarr.repositories.wizard import WizardRepository
from zondarr.repositories.wizard_step import WizardStepRepository
from zondarr.services.wizard import WizardService

from .converters import step_interaction_to_response, wizard_step_to_response
from .schemas import (
    StepInteractionCreate,
    StepInteractionResponse,
    StepInteractionUpdate,
    StepReorderRequest,
    StepValidationRequest,
    StepValidationResponse,
    WizardCreate,
    WizardDetailResponse,
    WizardListResponse,
    WizardResponse,
    WizardStepCreate,
    WizardStepResponse,
    WizardStepUpdate,
    WizardUpdate,
)


async def provide_wizard_repository(
    session: AsyncSession,
) -> WizardRepository:
    """Provide WizardRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured WizardRepository instance.
    """
    return WizardRepository(session)


async def provide_wizard_step_repository(
    session: AsyncSession,
) -> WizardStepRepository:
    """Provide WizardStepRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured WizardStepRepository instance.
    """
    return WizardStepRepository(session)


async def provide_step_interaction_repository(
    session: AsyncSession,
) -> StepInteractionRepository:
    """Provide StepInteractionRepository instance.

    Args:
        session: Database session from DI.

    Returns:
        Configured StepInteractionRepository instance.
    """
    return StepInteractionRepository(session)


async def provide_wizard_service(
    wizard_repository: WizardRepository,
    step_repository: WizardStepRepository,
    interaction_repository: StepInteractionRepository,
) -> WizardService:
    """Provide WizardService instance.

    Args:
        wizard_repository: WizardRepository from DI.
        step_repository: WizardStepRepository from DI.
        interaction_repository: StepInteractionRepository from DI.

    Returns:
        Configured WizardService instance.
    """
    return WizardService(wizard_repository, step_repository, interaction_repository)


class WizardController(Controller):
    """Controller for wizard management endpoints.

    Provides CRUD operations for wizards, steps, and interactions,
    plus a public validation endpoint for step completion verification.
    """

    path: str = "/api/v1/wizards"
    tags: Sequence[str] | None = ["Wizards"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "wizard_repository": Provide(provide_wizard_repository),
        "step_repository": Provide(provide_wizard_step_repository),
        "interaction_repository": Provide(provide_step_interaction_repository),
        "wizard_service": Provide(provide_wizard_service),
    }

    # ==================== Wizard CRUD ====================

    @post(
        "/",
        status_code=HTTP_201_CREATED,
        summary="Create wizard",
        description="Create a new wizard with configurable settings.",
    )
    async def create_wizard(
        self,
        data: WizardCreate,
        wizard_service: WizardService,
    ) -> WizardResponse:
        """Create a new wizard.

        Args:
            data: The wizard creation request.
            wizard_service: WizardService from DI.

        Returns:
            The created wizard.

        Raises:
            ValidationError: If the name is empty.
        """
        wizard = await wizard_service.create_wizard(
            name=data.name,
            description=data.description,
            enabled=data.enabled,
        )
        return self._to_response(wizard)

    @get(
        "/",
        summary="List wizards",
        description="List wizards with pagination and filtering.",
    )
    async def list_wizards(
        self,
        wizard_service: WizardService,
        page: Annotated[
            int,
            Parameter(
                ge=1,
                description="Page number (1-indexed)",
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Parameter(
                ge=1,
                le=100,
                description="Number of items per page (max 100)",
            ),
        ] = 50,
        enabled: Annotated[
            bool | None,
            Parameter(description="Filter by enabled status"),
        ] = None,
    ) -> WizardListResponse:
        """List wizards with pagination.

        Args:
            wizard_service: WizardService from DI.
            page: Page number (1-indexed).
            page_size: Number of items per page.
            enabled: Filter by enabled status.

        Returns:
            Paginated list of wizards.
        """
        items, total = await wizard_service.list_wizards(
            page=page,
            page_size=page_size,
            enabled=enabled,
        )

        response_items = [self._to_response(wizard) for wizard in items]

        return WizardListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )

    @get(
        "/{wizard_id:uuid}",
        summary="Get wizard details",
        description="Retrieve complete details for a wizard including all steps.",
    )
    async def get_wizard(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        wizard_service: WizardService,
    ) -> WizardDetailResponse:
        """Get wizard details by ID.

        Args:
            wizard_id: The UUID of the wizard.
            wizard_service: WizardService from DI.

        Returns:
            Complete wizard details including steps.

        Raises:
            NotFoundError: If the wizard does not exist.
        """
        wizard = await wizard_service.get_wizard(wizard_id)
        return self._to_detail_response(wizard)

    @patch(
        "/{wizard_id:uuid}",
        summary="Update wizard",
        description="Update mutable fields of a wizard.",
    )
    async def update_wizard(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        data: WizardUpdate,
        wizard_service: WizardService,
    ) -> WizardResponse:
        """Update a wizard.

        Args:
            wizard_id: The UUID of the wizard.
            data: The update request with fields to modify.
            wizard_service: WizardService from DI.

        Returns:
            The updated wizard.

        Raises:
            NotFoundError: If the wizard does not exist.
            ValidationError: If the name is empty.
        """
        wizard = await wizard_service.update_wizard(
            wizard_id,
            name=data.name,
            description=data.description,
            enabled=data.enabled,
        )
        return self._to_response(wizard)

    @delete(
        "/{wizard_id:uuid}",
        status_code=HTTP_204_NO_CONTENT,
        summary="Delete wizard",
        description="Delete a wizard and all its steps.",
    )
    async def delete_wizard(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        wizard_service: WizardService,
    ) -> None:
        """Delete a wizard.

        Removes the wizard and all associated steps from the database.

        Args:
            wizard_id: The UUID of the wizard.
            wizard_service: WizardService from DI.

        Raises:
            NotFoundError: If the wizard does not exist.
        """
        await wizard_service.delete_wizard(wizard_id)

    # ==================== Step CRUD ====================

    @post(
        "/{wizard_id:uuid}/steps",
        status_code=HTTP_201_CREATED,
        summary="Create step",
        description="Create a new step in a wizard.",
    )
    async def create_step(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        data: WizardStepCreate,
        wizard_service: WizardService,
    ) -> WizardStepResponse:
        """Create a new wizard step.

        If step_order is not provided, the step is appended to the end.

        Args:
            wizard_id: The UUID of the wizard.
            data: The step creation request.
            wizard_service: WizardService from DI.

        Returns:
            The created step.

        Raises:
            NotFoundError: If the wizard does not exist.
        """
        step = await wizard_service.create_step(
            wizard_id,
            title=data.title,
            content_markdown=data.content_markdown,
            step_order=data.step_order,
        )
        return wizard_step_to_response(step)

    @patch(
        "/{wizard_id:uuid}/steps/{step_id:uuid}",
        summary="Update step",
        description="Update mutable fields of a wizard step.",
    )
    async def update_step(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        data: WizardStepUpdate,
        wizard_service: WizardService,
    ) -> WizardStepResponse:
        """Update a wizard step.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            data: The update request with fields to modify.
            wizard_service: WizardService from DI.

        Returns:
            The updated step.

        Raises:
            NotFoundError: If the wizard or step does not exist.
        """
        step = await wizard_service.update_step(
            wizard_id,
            step_id,
            title=data.title,
            content_markdown=data.content_markdown,
        )
        return wizard_step_to_response(step)

    @delete(
        "/{wizard_id:uuid}/steps/{step_id:uuid}",
        status_code=HTTP_204_NO_CONTENT,
        summary="Delete step",
        description="Delete a wizard step and normalize remaining step orders.",
    )
    async def delete_step(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        wizard_service: WizardService,
    ) -> None:
        """Delete a wizard step.

        Removes the step and normalizes remaining step orders to maintain
        contiguous ordering.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            wizard_service: WizardService from DI.

        Raises:
            NotFoundError: If the wizard or step does not exist.
        """
        await wizard_service.delete_step(wizard_id, step_id)

    @post(
        "/{wizard_id:uuid}/steps/{step_id:uuid}/reorder",
        summary="Reorder step",
        description="Move a step to a new position in the wizard.",
    )
    async def reorder_step(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        data: StepReorderRequest,
        wizard_service: WizardService,
    ) -> WizardStepResponse:
        """Reorder a wizard step.

        Moves the step to the new position and shifts other steps to
        maintain contiguous ordering.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            data: The reorder request with new position.
            wizard_service: WizardService from DI.

        Returns:
            The reordered step.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            ValidationError: If the new_order is invalid.
        """
        step = await wizard_service.reorder_step(wizard_id, step_id, data.new_order)
        return wizard_step_to_response(step)

    # ==================== Interaction CRUD ====================

    @post(
        "/{wizard_id:uuid}/steps/{step_id:uuid}/interactions",
        status_code=HTTP_201_CREATED,
        summary="Add interaction",
        description="Add an interaction type to a wizard step.",
    )
    async def add_interaction(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        data: StepInteractionCreate,
        wizard_service: WizardService,
    ) -> StepInteractionResponse:
        """Add an interaction to a step.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            data: The interaction creation request.
            wizard_service: WizardService from DI.

        Returns:
            The created interaction.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            ValidationError: If the type or config is invalid.
        """
        interaction = await wizard_service.add_interaction(
            wizard_id,
            step_id,
            interaction_type=data.interaction_type,
            config=data.config,
            display_order=data.display_order,
        )
        return step_interaction_to_response(interaction)

    @patch(
        "/{wizard_id:uuid}/steps/{step_id:uuid}/interactions/{interaction_id:uuid}",
        summary="Update interaction",
        description="Update a step interaction's configuration.",
    )
    async def update_interaction(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        interaction_id: Annotated[
            UUID,
            Parameter(description="Interaction UUID"),
        ],
        data: StepInteractionUpdate,
        wizard_service: WizardService,
    ) -> StepInteractionResponse:
        """Update a step interaction.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            interaction_id: The UUID of the interaction.
            data: The update request.
            wizard_service: WizardService from DI.

        Returns:
            The updated interaction.

        Raises:
            NotFoundError: If the wizard, step, or interaction does not exist.
            ValidationError: If the config is invalid.
        """
        interaction = await wizard_service.update_interaction(
            wizard_id,
            step_id,
            interaction_id,
            config=data.config,
        )
        return step_interaction_to_response(interaction)

    @delete(
        "/{wizard_id:uuid}/steps/{step_id:uuid}/interactions/{interaction_id:uuid}",
        status_code=HTTP_204_NO_CONTENT,
        summary="Remove interaction",
        description="Remove an interaction from a wizard step.",
    )
    async def remove_interaction(
        self,
        wizard_id: Annotated[
            UUID,
            Parameter(description="Wizard UUID"),
        ],
        step_id: Annotated[
            UUID,
            Parameter(description="Step UUID"),
        ],
        interaction_id: Annotated[
            UUID,
            Parameter(description="Interaction UUID"),
        ],
        wizard_service: WizardService,
    ) -> None:
        """Remove an interaction from a step.

        Args:
            wizard_id: The UUID of the wizard.
            step_id: The UUID of the step.
            interaction_id: The UUID of the interaction.
            wizard_service: WizardService from DI.

        Raises:
            NotFoundError: If the wizard, step, or interaction does not exist.
        """
        await wizard_service.remove_interaction(wizard_id, step_id, interaction_id)

    # ==================== Step Validation ====================

    @post(
        "/validate-step",
        summary="Validate step completion",
        description="Validate a step completion response. Public endpoint.",
        exclude_from_auth=True,
    )
    async def validate_step(
        self,
        data: StepValidationRequest,
        wizard_service: WizardService,
    ) -> StepValidationResponse:
        """Validate a step completion.

        Validates all interaction responses for a step (AND logic).
        Empty interactions list = informational step, always valid.

        This endpoint is publicly accessible without authentication.

        Args:
            data: The validation request with step_id and interactions.
            wizard_service: WizardService from DI.

        Returns:
            Validation result with completion token if valid.

        Raises:
            NotFoundError: If the step or an interaction does not exist.
        """
        # Convert interaction responses to tuples
        interaction_tuples: list[tuple[UUID, Mapping[str, object], datetime | None]] = [
            (ir.interaction_id, ir.response, ir.started_at) for ir in data.interactions
        ]

        is_valid, error, token = await wizard_service.validate_step(
            data.step_id,
            interaction_tuples,
        )

        return StepValidationResponse(
            valid=is_valid,
            completion_token=token,
            error=error,
        )

    # ==================== Response Helpers ====================

    def _to_response(self, wizard: Wizard, /) -> WizardResponse:
        """Convert a Wizard entity to WizardResponse.

        Args:
            wizard: The Wizard entity.

        Returns:
            WizardResponse without steps.
        """
        return WizardResponse(
            id=wizard.id,
            name=wizard.name,
            enabled=wizard.enabled,
            created_at=wizard.created_at,
            description=wizard.description,
            updated_at=wizard.updated_at,
        )

    def _to_detail_response(self, wizard: Wizard, /) -> WizardDetailResponse:
        """Convert a Wizard entity to WizardDetailResponse.

        Args:
            wizard: The Wizard entity with steps.

        Returns:
            WizardDetailResponse with steps.
        """
        steps = [wizard_step_to_response(step) for step in wizard.steps]

        return WizardDetailResponse(
            id=wizard.id,
            name=wizard.name,
            enabled=wizard.enabled,
            created_at=wizard.created_at,
            steps=steps,
            description=wizard.description,
            updated_at=wizard.updated_at,
        )
