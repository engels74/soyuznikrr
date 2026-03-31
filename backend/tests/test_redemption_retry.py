"""Tests for retry logic in RedemptionService.redeem() create_user flow."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from zondarr.core.exceptions import ExternalServiceError, RedemptionError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import ExternalUser
from zondarr.models.media_server import MediaServer
from zondarr.services.redemption import RedemptionService

# Default test values for server connection details
_TEST_URL = "http://testserver.local:32400"
_TEST_API_KEY = "test-api-key"


def _make_server(
    *,
    name: str = "TestServer",
    server_type: str = "plex",
    url: str = _TEST_URL,
    api_key: str = _TEST_API_KEY,
) -> MagicMock:
    """Create a minimal MediaServer-like mock."""
    server = MagicMock(spec=MediaServer)
    server.id = uuid4()
    server.name = name
    server.server_type = server_type
    server.url = url
    server.api_key = api_key
    return server


def _make_invitation(
    *, code: str = "TEST-CODE", servers: list[MagicMock] | None = None
) -> MagicMock:
    """Create a minimal Invitation-like mock."""
    inv = MagicMock()
    inv.id = uuid4()
    inv.code = code
    inv.target_servers = servers or [_make_server()]
    inv.allowed_libraries = []
    inv.duration_days = None
    inv.pre_wizard_id = None
    return inv


def _make_external_user(username: str = "testuser") -> ExternalUser:
    return ExternalUser(
        external_user_id=str(uuid4()),
        username=username,
    )


def _make_redemption_service() -> tuple[RedemptionService, AsyncMock, AsyncMock]:
    """Create a RedemptionService with mocked dependencies."""
    invitation_service = AsyncMock()
    user_service = AsyncMock()

    # reserve() returns (True, None) for success
    invitation_service.reserve = AsyncMock(return_value=(True, None))

    # create_identity_with_users returns mock identity + users
    mock_identity = MagicMock()
    mock_identity.id = uuid4()
    mock_user = MagicMock()
    user_service.create_identity_with_users = AsyncMock(
        return_value=(mock_identity, [mock_user])
    )
    user_service.user_repository.get_by_username_and_server = AsyncMock(  # pyright: ignore[reportAny]
        return_value=None
    )
    user_service.cleanup_stale_local_users = AsyncMock(return_value=0)

    service = RedemptionService(invitation_service, user_service)
    return service, invitation_service, user_service


def _make_client(
    *,
    url: str = "http://test.local:32400",
    api_key: str = "test-api-key",
) -> AsyncMock:
    """Create a mock media client with async context manager support."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.url = url
    client.api_key = api_key
    return client


