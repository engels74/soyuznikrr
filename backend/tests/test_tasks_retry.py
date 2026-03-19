"""Integration tests for retry and circuit-breaker behaviour in BackgroundTaskManager."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

from litestar.datastructures import State
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.schemas import SyncResult
from zondarr.config import Settings
from zondarr.core.exceptions import ExternalServiceError, NotFoundError
from zondarr.core.tasks import BackgroundTaskManager
from zondarr.models.media_server import MediaServer
from zondarr.models.sync_run import SyncRun


def _make_test_settings(
    *,
    sync_max_retries: int = 2,
    sync_backoff_base_seconds: float = 0.5,
    sync_circuit_failure_threshold: int = 3,
    sync_circuit_recovery_seconds: int = 60,
) -> Settings:
    return Settings(
        secret_key="a" * 32,
        sync_interval_seconds=900,
        sync_per_server_timeout_seconds=300,
        sync_max_retries=sync_max_retries,
        sync_backoff_base_seconds=sync_backoff_base_seconds,
        sync_circuit_failure_threshold=sync_circuit_failure_threshold,
        sync_circuit_recovery_seconds=sync_circuit_recovery_seconds,
    )


def _make_sync_result(server_id: UUID) -> SyncResult:
    return SyncResult(
        server_id=server_id,
        server_name="Test Server",
        synced_at=datetime.now(UTC),
        orphaned_users=[],
        stale_users=[],
        matched_users=0,
        imported_users=0,
    )


async def _create_enabled_server(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    async with session_factory() as session:
        server = MediaServer(
            name="Test Server",
            server_type="plex",
            url="http://plex.local:32400",
            api_key="token",
            enabled=True,
        )
        session.add(server)
        await session.commit()
        return server.id


async def _get_sync_runs(
    session_factory: async_sessionmaker[AsyncSession],
    server_id: UUID,
) -> list[SyncRun]:
    async with session_factory() as session:
        result = await session.scalars(
            select(SyncRun)
            .where(SyncRun.media_server_id == server_id)
            .order_by(SyncRun.started_at)
        )
        return list(result.all())


class TestTransientFailureAndRecovery:
    """Mock server fails once with ExternalServiceError, then succeeds.

    Verifies retry happens and the final SyncRun is success, and the
    circuit breaker stays CLOSED.
    """

    async def test_retry_succeeds_after_transient_failure(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = await _create_enabled_server(session_factory)

            settings = _make_test_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)
            state = State({"session_factory": session_factory})

            lib_mock = AsyncMock(
                side_effect=[
                    ExternalServiceError("plex", "Connection refused"),
                    None,
                ]
            )
            user_mock = AsyncMock(return_value=_make_sync_result(server_id))

            with (
                patch.object(manager, "_sync_server_libraries", lib_mock),
                patch.object(manager, "_sync_server_users", user_mock),
                patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            ):
                await manager.sync_all_servers(state)

            assert lib_mock.call_count == 2
            assert user_mock.call_count == 1

            runs = await _get_sync_runs(session_factory, server_id)
            lib_runs = [r for r in runs if r.sync_type == "libraries"]
            user_runs = [r for r in runs if r.sync_type == "users"]

            assert len(lib_runs) == 1
            assert lib_runs[0].status == "success"
            assert len(user_runs) == 1
            assert user_runs[0].status == "success"

            circuit = manager.get_circuit_state(server_id)
            assert circuit is not None
            state_name, consecutive_failures, _ = circuit
            assert state_name == "CLOSED"
            assert consecutive_failures == 0
        finally:
            await engine.dispose()


class TestPermanentFailureAndCircuitOpen:
    """Mock server always fails with ExternalServiceError.

    Run _sync_all_servers multiple times, verify circuit opens after
    threshold failures and subsequent calls skip with circuit open message.
    """

    async def test_circuit_opens_after_threshold_failures(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = await _create_enabled_server(session_factory)

            settings = _make_test_settings(
                sync_max_retries=0,
                sync_circuit_failure_threshold=3,
            )
            manager = BackgroundTaskManager(settings)
            state = State({"session_factory": session_factory})

            lib_mock = AsyncMock(
                side_effect=ExternalServiceError("plex", "Connection refused"),
            )
            user_mock = AsyncMock(
                side_effect=ExternalServiceError("plex", "Connection refused"),
            )

            with (
                patch.object(manager, "_sync_server_libraries", lib_mock),
                patch.object(manager, "_sync_server_users", user_mock),
                patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            ):
                # Run sync 3 times to hit the threshold.
                # Each cycle: library fail (records failure) + user fail (records failure)
                # = 2 failures per cycle on the shared breaker.
                # After cycle 2, the breaker has 4 failures (>= threshold 3) so it opens.
                for _ in range(3):
                    await manager.sync_all_servers(state)

            circuit = manager.get_circuit_state(server_id)
            assert circuit is not None
            state_name, consecutive_failures, next_attempt_at = circuit
            assert state_name == "OPEN"
            assert consecutive_failures >= 3
            assert next_attempt_at is not None

            # Verify the last sync run has a circuit-breaker-open message
            runs = await _get_sync_runs(session_factory, server_id)
            circuit_open_runs = [
                r
                for r in runs
                if r.error_message is not None
                and "Circuit breaker open" in r.error_message
            ]
            assert len(circuit_open_runs) > 0
        finally:
            await engine.dispose()


class TestCircuitRecovery:
    """Set up circuit in OPEN state, mock time past recovery timeout.

    Verify transition to HALF_OPEN, then on success verify CLOSED,
    and on failure verify reopens to OPEN.
    """

    async def test_circuit_recovers_on_success(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = await _create_enabled_server(session_factory)

            settings = _make_test_settings(
                sync_max_retries=0,
                sync_circuit_failure_threshold=2,
                sync_circuit_recovery_seconds=60,
            )
            manager = BackgroundTaskManager(settings)
            state = State({"session_factory": session_factory})

            # Manually trip the circuit breaker to OPEN
            breaker = manager._circuit_registry.get_or_create(
                server_id,
                failure_threshold=2,
                recovery_timeout_seconds=60,
            )
            breaker.record_failure()
            breaker.record_failure()
            assert breaker.state == "OPEN"

            # Simulate recovery timeout elapsed by backdating _opened_at
            breaker._opened_at = datetime.now(UTC) - timedelta(seconds=120)

            lib_mock = AsyncMock(return_value=None)
            user_mock = AsyncMock(return_value=_make_sync_result(server_id))

            with (
                patch.object(manager, "_sync_server_libraries", lib_mock),
                patch.object(manager, "_sync_server_users", user_mock),
                patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            ):
                await manager.sync_all_servers(state)

            assert lib_mock.call_count == 1
            assert user_mock.call_count == 1

            circuit = manager.get_circuit_state(server_id)
            assert circuit is not None
            state_name, consecutive_failures, _ = circuit
            assert state_name == "CLOSED"
            assert consecutive_failures == 0
        finally:
            await engine.dispose()

    async def test_circuit_reopens_on_failure_in_half_open(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = await _create_enabled_server(session_factory)

            settings = _make_test_settings(
                sync_max_retries=0,
                sync_circuit_failure_threshold=2,
                sync_circuit_recovery_seconds=60,
            )
            manager = BackgroundTaskManager(settings)
            state = State({"session_factory": session_factory})

            # Trip the circuit breaker to OPEN
            breaker = manager._circuit_registry.get_or_create(
                server_id,
                failure_threshold=2,
                recovery_timeout_seconds=60,
            )
            breaker.record_failure()
            breaker.record_failure()
            assert breaker.state == "OPEN"

            # Simulate recovery timeout elapsed
            breaker._opened_at = datetime.now(UTC) - timedelta(seconds=120)

            lib_mock = AsyncMock(
                side_effect=ExternalServiceError("plex", "Still broken"),
            )
            user_mock = AsyncMock(
                side_effect=ExternalServiceError("plex", "Still broken"),
            )

            with (
                patch.object(manager, "_sync_server_libraries", lib_mock),
                patch.object(manager, "_sync_server_users", user_mock),
                patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            ):
                await manager.sync_all_servers(state)

            # Library sync fails in HALF_OPEN → circuit reopens to OPEN
            # User sync is then skipped because circuit is OPEN again
            circuit = manager.get_circuit_state(server_id)
            assert circuit is not None
            state_name, _, next_attempt_at = circuit
            assert state_name == "OPEN"
            assert next_attempt_at is not None

            runs = await _get_sync_runs(session_factory, server_id)
            lib_runs = [r for r in runs if r.sync_type == "libraries"]
            user_runs = [r for r in runs if r.sync_type == "users"]

            assert len(lib_runs) == 1
            assert lib_runs[0].status == "failed"

            # User sync should be skipped with circuit open message
            assert len(user_runs) == 1
            assert user_runs[0].status == "failed"
            assert user_runs[0].error_message is not None
            assert "Circuit breaker open" in user_runs[0].error_message
        finally:
            await engine.dispose()


class TestNonRetryableError:
    """Mock server fails with NotFoundError — no retries attempted.

    Verify only 1 call to the mock and that the circuit records the failure.
    """

    async def test_no_retry_on_non_retryable_error(self) -> None:
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            server_id = await _create_enabled_server(session_factory)

            settings = _make_test_settings(sync_max_retries=2)
            manager = BackgroundTaskManager(settings)
            state = State({"session_factory": session_factory})

            lib_mock = AsyncMock(
                side_effect=NotFoundError("MediaServer", str(server_id)),
            )
            user_mock = AsyncMock(
                side_effect=NotFoundError("MediaServer", str(server_id)),
            )

            with (
                patch.object(manager, "_sync_server_libraries", lib_mock),
                patch.object(manager, "_sync_server_users", user_mock),
                patch("zondarr.core.retry.asyncio.sleep", new_callable=AsyncMock),
            ):
                await manager.sync_all_servers(state)

            # Despite max_retries=2, NotFoundError is not retryable so only 1 call
            assert lib_mock.call_count == 1
            assert user_mock.call_count == 1

            runs = await _get_sync_runs(session_factory, server_id)
            lib_runs = [r for r in runs if r.sync_type == "libraries"]
            user_runs = [r for r in runs if r.sync_type == "users"]

            assert len(lib_runs) == 1
            assert lib_runs[0].status == "failed"
            assert len(user_runs) == 1
            assert user_runs[0].status == "failed"

            # Circuit breaker should record the failure
            circuit = manager.get_circuit_state(server_id)
            assert circuit is not None
            _, consecutive_failures, _ = circuit
            assert consecutive_failures == 2  # 1 for lib + 1 for user
        finally:
            await engine.dispose()
