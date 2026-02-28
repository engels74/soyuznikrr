"""Tests for DashboardController HTTP endpoint.

Integration tests via TestClient following test_settings_controller.py pattern.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.dashboard import DashboardController
from zondarr.models.identity import Identity, User
from zondarr.models.invitation import Invitation
from zondarr.models.media_server import MediaServer
from zondarr.models.sync_run import SyncRun


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
) -> Litestar:
    """Create a Litestar test app with the DashboardController."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return Litestar(
        route_handlers=[DashboardController],
        dependencies={
            "session": Provide(provide_session),
        },
    )


class TestGetDashboardStats:
    """Tests for GET /api/v1/dashboard/stats."""

    @pytest.mark.asyncio
    async def test_empty_database_returns_zero_counts(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                response = client.get("/api/v1/dashboard/stats")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["total_invitations"] == 0
                assert data["active_invitations"] == 0
                assert data["total_users"] == 0
                assert data["active_users"] == 0
                assert data["total_servers"] == 0
                assert data["enabled_servers"] == 0
                assert data["pending_invitations"] == 0
                assert data["recent_activity"] == []
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_counts_with_seeded_data(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            # Seed test data
            async with session_factory() as session:
                # Create invitations
                inv_active = Invitation(code="ACTIVE01", enabled=True, use_count=0)
                inv_used = Invitation(code="USED0001", enabled=True, use_count=2, max_uses=5)
                inv_disabled = Invitation(code="DISABLED", enabled=False, use_count=0)
                session.add_all([inv_active, inv_used, inv_disabled])

                # Create media servers
                server_enabled = MediaServer(
                    name="Jellyfin", server_type="jellyfin",
                    url="http://jf:8096", api_key="key1", enabled=True,
                )
                server_disabled = MediaServer(
                    name="Plex", server_type="plex",
                    url="http://plex:32400", api_key="key2", enabled=False,
                )
                session.add_all([server_enabled, server_disabled])
                await session.flush()

                # Create identity + users (User requires identity_id and media_server_id)
                identity = Identity(display_name="Test User")
                session.add(identity)
                await session.flush()

                user_active = User(
                    identity_id=identity.id,
                    media_server_id=server_enabled.id,
                    external_user_id="ext1",
                    username="active_user",
                    enabled=True,
                )
                user_disabled = User(
                    identity_id=identity.id,
                    media_server_id=server_enabled.id,
                    external_user_id="ext2",
                    username="disabled_user",
                    enabled=False,
                )
                session.add_all([user_active, user_disabled])
                await session.commit()

            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                response = client.get("/api/v1/dashboard/stats")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                assert data["total_invitations"] == 3
                assert data["active_invitations"] == 2  # ACTIVE01 + USED0001
                assert data["pending_invitations"] == 1  # ACTIVE01 (use_count=0)
                assert data["total_users"] == 2
                assert data["active_users"] == 1  # Only active_user
                assert data["total_servers"] == 2
                assert data["enabled_servers"] == 1  # Only Jellyfin
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_recent_activity_uses_finished_at_for_syncs(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                server = MediaServer(
                    name="TestServer", server_type="jellyfin",
                    url="http://jf:8096", api_key="key1", enabled=True,
                )
                session.add(server)
                await session.flush()

                now = datetime.now(UTC)
                sync = SyncRun(
                    media_server_id=server.id,
                    sync_type="libraries",
                    trigger="manual",
                    status="success",
                    started_at=now,
                    finished_at=now,
                )
                session.add(sync)
                await session.commit()

            app = _make_test_app(session_factory)

            with TestClient(app) as client:
                response = client.get("/api/v1/dashboard/stats")
                assert response.status_code == 200
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]

                activities: list[dict[str, object]] = data["recent_activity"]  # pyright: ignore[reportAny]
                sync_activities = [a for a in activities if a["type"] == "sync_completed"]
                assert len(sync_activities) == 1
                assert "libraries" in str(sync_activities[0]["description"])
        finally:
            await engine.dispose()
