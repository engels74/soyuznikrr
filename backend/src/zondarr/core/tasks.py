"""Background task management for Zondarr.

Provides:
- BackgroundTaskManager: Manages periodic background tasks
- background_tasks_lifespan: Lifespan context manager for task lifecycle

Background tasks include:
- Invitation expiration: Disables expired invitation codes
- Media server sync: Synchronizes user data with connected servers

Uses asyncio tasks with graceful shutdown support.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import structlog
from litestar import Litestar
from litestar.datastructures import State
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.config import Settings
from zondarr.repositories.admin import RefreshTokenRepository
from zondarr.repositories.identity import IdentityRepository
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.repositories.user import UserRepository
from zondarr.services.media_server import MediaServerService
from zondarr.services.sync import SyncService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]


class BackgroundTaskManager:
    """Manages periodic background tasks for Zondarr.

    Runs invitation expiration checks and media server synchronization
    at configurable intervals using asyncio tasks.

    Attributes:
        settings: Application settings containing task intervals.
    """

    _tasks: list[asyncio.Task[None]]
    _running: bool
    settings: Settings

    def __init__(self, settings: Settings, /) -> None:
        """Initialize the BackgroundTaskManager.

        Args:
            settings: Application settings with task intervals (positional-only).
        """
        self._tasks = []
        self._running = False
        self.settings = settings

    async def start(self, state: State, /) -> None:
        """Start all background tasks.

        Creates asyncio tasks for expiration checking and media server sync.
        Tasks run continuously until stop() is called.

        Args:
            state: Application state containing session factory (positional-only).
        """
        self._running = True

        self._tasks.append(
            asyncio.create_task(
                self._run_expiration_task(state),
                name="invitation-expiration",
            )
        )
        self._tasks.append(
            asyncio.create_task(
                self._run_sync_task(state),
                name="media-server-sync",
            )
        )
        self._tasks.append(
            asyncio.create_task(
                self._run_token_cleanup_task(state),
                name="token-cleanup",
            )
        )

        logger.info("Background tasks started")

    async def stop(self) -> None:
        """Stop all background tasks gracefully.

        Cancels all running tasks and waits for them to complete.
        Exceptions from cancelled tasks are suppressed.
        """
        self._running = False

        for task in self._tasks:
            _ = task.cancel()

        _ = await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Background tasks stopped")

    async def _run_expiration_task(self, state: State, /) -> None:
        """Periodically check and disable expired invitations.

        Runs at the interval specified by expiration_check_interval_seconds.
        Errors are logged but don't stop the task from continuing.

        Args:
            state: Application state containing session factory (positional-only).
        """
        interval = self.settings.expiration_check_interval_seconds

        while self._running:
            try:
                await self._check_expired_invitations(state)
            except Exception as exc:
                logger.exception("Expiration task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def _run_sync_task(self, state: State, /) -> None:
        """Periodically sync users with media servers.

        Runs at the interval specified by sync_interval_seconds.
        Errors are logged but don't stop the task from continuing.

        Args:
            state: Application state containing session factory (positional-only).
        """
        interval = self.settings.sync_interval_seconds

        while self._running:
            try:
                await self._sync_all_servers(state)
            except Exception as exc:
                logger.exception("Sync task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def check_expired_invitations(self, state: State, /) -> None:
        """Check for and disable expired invitations.

        Public method for testing. Delegates to internal implementation.

        Args:
            state: Application state containing session factory (positional-only).
        """
        await self._check_expired_invitations(state)

    async def sync_all_servers(self, state: State, /) -> None:
        """Sync users with all enabled media servers.

        Public method for testing. Delegates to internal implementation.

        Args:
            state: Application state containing session factory (positional-only).
        """
        await self._sync_all_servers(state)

    async def _check_expired_invitations(self, state: State, /) -> None:
        """Check for and disable expired invitations.

        Queries all expired but enabled invitations and disables them.
        Individual errors are logged but don't stop processing of remaining
        invitations.

        Args:
            state: Application state containing session factory (positional-only).
        """
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            repo = InvitationRepository(session)

            now = datetime.now(UTC)
            expired = await repo.get_expired(now)

            disabled_count = 0
            for invitation in expired:
                try:
                    if invitation.enabled:
                        invitation.enabled = False
                        _ = await repo.update(invitation)
                        disabled_count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to disable expired invitation",
                        invitation_id=str(invitation.id),
                        error=str(exc),
                    )

            if disabled_count > 0:
                await session.commit()
                logger.info(
                    "Disabled expired invitations",
                    count=disabled_count,
                    checked_at=now.isoformat(),
                )

    async def _sync_all_servers(self, state: State, /) -> None:
        """Sync users with all enabled media servers.

        Iterates through all enabled servers and performs sync.
        Individual server failures are logged but don't stop processing
        of remaining servers.

        Args:
            state: Application state containing session factory (positional-only).
        """
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            server_repo = MediaServerRepository(session)
            user_repo = UserRepository(session)

            servers = await server_repo.get_enabled()

            # Sync libraries for each server
            media_server_service = MediaServerService(server_repo)
            for server in servers:
                try:
                    _ = await media_server_service.sync_libraries(server.id)
                    logger.info(
                        "Library sync completed",
                        server_id=str(server.id),
                        server_name=server.name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Library sync failed",
                        server_id=str(server.id),
                        server_name=server.name,
                        error=str(exc),
                    )

            await session.commit()

            # Sync users for each server (import orphaned users)
            identity_repo = IdentityRepository(session)
            sync_service = SyncService(server_repo, user_repo, identity_repo)

            for server in servers:
                try:
                    result = await sync_service.sync_server(server.id, dry_run=False)
                    logger.info(
                        "Server sync completed",
                        server_id=str(server.id),
                        server_name=server.name,
                        orphaned=len(result.orphaned_users),
                        stale=len(result.stale_users),
                        matched=result.matched_users,
                        imported=result.imported_users,
                    )
                except Exception as exc:
                    logger.warning(
                        "Server sync failed",
                        server_id=str(server.id),
                        server_name=server.name,
                        error=str(exc),
                    )

            await session.commit()

    async def _run_token_cleanup_task(self, state: State, /) -> None:
        """Periodically clean up expired refresh tokens.

        Runs at the same interval as expiration checks.
        """
        interval = self.settings.expiration_check_interval_seconds

        while self._running:
            try:
                await self._cleanup_expired_tokens(state)
            except Exception as exc:
                logger.exception("Token cleanup task error", exc_info=exc)

            await asyncio.sleep(interval)

    async def _cleanup_expired_tokens(self, state: State, /) -> None:
        """Delete expired refresh tokens from the database."""
        session_factory = cast(
            async_sessionmaker[AsyncSession],
            state.session_factory,
        )

        async with session_factory() as session:
            repo = RefreshTokenRepository(session)
            now = datetime.now(UTC)
            deleted = await repo.delete_expired(now)
            if deleted > 0:
                await session.commit()
                logger.info("Cleaned up expired refresh tokens", count=deleted)


@asynccontextmanager
async def background_tasks_lifespan(app: Litestar):
    """Lifespan context manager for background tasks.

    Starts background tasks on application startup and stops them
    gracefully on shutdown.

    Args:
        app: The Litestar application instance.

    Yields:
        None - tasks are managed internally.
    """
    settings = cast(Settings, app.state.settings)
    manager = BackgroundTaskManager(settings)

    await manager.start(app.state)

    try:
        yield
    finally:
        await manager.stop()
