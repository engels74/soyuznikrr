"""Interaction type handlers for wizard step validation.

Provides a Protocol-based interface for interaction type handlers
and a registry for dispatching validation to type-specific implementations.

Each interaction type (click, timer, tos, text_input, quiz) has a dedicated
handler class that implements config and response validation.

Example usage:
    from zondarr.services.interactions import interaction_registry

    # Validate config for a step type
    config = interaction_registry.validate_config(InteractionType.TIMER, raw_config)

    # Validate a user response
    is_valid, error = interaction_registry.validate_response(step, response, started_at)
"""

from zondarr.services.interactions.handlers import (
    ClickHandler,
    QuizHandler,
    TextInputHandler,
    TimerHandler,
    TosHandler,
)
from zondarr.services.interactions.protocol import (
    InteractionHandler,
    InteractionSource,
    InteractionSourceData,
)
from zondarr.services.interactions.registry import InteractionRegistry

# Global registry instance with all built-in handlers registered
interaction_registry = InteractionRegistry()

__all__ = [
    "ClickHandler",
    "InteractionHandler",
    "InteractionRegistry",
    "InteractionSource",
    "InteractionSourceData",
    "QuizHandler",
    "TextInputHandler",
    "TimerHandler",
    "TosHandler",
    "interaction_registry",
]
