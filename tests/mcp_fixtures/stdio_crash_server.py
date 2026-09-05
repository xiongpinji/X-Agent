#!/usr/bin/env python3
"""完成 initialize + tools/list 应答后立即退出的 stdio 假 server。

验证：握手成功后插件进程自行退出 → 会话判死（dead）→ 后续 tools/call
fail-closed 且错误可诊断，而不是挂起或伪造成功。
"""

import json
import sys

TOOLS = [
    {
        "name": "boom",
        "description": "Server crashes after handshake",
        "inputSchema": {"type": "object", "properties": {}},
    }
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


shutting_down = False
while not shutting_down:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if "id" not in msg or "method" not in msg:
        continue
    method, msg_id = msg["method"], msg["id"]
    if method == "initialize":
        params = msg.get("params") or {}
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "crash-fake-plugin", "version": "0.0.1"},
            },
        })
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
        shutting_down = True  # 应答 tools/list 后立即退出
    else:
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": "Method not found"},
        })

sys.exit(0)
