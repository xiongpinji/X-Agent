"""MCP database operation tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncpg


class DatabaseOperationTool:
    """Database operation tool for MCP."""

    def __init__(self, connection_string: str):
        """Initialize database operation tool.

        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        self.pool = await asyncpg.create_pool(self.connection_string)

    async def execute_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Query results
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *(params or []))
            return [dict(row) for row in rows]

    async def execute_update(self, query: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Execute an INSERT/UPDATE/DELETE query.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Operation result
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *(params or []))
            return {
                "success": True,
                "affected_rows": int(result.split()[-1]) if result else 0,
            }

    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get table schema.

        Args:
            table_name: Table name

        Returns:
            Table schema
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, table_name)
            columns = [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                }
                for row in rows
            ]
            return {"table": table_name, "columns": columns}

    async def list_tables(self) -> Dict[str, Any]:
        """List all tables in the database.

        Returns:
            List of tables
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            tables = [row["table_name"] for row in rows]
            return {"tables": tables}

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
