"""Database MCP Plugin - 真实 stdio MCP server（官方 ``mcp`` SDK FastMCP）

迁移说明（原为普通 Python 类占位，握手必然失败）：

- 本模块是插件子进程入口（``python -m main``，stdio MCP server）；保留
  ``DatabasePlugin`` 入口类供 PluginRuntime.inspect_entrypoint() 进程内验证。
- 配置注入契约：从 ``XAGENT_PLUGIN_CONFIG`` 环境变量读取 JSON 对象配置。
- fail-closed 契约：缺必填连接配置（postgresql/mysql 需 db_host/db_user/
  db_password/db_name；sqlite 需 db_name 作为库文件路径）时进程在握手前
  退出（码 2 + stderr 诊断），绝不伪造可用。
- 连接策略：**惰性连接**。配置校验在启动时完成（保证握手成功与工具可发
  现），真实数据库连接在首次工具调用时建立——数据库暂不可达/驱动缺失是
  工具级失败（isError=True，会话保持可用，错误可诊断），不影响握手。
- 后端支持：postgresql（psycopg2）、mysql（mysql-connector）、sqlite
  （标准库 sqlite3，适合本地开发与测试）。驱动按需导入，缺失时工具级报错。

进程内使用（不经 MCP）::

    from main import DatabasePlugin
    plugin = DatabasePlugin({"db_type": "sqlite", "db_name": "C:/tmp/t.db"})
    await plugin.execute_query("SELECT 1 AS one")
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
from io import StringIO
from typing import Any, NoReturn

logger = logging.getLogger(__name__)

# 与 backend.app.core.mcp_plugin_adapter.PLUGIN_CONFIG_ENV_VAR 保持一致
CONFIG_ENV_VAR = "XAGENT_PLUGIN_CONFIG"
PLUGIN_NAME = "database-mcp"

SUPPORTED_DB_TYPES = ("postgresql", "mysql", "sqlite")

# 嵌入 SQL 的标识符（表名）必须匹配（防注入；参数化查询之外的全部嵌入点）
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _valid_identifier(name: str) -> bool:
    return bool(_IDENTIFIER_RE.match(name or ""))


def _jsonify(value: Any) -> Any:
    """行值 → JSON 可序列化值（日期/Decimal 等转字符串）。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


