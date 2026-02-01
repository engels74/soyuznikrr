"""Media client exceptions.

Provides domain-specific exceptions for media client operations:
- MediaClientError: Raised when a media client operation fails
- UnknownServerTypeError: Raised when an unknown server type is requested

All exceptions inherit from ZondarrError base class and include
error_code and context for traceability.
"""

from zondarr.core.exceptions import ZondarrError


class MediaClientError(ZondarrError):
    """Raised when a media client operation fails.

    Contains operation context including the operation name, server URL,
    and a description of the failure cause for debugging and logging.

    Attributes:
        operation: The media client operation that failed (e.g., "test_connection", "create_user").
        server_url: The URL of the media server where the operation failed (optional).
        cause: A description of what caused the failure.
        media_error_code: Specific error code for the failure (e.g., "USERNAME_TAKEN").
    """

    operation: str
    server_url: str | None
    cause: str
    media_error_code: str | None

    def __init__(
        self,
        message: str,
        /,
        *,
        operation: str,
        server_url: str | None = None,
        cause: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Initialize a MediaClientError.

        Args:
            message: Human-readable error description.
            operation: The media client operation that failed.
            server_url: The URL of the media server (optional).
            cause: A description of the failure cause (optional).
            error_code: Specific error code for the failure (e.g., "USERNAME_TAKEN").
        """
        super().__init__(
            message,
            error_code or "MEDIA_CLIENT_ERROR",
            operation=operation,
            server_url=server_url or "",
            cause=cause or "",
        )
        self.operation = operation
        self.server_url = server_url
        self.cause = cause or ""
        self.media_error_code = error_code


class UnknownServerTypeError(ZondarrError):
    """Raised when an unknown server type is requested from the registry.

    Used by ClientRegistry when get_client_class() or get_capabilities()
    is called with a server type that has not been registered.

    Attributes:
        server_type: The unknown server type that was requested.
    """

    server_type: str

    def __init__(self, server_type: str, /) -> None:
        """Initialize an UnknownServerTypeError.

        Args:
            server_type: The unknown server type that was requested.
        """
        super().__init__(
            f"Unknown server type: {server_type}",
            "UNKNOWN_SERVER_TYPE",
            server_type=server_type,
        )
        self.server_type = server_type
