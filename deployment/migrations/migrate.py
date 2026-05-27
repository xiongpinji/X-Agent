#!/usr/bin/env python3
"""
Database migration management for X-Agent production deployment.
Handles schema migrations, backups, and rollback procedures.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
from alembic import command
from alembic.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Manages database migrations and backups."""

    def __init__(self, db_url: str, backup_dir: str = "/backups"):
        self.db_url = db_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.alembic_cfg = Config("alembic.ini")

    async def backup_database(self) -> str:
        """
        Create a database backup before migration.

        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"backup_{timestamp}.sql"

        try:
            logger.info(f"Starting database backup to {backup_file}")

            # Parse connection string
            conn_params = self._parse_connection_string()

            # Create backup using pg_dump
            import subprocess
            cmd = [
                "pg_dump",
                f"--host={conn_params['host']}",
                f"--port={conn_params['port']}",
                f"--username={conn_params['user']}",
                f"--dbname={conn_params['database']}",
                "--format=custom",
                f"--file={backup_file}",
                "--verbose"
            ]

            env = {"PGPASSWORD": conn_params['password']}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"pg_dump failed: {result.stderr}")

            logger.info(f"Database backup completed: {backup_file}")
            return str(backup_file)

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    async def restore_database(self, backup_file: str) -> None:
        """
        Restore database from backup file.

        Args:
            backup_file: Path to the backup file
        """
        try:
            logger.info(f"Starting database restore from {backup_file}")

            conn_params = self._parse_connection_string()

            import subprocess
            cmd = [
                "pg_restore",
                f"--host={conn_params['host']}",
                f"--port={conn_params['port']}",
                f"--username={conn_params['user']}",
                f"--dbname={conn_params['database']}",
                "--clean",
                "--if-exists",
                backup_file
            ]

            env = {"PGPASSWORD": conn_params['password']}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"pg_restore failed: {result.stderr}")

            logger.info("Database restore completed")

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise

    async def run_migrations(self, target_revision: Optional[str] = None) -> None:
        """
        Execute database migrations.

        Args:
            target_revision: Target revision (default: head)
        """
        backup_file = None
        try:
            # Create backup before migration
            backup_file = await self.backup_database()

            # Run migrations
            target = target_revision or "head"
            logger.info(f"Running migrations to {target}")
            command.upgrade(self.alembic_cfg, target)
            logger.info("Migrations completed successfully")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if backup_file:
                logger.info("Attempting to restore from backup...")
                try:
                    await self.restore_database(backup_file)
                    logger.info("Restore completed")
                except Exception as restore_error:
                    logger.error(f"Restore failed: {restore_error}")
            raise

    async def rollback_migrations(self, steps: int = 1) -> None:
        """
        Rollback migrations by specified number of steps.

        Args:
            steps: Number of migration steps to rollback
        """
        try:
            logger.info(f"Rolling back {steps} migration(s)")

            # Get current revision
            current = command.current(self.alembic_cfg)
            logger.info(f"Current revision: {current}")

            # Rollback
            for _ in range(steps):
                command.downgrade(self.alembic_cfg, "-1")

            logger.info("Rollback completed")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

    async def verify_migration(self) -> bool:
        """
        Verify database schema after migration.

        Returns:
            True if verification passed
        """
        try:
            logger.info("Verifying database schema...")

            conn = await asyncpg.connect(self.db_url)

            # Check critical tables exist
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
            """)

            required_tables = {
                'users', 'workflows', 'runs', 'tasks',
                'audit_logs', 'approvals', 'memory_entries'
            }

            existing_tables = {row['table_name'] for row in tables}

            if not required_tables.issubset(existing_tables):
                missing = required_tables - existing_tables
                logger.error(f"Missing tables: {missing}")
                return False

            logger.info("Schema verification passed")
            await conn.close()
            return True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def _parse_connection_string(self) -> dict:
        """Parse PostgreSQL connection string."""
        # postgresql://user:password@host:port/database
        from urllib.parse import urlparse

        parsed = urlparse(self.db_url)
        return {
            'user': parsed.username,
            'password': parsed.password,
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/')
        }


async def main():
    """Main entry point."""
    import os

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    migrator = DatabaseMigrator(db_url)

    if len(sys.argv) < 2:
        logger.error("Usage: migrate.py [migrate|rollback|verify|backup|restore]")
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "migrate":
            target = sys.argv[2] if len(sys.argv) > 2 else None
            await migrator.run_migrations(target)
            if await migrator.verify_migration():
                logger.info("Migration successful and verified")
            else:
                logger.error("Migration verification failed")
                sys.exit(1)

        elif command == "rollback":
            steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            await migrator.rollback_migrations(steps)

        elif command == "verify":
            if await migrator.verify_migration():
                sys.exit(0)
            else:
                sys.exit(1)

        elif command == "backup":
            backup_file = await migrator.backup_database()
            logger.info(f"Backup created: {backup_file}")

        elif command == "restore":
            if len(sys.argv) < 3:
                logger.error("Usage: migrate.py restore <backup_file>")
                sys.exit(1)
            await migrator.restore_database(sys.argv[2])

        else:
            logger.error(f"Unknown command: {command}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
