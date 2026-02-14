"""Protocol definition for interaction type handlers.

Defines the InteractionHandler Protocol that all interaction type
implementations must satisfy. Uses structural subtyping — implementations
do not need to inherit from this class.

Also defines InteractionSource Protocol that both WizardStep and
StepInteraction satisfy, allowing handlers to work with either.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

import msgspec

from zondarr.models.wizard import InteractionType

# Type aliases matching WizardService conventions
ConfigValue = str | int | bool | list[str] | None
StepConfig = dict[str, ConfigValue]
InputConfig = Mapping[str, object]


class InteractionSource(Protocol):
    """Protocol for objects that provide interaction config.

    Both WizardStep (legacy) and StepInteraction satisfy this protocol
    structurally — they both have config and interaction_type attributes.

    Accepts InteractionType (StrEnum) or plain str for interaction_type
    to satisfy both ORM model types and plain dict/dataclass sources.
    """

    config: dict[str, ConfigValue]
    interaction_type: InteractionType | str


class InteractionSourceData(msgspec.Struct, kw_only=True):
    """Concrete adapter that satisfies InteractionSource protocol.

    Use this to wrap ORM model data (e.g., StepInteraction) before
    passing to the interaction registry, avoiding Mapped type mismatches.
    """

    interaction_type: InteractionType | str
    config: dict[str, ConfigValue]


class InteractionHandler(Protocol):
    """Protocol for wizard step interaction type handlers.

    Each interaction type (click, timer, tos, text_input, quiz) must provide:
    - Config validation: ensures step configuration is valid for the type
    - Response validation: ensures user response satisfies step requirements
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
        """Validate step configuration for this interaction type.

        Args:
            config: The raw configuration to validate (positional-only).

        Returns:
            The validated and normalized configuration.

        Raises:
            ValidationError: If the configuration is invalid.
        """
        ...

    def validate_response(
        self,
        source: InteractionSource,
        response: InputConfig,
        started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate a user's step completion response.

        Args:
            source: The interaction source with config and type (positional-only).
            response: The user's response data (positional-only).
            started_at: When the step was started, for timer validation (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
            If valid, error_message is None.
        """
        ...
