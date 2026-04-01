"""Tests for retry predicate functions in zondarr.core.retry."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from zondarr.core.retry import (
    _extract_retry_after,  # pyright: ignore[reportPrivateUsage]
    is_retryable_httpx_connection,
    is_retryable_httpx_error,
    is_retryable_sync_error,
)
from zondarr.media.exceptions import MediaClientError


def _make_http_status_error(
    status_code: int,
    headers: dict[str, str] | None = None,
) -> httpx.HTTPStatusError:
    """Create an HTTPStatusError with the given status code and headers."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request, headers=headers or {})
    return httpx.HTTPStatusError(
        f"{status_code} Error", request=request, response=response
    )


# ---------------------------------------------------------------------------
# is_retryable_httpx_error
# ---------------------------------------------------------------------------


class TestIsRetryableHttpxError:
    def test_connect_error_is_retryable(self) -> None:
        exc = httpx.ConnectError("connection refused")
        assert is_retryable_httpx_error(exc) is True

    def test_timeout_exception_is_retryable(self) -> None:
        exc = httpx.ReadTimeout("read timed out")
        assert is_retryable_httpx_error(exc) is True

    def test_connect_timeout_is_retryable(self) -> None:
        exc = httpx.ConnectTimeout("connect timed out")
        assert is_retryable_httpx_error(exc) is True

    @pytest.mark.parametrize("status_code", [429, 502, 503, 504])
    def test_retryable_status_codes(self, status_code: int) -> None:
        exc = _make_http_status_error(status_code)
        assert is_retryable_httpx_error(exc) is True

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 405, 422, 500])
    def test_non_retryable_status_codes(self, status_code: int) -> None:
        exc = _make_http_status_error(status_code)
        assert is_retryable_httpx_error(exc) is False

    def test_non_httpx_exception_is_not_retryable(self) -> None:
        assert is_retryable_httpx_error(ValueError("bad value")) is False

    def test_generic_exception_is_not_retryable(self) -> None:
        assert is_retryable_httpx_error(RuntimeError("oops")) is False

    def test_os_error_is_not_retryable(self) -> None:
        assert is_retryable_httpx_error(OSError("disk error")) is False


# ---------------------------------------------------------------------------
# is_retryable_httpx_connection
# ---------------------------------------------------------------------------


