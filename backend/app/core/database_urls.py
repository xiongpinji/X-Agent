"""Database URL normalization helpers without store import side effects."""

from __future__ import annotations


def normalize_sync_database_url(database_url: str) -> str:
    """Convert configured async database URLs to synchronous SQLAlchemy URLs."""
    url = database_url.strip()
    lowered = url.lower()
    if lowered.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if lowered.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if lowered.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if lowered.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + url[len("sqlite+aiosqlite://") :]
    return url
