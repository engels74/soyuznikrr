"""Tests for PlexOAuthService.create_pin() retry logic.

Verifies that transient network errors (ConnectError, TimeoutException)
are retried up to 2 times with exponential backoff, while non-transient
errors (HTTPStatusError, other RequestErrors) are raised immediately.
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
        "zondarr.media.providers.plex.oauth_service.asyncio.sleep",
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
                mock_sleep.assert_called_once_with(0.5)
            finally:
                await service.close()

    @patch(
        "zondarr.media.providers.plex.oauth_service.asyncio.sleep",
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
                mock_sleep.assert_any_call(0.5)
                mock_sleep.assert_any_call(1.0)
            finally:
                await service.close()

    @patch(
        "zondarr.media.providers.plex.oauth_service.asyncio.sleep",
        new_callable=AsyncMock,
    )
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