class TestRedemptionRetry:
    """Tests for retry behaviour around create_user in RedemptionService."""

    async def test_create_user_retries_on_external_service_error(self) -> None:
        """ExternalServiceError (DNS failure) is retried and succeeds."""
        service, invitation_service, _user_service = _make_redemption_service()
        url = _TEST_URL
        api_key = _TEST_API_KEY
        server = _make_server(url=url, api_key=api_key)
        invitation = _make_invitation(servers=[server])
        invitation_service.get_by_code = AsyncMock(return_value=invitation)

        external_user = _make_external_user()
        dns_error = ExternalServiceError(
            url, "DNS resolution failed", original=OSError("Name resolution")
        )

        # Each retry creates a fresh client. Track via side_effect.
        call_count = 0

        def create_client_side_effect(_server: MagicMock) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            client = _make_client(url=url, api_key=api_key)
            if call_count <= 2:
                client.__aenter__ = AsyncMock(side_effect=dns_error)
            else:
                client.create_user = AsyncMock(return_value=external_user)
            return client

        mock_registry = MagicMock()
        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )
        mock_registry.get_provider = MagicMock()

        with (
            patch("zondarr.services.redemption.registry", mock_registry),
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            identity, users = await service.redeem(
                "TEST-CODE", username="testuser", password="testpass"
            )

        assert identity is not None
        assert len(users) == 1
        # Verify 3 client creations (2 failures + 1 success)
        assert call_count == 3

    async def test_create_user_no_retry_on_username_taken(self) -> None:
        """MediaClientError with USERNAME_TAKEN is NOT retried."""
        service, invitation_service, _user_service = _make_redemption_service()
        url = _TEST_URL
        api_key = _TEST_API_KEY
        server = _make_server(url=url, api_key=api_key)
        invitation = _make_invitation(servers=[server])
        invitation_service.get_by_code = AsyncMock(return_value=invitation)

        username_taken = MediaClientError(
            "Username already exists",
            operation="create_user",
            server_url=url,
            error_code="USERNAME_TAKEN",
        )

        client = _make_client(url=url, api_key=api_key)
        client.create_user = AsyncMock(side_effect=username_taken)

        mock_registry = MagicMock()
        mock_registry.create_client_for_server = MagicMock(return_value=client)
        mock_registry.get_provider = MagicMock()

        with (
            patch("zondarr.services.redemption.registry", mock_registry),
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RedemptionError) as exc_info:
                _ = await service.redeem(
                    "TEST-CODE", username="testuser", password="testpass"
                )

        assert exc_info.value.redemption_error_code == "USERNAME_TAKEN"
        # create_client_for_server called once (no retry)
        assert mock_registry.create_client_for_server.call_count == 1  # pyright: ignore[reportAny]

    async def test_create_user_retries_exhausted_triggers_rollback(self) -> None:
        """All retries fail → rollback occurs and RedemptionError raised."""
        service, invitation_service, _user_service = _make_redemption_service()
        url = _TEST_URL
        api_key = _TEST_API_KEY
        server = _make_server(url=url, api_key=api_key)
        invitation = _make_invitation(servers=[server])
        invitation_service.get_by_code = AsyncMock(return_value=invitation)

        dns_error = ExternalServiceError(
            url, "DNS resolution failed", original=OSError("Name resolution")
        )

        def create_failing_client(_server: MagicMock) -> AsyncMock:
            client = _make_client(url=url, api_key=api_key)
            client.__aenter__ = AsyncMock(side_effect=dns_error)
            return client

        mock_registry = MagicMock()
        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_failing_client
        )
        mock_registry.get_provider = MagicMock()

        with (
            patch("zondarr.services.redemption.registry", mock_registry),
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RedemptionError) as exc_info:
                _ = await service.redeem(
                    "TEST-CODE", username="testuser", password="testpass"
                )

        assert exc_info.value.redemption_error_code == "SERVER_ERROR"
        # 6 attempts total: 1 initial + 5 retries
        assert mock_registry.create_client_for_server.call_count == 6  # pyright: ignore[reportAny]

    async def test_create_user_retries_on_connection_error(self) -> None:
        """Python ConnectionError is retried and succeeds."""
        service, invitation_service, _user_service = _make_redemption_service()
        url = _TEST_URL
        api_key = _TEST_API_KEY
        server = _make_server(url=url, api_key=api_key)
        invitation = _make_invitation(servers=[server])
        invitation_service.get_by_code = AsyncMock(return_value=invitation)

        external_user = _make_external_user()
        conn_error = ConnectionError("Connection refused")

        call_count = 0

        def create_client_side_effect(_server: MagicMock) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            client = _make_client(url=url, api_key=api_key)
            if call_count == 1:
                client.__aenter__ = AsyncMock(side_effect=conn_error)
            else:
                client.create_user = AsyncMock(return_value=external_user)
            return client

        mock_registry = MagicMock()
        mock_registry.create_client_for_server = MagicMock(
            side_effect=create_client_side_effect
        )
        mock_registry.get_provider = MagicMock()

        with (
            patch("zondarr.services.redemption.registry", mock_registry),
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            identity, users = await service.redeem(
                "TEST-CODE", username="testuser", password="testpass"
            )

        assert identity is not None
        assert len(users) == 1
        # 2 client creations: 1 failure + 1 success
        assert call_count == 2

    async def test_create_user_no_retry_on_generic_media_error(self) -> None:
        """Generic MediaClientError from create_user is NOT retried.

        This guards against orphan accounts: if create_user succeeds on the
        server but the response is lost (e.g. timeout wrapped as
        MediaClientError), retrying would create a duplicate.
        """
        service, invitation_service, _user_service = _make_redemption_service()
        url = _TEST_URL
        api_key = _TEST_API_KEY
        server = _make_server(url=url, api_key=api_key)
        invitation = _make_invitation(servers=[server])
        invitation_service.get_by_code = AsyncMock(return_value=invitation)

        # A generic MediaClientError (no specific error_code) that
        # is_retryable_sync_error would classify as retryable.
        ambiguous_error = MediaClientError(
            "Request timed out after server may have processed it",
            operation="create_user",
            server_url=url,
        )

        client = _make_client(url=url, api_key=api_key)
        client.create_user = AsyncMock(side_effect=ambiguous_error)

        mock_registry = MagicMock()
        mock_registry.create_client_for_server = MagicMock(return_value=client)
        mock_registry.get_provider = MagicMock()

        with (
            patch("zondarr.services.redemption.registry", mock_registry),
            patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RedemptionError) as exc_info:
                _ = await service.redeem(
                    "TEST-CODE", username="testuser", password="testpass"
                )

        assert exc_info.value.redemption_error_code == "SERVER_ERROR"
        # Only 1 client created — create_user errors are never retried
        assert mock_registry.create_client_for_server.call_count == 1  # pyright: ignore[reportAny]
