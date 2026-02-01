"""Alembic environment configuration for async SQLAlchemy migrations.

Supports both SQLite (development) and PostgreSQL (production) databases.
Uses async patterns for migration execution with proper connection handling.

The database URL is loaded from:
1. DATABASE_URL environment variable (preferred)
2. alembic.ini sqlalchemy.url setting (fallback)
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models to ensure they are registered with Base.metadata
# This is required for autogenerate to detect model changes
from zondarr.models import Base

# Alembic Config object - provides access to alembic.ini values
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
# This is the MetaData object from our declarative base
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from environment or config.

    Priority:
    1. DATABASE_URL environment variable
    2. sqlalchemy.url from alembic.ini

    Returns:
        Database connection URL string.
    """
    return os.environ.get(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./zondarr.db"),
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render as batch for SQLite ALTER TABLE support
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a connection context.

    Args:
        connection: SQLAlchemy connection to use for migrations.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Render as batch for SQLite ALTER TABLE support
        # This enables proper ALTER TABLE operations on SQLite
        render_as_batch=True,
        # Compare types to detect column type changes
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    Creates an async Engine and associates a connection with the context.
    Uses NullPool to avoid connection pooling issues during migrations.
    """
    # Build configuration dict with database URL
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    # Create async engine with NullPool for migrations
    # NullPool is recommended for migration scripts to avoid
    # connection pooling issues
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Wraps the async migration runner for synchronous Alembic execution.
    """
    asyncio.run(run_async_migrations())


# Determine which mode to run in
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