class TestIsRetryableHttpxConnection:
    def test_connect_error_is_retryable(self) -> None:
        exc = httpx.ConnectError("connection refused")
        assert is_retryable_httpx_connection(exc) is True

    def test_timeout_exception_is_retryable(self) -> None:
        exc = httpx.ReadTimeout("read timed out")
        assert is_retryable_httpx_connection(exc) is True

    def test_connect_timeout_is_retryable(self) -> None:
        exc = httpx.ConnectTimeout("connect timed out")
        assert is_retryable_httpx_connection(exc) is True

    @pytest.mark.parametrize("status_code", [429, 502, 503, 504])
    def test_http_status_error_not_retryable_even_for_transient_codes(
        self, status_code: int
    ) -> None:
        exc = _make_http_status_error(status_code)
        assert is_retryable_httpx_connection(exc) is False

    @pytest.mark.parametrize("status_code", [400, 401, 404, 500])
    def test_http_status_error_not_retryable_for_client_errors(
        self, status_code: int
    ) -> None:
        exc = _make_http_status_error(status_code)
        assert is_retryable_httpx_connection(exc) is False

    def test_non_httpx_exception_is_not_retryable(self) -> None:
        assert is_retryable_httpx_connection(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# is_retryable_sync_error (regression tests)
# ---------------------------------------------------------------------------


class TestIsRetryableSyncErrorRegression:
    def test_external_service_error_is_retryable(self) -> None:
        exc = ExternalServiceError("plex", "service down")
        assert is_retryable_sync_error(exc) is True

    def test_timeout_error_is_retryable(self) -> None:
        assert is_retryable_sync_error(TimeoutError("timed out")) is True

    def test_connection_error_is_retryable(self) -> None:
        assert is_retryable_sync_error(ConnectionError("refused")) is True

    def test_not_found_error_is_not_retryable(self) -> None:
        exc = NotFoundError("User", "abc123")
        assert is_retryable_sync_error(exc) is False

    def test_validation_error_is_not_retryable(self) -> None:
        exc = ValidationError("invalid", field_errors={"name": ["required"]})
        assert is_retryable_sync_error(exc) is False

    def test_media_client_error_retryable_by_default(self) -> None:
        exc = MediaClientError("transient", operation="test_connection")
        assert is_retryable_sync_error(exc) is True

    def test_media_client_error_non_retryable_code(self) -> None:
        exc = MediaClientError(
            "invalid token",
            operation="test_connection",
            error_code="INVALID_TOKEN",
        )
        assert is_retryable_sync_error(exc) is False

    def test_unknown_exception_is_not_retryable(self) -> None:
        assert is_retryable_sync_error(RuntimeError("unknown")) is False


# ---------------------------------------------------------------------------
# _extract_retry_after
# ---------------------------------------------------------------------------


class TestExtractRetryAfter:
    def test_returns_seconds_from_429_with_header(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "5"})
        assert _extract_retry_after(exc, max_delay=60.0) == 5.0

    def test_clamps_to_max_delay(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "120"})
        assert _extract_retry_after(exc, max_delay=30.0) == 30.0

    def test_returns_none_for_non_429_status(self) -> None:
        exc = _make_http_status_error(503, headers={"retry-after": "5"})
        assert _extract_retry_after(exc, max_delay=60.0) is None

    def test_returns_none_when_header_absent(self) -> None:
        exc = _make_http_status_error(429)
        assert _extract_retry_after(exc, max_delay=60.0) is None

    def test_returns_none_for_non_httpx_exception(self) -> None:
        assert _extract_retry_after(ValueError("bad"), max_delay=60.0) is None

    def test_returns_none_for_unparseable_header(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "not-a-number"})
        assert _extract_retry_after(exc, max_delay=60.0) is None

    def test_returns_none_for_negative_value(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "-1"})
        assert _extract_retry_after(exc, max_delay=60.0) is None

    def test_handles_fractional_seconds(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "1.5"})
        assert _extract_retry_after(exc, max_delay=60.0) == 1.5

    def test_zero_seconds_is_valid(self) -> None:
        exc = _make_http_status_error(429, headers={"retry-after": "0"})
        assert _extract_retry_after(exc, max_delay=60.0) == 0.0

    def test_http_date_future_returns_positive_delay(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=30)
        date_str = format_datetime(future, usegmt=True)
        exc = _make_http_status_error(429, headers={"retry-after": date_str})
        result = _extract_retry_after(exc, max_delay=60.0)
        assert result is not None
        # Allow some tolerance for test execution time.
        assert 28.0 <= result <= 31.0

    def test_http_date_past_returns_zero(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=10)
        date_str = format_datetime(past, usegmt=True)
        exc = _make_http_status_error(429, headers={"retry-after": date_str})
        assert _extract_retry_after(exc, max_delay=60.0) == 0.0

    def test_http_date_clamped_to_max_delay(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=120)
        date_str = format_datetime(future, usegmt=True)
        exc = _make_http_status_error(429, headers={"retry-after": date_str})
        assert _extract_retry_after(exc, max_delay=30.0) == 30.0

    def test_naive_datetime_treated_as_utc(self) -> None:
        """Naive datetime from parsedate_to_datetime is assumed UTC."""
        future = datetime.now(UTC) + timedelta(seconds=30)
        # Craft a date string without timezone — parsedate_to_datetime
        # returns a naive datetime for such inputs.
        naive_date_str = future.strftime("%a, %d %b %Y %H:%M:%S")
        exc = _make_http_status_error(429, headers={"retry-after": naive_date_str})
        result = _extract_retry_after(exc, max_delay=60.0)
        assert result is not None
        assert 28.0 <= result <= 31.0

    def test_malformed_http_date_returns_none(self) -> None:
        exc = _make_http_status_error(
            429, headers={"retry-after": "not-a-number-or-date"}
        )
        assert _extract_retry_after(exc, max_delay=60.0) is None
