"""WizardService for wizard business logic orchestration.

Provides methods to create, update, delete, and validate wizards and steps.
Implements validation logic for each interaction type and maintains
step order contiguity.

Implements:
- Property 5: Interaction Type Validation
- Property 6: Step Order Contiguity
- Property 7: Timer Duration Bounds
- Property 8: Quiz Configuration Completeness
"""

import secrets
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.models.wizard import InteractionType, Wizard, WizardStep
from zondarr.repositories.wizard import WizardRepository
from zondarr.repositories.wizard_step import WizardStepRepository

# Timer duration bounds
MIN_TIMER_DURATION: int = 1
MAX_TIMER_DURATION: int = 300

# Quiz configuration constraints
MIN_QUIZ_OPTIONS: int = 2
MAX_QUIZ_OPTIONS: int = 10

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
    - Validating step configurations by interaction type
    - Validating step completions during wizard execution

    Attributes:
        wizard_repo: The WizardRepository for wizard data access.
        step_repo: The WizardStepRepository for step data access.
    """

    wizard_repo: WizardRepository
    step_repo: WizardStepRepository

    def __init__(
        self,
        wizard_repo: WizardRepository,
        step_repo: WizardStepRepository,
        /,
    ) -> None:
        """Initialize the WizardService.

        Args:
            wizard_repo: The WizardRepository for wizard data access (positional-only).
            step_repo: The WizardStepRepository for step data access (positional-only).
        """
        self.wizard_repo = wizard_repo
        self.step_repo = step_repo

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
        interaction_type: str,
        title: str,
        content_markdown: str,
        config: InputConfig | None = None,
        step_order: int | None = None,
    ) -> WizardStep:
        """Create a new wizard step.

        If step_order is not provided, the step is appended to the end.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            interaction_type: The interaction type (keyword-only).
            title: The step title (keyword-only).
            content_markdown: The markdown content (keyword-only).
            config: The step configuration (keyword-only).
            step_order: The step position (keyword-only).

        Returns:
            The created WizardStep entity.

        Raises:
            NotFoundError: If the wizard does not exist.
            ValidationError: If the interaction type or config is invalid.
            RepositoryError: If the database operation fails.
        """
        # Verify wizard exists
        wizard = await self.wizard_repo.get_by_id(wizard_id)
        if wizard is None:
            raise NotFoundError("Wizard", str(wizard_id))

        # Validate interaction type (Property 5)
        validated_type = self._validate_interaction_type(interaction_type)

        # Validate config for the interaction type
        validated_config = self._validate_step_config(validated_type, config or {})

        # Auto-assign step_order if not provided
        if step_order is None:
            max_order = await self.step_repo.get_max_order(wizard_id)
            step_order = max_order + 1

        step = WizardStep(
            wizard_id=wizard_id,
            step_order=step_order,
            interaction_type=validated_type,
            title=title,
            content_markdown=content_markdown,
            config=validated_config,
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
        config: InputConfig | None = None,
    ) -> WizardStep:
        """Update a wizard step.

        Args:
            wizard_id: The UUID of the wizard (positional-only).
            step_id: The UUID of the step (positional-only).
            title: New title (keyword-only).
            content_markdown: New markdown content (keyword-only).
            config: New configuration (keyword-only).

        Returns:
            The updated WizardStep entity.

        Raises:
            NotFoundError: If the wizard or step does not exist.
            ValidationError: If the config is invalid.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.wizard_id != wizard_id:
            raise NotFoundError("WizardStep", str(step_id))

        if title is not None:
            step.title = title

        if content_markdown is not None:
            step.content_markdown = content_markdown

        if config is not None:
            validated_config = self._validate_step_config(step.interaction_type, config)
            step.config = validated_config

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

    # ==================== Step Validation ====================

    async def validate_step(
        self,
        step_id: UUID,
        response: InputConfig,
        /,
        *,
        started_at: datetime | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Validate a step completion response.

        Args:
            step_id: The UUID of the step (positional-only).
            response: The user's response data (positional-only).
            started_at: When the step was started (keyword-only, for timer validation).

        Returns:
            A tuple of (is_valid, error_message, completion_token).
            If valid, error_message is None and completion_token is set.
            If invalid, error_message is set and completion_token is None.

        Raises:
            NotFoundError: If the step does not exist.
            RepositoryError: If the database operation fails.
        """
        step = await self.step_repo.get_by_id(step_id)
        if step is None:
            raise NotFoundError("WizardStep", str(step_id))

        is_valid, error = self._validate_step_response(step, response, started_at)

        if is_valid:
            # Generate completion token
            token = secrets.token_urlsafe(32)
            return True, None, token
        else:
            return False, error, None

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
        """Validate step configuration for the given interaction type.

        Implements:
        - Property 7: Timer Duration Bounds
        - Property 8: Quiz Configuration Completeness

        Args:
            interaction_type: The interaction type (positional-only).
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If the configuration is invalid.
        """
        match interaction_type:
            case InteractionType.CLICK:
                return self._validate_click_config(config)
            case InteractionType.TIMER:
                return self._validate_timer_config(config)
            case InteractionType.TOS:
                return self._validate_tos_config(config)
            case InteractionType.TEXT_INPUT:
                return self._validate_text_input_config(config)
            case InteractionType.QUIZ:
                return self._validate_quiz_config(config)

    def _validate_click_config(self, config: InputConfig, /) -> StepConfig:
        """Validate click interaction configuration.

        Args:
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.
        """
        button_text = config.get("button_text")
        if button_text is not None and not isinstance(button_text, str):
            raise ValidationError(
                "button_text must be a string",
                field_errors={"config.button_text": ["Must be a string"]},
            )
        return {"button_text": button_text}

    def _validate_timer_config(self, config: InputConfig, /) -> StepConfig:
        """Validate timer interaction configuration.

        Implements Property 7: Timer Duration Bounds.

        Args:
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If duration_seconds is missing or out of bounds.
        """
        duration = config.get("duration_seconds")
        if duration is None:
            raise ValidationError(
                "duration_seconds is required for timer steps",
                field_errors={"config.duration_seconds": ["Required field"]},
            )

        if not isinstance(duration, int):
            raise ValidationError(
                "duration_seconds must be an integer",
                field_errors={"config.duration_seconds": ["Must be an integer"]},
            )

        if duration < MIN_TIMER_DURATION or duration > MAX_TIMER_DURATION:
            raise ValidationError(
                f"duration_seconds must be between {MIN_TIMER_DURATION} and {MAX_TIMER_DURATION}",
                field_errors={
                    "config.duration_seconds": [
                        f"Must be between {MIN_TIMER_DURATION} and {MAX_TIMER_DURATION}"
                    ]
                },
            )

        return {"duration_seconds": duration}

    def _validate_tos_config(self, config: InputConfig, /) -> StepConfig:
        """Validate TOS interaction configuration.

        Args:
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.
        """
        checkbox_label = config.get("checkbox_label")
        if checkbox_label is not None and not isinstance(checkbox_label, str):
            raise ValidationError(
                "checkbox_label must be a string",
                field_errors={"config.checkbox_label": ["Must be a string"]},
            )
        return {"checkbox_label": checkbox_label}

    def _validate_text_input_config(self, config: InputConfig, /) -> StepConfig:
        """Validate text input interaction configuration.

        Args:
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If label is missing or constraints are invalid.
        """
        label = config.get("label")
        if not label or not isinstance(label, str):
            raise ValidationError(
                "label is required for text_input steps",
                field_errors={"config.label": ["Required field"]},
            )

        placeholder = config.get("placeholder")
        if placeholder is not None and not isinstance(placeholder, str):
            raise ValidationError(
                "placeholder must be a string",
                field_errors={"config.placeholder": ["Must be a string"]},
            )

        required = config.get("required", True)
        if not isinstance(required, bool):
            raise ValidationError(
                "required must be a boolean",
                field_errors={"config.required": ["Must be a boolean"]},
            )

        min_length = config.get("min_length")
        if min_length is not None:
            if not isinstance(min_length, int) or min_length < 0:
                raise ValidationError(
                    "min_length must be a non-negative integer",
                    field_errors={
                        "config.min_length": ["Must be a non-negative integer"]
                    },
                )

        max_length = config.get("max_length")
        if max_length is not None:
            if not isinstance(max_length, int) or max_length < 1:
                raise ValidationError(
                    "max_length must be a positive integer",
                    field_errors={"config.max_length": ["Must be a positive integer"]},
                )

        if (
            min_length is not None
            and max_length is not None
            and min_length > max_length
        ):
            raise ValidationError(
                "min_length cannot be greater than max_length",
                field_errors={
                    "config.min_length": ["Cannot be greater than max_length"]
                },
            )

        return {
            "label": label,
            "placeholder": placeholder,
            "required": required,
            "min_length": min_length,
            "max_length": max_length,
        }

    def _validate_quiz_config(self, config: InputConfig, /) -> StepConfig:
        """Validate quiz interaction configuration.

        Implements Property 8: Quiz Configuration Completeness.

        Args:
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If question, options, or correct_answer_index is invalid.
        """
        question = config.get("question")
        if not question or not isinstance(question, str):
            raise ValidationError(
                "question is required for quiz steps",
                field_errors={"config.question": ["Required field"]},
            )

        options = config.get("options")
        if not options or not isinstance(options, list):
            raise ValidationError(
                "options array is required for quiz steps",
                field_errors={"config.options": ["Required field"]},
            )

        # Cast to list for type checking - we validate elements below
        options_list: list[object] = list(options)  # pyright: ignore[reportUnknownArgumentType]

        if len(options_list) < MIN_QUIZ_OPTIONS:
            raise ValidationError(
                f"Quiz requires at least {MIN_QUIZ_OPTIONS} options",
                field_errors={
                    "config.options": [f"Must have at least {MIN_QUIZ_OPTIONS} options"]
                },
            )

        if len(options_list) > MAX_QUIZ_OPTIONS:
            raise ValidationError(
                f"Quiz cannot have more than {MAX_QUIZ_OPTIONS} options",
                field_errors={
                    "config.options": [
                        f"Cannot have more than {MAX_QUIZ_OPTIONS} options"
                    ]
                },
            )

        validated_options: list[str] = []
        for i, opt in enumerate(options_list):
            if not isinstance(opt, str) or not opt.strip():
                raise ValidationError(
                    f"Option {i} must be a non-empty string",
                    field_errors={
                        "config.options": [f"Option {i} must be a non-empty string"]
                    },
                )
            validated_options.append(opt.strip())

        correct_answer_index = config.get("correct_answer_index")
        if correct_answer_index is None:
            raise ValidationError(
                "correct_answer_index is required for quiz steps",
                field_errors={"config.correct_answer_index": ["Required field"]},
            )

        if not isinstance(correct_answer_index, int):
            raise ValidationError(
                "correct_answer_index must be an integer",
                field_errors={"config.correct_answer_index": ["Must be an integer"]},
            )

        if correct_answer_index < 0 or correct_answer_index >= len(validated_options):
            raise ValidationError(
                "correct_answer_index must be a valid option index",
                field_errors={
                    "config.correct_answer_index": [
                        f"Must be between 0 and {len(validated_options) - 1}"
                    ]
                },
            )

        return {
            "question": question,
            "options": validated_options,
            "correct_answer_index": correct_answer_index,
        }

    def _validate_step_response(
        self,
        step: WizardStep,
        response: InputConfig,
        started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate a step completion response.

        Args:
            step: The wizard step (positional-only).
            response: The user's response data (positional-only).
            started_at: When the step was started (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        match step.interaction_type:
            case InteractionType.CLICK:
                return self._validate_click_response(response)
            case InteractionType.TIMER:
                return self._validate_timer_response(step, started_at)
            case InteractionType.TOS:
                return self._validate_tos_response(response)
            case InteractionType.TEXT_INPUT:
                return self._validate_text_input_response(step, response)
            case InteractionType.QUIZ:
                return self._validate_quiz_response(step, response)

    def _validate_click_response(
        self, response: InputConfig, /
    ) -> tuple[bool, str | None]:
        """Validate click interaction response.

        Args:
            response: The user's response data (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        acknowledged = response.get("acknowledged")
        if acknowledged is True:
            return True, None
        return False, "Click acknowledgment required"

    def _validate_timer_response(
        self, step: WizardStep, started_at: datetime | None, /
    ) -> tuple[bool, str | None]:
        """Validate timer interaction response.

        Implements Property 11: Timer Duration Validation.

        Args:
            step: The wizard step (positional-only).
            started_at: When the step was started (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        if started_at is None:
            return False, "Timer start time required"

        duration_seconds = step.config.get("duration_seconds", 0)
        if not isinstance(duration_seconds, int):
            return False, "Invalid timer configuration"

        now = datetime.now(UTC)
        elapsed = (now - started_at).total_seconds()

        if elapsed < duration_seconds:
            remaining = int(duration_seconds - elapsed)
            return False, f"Timer not complete. {remaining} seconds remaining"

        return True, None

    def _validate_tos_response(
        self, response: InputConfig, /
    ) -> tuple[bool, str | None]:
        """Validate TOS interaction response.

        Args:
            response: The user's response data (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        accepted = response.get("accepted")
        if accepted is True:
            return True, None
        return False, "Terms of service must be accepted"

    def _validate_text_input_response(
        self, step: WizardStep, response: InputConfig, /
    ) -> tuple[bool, str | None]:
        """Validate text input interaction response.

        Implements Property 10: Text Input Constraint Validation.

        Args:
            step: The wizard step (positional-only).
            response: The user's response data (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        text = response.get("text")
        config = step.config

        required = config.get("required", True)
        if required and (text is None or not str(text).strip()):
            return False, "Text input is required"

        if text is None:
            return True, None

        text_str = str(text)
        min_length = config.get("min_length")
        max_length = config.get("max_length")

        if min_length is not None and isinstance(min_length, int):
            if len(text_str) < min_length:
                return False, f"Text must be at least {min_length} characters"

        if max_length is not None and isinstance(max_length, int):
            if len(text_str) > max_length:
                return False, f"Text cannot exceed {max_length} characters"

        return True, None

    def _validate_quiz_response(
        self, step: WizardStep, response: InputConfig, /
    ) -> tuple[bool, str | None]:
        """Validate quiz interaction response.

        Implements Property 9: Quiz Answer Validation.

        Args:
            step: The wizard step (positional-only).
            response: The user's response data (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        answer_index = response.get("answer_index")
        if answer_index is None:
            return False, "Answer selection required"

        if not isinstance(answer_index, int):
            return False, "Answer index must be an integer"

        correct_index = step.config.get("correct_answer_index")
        if not isinstance(correct_index, int):
            return False, "Invalid quiz configuration"

        if answer_index == correct_index:
            return True, None

        return False, "Incorrect answer"
