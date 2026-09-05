#!/usr/bin/env python3
"""完成握手但对 tools/call 永不回包的 stdio 假 server。

验证 per-request 超时：call_tool 超时后会话判死（dead），
后续调用立即 fail-closed，且错误信息可诊断。
"""

import json
import sys

TOOLS = [
    {
        "name": "hang",
        "description": "Never answers tools/call",
        "inputSchema": {"type": "object", "properties": {}},
    }
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


while True:
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
                "serverInfo": {"name": "hang-fake-plugin", "version": "0.0.1"},
            },
        })
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        # 永不回包：客户端必须按请求超时判定失败
        pass
    else:
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": "Method not found"},
        })

sys.exit(0)
