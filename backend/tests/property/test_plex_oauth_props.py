"""Property-based tests for PlexOAuthService.

Feature: plex-integration
Properties: 11, 12
Validates: Requirements 13.1, 13.2, 14.1, 14.2, 14.3
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from zondarr.services.plex_oauth import (
    PlexOAuthError,
    PlexOAuthPin,
    PlexOAuthResult,
    PlexOAuthService,
)

# Strategy for client IDs (alphanumeric, 16-64 chars)
client_id_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-_"),
    min_size=16,
    max_size=64,
).filter(lambda s: s.strip())

# Strategy for PIN IDs (positive integers)
pin_id_strategy = st.integers(min_value=1, max_value=999999999)

# Strategy for PIN codes (alphanumeric, 4-8 chars)
pin_code_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=4,
    max_size=8,
).filter(lambda s: s.strip())

# Strategy for valid email addresses
email_strategy = st.emails()

# Strategy for auth tokens (alphanumeric, 20-50 chars)
auth_token_strategy = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="-_"),
    min_size=20,
    max_size=50,
).filter(lambda s: s.strip())


class TestOAuthPinGenerationReturnsValidResponse:
    """
    Feature: plex-integration
    Property 11: OAuth PIN Generation Returns Valid Response

    For any call to create_pin(), the response should contain a positive
    pin_id, a non-empty auth_url starting with "https://", and an
    expires_at in the future.

    **Validates: Requirements 13.1, 13.2**
    """

    @settings(max_examples=100)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
        pin_code=pin_code_strategy,
        expires_minutes=st.integers(min_value=1, max_value=60),
    )
    @pytest.mark.asyncio
    async def test_create_pin_returns_valid_response(
        self,
        client_id: str,
        pin_id: int,
        pin_code: str,
        expires_minutes: int,
    ) -> None:
        """create_pin returns PlexOAuthPin with valid pin_id, auth_url, and expires_at."""
        # Calculate expiration time in the future
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
        expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        mock_response.json = MagicMock(
            return_value={
                "id": pin_id,
                "code": pin_code,
                "expiresAt": expires_at_str,
            }
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.create_pin()

                # Verify result is PlexOAuthPin
                assert isinstance(result, PlexOAuthPin)

                # pin_id should be positive
                assert result.pin_id > 0
                assert result.pin_id == pin_id

                # code should be non-empty
                assert result.code
                assert result.code == pin_code

                # auth_url should start with https://
                assert result.auth_url.startswith("https://")

                # auth_url should contain the client_id and code
                assert client_id in result.auth_url
                assert pin_code in result.auth_url

                # expires_at should be in the future (or very close to now)
                # Allow 1 second tolerance for test execution time
                assert result.expires_at >= datetime.now(UTC) - timedelta(seconds=1)
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
        pin_code=pin_code_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_pin_auth_url_format(
        self,
        client_id: str,
        pin_id: int,
        pin_code: str,
    ) -> None:
        """create_pin returns auth_url with correct format for Plex authentication."""
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        mock_response.json = MagicMock(
            return_value={
                "id": pin_id,
                "code": pin_code,
                "expiresAt": expires_at_str,
            }
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.create_pin()

                # auth_url should be the Plex auth URL
                assert result.auth_url.startswith("https://app.plex.tv/auth#")

                # Should contain clientID parameter
                assert f"clientID={client_id}" in result.auth_url

                # Should contain code parameter
                assert f"code={pin_code}" in result.auth_url
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_pin_raises_on_http_error(
        self,
        client_id: str,
    ) -> None:
        """create_pin raises PlexOAuthError on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
    )
    @pytest.mark.asyncio
    async def test_create_pin_raises_on_invalid_response(
        self,
        client_id: str,
    ) -> None:
        """create_pin raises PlexOAuthError when response is missing required fields."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        # Missing required fields
        mock_response.json = MagicMock(return_value={})

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.create_pin()

                assert exc_info.value.operation == "create_pin"
            finally:
                await service.close()


class TestOAuthPinVerificationRetrievesEmailOnSuccess:
    """
    Feature: plex-integration
    Property 12: OAuth PIN Verification Retrieves Email on Success

    For any authenticated PIN, check_pin() should return a result with
    authenticated=True and a non-empty email field containing a valid
    email address.

    **Validates: Requirements 14.1, 14.2, 14.3**
    """

    @settings(max_examples=100)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
        auth_token=auth_token_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_check_pin_returns_email_on_success(
        self,
        client_id: str,
        pin_id: int,
        auth_token: str,
        email: str,
    ) -> None:
        """check_pin returns authenticated=True and email when PIN is authenticated."""
        # Mock the PIN check response (authenticated)
        mock_pin_response = MagicMock()
        mock_pin_response.raise_for_status = MagicMock(return_value=mock_pin_response)
        mock_pin_response.json = MagicMock(
            return_value={
                "id": pin_id,
                "authToken": auth_token,
            }
        )

        # Mock the user email response
        mock_user_response = MagicMock()
        mock_user_response.raise_for_status = MagicMock(return_value=mock_user_response)
        mock_user_response.json = MagicMock(
            return_value={
                "email": email,
            }
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            # First call returns PIN response, second call returns user response
            mock_get.side_effect = [mock_pin_response, mock_user_response]

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.check_pin(pin_id)

                # Verify result
                assert isinstance(result, PlexOAuthResult)
                assert result.authenticated is True
                assert result.email is not None
                assert result.email == email
                assert result.auth_token == auth_token
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
    )
    @pytest.mark.asyncio
    async def test_check_pin_returns_not_authenticated_when_pending(
        self,
        client_id: str,
        pin_id: int,
    ) -> None:
        """check_pin returns authenticated=False when PIN is not yet authenticated."""
        # Mock the PIN check response (not authenticated - no authToken)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        mock_response.json = MagicMock(
            return_value={
                "id": pin_id,
                "authToken": None,
            }
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.check_pin(pin_id)

                assert isinstance(result, PlexOAuthResult)
                assert result.authenticated is False
                assert result.email is None
                assert result.auth_token is None
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
    )
    @pytest.mark.asyncio
    async def test_check_pin_returns_error_when_not_found(
        self,
        client_id: str,
        pin_id: int,
    ) -> None:
        """check_pin returns authenticated=False with error when PIN is not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.check_pin(pin_id)

                assert isinstance(result, PlexOAuthResult)
                assert result.authenticated is False
                assert result.error == "PIN not found"
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        pin_id=pin_id_strategy,
    )
    @pytest.mark.asyncio
    async def test_check_pin_raises_on_server_error(
        self,
        client_id: str,
        pin_id: int,
    ) -> None:
        """check_pin raises PlexOAuthError on server error (non-404)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.check_pin(pin_id)

                assert exc_info.value.operation == "check_pin"
            finally:
                await service.close()


class TestGetUserEmail:
    """Tests for get_user_email method."""

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        auth_token=auth_token_strategy,
        email=email_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_user_email_returns_email(
        self,
        client_id: str,
        auth_token: str,
        email: str,
    ) -> None:
        """get_user_email returns the user's email address."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        mock_response.json = MagicMock(
            return_value={
                "email": email,
            }
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                result = await service.get_user_email(auth_token)

                assert result == email
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        auth_token=auth_token_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_user_email_raises_on_http_error(
        self,
        client_id: str,
        auth_token: str,
    ) -> None:
        """get_user_email raises PlexOAuthError on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.get_user_email(auth_token)

                assert exc_info.value.operation == "get_user_email"
            finally:
                await service.close()

    @settings(max_examples=25)
    @given(
        client_id=client_id_strategy,
        auth_token=auth_token_strategy,
    )
    @pytest.mark.asyncio
    async def test_get_user_email_raises_on_missing_email(
        self,
        client_id: str,
        auth_token: str,
    ) -> None:
        """get_user_email raises PlexOAuthError when email is missing from response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(return_value=mock_response)
        # Missing email field
        mock_response.json = MagicMock(return_value={})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            service = PlexOAuthService(client_id=client_id)
            try:
                with pytest.raises(PlexOAuthError) as exc_info:
                    _ = await service.get_user_email(auth_token)

                assert exc_info.value.operation == "get_user_email"
            finally:
                await service.close()
