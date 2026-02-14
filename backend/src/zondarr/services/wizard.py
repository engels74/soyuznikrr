"""WizardService for wizard business logic orchestration.

Provides methods to create, update, delete, and validate wizards, steps,
and step interactions. Delegates interaction type validation to the
InteractionRegistry, which dispatches to type-specific handler implementations.

Implements:
- Property 5: Interaction Type Validation
- Property 6: Step Order Contiguity
- Property 7: Timer Duration Bounds (via TimerHandler)
- Property 8: Quiz Configuration Completeness (via QuizHandler)
"""

import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.models.wizard import InteractionType, StepInteraction, Wizard, WizardStep
from zondarr.repositories.step_interaction import StepInteractionRepository
from zondarr.repositories.wizard import WizardRepository
from zondarr.repositories.wizard_step import WizardStepRepository
from zondarr.services.interactions import interaction_registry
from zondarr.services.interactions.protocol import InteractionSourceData

# Type alias for step configuration values
ConfigValue = str | int | bool | list[str] | None
StepConfig = dict[str, ConfigValue]

# Type alias for input config (can have any JSON-compatible values)
# Using object for maximum flexibility in accepting input
InputConfig = Mapping[str, object]


class WizardService:
    """Service for managing wizard operations.

    Orchestrates business logic for wizard management including:
    - Creating and updating wizards
    - Managing wizard steps with auto-ordering
    - Managing step interactions (composable interaction types)
    - Validating step configurations via InteractionRegistry
    - Validating step completions during wizard execution

    Attributes:
        wizard_repo: The WizardRepository for wizard data access.
        step_repo: The WizardStepRepository for step data access.
        interaction_repo: The StepInteractionRepository for interaction data access.
    """

    wizard_repo: WizardRepository
    step_repo: WizardStepRepository
    interaction_repo: StepInteractionRepository

    def __init__(
        self,
        wizard_repo: WizardRepository,
        step_repo: WizardStepRepository,
        interaction_repo: StepInteractionRepository,
        /,
    ) -> None:
        """Initialize the WizardService.

        Args:
            wizard_repo: The WizardRepository for wizard data access (positional-only).
            step_repo: The WizardStepRepository for step data access (positional-only).
            interaction_repo: The StepInteractionRepository for interaction data access (positional-only).
        """
        self.wizard_repo = wizard_repo
        self.step_repo = step_repo
        self.interaction_repo = interaction_repo

    # ==================== Wizard CRUD ====================

    async def create_wizard(
        self,
        *,
        name: str,
        description: str | None = None,
        enabled: bool = True,
    ) -> Wizard:
        """Create a new wizard.

        Args:
            name: The wizard name (keyword-only).
            description: Optional description (keyword-only).
            enabled: Whether the wizard is enabled (keyword-only).

        Returns:
            The created Wizard entity.

        Raises:
            ValidationError: If the name is empty.
            RepositoryError: If the database operation fails.
        """
        if not name or not name.strip():
            raise ValidationError(
                "Wizard name cannot be empty",
                field_errors={"name": ["Name is required"]},
            )

        wizard = Wizard(
            name=name.strip(),
            description=description,
            enabled=enabled,
        )
        return await self.wizard_repo.create(wizard)

    async def get_wizard(self, wizard_id: UUID, /) -> Wizard:
        """Retrieve a wizard by ID with all steps.

        Args:
            wizard_id: The UUID of the wizard (positional-only).

        Returns:
            The Wizard entity with steps.

        Raises:
            NotFoundError: If the wizard does not exist.
            RepositoryError: If the database operation fails.
        """
        wizard = await self.wizard_repo.get_with_steps(wizard_id)
        if wizard is None:
            raise NotFoundError("Wizard", str(wizard_id))
        return wizard

    async def list_wizards(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        enabled: bool | None = None,
    ) -> tuple[Sequence[Wizard], int]:
        """List wizards with pagination.

        Args:
            page: Page number (1-indexed) (keyword-only).
            page_size: Number of items per page (keyword-only).
            enabled: Filter by enabled status (keyword-only).

        Returns:
            A tuple of (wizards, total_count).

        Raises:
            RepositoryError: If the database operation fails.
        """
        return await self.wizard_repo.list_paginated(
            page=page,
            page_size=page_size,
            enabled=enabled,
        )

    async def update_wizard(
        self,
        wizard_id: UUID,
        /,
        *,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> Wizard:
        """Update a wizard.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            name: New name (keyword-only).
            description: New description (keyword-only).
            enabled: New enabled status (keyword-only).

        Returns:
            The updated Wizard entity.

        Raises:
            NotFoundError: If the wizard does not exist.
            ValidationError: If the name is empty.
            RepositoryError: If the database operation fails.
        """
        wizard = await self.wizard_repo.get_by_id(wizard_id)
        if wizard is None:
            raise NotFoundError("Wizard", str(wizard_id))

        if name is not None:
            if not name.strip():
                raise ValidationError(
                    "Wizard name cannot be empty",
                    field_errors={"name": ["Name is required"]},
                )
            wizard.name = name.strip()

        if description is not None:
            wizard.description = description

        if enabled is not None:
            wizard.enabled = enabled

        return await self.wizard_repo.update(wizard)

    async def delete_wizard(self, wizard_id: UUID, /) -> None:
        """Delete a wizard and all its steps.

        Args:
            wizard_id: The UUID of the wizard (positional-only).

        Raises:
            NotFoundError: If the wizard does not exist.
            RepositoryError: If the database operation fails.
        """
        wizard = await self.wizard_repo.get_by_id(wizard_id)
        if wizard is None:
            raise NotFoundError("Wizard", str(wizard_id))

        await self.wizard_repo.delete(wizard)

    # ==================== Step CRUD ====================

    async def create_step(
        self,
        wizard_id: UUID,
        /,
        *,
        title: str,
        content_markdown: str,
        step_order: int | None = None,
    ) -> WizardStep:
        """Create a new wizard step (bare content container).

        Steps are created without interaction types. Interactions are
        added separately via add_interaction().

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            title: The step title (keyword-only).
            content_markdown: The markdown content (keyword-only).
            step_order: The step position (keyword-only).

        Returns:
            The created WizardStep entity.

        Raises:
            NotFoundError: If the wizard does not exist.
            RepositoryError: If the database operation fails.
        """
        # Verify wizard exists
        wizard = await self.wizard_repo.get_by_id(wizard_id)
        if wizard is None:
            raise NotFoundError("Wizard", str(wizard_id))

        # Auto-assign step_order if not provided
        if step_order is None:
            max_order = await self.step_repo.get_max_order(wizard_id)
            step_order = max_order + 1

        step = WizardStep(
            wizard_id=wizard_id,
            step_order=step_order,
            title=title,
            content_markdown=content_markdown,
        )
        return await self.step_repo.create(step)

    async def update_step(
        self,
        wizard_id: UUID,
        step_id: UUID,
        /,
        *,
        title: str | None = None,
        content_markdown: str | None = None,
    ) -> WizardStep:
        """Update a wizard step.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            title: New title (keyword-only).
            content_markdown: New markdown content (keyword-only).

        Returns:
            The updated WizardStep entity.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        if title is not None:
            step.title = title

        if content_markdown is not None:
            step.content_markdown = content_markdown

        return await self.step_repo.update(step)

    async def delete_step(self, wizard_id: UUID, step_id: UUID, /) -> None:
        """Delete a wizard step and normalize remaining step orders.

        Implements Property 6: Step Order Contiguity.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).

        Raises:
            NotFoundError: If the wizard or step does not exist.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        await self.step_repo.delete(step)

        # Normalize step order to maintain contiguity (Property 6)
        await self.step_repo.normalize_order(wizard_id)

    async def reorder_step(
        self, wizard_id: UUID, step_id: UUID, new_order: int, /
    ) -> WizardStep:
        """Reorder a step to a new position.

        Implements Property 6: Step Order Contiguity.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            new_order: The new position (positional-only).

        Returns:
            The reordered WizardStep entity.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            ValidationError: If the new_order is invalid.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        # Validate new_order is within bounds
        max_order = await self.step_repo.get_max_order(wizard_id)
        if new_order < 0 or new_order > max_order:
            raise ValidationError(
                f"new_order must be between 0 and {max_order}",
                field_errors={"new_order": [f"Must be between 0 and {max_order}"]},
            )

        await self.step_repo.reorder_steps(wizard_id, step_id, new_order)

        # Refresh the step to get updated order
        updated_step = await self.step_repo.get_by_id(step_id)
        if updated_step is None:
            raise NotFoundError("WizardStep", str(step_id))
        return updated_step

    # ==================== Interaction CRUD ====================

    async def add_interaction(
        self,
        wizard_id: UUID,
        step_id: UUID,
        /,
        *,
        interaction_type: str,
        config: InputConfig | None = None,
        display_order: int | None = None,
    ) -> StepInteraction:
        """Add an interaction to a step.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            interaction_type: The interaction type (keyword-only).
            config: The interaction configuration (keyword-only).
            display_order: The display position (keyword-only).

        Returns:
            The created StepInteraction entity.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            ValidationError: If the interaction type or config is invalid,
                or if the type is already on this step.
            RepositoryError: If the database operation fails.
        """
        # Verify step exists and belongs to wizard
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        # Validate interaction type
        validated_type = self._validate_interaction_type(interaction_type)

        # Validate config
        validated_config = self._validate_step_config(validated_type, config or {})

        # Check for duplicate type on this step
        existing = await self.interaction_repo.get_by_step_id(step_id)
        for existing_interaction in existing:
            if existing_interaction.interaction_type == validated_type:
                raise ValidationError(
                    f"Step already has a {interaction_type} interaction",
                    field_errors={
                        "interaction_type": [
                            f"Duplicate interaction type: {interaction_type}"
                        ]
                    },
                )

        # Auto-assign display_order if not provided
        if display_order is None:
            display_order = len(existing)

        interaction = StepInteraction(
            step_id=step_id,
            interaction_type=validated_type,
            config=validated_config,
            display_order=display_order,
        )
        return await self.interaction_repo.create(interaction)

    async def update_interaction(
        self,
        wizard_id: UUID,
        step_id: UUID,
        interaction_id: UUID,
        /,
        *,
        config: InputConfig | None = None,
    ) -> StepInteraction:
        """Update a step interaction's config.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            interaction_id: The UUID of the interaction (positional-only).
            config: New configuration (keyword-only).

        Returns:
            The updated StepInteraction entity.

        Raises:
            NotFoundError: If the wizard, step, or interaction does not exist.
            ValidationError: If the config is invalid.
            RepositoryError: If the database operation fails.
        """
        interaction = await self.interaction_repo.get_by_id(interaction_id)
        if interaction is None or interaction.step_id != step_id:
            raise NotFoundError("StepInteraction", str(interaction_id))

        # Verify step belongs to wizard
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        if config is not None:
            validated_config = self._validate_step_config(
                interaction.interaction_type, config
            )
            interaction.config = validated_config

        return await self.interaction_repo.update(interaction)

    async def remove_interaction(
        self,
        wizard_id: UUID,
        step_id: UUID,
        interaction_id: UUID,
        /,
    ) -> None:
        """Remove an interaction from a step.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            interaction_id: The UUID of the interaction (positional-only).

        Raises:
            NotFoundError: If the wizard, step, or interaction does not exist.
            RepositoryError: If the database operation fails.
        """
        interaction = await self.interaction_repo.get_by_id(interaction_id)
        if interaction is None or interaction.step_id != step_id:
            raise NotFoundError("StepInteraction", str(interaction_id))

        # Verify step belongs to wizard
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        await self.interaction_repo.delete(interaction)

    # ==================== Step Validation ====================

    async def validate_step(
        self,
        step_id: UUID,
        interactions: list[tuple[UUID, InputConfig, datetime | None]],
        /,
    ) -> tuple[bool, str | None, str | None]:
        """Validate step completion with all interactions.

        Fetches the step's interactions from the DB and enforces that the
        client-submitted set matches exactly (no omissions, no extras).
        Steps with zero DB interactions are informational and always valid.
        All interactions must pass (AND logic).

        Args:
            step_id: The UUID of the step (positional-only).
            interactions: List of (interaction_id, response, started_at) tuples (positional-only).

        Returns:
            A tuple of (is_valid, error_message, completion_token).

        Raises:
            NotFoundError: If the step or an interaction does not exist.
            ValidationError: If submitted interaction IDs don't match the step's interactions.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None:
            raise NotFoundError("WizardStep", str(step_id))

        # Fetch authoritative interaction set from DB
        db_interactions = await self.interaction_repo.get_by_step_id(step_id)
        expected_ids = {i.id for i in db_interactions}
        submitted_ids = {iid for iid, _, _ in interactions}

        # Informational step: only valid when DB truly has zero interactions
        if not expected_ids:
            token = secrets.token_urlsafe(32)
            return True, None, token

        # Enforce exact match between submitted and expected interaction IDs
        missing = expected_ids - submitted_ids
        extra = submitted_ids - expected_ids
        if missing or extra:
            errors: list[str] = []
            if missing:
                errors.append(
                    f"Missing interactions: {', '.join(str(i) for i in missing)}"
                )
            if extra:
                errors.append(
                    f"Unknown interactions: {', '.join(str(i) for i in extra)}"
                )
            raise ValidationError(
                "Submitted interactions do not match step requirements",
                field_errors={"interactions": errors},
            )

        # Build lookup from DB interactions for validation
        db_lookup = {i.id: i for i in db_interactions}

        # Validate all interactions (AND logic)
        for interaction_id, response, started_at in interactions:
            interaction = db_lookup[interaction_id]

            source = InteractionSourceData(
                interaction_type=interaction.interaction_type,
                config=interaction.config,
            )
            is_valid, error = interaction_registry.validate_response(
                source,
                response,
                started_at,
            )
            if not is_valid:
                return False, error, None

        token = secrets.token_urlsafe(32)
        return True, None, token

    # ==================== Validation Helpers ====================

    def _validate_interaction_type(self, interaction_type: str, /) -> InteractionType:
        """Validate and convert interaction type string to enum.

        Implements Property 5: Interaction Type Validation.

        Args:
            interaction_type: The interaction type string (positional-only).

        Returns:
            The validated InteractionType enum value.

        Raises:
            ValidationError: If the interaction type is invalid.
        """
        try:
            return InteractionType(interaction_type)
        except ValueError:
            valid_types = [t.value for t in InteractionType]
            raise ValidationError(
                f"Invalid interaction type: {interaction_type}",
                field_errors={
                    "interaction_type": [f"Must be one of: {', '.join(valid_types)}"]
                },
            ) from None

    def _validate_step_config(
        self, interaction_type: InteractionType, config: InputConfig, /
    ) -> StepConfig:
        """Validate step configuration using the interaction registry.

        Delegates to the registered handler for the interaction type.

        Args:
            interaction_type: The interaction type (positional-only).
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If the configuration is invalid.
        """
        return interaction_registry.validate_config(interaction_type, config)
