#!/usr/bin/env python3
"""原始 JSON-RPC stdio 假 MCP server —— 把收到的全部消息记录到 JSON 文件。

不依赖 mcp SDK：手工解析/回包，用于断言客户端（官方 SDK 经
``backend.app.core.mcp_plugin_adapter.MCPPluginStdioSession``）发出的
真实线上握手消息序列：

1. ``initialize`` 请求（protocolVersion / capabilities / clientInfo）
2. ``notifications/initialized`` 通知（无 id，不回包）
3. ``tools/list`` 请求
4. ``tools/call`` 请求

用法：``python stdio_recording_server.py <record_path.json>``
（客户端经 MCP stdio 关停序列关闭 stdin 后，本进程写出记录并退出）
"""

import json
import sys

TOOLS = [
    {
        "name": "echo",
        "description": "Echo text back to the caller",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
]


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def handle_request(msg: dict) -> None:
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        params = msg.get("params") or {}
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                # 回显客户端请求的协议版本（受支持版本集合内的合法应答）
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "recording-fake-plugin", "version": "0.0.1"},
            },
        })
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in {"echo"}:
            # 未声明的工具：返回工具级错误（isError=True），会话保持可用
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                    "isError": True,
                },
            })
            return
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"echo:{name}:{json.dumps(arguments, sort_keys=True)}",
                    }
                ],
                "isError": False,
            },
        })
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
    else:
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })


def main() -> None:
    record_path = sys.argv[1] if len(sys.argv) > 1 else None
    received: list[dict] = []
    while True:
        line = sys.stdin.readline()
        if not line:  # stdin 关闭（MCP stdio 关停序列）
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        received.append(msg)
        if "id" in msg and "method" in msg:
            handle_request(msg)
        # 通知（notifications/initialized 等）只记录，不回包
    if record_path:
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(received, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
