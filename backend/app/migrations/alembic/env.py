"""Alembic environment configuration.

This script is run whenever alembic command is invoked.
It configures the logging and context for executing migrations.

Supports both online (live database) and offline (generate script) modes.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import declarative_base

# Import models for autogenerate
try:
    from backend.app.core.models import Base
except ImportError:
    # Fallback if models not yet available
    Base = declarative_base()

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# Set the SQLAlchemy URL from environment or config
def get_sqlalchemy_url() -> str:
    """Get database URL from environment or configuration."""
    from backend.app.core.config import get_settings

    try:
        settings = get_settings()
        return settings.database.url
    except Exception:
        # Fallback to config file
        return config.get_main_option("sqlalchemy.url", "sqlite:///./data/xagent.db")


# ============================================================================
# Offline Mode (generates SQL script)
# ============================================================================

def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    Generates SQL migration scripts that can be reviewed before running.
    This is useful for CI/CD pipelines where you want to inspect migrations first.
    """
    url = get_sqlalchemy_url()
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================================
# Online Mode (connects to database)
# ============================================================================

async def run_async_migrations() -> None:
    """Run async migrations.

    Supports async SQLAlchemy engines (asyncpg for PostgreSQL, aiosqlite for SQLite).
    """
    from backend.app.core.database import normalize_async_database_url

    url = get_sqlalchemy_url()
    async_url = normalize_async_database_url(url)

    config.set_main_option("sqlalchemy.url", async_url)

    connectable = create_async_engine(
        async_url,
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection) -> None:
    """Run migrations with connection object."""
    context.configure(connection=connection, target_metadata=Base.metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode.

    Connects to actual database and executes migrations.
    Detects if async engine is needed (PostgreSQL+asyncpg or SQLite+aiosqlite).
    """
    url = get_sqlalchemy_url()

    # Check if we need async
    is_async = url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://"))

    if is_async:
        # For async databases, run in event loop
        import asyncio
        asyncio.run(run_async_migrations())
    else:
        # For sync databases (shouldn't happen in X-Agent, but support fallback)
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
            )

            with context.begin_transaction():
                context.run_migrations()


# ============================================================================
# Main Entry Point
# ============================================================================

if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    run_migrations_online()
