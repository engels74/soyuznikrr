"""Unit tests for PlexOAuthController endpoints.

Feature: plex-integration
Task: 9.4 Write unit tests for OAuth endpoints
Validates: Requirements 13.1, 13.2, 14.1, 14.2

Tests PIN creation and PIN check endpoints via the Litestar test client.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import AsyncTestClient
from litestar.types import AnyCallable

from zondarr.api.plex_oauth import PlexOAuthController
from zondarr.services.plex_oauth import (
    PlexOAuthError,
    PlexOAuthPin,
    PlexOAuthResult,
    PlexOAuthService,
)


@pytest.fixture
def mock_oauth_service() -> AsyncMock:
    """Create a mock PlexOAuthService."""
    service = AsyncMock(spec=PlexOAuthService)
    service.close = AsyncMock()
    return service


@pytest.fixture
def sample_pin() -> PlexOAuthPin:
    """Create a sample PlexOAuthPin for testing."""
    return PlexOAuthPin(
        pin_id=12345,
        code="ABCD1234",
        auth_url="https://app.plex.tv/auth#?clientID=test&code=ABCD1234",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )


@pytest.fixture
def sample_authenticated_result() -> PlexOAuthResult:
    """Create a sample authenticated PlexOAuthResult."""
    return PlexOAuthResult(
        authenticated=True,
        email="user@example.com",
        auth_token="test-auth-token",
    )


@pytest.fixture
def sample_pending_result() -> PlexOAuthResult:
    """Create a sample pending (not authenticated) PlexOAuthResult."""
    return PlexOAuthResult(authenticated=False)


def create_test_app(mock_service: AsyncMock) -> Litestar:
    """Create a test Litestar app with mocked OAuth service."""

    async def mock_provide_service() -> PlexOAuthService:
        return mock_service  # type: ignore[return-value]

    # Create a controller without the default dependencies
    class TestPlexOAuthController(PlexOAuthController):
        dependencies: Mapping[str, Provide | AnyCallable] | None = {
            "oauth_service": Provide(mock_provide_service),
        }

    return Litestar(route_handlers=[TestPlexOAuthController])


class TestCreatePinEndpoint:
    """Tests for POST /api/v1/join/plex/oauth/pin endpoint.

    Validates: Requirements 13.1, 13.2
    """

    @pytest.mark.asyncio
    async def test_create_pin_returns_valid_response(
        self,
        mock_oauth_service: AsyncMock,
        sample_pin: PlexOAuthPin,
    ) -> None:
        """PIN creation returns valid response with pin_id, code, auth_url, expires_at."""
        mock_oauth_service.create_pin.return_value = sample_pin  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            response = await client.post("/api/v1/join/plex/oauth/pin")

        assert response.status_code == 200
        data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert data["pin_id"] == sample_pin.pin_id
        assert data["code"] == sample_pin.code
        assert data["auth_url"] == sample_pin.auth_url
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_create_pin_auth_url_starts_with_https(
        self,
        mock_oauth_service: AsyncMock,
        sample_pin: PlexOAuthPin,
    ) -> None:
        """PIN creation returns auth_url starting with https://."""
        mock_oauth_service.create_pin.return_value = sample_pin  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            response = await client.post("/api/v1/join/plex/oauth/pin")

        assert response.status_code == 200
        data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        auth_url = data["auth_url"]
        assert isinstance(auth_url, str)
        assert auth_url.startswith("https://")

    @pytest.mark.asyncio
    async def test_create_pin_closes_service_on_success(
        self,
        mock_oauth_service: AsyncMock,
        sample_pin: PlexOAuthPin,
    ) -> None:
        """PIN creation closes the OAuth service after completion."""
        mock_oauth_service.create_pin.return_value = sample_pin  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            _ = await client.post("/api/v1/join/plex/oauth/pin")

        mock_oauth_service.close.assert_awaited_once()  # pyright: ignore[reportAny]


class TestCheckPinEndpoint:
    """Tests for GET /api/v1/join/plex/oauth/pin/{pin_id} endpoint.

    Validates: Requirements 14.1, 14.2
    """

    @pytest.mark.asyncio
    async def test_check_pin_returns_authenticated_with_email(
        self,
        mock_oauth_service: AsyncMock,
        sample_authenticated_result: PlexOAuthResult,
    ) -> None:
        """PIN check returns authenticated=True and email when PIN is authenticated."""
        mock_oauth_service.check_pin.return_value = sample_authenticated_result  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            response = await client.get("/api/v1/join/plex/oauth/pin/12345")

        assert response.status_code == 200
        data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert data["authenticated"] is True
        assert data["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_check_pin_returns_not_authenticated_when_pending(
        self,
        mock_oauth_service: AsyncMock,
        sample_pending_result: PlexOAuthResult,
    ) -> None:
        """PIN check returns authenticated=False when PIN is not yet authenticated."""
        mock_oauth_service.check_pin.return_value = sample_pending_result  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            response = await client.get("/api/v1/join/plex/oauth/pin/12345")

        assert response.status_code == 200
        data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_check_pin_returns_error_on_service_error(
        self,
        mock_oauth_service: AsyncMock,
    ) -> None:
        """PIN check returns error response when service raises PlexOAuthError."""
        mock_oauth_service.check_pin.side_effect = PlexOAuthError(  # pyright: ignore[reportAny]
            "PIN check failed",
            operation="check_pin",
            cause="Server error",
        )
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            response = await client.get("/api/v1/join/plex/oauth/pin/12345")

        assert response.status_code == 200
        data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert data["authenticated"] is False
        assert data["error"] == "PIN check failed"

    @pytest.mark.asyncio
    async def test_check_pin_closes_service_on_success(
        self,
        mock_oauth_service: AsyncMock,
        sample_authenticated_result: PlexOAuthResult,
    ) -> None:
        """PIN check closes the OAuth service after completion."""
        mock_oauth_service.check_pin.return_value = sample_authenticated_result  # pyright: ignore[reportAny]
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            _ = await client.get("/api/v1/join/plex/oauth/pin/12345")

        mock_oauth_service.close.assert_awaited_once()  # pyright: ignore[reportAny]

    @pytest.mark.asyncio
    async def test_check_pin_closes_service_on_error(
        self,
        mock_oauth_service: AsyncMock,
    ) -> None:
        """PIN check closes the OAuth service even when error occurs."""
        mock_oauth_service.check_pin.side_effect = PlexOAuthError(  # pyright: ignore[reportAny]
            "PIN check failed",
            operation="check_pin",
            cause="Server error",
        )
        app = create_test_app(mock_oauth_service)

        async with AsyncTestClient(app) as client:
            _ = await client.get("/api/v1/join/plex/oauth/pin/12345")

        mock_oauth_service.close.assert_awaited_once()  # pyright: ignore[reportAny]
