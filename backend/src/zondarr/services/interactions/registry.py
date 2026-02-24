"""Registry for interaction type handlers.

Provides a registry that maps InteractionType enum values to handler
instances. All built-in interaction types are registered on
initialization via an exhaustive match in ``_create_handler()``.

Adding a new interaction type requires updating ``_create_handler()``
so that ``assert_never`` continues to guarantee full coverage.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import assert_never

from zondarr.core.exceptions import ValidationError
from zondarr.models.wizard import InteractionType

from .handlers import (
    ClickHandler,
    QuizHandler,
    TextInputHandler,
    TimerHandler,
    TosHandler,
)
from .protocol import InteractionHandler, InteractionSource, StepConfig

# Type alias for input config
InputConfig = Mapping[str, object]


class InteractionRegistry:
    """Registry for interaction type handlers.

    Maps InteractionType enum values to handler instances that implement
    the InteractionHandler protocol. Pre-populated with all built-in
    handlers on initialization.

    Adding a new interaction type requires:
    1. Add the type to InteractionType enum
    2. Create a handler class implementing InteractionHandler protocol
    3. Add a case for it in ``_create_handler()``

    Attributes:
        _handlers: Mapping from interaction types to handler instances.
    """

    _handlers: dict[InteractionType, InteractionHandler]

    def __init__(self) -> None:
        """Initialize registry with all built-in interaction handlers."""
        self._handlers = {}
        # Register all built-in handlers using exhaustive match
        for interaction_type in InteractionType:
            self.register(interaction_type, self._create_handler(interaction_type))

    @staticmethod
    def _create_handler(interaction_type: InteractionType, /) -> InteractionHandler:
        """Create the handler for a given interaction type.

        Uses exhaustive match with assert_never to ensure every
        InteractionType enum member has a corresponding handler.
        Adding a new enum value without updating this method will
        cause a type checker error.
        """
        match interaction_type:
            case InteractionType.CLICK:
                return ClickHandler()
            case InteractionType.TIMER:
                return TimerHandler()
            case InteractionType.TOS:
                return TosHandler()
            case InteractionType.TEXT_INPUT:
                return TextInputHandler()
            case InteractionType.QUIZ:
                return QuizHandler()
            case _ as unreachable:  # pyright: ignore[reportUnnecessaryComparison] -- exhaustiveness guard
                assert_never(unreachable)

    def register(
        self,
        interaction_type: InteractionType,
        handler: InteractionHandler,
        /,
    ) -> None:
        """Register a handler for an interaction type.

        Args:
            interaction_type: The interaction type to register (positional-only).
            handler: The handler instance (positional-only).
        """
        self._handlers[interaction_type] = handler

    def get_handler(self, interaction_type: InteractionType, /) -> InteractionHandler:
        """Get the handler for an interaction type.

        Args:
            interaction_type: The interaction type to look up (positional-only).

        Returns:
            The registered handler instance.

        Raises:
            ValidationError: If no handler is registered for the type.
        """
        handler = self._handlers.get(interaction_type)
        if handler is None:
            valid_types = [t.value for t in self._handlers]
            raise ValidationError(
                f"No handler registered for interaction type: {interaction_type}",
                field_errors={
                    "interaction_type": [f"Must be one of: {', '.join(valid_types)}"]
                },
            )
        return handler

    def validate_config(
        self, interaction_type: InteractionType, config: InputConfig, /
    ) -> StepConfig:
        """Validate step configuration using the registered handler.

        Args:
            interaction_type: The interaction type (positional-only).
            config: The configuration to validate (positional-only).

        Returns:
            The validated configuration.

        Raises:
            ValidationError: If the configuration is invalid.
        """
        return self.get_handler(interaction_type).validate_config(config)

    def validate_response(
        self,
        source: InteractionSource,
        response: InputConfig,
        started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate a response using the registered handler.

        Works with any object that has config and interaction_type attributes
        (both WizardStep and StepInteraction satisfy this).

        Args:
            source: The interaction source (positional-only).
            response: The user's response data (positional-only).
            started_at: When the step was started (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        return self.get_handler(
            InteractionType(source.interaction_type)
        ).validate_response(source, response, started_at)

    def registered_types(self) -> set[InteractionType]:
        """Return the set of registered interaction types.

        Returns:
            A set of InteractionType values that have handlers registered.
        """
        return set(self._handlers.keys())

    def clear(self) -> None:
        """Clear all registered handlers.

        Primarily useful for testing to reset the registry state.
        """
        self._handlers.clear()
