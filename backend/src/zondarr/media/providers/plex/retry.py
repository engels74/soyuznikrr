"""Async retry utility for Plex operations.

Provides a reusable async retry function with exponential backoff
and jitter for transient failure recovery when calling Plex APIs.
"""

import random
from collections.abc import Awaitable, Callable

import structlog

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5
DEFAULT_MAX_DELAY = 30.0


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    operation_name: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable: Callable[[Exception], bool] = lambda _: True,
    sleep: Callable[[float], Awaitable[object]] | None = None,
) -> T:
    """Execute an async operation with retry and exponential backoff with jitter.

    Args:
        operation: Async callable to execute.
        operation_name: Human-readable name for structured logging.
        max_retries: Maximum number of retry attempts (0 means single attempt).
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay cap in seconds.
        retryable: Predicate that returns True if the exception is retryable.
        sleep: Async sleep function (defaults to asyncio.sleep). Useful for testing.

    Returns:
        The result of the operation on success.

    Raises:
        Exception: The last exception after all retries are exhausted,
            or immediately if the exception is not retryable.
    """
    if sleep is None:
        import asyncio

        sleep = asyncio.sleep

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc

            if not retryable(exc):
                raise

            if attempt >= max_retries:
                log.error(
                    "retry_exhausted",
                    operation=operation_name,
                    attempts=attempt + 1,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                raise

            # Exponential backoff with jitter
            delay: float = min(base_delay * (2.0**attempt), max_delay)
            jitter: float = random.uniform(0, delay * 0.5)  # noqa: S311
            delay = delay + jitter

            log.warning(
                "retry_attempt",
                operation=operation_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=round(delay, 3),
                error_type=type(exc).__name__,
                error=str(exc),
            )

            _ = await sleep(delay)

    # Unreachable: last_exc is always set when the loop completes without returning.
    if last_exc is not None:  # pragma: no cover
        raise last_exc
    raise RuntimeError(
        "retry loop exited without result or exception"
    )  # pragma: no cover
