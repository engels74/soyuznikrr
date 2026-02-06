"""API error handlers for Zondarr.

Provides exception handlers for:
- ValidationError: Returns HTTP 400 with field-level error details
- NotFoundError: Returns HTTP 404 with resource type and identifier
- ExternalServiceError: Returns HTTP 502 with service identification
- Generic exceptions: Returns HTTP 500 with correlation ID

All error responses include:
- Correlation IDs for traceability
- Structured logging with context
- Safe error messages (no internal details exposed)

Uses msgspec for high-performance response serialization.
"""

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from litestar import Request, Response
from litestar.datastructures import State
from litestar.exceptions import HTTPException as LitestarHTTPException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
)

from ..core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from .schemas import ErrorResponse, FieldError, ValidationErrorResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]


def _generate_correlation_id() -> str:
    """Generate a unique correlation ID for error tracing."""
    return str(uuid4())


def validation_error_handler(
    request: Request[object, object, State],
    exc: ValidationError,
) -> Response[ValidationErrorResponse]:
    """Handle ValidationError exceptions.

    Returns HTTP 400 with field-level error details.
    Logs the validation failure with correlation ID for debugging.

    Args:
        request: The incoming request.
        exc: The ValidationError exception.

    Returns:
        Response with ValidationErrorResponse body and HTTP 400 status.
    """
    correlation_id = _generate_correlation_id()

    logger.warning(
        "Validation error",
        correlation_id=correlation_id,
        field_errors=exc.field_errors,
        path=str(request.url.path),
    )

    field_errors = [
        FieldError(field=field, messages=messages)
        for field, messages in exc.field_errors.items()
    ]

    return Response(
        ValidationErrorResponse(
            detail=exc.message,
            error_code=exc.error_code,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
            field_errors=field_errors,
        ),
        status_code=HTTP_400_BAD_REQUEST,
    )


def not_found_handler(
    request: Request[object, object, State],
    exc: NotFoundError,
) -> Response[ErrorResponse]:
    """Handle NotFoundError exceptions.

    Returns HTTP 404 with resource type and identifier.
    Logs the not found event with correlation ID for debugging.

    Args:
        request: The incoming request.
        exc: The NotFoundError exception.

    Returns:
        Response with ErrorResponse body and HTTP 404 status.
    """
    correlation_id = _generate_correlation_id()

    # Extract resource info from context
    resource_type = exc.context.get("resource_type", "Resource")
    identifier = exc.context.get("identifier", "unknown")

    logger.info(
        "Resource not found",
        correlation_id=correlation_id,
        resource_type=resource_type,
        identifier=identifier,
        path=str(request.url.path),
    )

    return Response(
        ErrorResponse(
            detail=exc.message,
            error_code=exc.error_code,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        ),
        status_code=HTTP_404_NOT_FOUND,
    )


def internal_error_handler(
    request: Request[object, object, State],
    exc: Exception,
) -> Response[ErrorResponse]:
    """Handle generic exceptions as internal server errors.

    Returns HTTP 500 with a safe error message and correlation ID.
    Logs the full exception with stack trace for debugging.
    Never exposes internal details (stack traces, file paths) in the response.

    Args:
        request: The incoming request.
        exc: The exception that was raised.

    Returns:
        Response with ErrorResponse body and HTTP 500 status.
    """
    correlation_id = _generate_correlation_id()

    # Log full exception details for debugging (not exposed to client)
    logger.exception(
        "Internal server error",
        correlation_id=correlation_id,
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )

    # Return safe error message without internal details
    return Response(
        ErrorResponse(
            detail="An internal error occurred",
            error_code="INTERNAL_ERROR",
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        ),
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )


def litestar_http_exception_handler(
    request: Request[object, object, State],
    exc: LitestarHTTPException,
) -> Response[ErrorResponse]:
    """Handle Litestar's built-in HTTP exceptions (404, 405, etc.).

    Preserves the correct status code from the exception instead of
    falling through to the generic 500 catch-all handler.

    Args:
        request: The incoming request.
        exc: The Litestar HTTPException.

    Returns:
        Response with ErrorResponse body and the exception's status code.
    """
    correlation_id = _generate_correlation_id()

    logger.debug(
        "HTTP error",
        correlation_id=correlation_id,
        path=str(request.url.path),
        status_code=exc.status_code,
    )

    return Response(
        ErrorResponse(
            detail=exc.detail,
            error_code="HTTP_ERROR",
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        ),
        status_code=exc.status_code,
    )


def external_service_error_handler(
    request: Request[object, object, State],
    exc: ExternalServiceError,
) -> Response[ErrorResponse]:
    """Handle ExternalServiceError exceptions.

    Returns HTTP 502 with service identification.
    Logs the external service failure with correlation ID for debugging.

    Args:
        request: The incoming request.
        exc: The ExternalServiceError exception.

    Returns:
        Response with ErrorResponse body and HTTP 502 status.
    """
    correlation_id = _generate_correlation_id()

    logger.warning(
        "External service error",
        correlation_id=correlation_id,
        service_name=exc.service_name,
        path=str(request.url.path),
    )

    return Response(
        ErrorResponse(
            detail=f"External service unavailable: {exc.service_name}",
            error_code=exc.error_code,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        ),
        status_code=HTTP_502_BAD_GATEWAY,
    )
