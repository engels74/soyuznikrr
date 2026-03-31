"""Tests for retry predicate functions in zondarr.core.retry."""

import httpx
import pytest

from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from zondarr.core.retry import (
    is_retryable_httpx_connection,
    is_retryable_httpx_error,
    is_retryable_sync_error,
)
from zondarr.media.exceptions import MediaClientError


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an HTTPStatusError with the given status code."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request)
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