class DatabasePlugin:
    """Database MCP Plugin Server（query 工具 + 配置校验 + 惰性连接）"""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Database plugin（校验配置；不建立连接）"""
        self.config = config or {}
        self.db_type = str(self.config.get("db_type") or "postgresql").lower().strip()
        self.db_host = self.config.get("db_host")
        self.db_port = self.config.get("db_port")
        self.db_user = self.config.get("db_user")
        self.db_password = self.config.get("db_password")
        self.db_name = self.config.get("db_name")
        self.timeout = self.config.get("timeout", 30)

        if self.db_type not in SUPPORTED_DB_TYPES:
            raise ValueError(
                f"Unsupported db_type: {self.db_type!r} "
                f"(supported: {', '.join(SUPPORTED_DB_TYPES)})"
            )

        if self.db_type == "sqlite":
            # sqlite：db_name 即库文件路径（其余连接字段不适用）
            if not self.db_name:
                raise ValueError(
                    "db_name is required for db_type=sqlite "
                    "(path to the sqlite database file)"
                )
            self.db_port = self.db_port or 0
        else:
            # postgresql / mysql：完整连接五元组
            missing = [
                f for f in ("db_host", "db_user", "db_password", "db_name")
                if not self.config.get(f)
            ]
            if missing:
                raise ValueError(
                    f"required configuration missing for db_type={self.db_type}: "
                    f"{', '.join(missing)}"
                )
            if self.db_type == "postgresql" and not self.db_port:
                self.db_port = 5432
            if self.db_type == "mysql" and not self.db_port:
                self.db_port = 3306

        self.connection = None
        logger.info("DatabasePlugin initialized for %s (connection is lazy)", self.db_type)

    # ------------------------------------------------------------------
    # 连接（惰性；驱动按需导入）
    # ------------------------------------------------------------------

    def _connect(self):
        """获取连接（复用已有）。驱动缺失/数据库不可达 → RuntimeError（工具级失败）。"""
        if self.connection is not None:
            return self.connection
        try:
            if self.db_type == "sqlite":
                import sqlite3

                self.connection = sqlite3.connect(
                    self.db_name, timeout=self.timeout
                )
            elif self.db_type == "postgresql":
                try:
                    import psycopg2
                except ImportError as exc:
                    raise RuntimeError(
                        "postgresql driver 'psycopg2-binary' is not installed "
                        "in the plugin process environment"
                    ) from exc
                self.connection = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    dbname=self.db_name,
                    connect_timeout=self.timeout,
                )
            elif self.db_type == "mysql":
                try:
                    import mysql.connector
                except ImportError as exc:
                    raise RuntimeError(
                        "mysql driver 'mysql-connector-python' is not installed "
                        "in the plugin process environment"
                    ) from exc
                self.connection = mysql.connector.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.db_name,
                    connection_timeout=self.timeout,
                )
            else:  # pragma: no cover - init 已校验
                raise ValueError(f"Unsupported database type: {self.db_type}")
            return self.connection
        except RuntimeError:
            raise
        except Exception as e:
            self.connection = None
            raise RuntimeError(
                f"Failed to connect to {self.db_type} database "
                f"{self.db_host or ''}{self.db_name or ''}: {e}"
            ) from e

    def _require_table(self, table_name: str) -> None:
        if not _valid_identifier(table_name):
            raise ValueError(
                f"Invalid table name: {table_name!r} "
                "(must match [A-Za-z_][A-Za-z0-9_]*)"
            )

    # ------------------------------------------------------------------
    # 工具实现（与 manifest.tools 一一对应）
    # ------------------------------------------------------------------

    async def execute_query(self, query: str, limit: int = 100) -> dict[str, Any]:
        """Execute a SQL query"""
        try:
            connection = self._connect()
            cursor = connection.cursor()

            # 只对无 LIMIT 的 SELECT 追加行数上限，防止意外全表拉取
            normalized = query.lstrip().rstrip(";").lstrip()
            if (
                normalized.upper().startswith("SELECT")
                and "LIMIT" not in normalized.upper()
            ):
                normalized = f"{normalized} LIMIT {int(limit)}"

            cursor.execute(normalized)

            if cursor.description is None:
                connection.commit()
                cursor.close()
                return {
                    "status": "success",
                    "data": {"rows_affected": cursor.rowcount},
                }

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchmany(int(limit))
            results = [
                {col: _jsonify(value) for col, value in zip(columns, row)}
                for row in rows
            ]
            cursor.close()
            return {
                "status": "success",
                "data": results,
                "count": len(results),
                "columns": columns,
            }
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return {"status": "error", "message": f"Query execution error: {e}"}

    async def list_tables(self) -> dict[str, Any]:
        """List all tables in the database"""
        try:
            connection = self._connect()
            cursor = connection.cursor()

            if self.db_type == "sqlite":
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            elif self.db_type == "postgresql":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            elif self.db_type == "mysql":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s ORDER BY table_name",
                    (self.db_name,),
                )
            else:  # pragma: no cover - init 已校验
                return {"status": "error", "message": "Unsupported database type"}

            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return {"status": "success", "data": tables, "count": len(tables)}
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return {"status": "error", "message": f"Failed to list tables: {e}"}

    async def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get table schema"""
        try:
            self._require_table(table_name)
            connection = self._connect()
            cursor = connection.cursor()

            if self.db_type == "sqlite":
                cursor.execute(
                    'SELECT name, type, "notnull", dflt_value FROM '
                    f'pragma_table_info("{table_name}")'
                )
                schema = [
                    {"name": col[0], "type": col[1], "nullable": not col[2]}
                    for col in cursor.fetchall()
                ]
            elif self.db_type == "postgresql":
                cursor.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_name = %s ORDER BY ordinal_position",
                    (table_name,),
                )
                schema = [
                    {"name": col[0], "type": col[1], "nullable": col[2] == "YES"}
                    for col in cursor.fetchall()
                ]
            elif self.db_type == "mysql":
                cursor.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s "
                    "ORDER BY ordinal_position",
                    (self.db_name, table_name),
                )
                schema = [
                    {"name": col[0], "type": col[1], "nullable": col[2] == "YES"}
                    for col in cursor.fetchall()
                ]
            else:  # pragma: no cover - init 已校验
                return {"status": "error", "message": "Unsupported database type"}

            cursor.close()
            return {"status": "success", "data": schema, "count": len(schema)}
        except Exception as e:
            logger.error(f"Failed to get table schema: {e}")
            return {"status": "error", "message": f"Failed to get table schema: {e}"}

    async def export_query_result(
        self, query: str, filename: str, format: str = "csv"
    ) -> dict[str, Any]:
        """Export query result to a file (csv or json)"""
        try:
            result = await self.execute_query(query)
            if result.get("status") != "success" or "columns" not in result:
                return result

            data = result["data"]
            columns = result["columns"]

            if format == "csv":
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
                content = output.getvalue()
                file_path = filename if filename.endswith(".csv") else f"{filename}.csv"
            elif format == "json":
                content = json.dumps(data, indent=2, default=str, ensure_ascii=False)
                file_path = filename if filename.endswith(".json") else f"{filename}.json"
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported format: {format} (supported: csv, json)",
                }

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "success",
                "message": f"Exported to {file_path}",
                "file_path": file_path,
                "rows": len(data),
            }
        except Exception as e:
            logger.error(f"Export error: {e}")
            return {"status": "error", "message": f"Export error: {e}"}

    async def analyze_table(self, table_name: str) -> dict[str, Any]:
        """Analyze table statistics"""
        try:
            self._require_table(table_name)
            connection = self._connect()
            cursor = connection.cursor()

            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]

            if self.db_type == "sqlite":
                cursor.execute(
                    'SELECT COUNT(*) FROM pragma_table_info(?)', (table_name,)
                )
                column_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                table_size = f"{(page_count or 0) * (page_size or 0) / 1024:.1f} KB"
            elif self.db_type == "postgresql":
                cursor.execute(
                    "SELECT pg_size_pretty(pg_total_relation_size(%s))",
                    (table_name,),
                )
                table_size = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = %s",
                    (table_name,),
                )
                column_count = cursor.fetchone()[0]
            else:  # mysql
                cursor.execute(
                    "SELECT ROUND(((data_length + index_length) / 1024 / 1024), 2) "
                    "FROM information_schema.TABLES "
                    "WHERE table_schema = %s AND table_name = %s",
                    (self.db_name, table_name),
                )
                size_result = cursor.fetchone()
                table_size = f"{size_result[0]} MB" if size_result else "Unknown"
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s",
                    (self.db_name, table_name),
                )
                column_count = cursor.fetchone()[0]

            cursor.close()
            return {
                "status": "success",
                "data": {
                    "table_name": table_name,
                    "row_count": row_count,
                    "column_count": column_count,
                    "table_size": table_size,
                },
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {"status": "error", "message": f"Analysis error: {e}"}

    def __del__(self):
        """Close database connection"""
        if getattr(self, "connection", None):
            try:
                self.connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


# ----------------------------------------------------------------------
# stdio MCP server 入口（python -m main）
# ----------------------------------------------------------------------

def _fail_closed(message: str) -> NoReturn:
    """输出可诊断错误并退出（不进入 MCP 循环，握手 fail-closed）。"""
    import time

    sys.stderr.write(f"[{PLUGIN_NAME}] fail-closed: {message}\n")
    sys.stderr.write(
        f"[{PLUGIN_NAME}] configure this plugin via the {CONFIG_ENV_VAR} "
        "environment variable (JSON object; provided by the X-Agent plugin "
        "runtime, e.g. PluginRuntime.start(name, config={...})).\n"
    )
    sys.stderr.flush()
    time.sleep(0.25)
    raise SystemExit(2)


def load_config_from_env() -> dict[str, Any]:
    """从约定环境变量读取 JSON 配置（缺失返回空 dict，由插件自行校验）。"""
    raw = (os.environ.get(CONFIG_ENV_VAR) or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        _fail_closed(f"{CONFIG_ENV_VAR} is not valid JSON: {e}")
    if not isinstance(parsed, dict):
        _fail_closed(
            f"{CONFIG_ENV_VAR} must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def build_server(config: dict[str, Any]) -> Any:
    """构建 FastMCP stdio server（工具 = DatabasePlugin 类方法）。"""
    from mcp.server.fastmcp import FastMCP

    plugin = DatabasePlugin(config)

    mcp = FastMCP(PLUGIN_NAME)

    mcp.tool()(plugin.execute_query)
    mcp.tool()(plugin.list_tables)
    mcp.tool()(plugin.get_table_schema)
    mcp.tool()(plugin.export_query_result)
    mcp.tool()(plugin.analyze_table)

    return mcp


def main() -> None:
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    config = load_config_from_env()

    if not config:
        _fail_closed(
            "required configuration missing entirely (db_type/db_host/db_user/"
            "db_password/db_name for postgresql|mysql; db_name for sqlite); "
            f"db_type defaults to postgresql (supported: {', '.join(SUPPORTED_DB_TYPES)})"
        )

    try:
        server = build_server(config)
    except ValueError as e:
        _fail_closed(str(e))

    server.run()  # stdio 传输


if __name__ == "__main__":
    main()
