#!/usr/bin/env python3
"""MCP 黑板通讯服务 —— ZCode 与 Codex 双向通讯中介。

设计目标
--------
两个 AI agent(ZCode / Codex)在本机各自有会话,但无法直接互调进程:
- ZCode 是 GUI 应用,无 headless CLI 入口,Codex 无法 `zcode exec` 拉起它。
- Codex 有 `codex exec` 非交互入口,可被 ZCode 的 Bash 同步调用。

为让两边**对称地、实时地**互发消息,本 server 作为共享中介:
双方各自把它作为 MCP server 挂载,通过同一组工具读写同一个 SQLite 队列。
谁也不用"调起"对方进程,而是往共享队列 post / 从自己 inbox read。

协议形态:标准 MCP(stdio + JSON-RPC 2.0),手写实现,零外部依赖,
任意 Python 3.8+ 即可运行,无需安装 `mcp` SDK。

提供的工具(MCP tools)
----------------------
- post_message(to, subject, body)         -> 往收件人 inbox 投递一条消息
- read_inbox(since_id, limit)             -> 读取自己的未读/新消息
- claim_task(task_id)                     -> 认领一个任务(置为进行中)
- report_done(task_id, status, summary)   -> 报告任务完成/失败

消息持久化在 SQLite,路径默认 `audit_reports/_comm/blackboard.sqlite`,
可通过环境变量 `BLACKBOARD_DB` 覆盖。

用法(被 MCP client 挂载)
--------------------------
ZCode  .mcp.json:
  "blackboard": { "type":"stdio", "command":"<venv-python>",
                  "args":["<repo>/scripts/mcp_blackboard_server.py"] }

Codex  config.toml:
  [mcp_servers.blackboard]
  command = "<venv-python>"
  args    = ["<repo>/scripts/mcp_blackboard_server.py"]
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 数据库路径:默认放在 audit_reports/_comm/blackboard.sqlite
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = _REPO_ROOT / "audit_reports" / "_comm" / "blackboard.sqlite"
DB_PATH = Path(os.environ.get("BLACKBOARD_DB", str(_DEFAULT_DB)))

# 合法的收件人(也是合法的发送者)
AGENTS = {"zcode", "codex"}

# 单条消息 body 最大长度,防止失控写入
MAX_BODY = 64 * 1024

# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    """每次调用建一个连接(SQLite 文件级锁足够,连接轻量)。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    """建表。幂等。"""
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,          -- uuid
                ts          TEXT NOT NULL,             -- ISO8601 UTC
                sender      TEXT NOT NULL,             -- zcode | codex
                recipient   TEXT NOT NULL,             -- zcode | codex | broadcast
                subject     TEXT NOT NULL,
                body        TEXT NOT NULL,
                read_at     TEXT                       -- NULL=未读
            );
            CREATE INDEX IF NOT EXISTS idx_messages_recipient_ts
                ON messages(recipient, ts);

            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,          -- 形如 P0-02 或 uuid
                ts          TEXT NOT NULL,
                created_by  TEXT NOT NULL,
                assigned_to TEXT,                      -- 认领方
                status      TEXT NOT NULL DEFAULT 'open',
                            -- open | in_progress | done | failed | blocked
                summary     TEXT,
                detail      TEXT,
                updated_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            """
        )


# ---------------------------------------------------------------------------
# 工具实现(被 JSON-RPC 层调用)
# ---------------------------------------------------------------------------


def tool_post_message(
    sender: str, recipient: str, subject: str, body: str
) -> dict[str, Any]:
    if sender not in AGENTS:
        return {"error": f"invalid sender: {sender}"}
    if recipient not in AGENTS and recipient != "broadcast":
        return {"error": f"invalid recipient: {recipient}"}
    if not subject.strip():
        return {"error": "subject must not be empty"}
    if len(body) > MAX_BODY:
        return {"error": f"body too large (>{MAX_BODY} bytes)"}

    mid = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO messages(id,ts,sender,recipient,subject,body) "
            "VALUES(?,?,?,?,?,?)",
            (mid, ts, sender, recipient, subject, body),
        )
    return {"id": mid, "ts": ts, "status": "posted"}


def tool_read_inbox(agent: str, since_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    if agent not in AGENTS:
        return {"error": f"invalid agent: {agent}"}
    limit = max(1, min(int(limit), 200))
    with _lock, _connect() as conn:
        if since_id:
            # 取 since_id 之后的所有消息(按时间序)
            row = conn.execute(
                "SELECT ts FROM messages WHERE id=?", (since_id,)
            ).fetchone()
            if not row:
                return {"error": f"unknown since_id: {since_id}"}
            since_ts = row["ts"]
            rows = conn.execute(
                "SELECT * FROM messages WHERE recipient IN (?, 'broadcast') "
                "AND ts > ? ORDER BY ts ASC LIMIT ?",
                (agent, since_ts, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE recipient IN (?, 'broadcast') "
                "AND read_at IS NULL ORDER BY ts ASC LIMIT ?",
                (agent, limit),
            ).fetchall()
            # 标记为已读
            for r in rows:
                conn.execute(
                    "UPDATE messages SET read_at=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), r["id"]),
                )
    return {
        "count": len(rows),
        "messages": [dict(r) for r in rows],
    }


def tool_claim_task(task_id: str, claimed_by: str) -> dict[str, Any]:
    if claimed_by not in AGENTS:
        return {"error": f"invalid agent: {claimed_by}"}
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return {"error": f"unknown task: {task_id}"}
        if row["status"] not in ("open", "blocked"):
            return {
                "error": f"task not claimable (status={row['status']}, "
                f"assigned_to={row['assigned_to']})"
            }
        conn.execute(
            "UPDATE tasks SET assigned_to=?, status='in_progress', updated_at=? "
            "WHERE id=?",
            (claimed_by, now, task_id),
        )
    return {"task_id": task_id, "status": "in_progress", "claimed_by": claimed_by}


def tool_report_done(
    task_id: str, status: str, summary: str, by: str
) -> dict[str, Any]:
    if by not in AGENTS:
        return {"error": f"invalid agent: {by}"}
    if status not in ("done", "failed", "blocked"):
        return {"error": f"invalid status: {status} (done|failed|blocked)"}
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return {"error": f"unknown task: {task_id}"}
        conn.execute(
            "UPDATE tasks SET status=?, summary=?, updated_at=? WHERE id=?",
            (status, summary, now, task_id),
        )
    return {"task_id": task_id, "status": status, "summary": summary}

def tool_create_task(
    task_id: str, created_by: str, summary: str, detail: str = ""
) -> dict[str, Any]:
    """创建一个任务到任务板(供 post_message 之外的显式任务跟踪)。"""
    if created_by not in AGENTS:
        return {"error": f"invalid agent: {created_by}"}
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO tasks(id,ts,created_by,status,summary,detail,updated_at) "
                "VALUES(?,?,?,'open',?,?,?)",
                (task_id, now, created_by, summary, detail, now),
            )
        except sqlite3.IntegrityError:
            return {"error": f"task already exists: {task_id}"}
    return {"task_id": task_id, "status": "open"}

def tool_list_tasks(status: str | None = None) -> dict[str, Any]:
    with _lock, _connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC"
            ).fetchall()
    return {"count": len(rows), "tasks": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# MCP 工具声明(JSON-RPC schema)
# ---------------------------------------------------------------------------

TOOLS_SPEC: list[dict[str, Any]] = [
    {
        "name": "post_message",
        "description": (
            "往另一个 agent 的收件箱投递一条消息。用于 ZCode 与 Codex 之间的"
            "双向通讯。recipient 可为 'zcode'/'codex'/'broadcast'。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "enum": ["zcode", "codex"]},
                "recipient": {
                    "type": "string",
                    "enum": ["zcode", "codex", "broadcast"],
                },
                "subject": {"type": "string", "description": "简短主题"},
                "body": {"type": "string", "description": "消息正文(markdown 可)"},
            },
            "required": ["sender", "recipient", "subject", "body"],
        },
    },
    {
        "name": "read_inbox",
        "description": (
            "读取自己的收件箱。不带 since_id 时返回所有未读消息并标记已读;"
            "带 since_id 时返回该消息之后的所有消息(不改变已读状态)。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "enum": ["zcode", "codex"]},
                "since_id": {"type": "string", "description": "从哪条消息之后开始读"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["agent"],
        },
    },
    {
        "name": "claim_task",
        "description": "认领任务板上的一个任务,状态置为 in_progress。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "claimed_by": {"type": "string", "enum": ["zcode", "codex"]},
            },
            "required": ["task_id", "claimed_by"],
        },
    },
    {
        "name": "report_done",
        "description": "报告任务完成/失败/阻塞。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "status": {"type": "string", "enum": ["done", "failed", "blocked"]},
                "summary": {"type": "string"},
                "by": {"type": "string", "enum": ["zcode", "codex"]},
            },
            "required": ["task_id", "status", "summary", "by"],
        },
    },
    {
        "name": "create_task",
        "description": "在共享任务板上创建一个任务。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "如 P0-02 或自定义 id"},
                "created_by": {"type": "string", "enum": ["zcode", "codex"]},
                "summary": {"type": "string"},
                "detail": {"type": "string"},
            },
            "required": ["task_id", "created_by", "summary"],
        },
    },
    {
        "name": "list_tasks",
        "description": "列出任务板上的任务,可按状态过滤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done", "failed", "blocked"],
                },
            },
        },
    },
]


def _dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """根据工具名分派到实现,返回结果 dict。"""
    try:
        if name == "post_message":
            return tool_post_message(**args)
        if name == "read_inbox":
            return tool_read_inbox(**args)
        if name == "claim_task":
            return tool_claim_task(**args)
        if name == "report_done":
            return tool_report_done(**args)
        if name == "create_task":
            return tool_create_task(**args)
        if name == "list_tasks":
            return tool_list_tasks(**args)
        return {"error": f"unknown tool: {name}"}
    except TypeError as e:
        # 参数不匹配
        return {"error": f"bad arguments: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 / MCP stdio 主循环(手写,零依赖)
# ---------------------------------------------------------------------------


def _send(msg: dict[str, Any]) -> None:
    """向 stdout 写一行 JSON-RPC 消息。"""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str, data: Any = None) -> None:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _send({"jsonrpc": "2.0", "id": req_id, "error": err})


def serve() -> None:
    init_db()
    # stderr 留给诊断日志,绝不污染 stdout(JSON-RPC 通道)
    sys.stderr.write(
        f"[blackboard] serving, db={DB_PATH}\n"
    )
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            _error(None, -32700, "parse error")
            continue

        req_id = req.get("id")
        method = req.get("method", "")

        # --- 通知(无 id)---
        if method == "notifications/initialized":
            continue

        # --- 初始化握手 ---
        if method == "initialize":
            _result(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "xagent-blackboard",
                        "version": "1.0.0",
                    },
                },
            )
            continue

        if method == "tools/list":
            _result(req_id, {"tools": TOOLS_SPEC})
            continue

        if method == "tools/call":
            params = req.get("params", {})
            tname = params.get("name")
            targs = params.get("arguments", {}) or {}
            out = _dispatch_tool(tname, targs)
            if isinstance(out, dict) and "error" in out:
                # 工具级错误:用 MCP 的 isError 标记,仍以 result 返回
                _result(
                    req_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(out, ensure_ascii=False),
                            }
                        ],
                        "isError": True,
                    },
                )
            else:
                _result(
                    req_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(out, ensure_ascii=False, indent=2),
                            }
                        ],
                    },
                )
            continue

        _error(req_id, -32601, f"method not found: {method}")


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        sys.exit(0)
