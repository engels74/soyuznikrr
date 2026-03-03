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
from zondarr.core.wizard_token import (
    sign_wizard_completion,
    sign_wizard_progress,
    verify_wizard_progress,
)
from zondarr.models.wizard import (
    InteractionType,
    StepInteraction,
    Wizard,
    WizardStep,
    WizardStepTranslation,
)
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
        primary_language: str = "en",
        translations: list[dict[str, str]] | None = None,
    ) -> WizardStep:
        """Create a new wizard step (bare content container).

        Steps are created without interaction types. Interactions are
        added separately via add_interaction().

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            title: The step title (keyword-only).
            content_markdown: The markdown content (keyword-only).
            step_order: The step position (keyword-only).
            primary_language: Language code of the title/content fields (keyword-only).
            translations: Optional list of translation dicts with
                language_code, title, content_markdown (keyword-only).

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
            primary_language=primary_language,
        )
        created_step = await self.step_repo.create(step)

        # Create translation records if provided
        if translations:
            for t in translations:
                translation = WizardStepTranslation(
                    step_id=created_step.id,
                    language_code=t["language_code"],
                    title=t["title"],
                    content_markdown=t["content_markdown"],
                )
                self.step_repo.session.add(translation)
            await self.step_repo.session.flush()

        await self.step_repo.session.refresh(
            created_step, ["interactions", "translations"]
        )
        return created_step

    async def update_step(
        self,
        wizard_id: UUID,
        step_id: UUID,
        /,
        *,
        title: str | None = None,
        content_markdown: str | None = None,
        primary_language: str | None = None,
        translations: list[dict[str, str]] | None = None,
    ) -> WizardStep:
        """Update a wizard step.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            title: New title (keyword-only).
            content_markdown: New markdown content (keyword-only).
            primary_language: New language code (keyword-only).
            translations: List of translation dicts to upsert. Replaces
                the full set: languages not in the list are removed,
                existing languages are updated, new languages are added
                (keyword-only).

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

        if primary_language is not None:
            step.primary_language = primary_language

        # Upsert translations if provided (replace full set)
        if translations is not None:
            # Load current translations
            await self.step_repo.session.refresh(step, ["translations"])
            existing_by_lang = {t.language_code: t for t in step.translations}
            incoming_langs = {t["language_code"] for t in translations}

            # Remove translations not in the incoming set
            for lang, existing_t in existing_by_lang.items():
                if lang not in incoming_langs:
                    await self.step_repo.session.delete(existing_t)

            # Add or update translations
            for t in translations:
                lang = t["language_code"]
                if lang in existing_by_lang:
                    existing_t = existing_by_lang[lang]
                    existing_t.title = t["title"]
                    existing_t.content_markdown = t["content_markdown"]
                else:
                    new_t = WizardStepTranslation(
                        step_id=step_id,
                        language_code=lang,
                        title=t["title"],
                        content_markdown=t["content_markdown"],
                    )
                    self.step_repo.session.add(new_t)

            await self.step_repo.session.flush()

        updated_step = await self.step_repo.update(step)
        await self.step_repo.session.refresh(
            updated_step, ["interactions", "translations"]
        )
        return updated_step

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
        await self.step_repo.session.refresh(updated_step, ["interactions"])
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

        updated = await self.interaction_repo.update(interaction)
        await self.interaction_repo.session.refresh(updated, ["step"])
        return updated

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
        *,
        secret_key: str | None = None,
        progress_token: str | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Validate step completion with all interactions.

        Fetches the step's interactions from the DB and enforces that the
        client-submitted set matches exactly (no omissions, no extras).
        Steps with zero DB interactions are informational and always valid.
        All interactions must pass (AND logic).

        Uses signed progress tokens to enforce sequential step completion.
        Non-first steps require a valid ``progress_token`` proving all
        prior steps were validated. The returned token is either a progress
        token (for intermediate steps) or a signed wizard completion token
        (for the final step, when ``secret_key`` is provided).

        Args:
            step_id: The UUID of the step (positional-only).
            interactions: List of (interaction_id, response, started_at) tuples (positional-only).
            secret_key: App secret key for signing tokens (keyword-only).
            progress_token: Signed progress token from prior step validation (keyword-only).

        Returns:
            A tuple of (is_valid, error_message, token).

        Raises:
            NotFoundError: If the step or an interaction does not exist.
            ValidationError: If submitted interaction IDs don't match the step's interactions,
                or if a required progress token is missing/invalid.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None:
            raise NotFoundError("WizardStep", str(step_id))

        # Fetch authoritative interaction set from DB
        db_interactions = await self.interaction_repo.get_by_step_id(step_id)
        expected_ids = {i.id for i in db_interactions}
        submitted_ids = {iid for iid, _, _ in interactions}

        # Determine step position within the wizard
        wizard_steps = await self.step_repo.get_by_wizard_id(step.wizard_id)
        step_ids = [s.id for s in wizard_steps]
        step_index = step_ids.index(step.id) if step.id in step_ids else -1
        is_first_step = step_index == 0
        is_last_step = step_index == len(step_ids) - 1

        # Verify progress token for non-first steps
        prior_validated_ids = self._verify_progress(
            step, step_ids, step_index, is_first_step, secret_key, progress_token
        )

        # Informational step: only valid when DB truly has zero interactions
        if not expected_ids:
            token = self._make_step_token(
                step, secret_key, is_last_step, prior_validated_ids
            )
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

        token = self._make_step_token(
            step, secret_key, is_last_step, prior_validated_ids
        )
        return True, None, token

    @staticmethod
    def _verify_progress(
        step: WizardStep,
        step_ids: list[UUID],
        step_index: int,
        is_first_step: bool,
        secret_key: str | None,
        progress_token: str | None,
    ) -> list[str]:
        """Verify the progress token proves all prior steps were validated.

        Args:
            step: The current step being validated.
            step_ids: Ordered list of all step IDs in the wizard.
            step_index: Index of the current step in the wizard.
            is_first_step: Whether this is the first step.
            secret_key: App secret key for token verification.
            progress_token: The progress token to verify.

        Returns:
            List of previously validated step ID strings (empty for first step).

        Raises:
            ValidationError: If the progress token is missing or invalid
                for a non-first step.
        """
        if is_first_step:
            return []

        if secret_key is None:
            # No secret key — can't verify progress, allow (dev mode)
            return []

        if progress_token is None:
            raise ValidationError(
                "Progress token is required for non-first steps",
                field_errors={
                    "progress_token": [
                        "Must complete prior steps before validating this step"
                    ]
                },
            )

        validated_ids = verify_wizard_progress(
            progress_token,
            step.wizard_id,
            secret_key,
        )

        if validated_ids is None:
            raise ValidationError(
                "Invalid or expired progress token",
                field_errors={
                    "progress_token": [
                        "Progress token is invalid, expired, or for a different wizard"
                    ]
                },
            )

        # Verify the progress token contains all expected prior step IDs
        expected_prior = [str(sid) for sid in step_ids[:step_index]]
        if validated_ids != expected_prior:
            raise ValidationError(
                "Progress token does not cover all prior steps",
                field_errors={
                    "progress_token": ["Must complete all prior steps in order"]
                },
            )

        return validated_ids

    @staticmethod
    def _make_step_token(
        step: WizardStep,
        secret_key: str | None,
        is_last_step: bool,
        prior_validated_ids: list[str],
    ) -> str:
        """Generate a token for a validated step.

        Returns a signed wizard completion token for the final step
        (when ``secret_key`` is provided), a signed progress token for
        intermediate steps, or a random token when no secret key is
        available.

        Args:
            step: The validated wizard step.
            secret_key: App secret key for signing, or None.
            is_last_step: Whether this step is the last step of its wizard.
            prior_validated_ids: Step IDs validated before this step.

        Returns:
            A token string (completion, progress, or random).
        """
        if secret_key is None:
            return secrets.token_urlsafe(32)

        if is_last_step:
            return sign_wizard_completion(step.wizard_id, secret_key)

        # Intermediate step: return a progress token with this step added
        all_validated = [*prior_validated_ids, str(step.id)]
        return sign_wizard_progress(
            step.wizard_id,
            [UUID(sid) for sid in all_validated],
            secret_key,
        )

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
