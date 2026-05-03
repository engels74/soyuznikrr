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


class RedemptionError(ValidationError):
    """Raised when invitation redemption fails.

    Carries redemption-specific context so the error handler can produce
    a ``RedemptionErrorResponse`` with the correct error code and optional
    failed server name.  Because it inherits from ``ValidationError``, an
    unhandled ``RedemptionError`` will still be caught by the generic
    validation handler, but a dedicated handler registered *before* the
    ``ValidationError`` entry takes priority in Litestar.

    Attributes:
        redemption_error_code: Machine-readable code (e.g. "INVALID_INVITATION").
        failed_server: Name of the media server that failed, if applicable.
    """

    redemption_error_code: str
    failed_server: str | None

    def __init__(
        self,
        message: str,
        /,
        *,
        redemption_error_code: str,
        failed_server: str | None = None,
    ) -> None:
        """Initialize a RedemptionError.

        Args:
            message: Human-readable error description.
            redemption_error_code: Machine-readable error code for the response.
            failed_server: Optional name of the server that failed.
        """
        super().__init__(message, field_errors={})
        self.redemption_error_code = redemption_error_code
        self.failed_server = failed_server


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


class AuthenticationError(ZondarrError):
    """Raised when authentication fails.

    Covers invalid credentials, disabled accounts, and setup-required states.
    """


class ExternalServiceError(ZondarrError):
    """Raised when an external service (media server) fails.

    Includes service identification for debugging.

    Attributes:
        service_name: The name of the external service that failed.
        original: The original exception that caused this error, if any.
    """

    service_name: str
    original: Exception | None

    def __init__(
        self, service_name: str, message: str, /, *, original: Exception | None = None
    ) -> None:
        """Initialize an ExternalServiceError.

        Args:
            service_name: The name of the external service that failed.
            message: Human-readable error description.
            original: The original exception that caused this error.
        """
        super().__init__(
            message,
            "EXTERNAL_SERVICE_ERROR",
            service_name=service_name,
        )
        self.service_name = service_name
        self.original = original


class MediaServerUnreachableError(ZondarrError):
    """Raised when a media server cannot be reached during sync.

    Mapped to HTTP 503 by ``media_server_unreachable_error_handler``.

    Attributes:
        server_id: The UUID of the media server that was unreachable.
        original: The underlying ``MediaClientError`` that triggered this, if any.
    """

    server_id: str
    original: Exception | None

    def __init__(
        self,
        server_id: str,
        message: str,
        /,
        *,
        original: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            "SERVER_UNREACHABLE",
            server_id=server_id,
        )
        self.server_id = server_id
        self.original = original
