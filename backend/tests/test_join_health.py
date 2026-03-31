"""Tests for the GET /api/v1/join/health/{code} endpoint.

Verifies that the join health check endpoint correctly probes target server
reachability and returns per-server health status without exposing sensitive info.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import msgspec
import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.join import JoinController
from zondarr.core.exceptions import ExternalServiceError
from zondarr.media.providers import register_all_providers
from zondarr.models.invitation import Invitation, invitation_servers
from zondarr.models.media_server import MediaServer

# Type-safe JSON response types for pyright.
_Json = dict[str, object]
_JsonList = list[_Json]


def _decode(response: httpx.Response) -> _Json:
    """Decode a TestClient response body into a typed dict."""
    return msgspec.json.decode(response.content, type=_Json)


def _as_list(obj: object) -> _JsonList:
    """Narrow an object from a JSON dict value to a list of dicts."""
    assert isinstance(obj, list)
    return cast(_JsonList, obj)


def _as_dict(obj: object) -> _Json:
    """Narrow an object from a JSON list element to a dict."""
    assert isinstance(obj, dict)
    return cast(_Json, obj)


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
) -> Litestar:
    """Create a Litestar test app with the JoinController."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return Litestar(
        route_handlers=[JoinController],
        dependencies={
            "session": Provide(provide_session),
        },
    )


async def _seed_invitation_with_server(
    session_factory: async_sessionmaker[AsyncSession],
    code: str = "HEALTHTEST1",
    server_name: str = "Test Plex",
    server_type: str = "plex",
) -> None:
    """Seed DB with an invitation linked to a server."""
    async with session_factory() as session:
        server = MediaServer()
        server.name = server_name
        server.server_type = server_type
        server.url = "http://plex.local:32400"
        server.api_key = "test-api-key"
        server.enabled = True
        session.add(server)
        await session.flush()

        invitation = Invitation()
        invitation.code = code
        invitation.enabled = True
        session.add(invitation)
        await session.flush()

        _ = await session.execute(
            invitation_servers.insert().values(
                invitation_id=invitation.id,
                media_server_id=server.id,
            )
        )
        await session.commit()


class TestJoinHealthEndpoint:
    """Tests for GET /api/v1/join/health/{code}."""

    @pytest.fixture(autouse=True)
    def _register_providers(self) -> None:
        register_all_providers()

    @pytest.mark.asyncio
    async def test_health_all_servers_reachable(self) -> None:
        """All servers reachable returns all_reachable=True."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            await _seed_invitation_with_server(session_factory)

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.test_connection = AsyncMock(return_value=True)

            app = _make_test_app(session_factory)
            with (
                patch(
                    "zondarr.api.join.registry.create_client_for_server",
                    return_value=mock_client,
                ),
                TestClient(app) as client,
            ):
                resp = client.get("/api/v1/join/health/HEALTHTEST1")
                assert resp.status_code == 200

                data = _decode(resp)
                assert data["all_reachable"] is True

                servers = _as_list(data["servers"])
                assert len(servers) == 1

                server = _as_dict(servers[0])
                assert server["name"] == "Test Plex"
                assert server["server_type"] == "plex"
                assert server["reachable"] is True

                # Sensitive fields must not be present
                assert "url" not in server
                assert "id" not in server
                assert "api_key" not in server
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_health_server_unreachable(self) -> None:
        """Server connect raising ExternalServiceError marks reachable=False."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            await _seed_invitation_with_server(session_factory)

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=ExternalServiceError("plex", "Connection refused")
            )
            mock_client.__aexit__ = AsyncMock(return_value=False)

            app = _make_test_app(session_factory)
            with (
                patch(
                    "zondarr.api.join.registry.create_client_for_server",
                    return_value=mock_client,
                ),
                TestClient(app) as client,
            ):
                resp = client.get("/api/v1/join/health/HEALTHTEST1")
                assert resp.status_code == 200

                data = _decode(resp)
                assert data["all_reachable"] is False

                servers = _as_list(data["servers"])
                assert len(servers) == 1

                server = _as_dict(servers[0])
                assert server["reachable"] is False
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_health_invalid_code_returns_404(self) -> None:
        """Invalid invitation code returns 404."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                resp = client.get("/api/v1/join/health/NONEXISTENT")
                assert resp.status_code == 404
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_health_timeout_marks_unreachable(self) -> None:
        """test_connection exceeding timeout marks server as unreachable."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            await _seed_invitation_with_server(session_factory)

            async def slow_test_connection() -> bool:
                await asyncio.sleep(20)
                return True

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.test_connection = MagicMock(
                side_effect=lambda: slow_test_connection()
            )

            app = _make_test_app(session_factory)
            with (
                patch(
                    "zondarr.api.join.registry.create_client_for_server",
                    return_value=mock_client,
                ),
                patch(
                    "zondarr.api.join.asyncio.wait_for", wraps=asyncio.wait_for
                ) as mock_wait_for,
                TestClient(app) as client,
            ):
                # Override the timeout to be very short for the test
                original_wait_for = asyncio.wait_for

                async def short_timeout_wait_for(
                    coro: object, *, timeout: float
                ) -> object:
                    return await original_wait_for(coro, timeout=0.01)  # pyright: ignore[reportArgumentType,reportUnknownVariableType]

                mock_wait_for.side_effect = short_timeout_wait_for

                resp = client.get("/api/v1/join/health/HEALTHTEST1")
                assert resp.status_code == 200

                data = _decode(resp)
                assert data["all_reachable"] is False

                servers = _as_list(data["servers"])
                server = _as_dict(servers[0])
                assert server["reachable"] is False
        finally:
            await engine.dispose()
