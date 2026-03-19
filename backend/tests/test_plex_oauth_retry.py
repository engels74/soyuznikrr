"""Tests for PlexOAuthService retry logic.

Verifies that transient network errors (ConnectError, TimeoutException)
are retried up to 2 times with exponential backoff via retry_async,
while non-transient errors (HTTPStatusError, other RequestErrors) are
raised immediately.
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


def _make_user_response(email: str = "user@example.com") -> MagicMock:
    """Create a mock successful Plex user info response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=resp)
    resp.json = MagicMock(return_value={"email": email})
    return resp


def _make_check_pin_response(*, auth_token: str | None = None) -> MagicMock:
    """Create a mock Plex PIN check response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=resp)
    data: dict[str, object] = {}
    if auth_token:
        data["authToken"] = auth_token
    resp.json = MagicMock(return_value=data)
    return resp


# Patch target for asyncio.sleep used by retry_async
_RETRY_SLEEP_PATCH = "asyncio.sleep"


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

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
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
                assert mock_sleep.call_count == 1
            finally:
                await service.close()

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
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

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
    async def test_raises_after_all_retries_exhausted(
        self, mock_sleep: AsyncMock
    ) -> None:
        """create_pin raises PlexOAuthError after 3 failed attempts (1 + 2 retries)."""
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
                assert mock_post.call_count == 3  # 1 initial + 2 retries
                assert mock_sleep.call_count == 2
            finally:
                await service.close()

    async def test_no_retry_on_http_status_error(self) -> None:
        """create_pin does not retry on HTTPStatusError (non-transient)."""
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


class TestCheckPinRetry:
    """Retry logic for transient errors in check_pin()."""

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
    async def test_retries_on_connect_error_then_succeeds(
        self, mock_sleep: AsyncMock
    ) -> None:
        """check_pin retries on ConnectError and succeeds on second attempt."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.ConnectError("Connection refused"),
                _make_check_pin_response(),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                result = await service.check_pin(123)
                assert result.authenticated is False
                assert mock_get.call_count == 2
                assert mock_sleep.call_count == 1
            finally:
                await service.close()

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
    async def test_raises_after_all_retries_exhausted(
        self, mock_sleep: AsyncMock
    ) -> None:
        """check_pin raises PlexOAuthError after all retries exhausted."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.check_pin(123)

                assert exc_info.value.operation == "check_pin"
                assert "Connection refused" in str(exc_info.value.cause)
                assert mock_get.call_count == 3  # 1 initial + 2 retries
            finally:
                await service.close()

    async def test_no_retry_on_http_status_error(self) -> None:
        """check_pin does not retry on HTTPStatusError (non-transient)."""
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


class TestGetUserEmailRetry:
    """Retry logic for transient errors in get_user_email()."""

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
    async def test_retries_on_timeout_then_succeeds(
        self, mock_sleep: AsyncMock
    ) -> None:
        """get_user_email retries on TimeoutException and succeeds."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.ReadTimeout("Read timed out"),
                _make_user_response("user@example.com"),
            ]

            service = PlexOAuthService(client_id="test-client")
            try:
                email = await service.get_user_email("test-token")
                assert email == "user@example.com"
                assert mock_get.call_count == 2
                assert mock_sleep.call_count == 1
            finally:
                await service.close()

    @patch(_RETRY_SLEEP_PATCH, new_callable=AsyncMock)
    async def test_raises_after_all_retries_exhausted(
        self, mock_sleep: AsyncMock
    ) -> None:
        """get_user_email raises PlexOAuthError after all retries exhausted."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.get_user_email("test-token")

                assert exc_info.value.operation == "get_user_email"
                assert "Connection refused" in str(exc_info.value.cause)
                assert mock_get.call_count == 3  # 1 initial + 2 retries
            finally:
                await service.close()

    async def test_no_retry_on_http_status_error(self) -> None:
        """get_user_email does not retry on HTTPStatusError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id="test-client")
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.get_user_email("test-token")

                assert exc_info.value.operation == "get_user_email"
                assert mock_get.call_count == 1  # No retries
            finally:
                await service.close()
