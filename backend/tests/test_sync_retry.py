"""Tests for retry behavior in background sync tasks."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from litestar.datastructures import State
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.schemas import SyncResult
from zondarr.config import Settings
from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from zondarr.core.tasks import BackgroundTaskManager
from zondarr.models.media_server import MediaServer
from zondarr.models.sync_run import SyncRun


def _make_settings(*, sync_max_retries: int = 2) -> Settings:
    return Settings(
        secret_key="a" * 32,
        sync_interval_seconds=900,
        sync_max_retries=sync_max_retries,
    )


def _make_sync_result(server_id=None) -> SyncResult:
    return SyncResult(
        server_id=server_id or uuid4(),
        server_name="Test Server",
        synced_at=datetime.now(UTC),
        orphaned_users=[],
        stale_users=[],
        matched_users=0,
        imported_users=0,
    )


class TestSyncRetryBehavior:
    """Tests that transient errors are retried during server sync."""

    @pytest.mark.asyncio
    async def test_library_sync_retries_on_external_service_error(self) -> None:
        """Library sync should retry on ExternalServiceError and succeed."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)

            # Create a server in the DB
            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            # First call fails, second succeeds
            call_count = 0

            async def mock_sync_libraries(sf, sid):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ExternalServiceError("plex", "Connection refused")
                return None

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                await manager.sync_all_servers(state)

            assert call_count == 2

            # Should record success (not failure)
            async with session_factory() as session:
                from sqlalchemy import select

                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "libraries",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "success"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_user_sync_retries_on_timeout_error(self) -> None:
        """User sync should retry on TimeoutError and succeed."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            # Library sync always succeeds
            with patch.object(
                manager, "_sync_server_libraries", new_callable=AsyncMock
            ):
                # User sync: first call times out, second succeeds
                call_count = 0
                sync_result = _make_sync_result(server_id)

                async def mock_sync_users(sf, sid):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise TimeoutError("timed out")
                    return sync_result

                with patch.object(
                    manager, "_sync_server_users", side_effect=mock_sync_users
                ):
                    await manager.sync_all_servers(state)

            assert call_count == 2

            # Should record success for users
            async with session_factory() as session:
                from sqlalchemy import select

                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "users",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "success"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_sync_does_not_retry_on_not_found_error(self) -> None:
        """Non-transient errors like NotFoundError should NOT be retried."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            call_count = 0

            async def mock_sync_libraries(sf, sid):
                nonlocal call_count
                call_count += 1
                raise NotFoundError("MediaServer", str(sid))

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                # User sync always succeeds
                with patch.object(
                    manager,
                    "_sync_server_users",
                    new_callable=AsyncMock,
                    return_value=_make_sync_result(server_id),
                ):
                    await manager.sync_all_servers(state)

            # Should only be called once (no retries)
            assert call_count == 1

            # Should record failure
            async with session_factory() as session:
                from sqlalchemy import select

                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "libraries",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "failed"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_sync_does_not_retry_on_validation_error(self) -> None:
        """ValidationError should NOT be retried."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            call_count = 0

            async def mock_sync_libraries(sf, sid):
                nonlocal call_count
                call_count += 1
                raise ValidationError("bad data", field_errors={"name": ["invalid"]})

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                with patch.object(
                    manager,
                    "_sync_server_users",
                    new_callable=AsyncMock,
                    return_value=_make_sync_result(server_id),
                ):
                    await manager.sync_all_servers(state)

            assert call_count == 1
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_sync_records_failure_after_retries_exhausted(self) -> None:
        """After all retries are exhausted, SyncRun should record final failure."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            call_count = 0

            async def mock_sync_libraries(sf, sid):
                nonlocal call_count
                call_count += 1
                raise ExternalServiceError("plex", "Connection refused")

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                with patch.object(
                    manager,
                    "_sync_server_users",
                    new_callable=AsyncMock,
                    return_value=_make_sync_result(server_id),
                ):
                    await manager.sync_all_servers(state)

            # 1 initial + 2 retries = 3 calls
            assert call_count == 3

            # Should record a single failure (not intermediate attempts)
            async with session_factory() as session:
                from sqlalchemy import select

                runs = (
                    await session.scalars(
                        select(SyncRun).where(
                            SyncRun.media_server_id == server_id,
                            SyncRun.sync_type == "libraries",
                        )
                    )
                ).all()
                assert len(runs) == 1
                assert runs[0].status == "failed"
                assert "Connection refused" in (runs[0].error_message or "")
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_sync_with_zero_retries_behaves_like_no_retry(self) -> None:
        """With sync_max_retries=0, failures should not be retried."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=0)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server = MediaServer(
                    name="Plex Test",
                    server_type="plex",
                    url="http://plex.local:32400",
                    api_key="token",
                    enabled=True,
                )
                session.add(server)
                await session.commit()
                server_id = server.id

            state = State({"session_factory": session_factory})

            call_count = 0

            async def mock_sync_libraries(sf, sid):
                nonlocal call_count
                call_count += 1
                raise ExternalServiceError("plex", "Connection refused")

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                with patch.object(
                    manager,
                    "_sync_server_users",
                    new_callable=AsyncMock,
                    return_value=_make_sync_result(server_id),
                ):
                    await manager.sync_all_servers(state)

            # Only 1 attempt, no retries
            assert call_count == 1
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_other_servers_continue_after_one_fails(self) -> None:
        """Failure in one server should not prevent syncing the next server."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = _make_settings(sync_max_retries=1)
            manager = BackgroundTaskManager(settings)

            async with session_factory() as session:
                server1 = MediaServer(
                    name="Plex Main",
                    server_type="plex",
                    url="http://plex1.local:32400",
                    api_key="token1",
                    enabled=True,
                )
                server2 = MediaServer(
                    name="Jellyfin",
                    server_type="jellyfin",
                    url="http://jf.local:8096",
                    api_key="token2",
                    enabled=True,
                )
                session.add_all([server1, server2])
                await session.commit()
                server1_id = server1.id
                server2_id = server2.id

            state = State({"session_factory": session_factory})

            synced_servers: list[str] = []

            async def mock_sync_libraries(sf, sid):
                if sid == server1_id:
                    raise ExternalServiceError("plex", "Connection refused")
                synced_servers.append(str(sid))

            with patch.object(
                manager, "_sync_server_libraries", side_effect=mock_sync_libraries
            ):
                with patch.object(
                    manager,
                    "_sync_server_users",
                    new_callable=AsyncMock,
                    return_value=_make_sync_result(),
                ):
                    await manager.sync_all_servers(state)

            # Server 2 should still have been synced
            assert str(server2_id) in synced_servers
        finally:
            await engine.dispose()


