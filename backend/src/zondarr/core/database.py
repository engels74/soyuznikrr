"""Database engine, session factory, and lifespan management.

Provides:
- create_engine_from_url: Creates async SQLAlchemy engine with proper configuration
- create_session_factory: Creates async session factory with expire_on_commit=False
- db_lifespan: Lifespan context manager for connection pool management
- provide_db_session: Generator dependency for session management with auto commit/rollback

Uses SQLAlchemy 2.0 async patterns with proper connection pooling.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from litestar import Litestar
from litestar.datastructures import State
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from zondarr.config import Settings


def create_engine_from_url(
    database_url: str,
    /,
    *,
    debug: bool = False,
    pool_pre_ping: bool = True,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine from a database URL.

    Args:
        database_url: Database connection URL (sqlite+aiosqlite:// or postgresql+asyncpg://).
        debug: Enable SQL echo logging for debugging.
        pool_pre_ping: Enable connection health checks before use.

    Returns:
        Configured AsyncEngine instance.
    """
    return create_async_engine(
        database_url,
        echo=debug,
        pool_pre_ping=pool_pre_ping,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the given engine.

    Uses expire_on_commit=False to allow accessing attributes after commit
    without triggering lazy loads in async context.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        Configured async_sessionmaker instance.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None]:
    """Manage database connection pool lifecycle.

    Creates the engine and session factory on startup, stores them in app state,
    and disposes the engine on shutdown.

    Args:
        app: The Litestar application instance.

    Yields:
        None - resources are stored in app.state.

    Note:
        Expects app.state.settings to be a Settings instance.
        This is set by the application factory before lifespan runs.
    """
    # Cast is safe here - app factory guarantees Settings is in state
    settings = cast(Settings, app.state.settings)
    engine = create_engine_from_url(
        settings.database_url,
        debug=settings.debug,
    )
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


async def provide_db_session(state: State) -> AsyncGenerator[AsyncSession]:
    """Provide a database session with automatic commit/rollback.

    This is a generator dependency that:
    - Creates a new session from the factory
    - Yields it for use in handlers
    - Commits on success
    - Rolls back on exception

    Args:
        state: The application state containing the session factory.

    Yields:
        An AsyncSession instance for database operations.

    Note:
        Expects state.session_factory to be an async_sessionmaker[AsyncSession].
        This is set by db_lifespan during application startup.
    """
    # Cast is safe here - db_lifespan guarantees session_factory is in state
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        state.session_factory,
    )
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
