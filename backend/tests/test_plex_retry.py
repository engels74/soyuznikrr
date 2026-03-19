"""Tests for the async retry utility.

Covers: successful retry, max retries exceeded, non-retryable pass-through,
jitter is applied, and zero retries means a single attempt.
"""

from unittest.mock import AsyncMock

import pytest

from zondarr.media.providers.plex.retry import retry_async


class _TransientError(Exception):
    """Simulates a retryable transient error."""


class _PermanentError(Exception):
    """Simulates a non-retryable error."""


def _is_transient(exc: Exception) -> bool:
    return isinstance(exc, _TransientError)


class TestRetrySuccess:
    """Successful retry after transient failure."""

    async def test_succeeds_after_transient_failure(self) -> None:
        mock_sleep = AsyncMock()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _TransientError("boom")
            return "ok"

        result = await retry_async(
            flaky,
            operation_name="test_op",
            max_retries=3,
            retryable=_is_transient,
            sleep=mock_sleep,
        )

        assert result == "ok"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    async def test_succeeds_on_first_try(self) -> None:
        mock_sleep = AsyncMock()

        async def ok() -> int:
            return 42

        result = await retry_async(
            ok,
            operation_name="first_try",
            max_retries=3,
            sleep=mock_sleep,
        )

        assert result == 42
        assert mock_sleep.call_count == 0


class TestRetryExhausted:
    """Max retries exceeded raises the original exception."""

    async def test_raises_after_max_retries(self) -> None:
        mock_sleep = AsyncMock()

        async def always_fail() -> None:
            raise _TransientError("persistent failure")

        with pytest.raises(_TransientError, match="persistent failure"):
            await retry_async(
                always_fail,
                operation_name="failing_op",
                max_retries=2,
                retryable=_is_transient,
                sleep=mock_sleep,
            )

        # 1 initial + 2 retries = 2 sleeps
        assert mock_sleep.call_count == 2


class TestNonRetryablePassThrough:
    """Non-retryable errors pass through immediately."""

    async def test_non_retryable_raises_immediately(self) -> None:
        mock_sleep = AsyncMock()

        async def permanent() -> None:
            raise _PermanentError("bad request")

        with pytest.raises(_PermanentError, match="bad request"):
            await retry_async(
                permanent,
                operation_name="perm_op",
                max_retries=5,
                retryable=_is_transient,
                sleep=mock_sleep,
            )

        # No sleep calls: raised immediately
        assert mock_sleep.call_count == 0


class TestJitterApplied:
    """Jitter makes delay differ from the exact base calculation."""

    async def test_delay_includes_jitter(self) -> None:
        delays: list[float] = []

        async def capture_sleep(d: float) -> None:
            delays.append(d)

        async def fail() -> None:
            raise _TransientError("err")

        with pytest.raises(_TransientError):
            await retry_async(
                fail,
                operation_name="jitter_test",
                max_retries=3,
                base_delay=1.0,
                retryable=_is_transient,
                sleep=capture_sleep,
            )

        # base delays without jitter: 1.0, 2.0, 4.0
        exact_delays = [1.0, 2.0, 4.0]
        for actual, exact in zip(delays, exact_delays, strict=True):
            # With jitter added, actual should be > exact base
            assert actual >= exact
            # Jitter is up to 50% of base, so max is 1.5x
            assert actual <= exact * 1.5

        # At least one delay should differ from the exact base
        assert any(d != exact for d, exact in zip(delays, exact_delays, strict=True))


class TestZeroRetries:
    """Zero retries means a single attempt."""

    async def test_single_attempt_no_retry(self) -> None:
        mock_sleep = AsyncMock()
        call_count = 0

        async def fail_once() -> None:
            nonlocal call_count
            call_count += 1
            raise _TransientError("single shot")

        with pytest.raises(_TransientError, match="single shot"):
            await retry_async(
                fail_once,
                operation_name="zero_retry",
                max_retries=0,
                retryable=_is_transient,
                sleep=mock_sleep,
            )

        assert call_count == 1
        assert mock_sleep.call_count == 0


class TestMaxDelayCap:
    """Delay is capped at max_delay."""

    async def test_delay_capped(self) -> None:
        delays: list[float] = []

        async def capture_sleep(d: float) -> None:
            delays.append(d)

        async def fail() -> None:
            raise _TransientError("err")

        with pytest.raises(_TransientError):
            await retry_async(
                fail,
                operation_name="cap_test",
                max_retries=10,
                base_delay=5.0,
                max_delay=10.0,
                retryable=_is_transient,
                sleep=capture_sleep,
            )

        # With max_delay=10 and jitter up to 50%, cap is 15.0
        for d in delays:
            assert d <= 10.0 * 1.5
