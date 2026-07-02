#!/usr/bin/env python3
"""send_to_zcode.py —— Codex 侧向 ZCode 发消息的入口(B 方案 Codex→ZCode 方向)。

Codex 在自己的会话里用 Bash 调用本脚本,把消息写进共享 SQLite,
ZCode 下一轮读取时即可收到。消息同时落一份到文件收件箱作兜底。

用法(Codex 在会话内执行):
    python scripts/send_to_zcode.py --subject "P0-02 已修复" --body "改动见 sessions.py 第 45 行..."
    python scripts/send_to_zcode.py --subject "疑问" --body "sessions.py 的 principal 怎么取?" --task-id P0-02 --status blocked

也可用于报告任务状态:
    python scripts/send_to_zcode.py --task-id P0-02 --status done --summary "6 端点已加授权,测试通过"

ZCode 侧读取:scripts/read_codex_messages.py 或直接查 blackboard.sqlite。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "audit_reports" / "_comm" / "blackboard.sqlite"
INBOX_ZCODE = REPO_ROOT / "audit_reports" / "_comm" / "inbox_zcode"


def main() -> int:
    ap = argparse.ArgumentParser(description="Codex 向 ZCode 发消息 / 报告任务状态")
    ap.add_argument("--subject", required=True, help="消息主题")
    ap.add_argument("--body", default="", help="消息正文(markdown 可)")
    ap.add_argument("--task-id", default=None, help="关联的任务 ID(如 P0-02)")
    ap.add_argument("--status", default=None,
                    help="任务状态报告:done/failed/blocked(可选,报告状态时用)")
    args = ap.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_ZCODE.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    # 确保表存在(幂等,与 mcp_blackboard_server.init_db 一致)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, ts TEXT NOT NULL, sender TEXT NOT NULL,
            recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
            read_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, ts TEXT NOT NULL, created_by TEXT NOT NULL,
            assigned_to TEXT, status TEXT NOT NULL DEFAULT 'open',
            summary TEXT, detail TEXT, updated_at TEXT
        );
    """)

    mid = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    full_body = args.body
    if args.task_id:
        full_body = f"[task: {args.task_id}]\n{args.body}"

    conn.execute(
        "INSERT INTO messages(id,ts,sender,recipient,subject,body) VALUES(?,?,?,?,?,?)",
        (mid, ts, "codex", "zcode", args.subject, full_body),
    )

    # 报告任务状态(可选)
    task_result = None
    if args.task_id and args.status:
        now = ts
        row = conn.execute("SELECT id FROM tasks WHERE id=?", (args.task_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE tasks SET status=?, summary=?, updated_at=? WHERE id=?",
                (args.status, args.subject, now, args.task_id),
            )
            task_result = {"task_id": args.task_id, "status": args.status}
        else:
            task_result = {"error": f"task {args.task_id} not found on board"}

    conn.commit()
    conn.close()

    # 文件兜底:同时写一份到 inbox_zcode/
    safe_subj = "".join(c if c.isalnum() or c in "-_" else "-" for c in args.subject)[:40]
    fname = f"{ts.replace(':','-').replace('.','')[:19]}_{safe_subj}.md"
    fpath = INBOX_ZCODE / fname
    front = "---\n"
    front += f"from: codex\nto: zcode\nts: {ts}\n"
    if args.task_id:
        front += f"task_id: {args.task_id}\n"
    if args.status:
        front += f"status: {args.status}\n"
    front += "---\n\n"
    fpath.write_text(front + f"# {args.subject}\n\n{args.body}\n", encoding="utf-8")

    result = {"message_id": mid, "ts": ts, "written_to": str(fpath), "task": task_result}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
