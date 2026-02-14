"""Registry for interaction type handlers.

Provides a registry that maps InteractionType enum values to handler
instances. Follows the same pattern as ClientRegistry in
zondarr.media.registry.

The registry is pre-populated with all built-in interaction types
on initialization. New interaction types can be registered at runtime
without modifying existing code.
"""

from collections.abc import Mapping
from datetime import datetime

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
    3. Register it via registry.register(type, handler)

    Attributes:
        _handlers: Mapping from interaction types to handler instances.
    """

    _handlers: dict[InteractionType, InteractionHandler]

    def __init__(self) -> None:
        """Initialize registry with all built-in interaction handlers."""
        self._handlers = {}
        # Register all built-in handlers
        self.register(InteractionType.CLICK, ClickHandler())
        self.register(InteractionType.TIMER, TimerHandler())
        self.register(InteractionType.TOS, TosHandler())
        self.register(InteractionType.TEXT_INPUT, TextInputHandler())
        self.register(InteractionType.QUIZ, QuizHandler())

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
