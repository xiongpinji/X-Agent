#!/usr/bin/env python3
"""read_codex_messages.py —— ZCode 侧读取 Codex 发来的消息(B 方案 Codex→ZCode 方向)。

ZCode 在自己的会话里用 Bash 调用本脚本,从共享 SQLite 读 Codex 给我的消息。
默认读未读消息并标记已读;加 --all 可看全部历史。

用法:
    python scripts/read_codex_messages.py                # 读未读
    python scripts/read_codex_messages.py --all          # 读全部历史
    python scripts/read_codex_messages.py --watch 30     # 每 30 秒轮询一次,有新消息打印
    python scripts/read_codex_messages.py --json         # 输出 JSON 格式
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "audit_reports" / "_comm" / "blackboard.sqlite"


def fetch(all_msgs: bool, mark_read: bool) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")

    if all_msgs:
        rows = conn.execute(
            "SELECT * FROM messages WHERE recipient='zcode' "
            "ORDER BY ts ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE recipient='zcode' AND read_at IS NULL "
            "ORDER BY ts ASC"
        ).fetchall()
        if mark_read and rows:
            now = datetime.now(timezone.utc).isoformat()
            for r in rows:
                conn.execute(
                    "UPDATE messages SET read_at=? WHERE id=?", (now, r["id"])
                )
            conn.commit()
    conn.close()
    return [dict(r) for r in rows]


def render(msgs: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
        return
    if not msgs:
        print("(无消息)")
        return
    for m in msgs:
        unread = "[未读]" if not m.get("read_at") else "[已读]"
        print(f"\n=== {m['ts']}  from:{m['sender']}  {unread} ===")
        print(f"主题: {m['subject']}")
        print(f"id:   {m['id']}")
        print("-" * 60)
        print(m["body"])
        print("-" * 60)
    print(f"\n共 {len(msgs)} 条消息")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="读全部历史(不只未读)")
    ap.add_argument("--no-mark-read", action="store_true",
                    help="不要标记为已读(默认会标记)")
    ap.add_argument("--json", action="store_true", help="输出 JSON 格式")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="轮询模式:每 N 秒检查一次新消息")
    args = ap.parse_args()

    if args.watch > 0:
        seen = set()
        try:
            while True:
                msgs = fetch(all_msgs=False, mark_read=not args.no_mark_read)
                new = [m for m in msgs if m["id"] not in seen]
                if new:
                    render(new, args.json)
                    for m in new:
                        seen.add(m["id"])
                time.sleep(args.watch)
        except KeyboardInterrupt:
            return 0
    else:
        msgs = fetch(all_msgs=args.all, mark_read=not args.no_mark_read)
        render(msgs, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
