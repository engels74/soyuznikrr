"""Integration tests for server sync status and manual sync endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.schemas import SyncResult
from zondarr.api.servers import ServerController
from zondarr.config import Settings
from zondarr.media.providers.jellyfin import JellyfinProvider
from zondarr.media.providers.plex import PlexProvider
from zondarr.media.registry import registry
from zondarr.models.media_server import Library, MediaServer
from zondarr.models.sync_run import SyncRun
from zondarr.services.media_server import LibrarySyncSummary, MediaServerService
from zondarr.services.sync import SyncService


class SyncChannelStatusPayload(TypedDict):
    in_progress: bool
    last_completed_at: str | None
    next_scheduled_at: str | None


class ServerSyncStatusPayload(TypedDict):
    libraries: SyncChannelStatusPayload
    users: SyncChannelStatusPayload


class ServerDetailPayload(TypedDict):
    id: str
    libraries: list[object]
    sync_status: ServerSyncStatusPayload


def _make_test_settings() -> Settings:
    return Settings(
        secret_key="a" * 32,
        sync_interval_seconds=900,
    )


def _ensure_registry() -> None:
    registry.register(PlexProvider())
    registry.register(JellyfinProvider())


def _make_test_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    background_task_manager: object | None = None,
) -> Litestar:
    _ensure_registry()

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def provide_settings_fn(state: State) -> Settings:
        return state.settings  # pyright: ignore[reportAny]

    state: dict[str, object] = {"settings": settings}
    if background_task_manager is not None:
        state["background_task_manager"] = background_task_manager

    return Litestar(
        route_handlers=[ServerController],
        state=State(state),
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(provide_settings_fn, sync_to_thread=False),
        },
    )


class _FakeBackgroundTaskManager:
    _next_sync_at: datetime | None
    _libraries_in_progress: bool
    _users_in_progress: bool

    def __init__(
        self,
        *,
        next_sync_at: datetime | None = None,
        libraries_in_progress: bool = False,
        users_in_progress: bool = False,
    ) -> None:
        self._next_sync_at = next_sync_at
        self._libraries_in_progress = libraries_in_progress
        self._users_in_progress = users_in_progress

    def get_next_sync_run_at(self) -> datetime | None:
        return self._next_sync_at

    def is_libraries_sync_in_progress(self, _server_id: UUID) -> bool:
        return self._libraries_in_progress

    def is_users_sync_in_progress(self, _server_id: UUID) -> bool:
        return self._users_in_progress


class TestServerSyncStatus:
    @pytest.mark.asyncio
    async def test_get_server_returns_sync_status(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings()

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Main",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.flush()

                library = Library(
                    media_server_id=server.id,
                    external_id="1",
                    name="Movies",
                    library_type="movie",
                )
                session.add(library)

                base_time = datetime.now(UTC) - timedelta(minutes=10)
                session.add(
                    SyncRun(
                        media_server_id=server.id,
                        sync_type="libraries",
                        trigger="automatic",
                        status="success",
                        started_at=base_time,
                        finished_at=base_time + timedelta(seconds=20),
                    )
                )
                session.add(
                    SyncRun(
                        media_server_id=server.id,
                        sync_type="users",
                        trigger="automatic",
                        status="success",
                        started_at=base_time + timedelta(minutes=2),
                        finished_at=base_time + timedelta(minutes=2, seconds=30),
                    )
                )
                await session.commit()
                server_id = server.id

            manager = _FakeBackgroundTaskManager(
                next_sync_at=datetime.now(UTC) + timedelta(minutes=5),
                libraries_in_progress=False,
                users_in_progress=True,
            )
            app = _make_test_app(
                session_factory,
                settings,
                background_task_manager=manager,
            )

            with TestClient(app) as client:
                response = client.get(f"/api/v1/servers/{server_id}")
                assert response.status_code == 200
                payload = cast(ServerDetailPayload, response.json())

                assert payload["id"] == str(server_id)
                assert len(payload["libraries"]) == 1
                sync_status = payload["sync_status"]
                assert sync_status["libraries"]["in_progress"] is False
                assert sync_status["users"]["in_progress"] is True
                assert sync_status["libraries"]["next_scheduled_at"] is not None
                assert sync_status["users"]["last_completed_at"] is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_sync_libraries_returns_counts_and_records_run(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings()

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Main",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.flush()

                lib_a = Library(
                    media_server_id=server.id,
                    external_id="1",
                    name="Movies",
                    library_type="movie",
                )
                lib_b = Library(
                    media_server_id=server.id,
                    external_id="2",
                    name="Shows",
                    library_type="show",
                )
                session.add_all([lib_a, lib_b])
                await session.commit()
                server_id = server.id

            app = _make_test_app(session_factory, settings)
            summary = LibrarySyncSummary(
                libraries=[lib_a, lib_b],
                added_count=1,
                updated_count=2,
                removed_count=0,
            )

            with patch.object(
                MediaServerService,
                "sync_libraries_detailed",
                AsyncMock(return_value=summary),
            ):
                with TestClient(app) as client:
                    response = client.post(
                        f"/api/v1/servers/{server_id}/sync-libraries"
                    )
                    assert response.status_code == 200
                    payload: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                    assert payload["server_id"] == str(server_id)
                    assert payload["total_libraries"] == 2
                    assert payload["added_count"] == 1
                    assert payload["updated_count"] == 2
                    assert payload["removed_count"] == 0

            async with session_factory() as session:
                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "libraries",
                            SyncRun.trigger == "manual",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "success"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_manual_user_sync_records_run(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_test_settings()

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Main",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            app = _make_test_app(session_factory, settings)
            sync_result = SyncResult(
                server_id=server_id,
                server_name="Plex Main",
                synced_at=datetime.now(UTC),
                orphaned_users=[],
                stale_users=[],
                matched_users=0,
                imported_users=0,
            )

            with patch.object(
                SyncService,
                "sync_server",
                AsyncMock(return_value=sync_result),
            ):
                with TestClient(app) as client:
                    response = client.post(
                        f"/api/v1/servers/{server_id}/sync",
                        json={"dry_run": False},
                    )
                    assert response.status_code == 201

            async with session_factory() as session:
                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "users",
                            SyncRun.trigger == "manual",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "success"
        finally:
            await engine.dispose()
