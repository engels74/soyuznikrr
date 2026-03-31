"""Tests for PlexOAuthService retry logic.

Verifies that transient network errors and HTTP status errors are retried
using RetryPolicy with the correct predicates and retry counts.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zondarr.media.providers.plex.oauth_service import (
    PlexOAuthError,
    PlexOAuthService,
)


def _make_successful_response(pin_id: int = 123, code: str = "ABCD") -> MagicMock:
    """Create a mock successful Plex PIN creation response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=resp)
    resp.json = MagicMock(
        return_value={
            "id": pin_id,
            "code": code,
            "expiresAt": "2099-01-01T00:00:00Z",
        }
    )
    return resp


def _make_pin_check_response(auth_token: str | None = None) -> MagicMock:
    """Create a mock successful Plex PIN check response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=resp)
    resp.json = MagicMock(return_value={"authToken": auth_token})
    return resp


def _make_user_email_response(email: str = "test@example.com") -> MagicMock:
    """Create a mock successful Plex user email response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=resp)
    resp.json = MagicMock(return_value={"email": email})
    return resp


class TestCreatePinRetry:
    """Retry logic for transient errors in create_pin()."""

    async def test_succeeds_on_first_try(self) -> None:
        """create_pin succeeds without retry when no error occurs."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = _make_successful_response()

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.create_pin()
                assert result.pin_id == 123
                assert result.code == "ABCD"
                assert mock_post.call_count == 1
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_connect_error_then_succeeds(
        self, mock_sleep: AsyncMock
    ) -> None:
        """create_pin retries on ConnectError and succeeds on second attempt."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = [
                httpx.ConnectError("Connection refused"),
                _make_successful_response(),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.create_pin()
                assert result.pin_id == 123
                assert mock_post.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_timeout_then_succeeds(
        self, mock_sleep: AsyncMock
    ) -> None:
        """create_pin retries on TimeoutException and succeeds on third attempt."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = [
                httpx.ReadTimeout("Read timed out"),
                httpx.ConnectTimeout("Connect timed out"),
                _make_successful_response(),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.create_pin()
                assert result.pin_id == 123
                assert mock_post.call_count == 3
                assert mock_sleep.call_count == 2
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_raises_after_all_retries_exhausted(
        self, mock_sleep: AsyncMock
    ) -> None:
        """create_pin raises PlexOAuthError after 6 failed attempts (1 + 5 retries)."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
                assert "Connection refused" in str(exc_info.value.cause)
                assert mock_post.call_count == 6  # 1 initial + 5 retries
                assert mock_sleep.call_count == 5
            finally:
                await service.close()

    async def test_no_retry_on_http_status_error(self) -> None:
        """create_pin does not retry on non-retryable HTTPStatusError (e.g. 500)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
                assert mock_post.call_count == 1  # No retries
            finally:
                await service.close()

    async def test_no_retry_on_non_transient_request_error(self) -> None:
        """create_pin does not retry on non-transient RequestError (e.g. InvalidURL)."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.DecodingError("Invalid encoding")

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
                assert mock_post.call_count == 1  # No retries
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_502_status_error(self, mock_sleep: AsyncMock) -> None:
        """create_pin retries on HTTP 502 (retryable status code)."""
        mock_response_502 = MagicMock()
        mock_response_502.status_code = 502
        mock_response_502.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Gateway", request=MagicMock(), response=mock_response_502
            )
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = [
                mock_response_502,
                _make_successful_response(),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.create_pin()
                assert result.pin_id == 123
                assert mock_post.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    async def test_no_retry_on_400_status_error(self) -> None:
        """create_pin does not retry on HTTP 400 (non-retryable status code)."""
        mock_response_400 = MagicMock()
        mock_response_400.status_code = 400
        mock_response_400.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=mock_response_400
            )
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response_400

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
                assert "400" in exc_info.value.message
                assert mock_post.call_count == 1  # No retries
            finally:
                await service.close()


class TestCheckPinRetry:
    """Retry logic for transient errors in check_pin()."""

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_connect_error(self, mock_sleep: AsyncMock) -> None:
        """check_pin retries on ConnectError and succeeds."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.ConnectError("Connection refused"),
                _make_pin_check_response(auth_token=None),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.check_pin(123)
                assert result.authenticated is False
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_timeout(self, mock_sleep: AsyncMock) -> None:
        """check_pin retries on TimeoutException and succeeds."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.ReadTimeout("Read timed out"),
                _make_pin_check_response(auth_token=None),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.check_pin(123)
                assert result.authenticated is False
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    async def test_no_retry_on_http_status_error(self) -> None:
        """check_pin does not retry on HTTPStatusError (passes through to handlers)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.check_pin(123)

                assert exc_info.value.operation == "check_pin"
                assert mock_get.call_count == 1  # No retries
            finally:
                await service.close()

    async def test_429_returns_gracefully(self) -> None:
        """check_pin returns unauthenticated on 429 (rate limited)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.check_pin(123)
                assert result.authenticated is False
                assert result.error is None
                assert mock_get.call_count == 1
            finally:
                await service.close()


class TestGetUserEmailRetry:
    """Retry logic for transient errors in get_user_email()."""

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_connect_error(self, mock_sleep: AsyncMock) -> None:
        """get_user_email retries on ConnectError and succeeds."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.ConnectError("Connection refused"),
                _make_user_email_response("user@example.com"),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                email = await service.get_user_email("test-token")
                assert email == "user@example.com"
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_retries_on_503_status_error(self, mock_sleep: AsyncMock) -> None:
        """get_user_email retries on HTTP 503 (retryable status code)."""
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        mock_response_503.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=mock_response_503,
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                mock_response_503,
                _make_user_email_response("user@example.com"),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                email = await service.get_user_email("test-token")
                assert email == "user@example.com"
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once()
            finally:
                await service.close()

    @patch(
        "zondarr.core.retry.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_raises_after_retries_exhausted(self, mock_sleep: AsyncMock) -> None:
        """get_user_email raises PlexOAuthError after all retries exhausted."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.get_user_email("test-token")

                assert exc_info.value.operation == "get_user_email"
                assert "Connection refused" in str(exc_info.value.cause)
                assert mock_get.call_count == 4  # 1 initial + 3 retries
                assert mock_sleep.call_count == 3
            finally:
                await service.close()
