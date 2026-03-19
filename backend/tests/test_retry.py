"""Tests for retry and circuit-breaker infrastructure."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from zondarr.core.retry import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    RetryPolicy,
    is_retryable_sync_error,
)
from zondarr.media.exceptions import MediaClientError

# ---------------------------------------------------------------------------
# is_retryable_sync_error
# ---------------------------------------------------------------------------


class TestIsRetryableSyncError:
    def test_external_service_error_is_retryable(self) -> None:
        exc = ExternalServiceError("svc", "boom")
        assert is_retryable_sync_error(exc) is True

    def test_timeout_error_is_retryable(self) -> None:
        assert is_retryable_sync_error(TimeoutError("timed out")) is True

    def test_connection_error_is_retryable(self) -> None:
        assert is_retryable_sync_error(ConnectionError("refused")) is True

    def test_os_error_is_retryable(self) -> None:
        assert is_retryable_sync_error(OSError("disk")) is True

    def test_not_found_error_is_not_retryable(self) -> None:
        exc = NotFoundError("User", "123")
        assert is_retryable_sync_error(exc) is False

    def test_validation_error_is_not_retryable(self) -> None:
        exc = ValidationError("bad input", field_errors={"x": ["required"]})
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_invalid_token_is_not_retryable(self) -> None:
        exc = MediaClientError(
            "auth failed",
            operation="test_connection",
            error_code="INVALID_TOKEN",
        )
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_user_not_found_is_not_retryable(self) -> None:
        exc = MediaClientError(
            "no user",
            operation="create_user",
            error_code="USER_NOT_FOUND",
        )
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_username_taken_is_not_retryable(self) -> None:
        exc = MediaClientError(
            "taken",
            operation="create_user",
            error_code="USERNAME_TAKEN",
        )
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_permission_denied_is_not_retryable(self) -> None:
        exc = MediaClientError(
            "denied",
            operation="create_user",
            error_code="PERMISSION_DENIED",
        )
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_no_special_code_is_retryable(self) -> None:
        exc = MediaClientError(
            "transient failure",
            operation="list_libraries",
        )
        assert is_retryable_sync_error(exc) is True

    def test_media_client_error_generic_code_is_retryable(self) -> None:
        exc = MediaClientError(
            "server error",
            operation="sync",
            error_code="INTERNAL_ERROR",
        )
        assert is_retryable_sync_error(exc) is True

    def test_unknown_runtime_error_is_not_retryable(self) -> None:
        assert is_retryable_sync_error(RuntimeError("unexpected")) is False

    def test_unknown_value_error_is_not_retryable(self) -> None:
        assert is_retryable_sync_error(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    async def test_success_on_first_try(self) -> None:
        policy = RetryPolicy(max_retries=3, backoff_base=1.0)
        operation = AsyncMock(return_value="ok")

        result = await policy.execute(operation)

        assert result == "ok"
        assert operation.await_count == 1

    async def test_transient_failure_then_success(self) -> None:
        policy = RetryPolicy(max_retries=3, backoff_base=0.1)
        operation = AsyncMock(
            side_effect=[ConnectionError("fail"), ConnectionError("fail"), "ok"],
        )

        with patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await policy.execute(operation)

        assert result == "ok"
        assert operation.await_count == 3

    async def test_non_retryable_error_fails_immediately(self) -> None:
        policy = RetryPolicy(max_retries=3, backoff_base=0.1)
        exc = NotFoundError("User", "123")
        operation = AsyncMock(side_effect=exc)

        with pytest.raises(NotFoundError):
            await policy.execute(operation)

        assert operation.await_count == 1

    async def test_all_retries_exhausted_raises_last_exception(self) -> None:
        policy = RetryPolicy(max_retries=2, backoff_base=0.1)
        operation = AsyncMock(side_effect=ConnectionError("always fails"))

        with (
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ConnectionError, match="always fails"),
        ):
            await policy.execute(operation)

        assert operation.await_count == 3  # 1 initial + 2 retries

    async def test_backoff_delay_within_expected_range(self) -> None:
        policy = RetryPolicy(
            max_retries=3, backoff_base=1.0, max_delay=10.0, jitter=0.1
        )
        operation = AsyncMock(
            side_effect=[ConnectionError(), ConnectionError(), "ok"],
        )
        sleep_mock = AsyncMock()

        with patch("zondarr.core.retry.asyncio.sleep", sleep_mock):
            await policy.execute(operation)

        assert sleep_mock.await_count == 2
        # attempt 0: base * 2^0 = 1.0, with jitter [1.0, 1.1]
        delay_0 = sleep_mock.call_args_list[0][0][0]
        assert 1.0 <= delay_0 <= 1.1

        # attempt 1: base * 2^1 = 2.0, with jitter [2.0, 2.2]
        delay_1 = sleep_mock.call_args_list[1][0][0]
        assert 2.0 <= delay_1 <= 2.2

    async def test_backoff_respects_max_delay(self) -> None:
        policy = RetryPolicy(
            max_retries=5, backoff_base=10.0, max_delay=15.0, jitter=0.0
        )
        operation = AsyncMock(
            side_effect=[
                ConnectionError(),
                ConnectionError(),
                ConnectionError(),
                "ok",
            ],
        )
        sleep_mock = AsyncMock()

        with patch("zondarr.core.retry.asyncio.sleep", sleep_mock):
            with patch("zondarr.core.retry.random.random", return_value=0.0):
                await policy.execute(operation)

        # attempt 0: min(10*1, 15) = 10.0
        # attempt 1: min(10*2, 15) = 15.0 (capped)
        # attempt 2: min(10*4, 15) = 15.0 (capped)
        assert sleep_mock.call_args_list[0][0][0] == 10.0
        assert sleep_mock.call_args_list[1][0][0] == 15.0
        assert sleep_mock.call_args_list[2][0][0] == 15.0

    async def test_on_retry_callback_called_with_correct_args(self) -> None:
        policy = RetryPolicy(max_retries=2, backoff_base=1.0, jitter=0.0)
        err = ConnectionError("oops")
        operation = AsyncMock(side_effect=[err, "ok"])
        on_retry = MagicMock()

        with (
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            patch("zondarr.core.retry.random.random", return_value=0.0),
        ):
            await policy.execute(operation, on_retry=on_retry)

        on_retry.assert_called_once()
        args = on_retry.call_args[0]
        assert args[0] == 0  # attempt
        assert args[1] == 1.0  # delay (backoff_base * 2^0 * 1.0)
        assert args[2] is err  # exception

    async def test_zero_max_retries_behaves_like_direct_execution(self) -> None:
        policy = RetryPolicy(max_retries=0, backoff_base=1.0)

        # Success case
        operation = AsyncMock(return_value="ok")
        result = await policy.execute(operation)
        assert result == "ok"

        # Failure case — raises immediately
        operation = AsyncMock(side_effect=ConnectionError("fail"))
        with pytest.raises(ConnectionError):
            await policy.execute(operation)
        assert operation.await_count == 1

    async def test_custom_is_retryable_predicate(self) -> None:
        policy = RetryPolicy(max_retries=3, backoff_base=0.1)
        operation = AsyncMock(
            side_effect=[ValueError("transient"), "ok"],
        )

        with patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await policy.execute(
                operation,
                is_retryable=lambda exc: isinstance(exc, ValueError),
            )

        assert result == "ok"
        assert operation.await_count == 2


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60)
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 0
        assert cb.next_attempt_at is None

    def test_should_allow_when_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60)
        assert cb.should_allow() is True

    def test_opens_at_failure_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "CLOSED"

        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.consecutive_failures == 3

    def test_should_allow_returns_false_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60)
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.should_allow() is False

    def test_next_attempt_at_set_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60)
        before = datetime.now(UTC)
        cb.record_failure()
        after = datetime.now(UTC)

        naa = cb.next_attempt_at
        assert naa is not None
        assert before + timedelta(seconds=60) <= naa <= after + timedelta(seconds=60)

    def test_transitions_to_half_open_after_recovery_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)
        cb.record_failure()
        assert cb.state == "OPEN"

        past = datetime.now(UTC) - timedelta(seconds=31)
        cb._opened_at = past

        assert cb.should_allow() is True
        assert cb.state == "HALF_OPEN"

    def test_closes_on_success_in_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)
        cb.record_failure()
        cb._opened_at = datetime.now(UTC) - timedelta(seconds=31)
        cb.should_allow()  # transitions to HALF_OPEN
        assert cb.state == "HALF_OPEN"

        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 0
        assert cb.next_attempt_at is None

    def test_reopens_on_failure_in_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)
        cb.record_failure()
        cb._opened_at = datetime.now(UTC) - timedelta(seconds=31)
        cb.should_allow()  # transitions to HALF_OPEN
        assert cb.state == "HALF_OPEN"

        cb.record_failure()
        assert cb.state == "OPEN"

    def test_record_success_resets_from_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2

        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 0

    def test_failures_below_threshold_stay_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 4


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------


class TestCircuitBreakerRegistry:
    def test_get_or_create_returns_new_breaker(self) -> None:
        reg = CircuitBreakerRegistry()
        server_id = uuid4()
        cb = reg.get_or_create(
            server_id, failure_threshold=3, recovery_timeout_seconds=60
        )
        assert isinstance(cb, CircuitBreaker)
        assert cb.state == "CLOSED"

    def test_get_or_create_returns_same_breaker(self) -> None:
        reg = CircuitBreakerRegistry()
        server_id = uuid4()
        cb1 = reg.get_or_create(
            server_id, failure_threshold=3, recovery_timeout_seconds=60
        )
        cb2 = reg.get_or_create(
            server_id, failure_threshold=3, recovery_timeout_seconds=60
        )
        assert cb1 is cb2

    def test_remove_deletes_breaker(self) -> None:
        reg = CircuitBreakerRegistry()
        server_id = uuid4()
        reg.get_or_create(server_id, failure_threshold=3, recovery_timeout_seconds=60)
        reg.remove(server_id)
        assert reg.get_state(server_id) is None

    def test_remove_nonexistent_is_noop(self) -> None:
        reg = CircuitBreakerRegistry()
        reg.remove(uuid4())  # Should not raise

    def test_reset_clears_to_closed(self) -> None:
        reg = CircuitBreakerRegistry()
        server_id = uuid4()
        cb = reg.get_or_create(
            server_id, failure_threshold=1, recovery_timeout_seconds=60
        )
        cb.record_failure()
        assert cb.state == "OPEN"

        reg.reset(server_id)
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 0

    def test_reset_nonexistent_is_noop(self) -> None:
        reg = CircuitBreakerRegistry()
        reg.reset(uuid4())  # Should not raise

    def test_get_state_returns_tuple(self) -> None:
        reg = CircuitBreakerRegistry()
        server_id = uuid4()
        cb = reg.get_or_create(
            server_id, failure_threshold=3, recovery_timeout_seconds=60
        )
        cb.record_failure()

        state = reg.get_state(server_id)
        assert state is not None
        assert state[0] == "CLOSED"
        assert state[1] == 1
        assert state[2] is None  # next_attempt_at is None when CLOSED

    def test_get_state_nonexistent_returns_none(self) -> None:
        reg = CircuitBreakerRegistry()
        assert reg.get_state(uuid4()) is None
