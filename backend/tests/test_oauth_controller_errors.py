"""Tests for OAuthController error handling of PlexOAuthError.

Verifies that PlexOAuthError from the provider is caught and returned
as HTTP 502 with a structured ErrorResponse in both create_pin and check_pin.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.oauth import OAuthController
from zondarr.config import Settings
from zondarr.media.providers.plex.oauth_service import PlexOAuthError


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings | None = None,
) -> Litestar:
    """Create a Litestar test app with the OAuthController."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    if settings is None:
        settings = Settings(secret_key="a" * 32)

    app = Litestar(
        route_handlers=[OAuthController],
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(lambda: settings, sync_to_thread=False),
        },
        state=State({"session_factory": session_factory}),
    )
    return app


class TestCreatePinPlexOAuthError:
    """PlexOAuthError in create_pin returns HTTP 502."""

    @pytest.mark.asyncio
    async def test_create_pin_returns_502_on_plex_oauth_error(self) -> None:
        engine = await create_test_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        mock_flow = AsyncMock()
        mock_flow.create_pin = AsyncMock(
            side_effect=PlexOAuthError(
                "Failed to create Plex OAuth PIN: Connection refused",
                operation="create_pin",
                cause="Connection refused",
            )
        )
        mock_flow.close = AsyncMock()

        app = _make_test_app(session_factory)

        with (
            patch(
                "zondarr.api.oauth.registry.create_oauth_flow_provider",
                return_value=mock_flow,
            ),
            TestClient(app) as client,
        ):
            response = client.post("/api/v1/join/plex/oauth/pin")

        assert response.status_code == 502
        body: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert body["error_code"] == "EXTERNAL_SERVICE_ERROR"
        assert "plex" in str(body["detail"])
        assert "timestamp" in body

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_create_pin_flow_closed_on_error(self) -> None:
        """Ensure flow.close() is always called even when PlexOAuthError is raised."""
        engine = await create_test_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        mock_flow = AsyncMock()
        mock_flow.create_pin = AsyncMock(
            side_effect=PlexOAuthError(
                "Network error",
                operation="create_pin",
                cause="timeout",
            )
        )
        mock_flow.close = AsyncMock()

        app = _make_test_app(session_factory)

        with (
            patch(
                "zondarr.api.oauth.registry.create_oauth_flow_provider",
                return_value=mock_flow,
            ),
            TestClient(app) as client,
        ):
            _ = client.post("/api/v1/join/plex/oauth/pin")

        mock_flow.close.assert_called_once()  # pyright: ignore[reportAny]

        await engine.dispose()


class TestCheckPinPlexOAuthError:
    """PlexOAuthError in check_pin returns HTTP 502."""

    @pytest.mark.asyncio
    async def test_check_pin_returns_502_on_plex_oauth_error(self) -> None:
        engine = await create_test_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        # First create a valid session in the DB
        from zondarr.services.oauth_session import OAuthSessionStore

        store = OAuthSessionStore()
        async with session_factory() as session:
            handle = await store.create(session, "plex", 12345)
            await session.commit()

        # Mock the flow to raise on check_pin
        mock_flow = AsyncMock()
        mock_flow.check_pin = AsyncMock(
            side_effect=PlexOAuthError(
                "Failed to check Plex OAuth PIN: Connection refused",
                operation="check_pin",
                cause="Connection refused",
            )
        )
        mock_flow.close = AsyncMock()

        app = _make_test_app(session_factory)

        with (
            patch(
                "zondarr.api.oauth.registry.create_oauth_flow_provider",
                return_value=mock_flow,
            ),
            TestClient(app) as client,
        ):
            response = client.get(f"/api/v1/join/plex/oauth/pin/{handle}")

        assert response.status_code == 502
        body: dict[str, object] = response.json()  # pyright: ignore[reportAny]
        assert body["error_code"] == "EXTERNAL_SERVICE_ERROR"
        assert "plex" in str(body["detail"])
        assert "timestamp" in body

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_check_pin_flow_closed_on_error(self) -> None:
        """Ensure flow.close() is always called even when PlexOAuthError is raised."""
        engine = await create_test_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        from zondarr.services.oauth_session import OAuthSessionStore

        store = OAuthSessionStore()
        async with session_factory() as session:
            handle = await store.create(session, "plex", 12345)
            await session.commit()

        mock_flow = AsyncMock()
        mock_flow.check_pin = AsyncMock(
            side_effect=PlexOAuthError(
                "Network error",
                operation="check_pin",
                cause="timeout",
            )
        )
        mock_flow.close = AsyncMock()

        app = _make_test_app(session_factory)

        with (
            patch(
                "zondarr.api.oauth.registry.create_oauth_flow_provider",
                return_value=mock_flow,
            ),
            TestClient(app) as client,
        ):
            _ = client.get(f"/api/v1/join/plex/oauth/pin/{handle}")

        mock_flow.close.assert_called_once()  # pyright: ignore[reportAny]

        await engine.dispose()
