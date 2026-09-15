"""Alembic environment configuration for X-Agent.

Supports both async (asyncpg) and sync (psycopg2) migration modes.
Reads DATABASE_URL from alembic.ini or XAGENT_DATABASE_URL env var.
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to path so backend.app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

# Import all models so they register with Base.metadata
from backend.app.models import (  # noqa: F401
    APIKeyStoreModel,
    ApprovalStoreModel,
    Base,
    CSRFTokenModel,
    RateLimitLogModel,
    UserStoreModel,
)

try:
    from backend.app.models.subscription import (  # noqa: F401
        QuotaModel,
        SubscriptionHistoryModel,
        SubscriptionModel,
    )
except ImportError:
    pass

try:
    from backend.app.models.feedback import (  # noqa: F401
        FeedbackAnalysisModel,
        FeedbackModel,
    )
except ImportError:
    pass

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment if available
db_url = os.environ.get("XAGENT_DATABASE_URL", "")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to script output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("No sqlalchemy.url configured")

    # Convert sync URL to async if needed
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite:///") and "+aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = config.get_main_option("sqlalchemy.url") or ""
    if "asyncpg" in url or "aiosqlite" in url or url.startswith("postgresql://"):
        asyncio.run(run_async_migrations())
    else:
        # Fallback: sync engine
        from sqlalchemy import create_engine
        connectable = create_engine(url, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            do_run_migrations(connection)
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
