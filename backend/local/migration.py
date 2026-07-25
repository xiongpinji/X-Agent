"""
X-Agent Local Database Migration Scripts

Handles database schema initialization and data migration.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.local.database import DatabaseConfig, LocalDatabase
from backend.local.schema import (
    ALL_TABLES,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Handles database migrations."""

    def __init__(self, db: LocalDatabase):
        """Initialize migration handler.

        Args:
            db: Local database instance
        """
        self.db = db

    def migrate_v1_initial(self) -> None:
        """Execute initial schema migration (v1).

        Creates all tables and indexes.
        """
        logger.info("Executing migration: v1_initial")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Enable foreign keys
                cursor.execute("PRAGMA foreign_keys = ON")

                # Create all tables
                # 每个 *_TABLE 含多条语句(CREATE TABLE + 多条 CREATE INDEX),
                # sqlite3 的 execute() 一次只能跑一条,必须用 executescript()。
                for table_sql in ALL_TABLES:
                    cursor.executescript(table_sql)
                    logger.debug("Created table from schema")

                # Create views
                self._create_views(cursor)

                # Record migration
                self._record_migration(cursor, "v1_initial", "Initial schema creation")

                logger.info("Migration v1_initial completed successfully")

        except Exception as e:
            logger.error(f"Migration v1_initial failed: {e}")
            raise

    def _create_views(self, cursor) -> None:
        """Create database views.

        Args:
            cursor: Database cursor
        """
        # Pending sync view
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS pending_sync AS
            SELECT
                sq.id,
                sq.entity_type,
                sq.entity_id,
                sq.operation,
                sq.priority,
                sq.retry_count,
                sq.created_at,
                ss.state as sync_state
            FROM sync_queue sq
            LEFT JOIN sync_state ss ON sq.entity_type = ss.entity_type
                AND sq.entity_id = ss.entity_id
            WHERE sq.status = 'pending'
            ORDER BY sq.priority DESC, sq.created_at ASC
        """)

        # Conflicted entities view
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS conflicted_entities AS
            SELECT
                cl.entity_type,
                cl.entity_id,
                COUNT(*) as conflict_count,
                MAX(cl.created_at) as latest_conflict,
                GROUP_CONCAT(DISTINCT cl.conflict_type) as conflict_types
            FROM conflict_log cl
            WHERE cl.resolved_at IS NULL
            GROUP BY cl.entity_type, cl.entity_id
        """)

        # Sync performance view
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS sync_performance AS
            SELECT
                DATE(sh.created_at) as sync_date,
                sh.entity_type,
                COUNT(*) as total_operations,
                SUM(CASE WHEN sh.status = 'success' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN sh.status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(sh.duration_ms) as avg_duration_ms,
                MAX(sh.duration_ms) as max_duration_ms
            FROM sync_history sh
            GROUP BY DATE(sh.created_at), sh.entity_type
        """)

        logger.info("Database views created")

    def _record_migration(self, cursor, migration_name: str, description: str) -> None:
        """Record migration execution.

        Args:
            cursor: Database cursor
            migration_name: Migration name
            description: Migration description
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                migration_name TEXT NOT NULL UNIQUE,
                description TEXT,
                executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO schema_migrations
            (id, migration_name, description, executed_at)
            VALUES (?, ?, ?, ?)
        """, (
            f"{migration_name}_{datetime.now(UTC).timestamp()}",
            migration_name,
            description,
            datetime.now(UTC),
        ))

    def get_migration_status(self) -> dict:
        """Get migration status.

        Returns:
            Migration status dictionary
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            # Check if migrations table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_migrations'
            """)

            if not cursor.fetchone():
                return {
                    "initialized": False,
                    "current_version": None,
                    "migrations": [],
                }

            # Get executed migrations
            cursor.execute("""
                SELECT migration_name, executed_at
                FROM schema_migrations
                ORDER BY executed_at DESC
            """)

            migrations = [
                {
                    "name": row[0],
                    "executed_at": row[1],
                }
                for row in cursor.fetchall()
            ]

            return {
                "initialized": True,
                "current_version": SCHEMA_VERSION,
                "migrations": migrations,
            }

        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {
                "initialized": False,
                "current_version": None,
                "migrations": [],
            }


class DataMigration:
    """Handles data migration from PostgreSQL to SQLite."""

    def __init__(self, db: LocalDatabase, pg_connection=None):
        """Initialize data migration handler.

        Args:
            db: Local database instance
            pg_connection: PostgreSQL connection (optional)
        """
        self.db = db
        self.pg_connection = pg_connection

    def migrate_memories(self, batch_size: int = 100) -> int:
        """Migrate memories from PostgreSQL to SQLite.

        Args:
            batch_size: Batch size for migration

        Returns:
            Number of records migrated
        """
        if not self.pg_connection:
            logger.warning("PostgreSQL connection not available, skipping memory migration")
            return 0

        logger.info("Starting memory migration")

        try:
            pg_cursor = self.pg_connection.cursor()

            # Get total count
            pg_cursor.execute("SELECT COUNT(*) FROM memories")
            total = pg_cursor.fetchone()[0]

            migrated = 0

            # Migrate in batches
            for offset in range(0, total, batch_size):
                pg_cursor.execute("""
                    SELECT id, tenant_id, agent_id, session_id, content, layer,
                           importance, tags, created_at, updated_at
                    FROM memories
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))

                rows = pg_cursor.fetchall()

                with self.db.transaction() as conn:
                    cursor = conn.cursor()

                    for row in rows:
                        cursor.execute("""
                            INSERT INTO local_memories
                            (id, tenant_id, agent_id, session_id, content, layer,
                             importance, tags, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, row)

                        # Set metadata
                        self.db.set_metadata(
                            entity_type="memory",
                            entity_id=row[0],
                            local_version=1,
                            cloud_version=1,
                        )

                migrated += len(rows)
                logger.info(f"Migrated {migrated}/{total} memories")

            logger.info(f"Memory migration completed: {migrated} records")
            return migrated

        except Exception as e:
            logger.error(f"Memory migration failed: {e}")
            raise

    def migrate_workflows(self, batch_size: int = 50) -> int:
        """Migrate workflows from PostgreSQL to SQLite.

        Args:
            batch_size: Batch size for migration

        Returns:
            Number of records migrated
        """
        if not self.pg_connection:
            logger.warning("PostgreSQL connection not available, skipping workflow migration")
            return 0

        logger.info("Starting workflow migration")

        try:
            pg_cursor = self.pg_connection.cursor()

            # Get total count
            pg_cursor.execute("SELECT COUNT(*) FROM workflows")
            total = pg_cursor.fetchone()[0]

            migrated = 0

            # Migrate in batches
            for offset in range(0, total, batch_size):
                pg_cursor.execute("""
                    SELECT id, tenant_id, name, description, definition, status,
                           version, tags, created_at, updated_at
                    FROM workflows
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))

                rows = pg_cursor.fetchall()

                with self.db.transaction() as conn:
                    cursor = conn.cursor()

                    for row in rows:
                        cursor.execute("""
                            INSERT INTO local_workflows
                            (id, tenant_id, name, description, definition, status,
                             version, tags, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, row)

                        # Set metadata
                        self.db.set_metadata(
                            entity_type="workflow",
                            entity_id=row[0],
                            local_version=1,
                            cloud_version=1,
                        )

                migrated += len(rows)
                logger.info(f"Migrated {migrated}/{total} workflows")

            logger.info(f"Workflow migration completed: {migrated} records")
            return migrated

        except Exception as e:
            logger.error(f"Workflow migration failed: {e}")
            raise

    def migrate_runs(self, batch_size: int = 100) -> int:
        """Migrate runs from PostgreSQL to SQLite.

        Args:
            batch_size: Batch size for migration

        Returns:
            Number of records migrated
        """
        if not self.pg_connection:
            logger.warning("PostgreSQL connection not available, skipping run migration")
            return 0

        logger.info("Starting run migration")

        try:
            pg_cursor = self.pg_connection.cursor()

            # Get total count
            pg_cursor.execute("SELECT COUNT(*) FROM runs")
            total = pg_cursor.fetchone()[0]

            migrated = 0

            # Migrate in batches
            for offset in range(0, total, batch_size):
                pg_cursor.execute("""
                    SELECT id, tenant_id, workflow_id, agent_id, status,
                           input, output, error_message, started_at, completed_at,
                           duration_ms, created_at, updated_at
                    FROM runs
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))

                rows = pg_cursor.fetchall()

                with self.db.transaction() as conn:
                    cursor = conn.cursor()

                    for row in rows:
                        cursor.execute("""
                            INSERT INTO local_runs
                            (id, tenant_id, workflow_id, agent_id, status,
                             input, output, error_message, started_at, completed_at,
                             duration_ms, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, row)

                        # Set metadata
                        self.db.set_metadata(
                            entity_type="run",
                            entity_id=row[0],
                            local_version=1,
                            cloud_version=1,
                        )

                migrated += len(rows)
                logger.info(f"Migrated {migrated}/{total} runs")

            logger.info(f"Run migration completed: {migrated} records")
            return migrated

        except Exception as e:
            logger.error(f"Run migration failed: {e}")
            raise

    def migrate_sessions(self, batch_size: int = 100) -> int:
        """Migrate sessions from PostgreSQL to SQLite.

        Args:
            batch_size: Batch size for migration

        Returns:
            Number of records migrated
        """
        if not self.pg_connection:
            logger.warning("PostgreSQL connection not available, skipping session migration")
            return 0

        logger.info("Starting session migration")

        try:
            pg_cursor = self.pg_connection.cursor()

            # Get total count
            pg_cursor.execute("SELECT COUNT(*) FROM sessions")
            total = pg_cursor.fetchone()[0]

            migrated = 0

            # Migrate in batches
            for offset in range(0, total, batch_size):
                pg_cursor.execute("""
                    SELECT id, tenant_id, user_id, agent_id, title, summary,
                           tags, created_at, updated_at
                    FROM sessions
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))

                rows = pg_cursor.fetchall()

                with self.db.transaction() as conn:
                    cursor = conn.cursor()

                    for row in rows:
                        cursor.execute("""
                            INSERT INTO local_sessions
                            (id, tenant_id, user_id, agent_id, title, summary,
                             tags, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, row)

                        # Set metadata
                        self.db.set_metadata(
                            entity_type="session",
                            entity_id=row[0],
                            local_version=1,
                            cloud_version=1,
                        )

                migrated += len(rows)
                logger.info(f"Migrated {migrated}/{total} sessions")

            logger.info(f"Session migration completed: {migrated} records")
            return migrated

        except Exception as e:
            logger.error(f"Session migration failed: {e}")
            raise


def initialize_local_database(db_path: str = "~/.xagent/local.db") -> LocalDatabase:
    """Initialize local database with schema.

    Args:
        db_path: Path to database file

    Returns:
        Initialized LocalDatabase instance
    """
    logger.info(f"Initializing local database at {db_path}")

    # Create database config
    db_config = DatabaseConfig(
        db_path=db_path,
        timeout=30.0,
        enable_wal=True,
        enable_foreign_keys=True,
    )

    # Create database instance
    db = LocalDatabase(db_config)

    # Initialize schema
    db.initialize()

    # Execute migrations
    migration = DatabaseMigration(db)
    migration.migrate_v1_initial()

    logger.info("Local database initialized successfully")
    return db


def migrate_data_from_postgres(
    db: LocalDatabase,
    pg_connection,
    migrate_all: bool = True,
) -> dict:
    """Migrate data from PostgreSQL to SQLite.

    Args:
        db: Local database instance
        pg_connection: PostgreSQL connection
        migrate_all: Whether to migrate all data types

    Returns:
        Migration statistics
    """
    logger.info("Starting data migration from PostgreSQL")

    data_migration = DataMigration(db, pg_connection)

    stats = {
        "memories": 0,
        "workflows": 0,
        "runs": 0,
        "sessions": 0,
        "total": 0,
    }

    try:
        if migrate_all:
            stats["memories"] = data_migration.migrate_memories()
            stats["workflows"] = data_migration.migrate_workflows()
            stats["runs"] = data_migration.migrate_runs()
            stats["sessions"] = data_migration.migrate_sessions()

        stats["total"] = sum(v for k, v in stats.items() if k != "total")

        logger.info(f"Data migration completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Data migration failed: {e}")
        raise
