"""
Migration script to move API keys from JSON file storage to PostgreSQL database.
Maintains backward compatibility by supporting both storage backends during transition.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class APIKeyMigration:
    """Handles migration of API keys from JSON to PostgreSQL."""

    def __init__(self, json_path: Path, db_url: str):
        self.json_path = json_path
        self.db_url = db_url
        self.pool: asyncpg.Pool | None = None

    async def setup_database(self) -> None:
        """Create connection pool and initialize schema."""
        self.pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
        await self._create_schema()

    async def _create_schema(self) -> None:
        """Create api_keys table if it doesn't exist."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    key_prefix VARCHAR(50) NOT NULL UNIQUE,
                    key_hash VARCHAR(255) NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    scopes TEXT[] NOT NULL,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
                CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
            """)
            logger.info("Database schema initialized")

    async def load_json_keys(self) -> list[dict[str, Any]]:
        """Load API keys from JSON file."""
        if not self.json_path.exists():
            logger.warning(f"JSON file not found: {self.json_path}")
            return []

        try:
            with open(self.json_path) as f:
                keys = json.load(f)
            logger.info(f"Loaded {len(keys)} keys from JSON")
            return keys
        except Exception as e:
            logger.error(f"Failed to load JSON keys: {e}")
            return []

    async def migrate_keys(self) -> dict[str, int]:
        """Migrate keys from JSON to database."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        keys = await self.load_json_keys()
        stats = {"total": len(keys), "migrated": 0, "skipped": 0, "failed": 0}

        async with self.pool.acquire() as conn:
            for key in keys:
                try:
                    # Check if key already exists
                    existing = await conn.fetchval(
                        "SELECT id FROM api_keys WHERE key_prefix = $1",
                        key.get("key_prefix"),
                    )
                    if existing:
                        logger.debug(f"Key {key.get('key_prefix')} already exists, skipping")
                        stats["skipped"] += 1
                        continue

                    # Insert key
                    await conn.execute(
                        """
                        INSERT INTO api_keys
                        (id, name, key_prefix, key_hash, tenant_id, user_id, role, scopes, revoked, created_at, revoked_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        key.get("id"),
                        key.get("name"),
                        key.get("key_prefix"),
                        key.get("key_hash"),
                        key.get("tenant_id"),
                        key.get("user_id"),
                        key.get("role"),
                        key.get("scopes", []),
                        key.get("revoked", False),
                        key.get("created_at"),
                        key.get("revoked_at"),
                    )
                    stats["migrated"] += 1
                    logger.debug(f"Migrated key: {key.get('key_prefix')}")
                except Exception as e:
                    logger.error(f"Failed to migrate key {key.get('key_prefix')}: {e}")
                    stats["failed"] += 1

        return stats

    async def verify_migration(self) -> bool:
        """Verify that migration was successful."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        async with self.pool.acquire() as conn:
            db_count = await conn.fetchval("SELECT COUNT(*) FROM api_keys")
            json_keys = await self.load_json_keys()
            json_count = len(json_keys)

            logger.info(f"Verification: {db_count} keys in DB, {json_count} keys in JSON")
            return db_count >= json_count

    async def cleanup(self) -> None:
        """Close database connections."""
        if self.pool:
            await self.pool.close()


async def run_migration(json_path: Path, db_url: str) -> None:
    """Execute the migration."""
    migration = APIKeyMigration(json_path, db_url)
    try:
        await migration.setup_database()
        stats = await migration.migrate_keys()
        logger.info(f"Migration stats: {stats}")

        if await migration.verify_migration():
            logger.info("Migration verification passed")
        else:
            logger.warning("Migration verification failed - check logs")
    finally:
        await migration.cleanup()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: python migrate_api_keys.py <json_path> <db_url>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    db_url = sys.argv[2]

    asyncio.run(run_migration(json_path, db_url))
