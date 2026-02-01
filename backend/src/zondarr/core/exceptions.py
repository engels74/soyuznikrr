"""Domain exceptions for Zondarr.

All domain exceptions inherit from ZondarrError base class.
Each exception includes an error_code and context for traceability.
"""


class ZondarrError(Exception):
    """Base exception for all Zondarr errors.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code for API responses.
        context: Additional context about the error (operation, identifiers, etc.).
    """

    message: str
    error_code: str
    context: dict[str, str | int | bool | None]

    def __init__(
        self, message: str, error_code: str, /, **context: str | int | bool | None
    ) -> None:
        """Initialize a ZondarrError.

        Args:
            message: Human-readable error description.
            error_code: Machine-readable error code.
            **context: Additional context key-value pairs.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context


class ConfigurationError(ZondarrError):
    """Raised when configuration is invalid or missing.

    Used for startup validation failures and missing required settings.
    """


class RepositoryError(ZondarrError):
    """Raised when a repository operation fails.

    Wraps database exceptions with operation context for debugging.

    Attributes:
        original: The original exception that caused this error, if any.
    """

    original: Exception | None

    def __init__(
        self, message: str, /, *, operation: str, original: Exception | None = None
    ) -> None:
        """Initialize a RepositoryError.

        Args:
            message: Human-readable error description.
            operation: The repository operation that failed (e.g., "get_by_id", "create").
            original: The original exception that caused this error.
        """
        super().__init__(message, "REPOSITORY_ERROR", operation=operation)
        self.original = original


class ValidationError(ZondarrError):
    """Raised when input validation fails.

    Contains field-level error details for API responses.

    Attributes:
        field_errors: Mapping of field names to lists of error messages.
    """

    field_errors: dict[str, list[str]]

    def __init__(self, message: str, /, *, field_errors: dict[str, list[str]]) -> None:
        """Initialize a ValidationError.

        Args:
            message: Human-readable error description.
            field_errors: Mapping of field names to lists of error messages.
        """
        super().__init__(message, "VALIDATION_ERROR")
        self.field_errors = field_errors


class NotFoundError(ZondarrError):
    """Raised when a requested resource is not found.

    Includes resource type and identifier for API responses.
    """

    def __init__(self, resource_type: str, identifier: str, /) -> None:
        """Initialize a NotFoundError.

        Args:
            resource_type: The type of resource that was not found (e.g., "User", "MediaServer").
            identifier: The identifier used to look up the resource.
        """
        super().__init__(
            f"{resource_type} not found: {identifier}",
            "NOT_FOUND",
            resource_type=resource_type,
            identifier=identifier,
        )
