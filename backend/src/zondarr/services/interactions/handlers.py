"""Built-in interaction type handler implementations.

Provides handler classes for all 5 interaction types:
- ClickHandler: Simple button confirmation
- TimerHandler: Timed delay before proceeding
- TosHandler: Terms of service acceptance
- TextInputHandler: Free-form text input
- QuizHandler: Multiple choice question

Each handler validates both configuration (admin-side) and
response (user-side) for its interaction type.
"""

from datetime import UTC, datetime

from zondarr.core.exceptions import ValidationError

from .protocol import InputConfig, InteractionSource, StepConfig

# Timer duration bounds
MIN_TIMER_DURATION: int = 1
MAX_TIMER_DURATION: int = 300

# Quiz configuration constraints
MIN_QUIZ_OPTIONS: int = 2
MAX_QUIZ_OPTIONS: int = 10


class ClickHandler:
    """Handler for click interaction type.

    Config: optional button_text string.
    Response: requires acknowledged=true.
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
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

    def validate_response(
        self,
        _source: InteractionSource,
        response: InputConfig,
        _started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate click interaction response.

        Args:
            _source: The interaction source (positional-only, unused).
            response: The user's response data (positional-only).
            _started_at: Unused for click (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        acknowledged = response.get("acknowledged")
        if acknowledged is True:
            return True, None
        return False, "Click acknowledgment required"


class TimerHandler:
    """Handler for timer interaction type.

    Config: requires duration_seconds integer in [1, 300].
    Response: validates elapsed time >= duration_seconds.
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
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

    def validate_response(
        self,
        source: InteractionSource,
        _response: InputConfig,
        started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate timer interaction response.

        Implements Property 11: Timer Duration Validation.

        Args:
            source: The interaction source (positional-only).
            _response: Unused for timer (positional-only).
            started_at: When the step was started (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        if started_at is None:
            return False, "Timer start time required"

        duration_seconds = source.config.get("duration_seconds", 0)
        if not isinstance(duration_seconds, int):
            return False, "Invalid timer configuration"

        now = datetime.now(UTC)
        elapsed = (now - started_at).total_seconds()

        if elapsed < duration_seconds:
            remaining = int(duration_seconds - elapsed)
            return False, f"Timer not complete. {remaining} seconds remaining"

        return True, None


class TosHandler:
    """Handler for TOS interaction type.

    Config: optional checkbox_label string.
    Response: requires accepted=true.
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
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

    def validate_response(
        self,
        _source: InteractionSource,
        response: InputConfig,
        _started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate TOS interaction response.

        Args:
            _source: The interaction source (positional-only, unused).
            response: The user's response data (positional-only).
            _started_at: Unused for TOS (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        accepted = response.get("accepted")
        if accepted is True:
            return True, None
        return False, "Terms of service must be accepted"


class TextInputHandler:
    """Handler for text_input interaction type.

    Config: requires label, optional placeholder/required/min_length/max_length.
    Response: validates text against configured constraints.
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
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

    def validate_response(
        self,
        source: InteractionSource,
        response: InputConfig,
        _started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate text input interaction response.

        Implements Property 10: Text Input Constraint Validation.

        Args:
            source: The interaction source (positional-only).
            response: The user's response data (positional-only).
            _started_at: Unused for text input (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        text = response.get("text")
        config = source.config

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


class QuizHandler:
    """Handler for quiz interaction type.

    Config: requires question, options (2-10), correct_answer_index.
    Response: validates answer_index matches correct_answer_index.
    """

    def validate_config(self, config: InputConfig, /) -> StepConfig:
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

    def validate_response(
        self,
        source: InteractionSource,
        response: InputConfig,
        _started_at: datetime | None,
        /,
    ) -> tuple[bool, str | None]:
        """Validate quiz interaction response.

        Implements Property 9: Quiz Answer Validation.

        Args:
            source: The interaction source (positional-only).
            response: The user's response data (positional-only).
            _started_at: Unused for quiz (positional-only).

        Returns:
            A tuple of (is_valid, error_message).
        """
        answer_index = response.get("answer_index")
        if answer_index is None:
            return False, "Answer selection required"

        if not isinstance(answer_index, int):
            return False, "Answer index must be an integer"

        correct_index = source.config.get("correct_answer_index")
        if not isinstance(correct_index, int):
            return False, "Invalid quiz configuration"

        if answer_index == correct_index:
            return True, None

        return False, "Incorrect answer"