class TestIsRetryable:
    """Unit tests for the _is_retryable predicate."""

    def test_external_service_error_is_retryable(self) -> None:
        exc = ExternalServiceError("plex", "Connection refused")
        assert BackgroundTaskManager._is_retryable(exc) is True

    def test_timeout_error_is_retryable(self) -> None:
        exc = TimeoutError("timed out")
        assert BackgroundTaskManager._is_retryable(exc) is True

    def test_not_found_error_is_not_retryable(self) -> None:
        exc = NotFoundError("MediaServer", "abc")
        assert BackgroundTaskManager._is_retryable(exc) is False

    def test_validation_error_is_not_retryable(self) -> None:
        exc = ValidationError("bad", field_errors={})
        assert BackgroundTaskManager._is_retryable(exc) is False

    def test_generic_exception_is_not_retryable(self) -> None:
        exc = RuntimeError("unexpected")
        assert BackgroundTaskManager._is_retryable(exc) is False


class TestSyncMaxRetriesConfig:
    """Tests for the sync_max_retries config setting."""

    def test_default_value(self) -> None:
        settings = Settings(secret_key="a" * 32)
        assert settings.sync_max_retries == 2

    def test_custom_value(self) -> None:
        settings = Settings(secret_key="a" * 32, sync_max_retries=5)
        assert settings.sync_max_retries == 5

    def test_zero_retries_allowed(self) -> None:
        settings = Settings(secret_key="a" * 32, sync_max_retries=0)
        assert settings.sync_max_retries == 0

    def test_load_settings_reads_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("SYNC_MAX_RETRIES", "5")
        from zondarr.config import load_settings

        settings = load_settings()
        assert settings.sync_max_retries == 5

    def test_load_settings_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.delenv("SYNC_MAX_RETRIES", raising=False)
        from zondarr.config import load_settings

        settings = load_settings()
        assert settings.sync_max_retries == 2
