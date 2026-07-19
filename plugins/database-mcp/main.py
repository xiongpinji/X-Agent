"""Database MCP Plugin - Query and manage PostgreSQL and MySQL databases"""

import logging
from typing import Any, Optional, List
import csv
import json
from io import StringIO

logger = logging.getLogger(__name__)


class DatabasePlugin:
    """Database MCP Plugin Server"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize Database plugin"""
        self.config = config or {}
        self.db_type = self.config.get("db_type", "postgresql")
        self.db_host = self.config.get("db_host")
        self.db_port = self.config.get("db_port", 5432)
        self.db_user = self.config.get("db_user")
        self.db_password = self.config.get("db_password")
        self.db_name = self.config.get("db_name")
        self.timeout = self.config.get("timeout", 30)

        # Validate required config
        required_fields = ["db_host", "db_user", "db_password", "db_name"]
        for field in required_fields:
            if not self.config.get(field):
                raise ValueError(f"{field} is required")

        self.connection = None
        self._connect()
        logger.info(f"DatabasePlugin initialized for {self.db_type}")

    def _connect(self) -> None:
        """Connect to database"""
        try:
            if self.db_type == "postgresql":
                import psycopg2
                self.connection = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name,
                    connect_timeout=self.timeout
                )
            elif self.db_type == "mysql":
                import mysql.connector
                self.connection = mysql.connector.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name,
                    connection_timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")

            logger.info(f"Connected to {self.db_type} database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def execute_query(self, query: str, limit: int = 100) -> dict[str, Any]:
        """Execute a SQL query"""
        try:
            cursor = self.connection.cursor()

            # Add LIMIT clause if not present
            if "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"

            cursor.execute(query)

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Fetch results
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))

            cursor.close()

            return {
                "status": "success",
                "data": results,
                "count": len(results),
                "columns": columns
            }
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return {
                "status": "error",
                "message": f"Query execution error: {str(e)}"
            }

    async def list_tables(self) -> dict[str, Any]:
        """List all tables in the database"""
        try:
            cursor = self.connection.cursor()

            if self.db_type == "postgresql":
                query = """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """
            elif self.db_type == "mysql":
                query = f"SHOW TABLES FROM {self.db_name}"
            else:
                return {"status": "error", "message": "Unsupported database type"}

            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()

            return {
                "status": "success",
                "data": tables,
                "count": len(tables)
            }
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return {
                "status": "error",
                "message": f"Failed to list tables: {str(e)}"
            }

    async def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get table schema"""
        try:
            cursor = self.connection.cursor()

            if self.db_type == "postgresql":
                query = f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """
            elif self.db_type == "mysql":
                query = f"DESCRIBE {table_name}"
            else:
                return {"status": "error", "message": "Unsupported database type"}

            cursor.execute(query)
            columns = cursor.fetchall()
            cursor.close()

            schema = []
            for col in columns:
                if self.db_type == "postgresql":
                    schema.append({
                        "name": col[0],
                        "type": col[1],
                        "nullable": col[2] == "YES"
                    })
                elif self.db_type == "mysql":
                    schema.append({
                        "name": col[0],
                        "type": col[1],
                        "nullable": col[2] == "YES"
                    })

            return {
                "status": "success",
                "data": schema,
                "count": len(schema)
            }
        except Exception as e:
            logger.error(f"Failed to get table schema: {e}")
            return {
                "status": "error",
                "message": f"Failed to get table schema: {str(e)}"
            }

    async def export_query_result(
        self,
        query: str,
        format: str = "csv",
        filename: str = "export"
    ) -> dict[str, Any]:
        """Export query result to file"""
        try:
            # Execute query
            result = await self.execute_query(query)
            if result["status"] != "success":
                return result

            data = result["data"]
            columns = result["columns"]

            # Export based on format
            if format == "csv":
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
                content = output.getvalue()
                file_path = f"{filename}.csv"

            elif format == "json":
                content = json.dumps(data, indent=2, default=str)
                file_path = f"{filename}.json"

            elif format == "excel":
                try:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    file_path = f"{filename}.xlsx"
                    df.to_excel(file_path, index=False)
                    return {
                        "status": "success",
                        "message": f"Exported to {file_path}",
                        "file_path": file_path
                    }
                except ImportError:
                    return {
                        "status": "error",
                        "message": "Excel export requires pandas and openpyxl"
                    }
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported format: {format}"
                }

            # Write to file
            with open(file_path, "w") as f:
                f.write(content)

            return {
                "status": "success",
                "message": f"Exported to {file_path}",
                "file_path": file_path,
                "rows": len(data)
            }
        except Exception as e:
            logger.error(f"Export error: {e}")
            return {
                "status": "error",
                "message": f"Export error: {str(e)}"
            }

    async def analyze_table(self, table_name: str) -> dict[str, Any]:
        """Analyze table statistics"""
        try:
            cursor = self.connection.cursor()

            if self.db_type == "postgresql":
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                # Get table size
                cursor.execute(f"""
                    SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
                """)
                table_size = cursor.fetchone()[0]

                # Get column count
                cursor.execute(f"""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                """)
                column_count = cursor.fetchone()[0]

            elif self.db_type == "mysql":
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                # Get table size
                cursor.execute(f"""
                    SELECT ROUND(((data_length + index_length) / 1024 / 1024), 2)
                    FROM information_schema.TABLES
                    WHERE table_schema = '{self.db_name}' AND table_name = '{table_name}'
                """)
                size_result = cursor.fetchone()
                table_size = f"{size_result[0]} MB" if size_result else "Unknown"

                # Get column count
                cursor.execute(f"DESCRIBE {table_name}")
                column_count = len(cursor.fetchall())

            cursor.close()

            return {
                "status": "success",
                "data": {
                    "table_name": table_name,
                    "row_count": row_count,
                    "column_count": column_count,
                    "table_size": table_size
                }
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {
                "status": "error",
                "message": f"Analysis error: {str(e)}"
            }

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Handle tool calls"""
        try:
            if tool_name == "execute_query":
                return await self.execute_query(**args)
            elif tool_name == "list_tables":
                return await self.list_tables()
            elif tool_name == "get_table_schema":
                return await self.get_table_schema(**args)
            elif tool_name == "export_query_result":
                return await self.export_query_result(**args)
            elif tool_name == "analyze_table":
                return await self.analyze_table(**args)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "status": "error",
                "message": f"Tool execution error: {str(e)}"
            }

    def __del__(self):
        """Close database connection"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


# Entry point for MCP server
if __name__ == "__main__":
    import asyncio

    # Example usage
    config = {
        "db_type": "postgresql",
        "db_host": "localhost",
        "db_port": 5432,
        "db_user": "postgres",
        "db_password": "password",
        "db_name": "mydb"
    }

    plugin = DatabasePlugin(config)

    # Test
    result = asyncio.run(plugin.list_tables())
    print(result)
