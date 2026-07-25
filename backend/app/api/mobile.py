"""P2-08: 移动端 Agent 触发/监控 API.

提供移动端远程触发 Agent 执行、实时状态监控、推送通知等能力:
- POST /api/v1/mobile/trigger — 远程触发 Agent 执行
- GET  /api/v1/mobile/runs — 列出移动端触发的 runs
- GET  /api/v1/mobile/runs/{run_id}/status — 查询 run 状态
- POST /api/v1/mobile/runs/{run_id}/cancel — 取消执行
- WS   /api/v1/mobile/ws — WebSocket 实时状态推送
- POST /api/v1/mobile/push/register — 注册推送 token
- DELETE /api/v1/mobile/push/unregister — 注销推送 token
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.app.core.contracts import RunContext
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mobile", tags=["mobile"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────


class TriggerRequest(BaseModel):
    """移动端触发 Agent 执行请求."""

    task: str = Field(..., min_length=1, max_length=4096, description="任务描述")
    agent_id: str = Field(default="default", description="Agent ID")
    priority: str = Field(default="normal", description="优先级: low/normal/high/urgent")
    timeout_seconds: int = Field(default=300, ge=10, le=3600, description="超时时间")
    notify_on_complete: bool = Field(default=True, description="完成后推送通知")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class TriggerResponse(BaseModel):
    """触发响应."""

    run_id: str
    trace_id: str
    status: str
    created_at: str
    estimated_duration_seconds: int = 60
    ws_url: str = ""


class RunStatusResponse(BaseModel):
    """Run 状态响应."""

    run_id: str
    trace_id: str
    status: str  # pending | running | completed | failed | cancelled
    progress_percent: float = 0.0
    current_step: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result_summary: str = ""
    error: str | None = None
    iterations: int = 0
    tool_calls_count: int = 0


class MobileRunRecord(BaseModel):
    """移动端 run 记录."""

    run_id: str
    trace_id: str
    task: str
    agent_id: str
    priority: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    notify_on_complete: bool = True
    device_id: str = ""


class PushRegisterRequest(BaseModel):
    """注册推送 token."""

    device_id: str = Field(..., min_length=1)
    platform: str = Field(default="ios", description="ios | android | harmony")
    push_token: str = Field(..., min_length=1, description="APNs/FCM token")
    topics: list[str] = Field(default_factory=lambda: ["agent_complete", "agent_error"])


class PushRegisterResponse(BaseModel):
    device_id: str
    registered: bool
    topics: list[str]


# ─── 内存状态管理 ─────────────────────────────────────────────────────────────


class MobileRunManager:
    """移动端 run 管理器 (进程内)."""

    def __init__(self):
        self._runs: dict[str, MobileRunRecord] = {}
        self._push_tokens: dict[str, dict] = {}  # device_id -> {platform, token, topics}
        self._ws_clients: dict[str, list[WebSocket]] = defaultdict(list)  # run_id -> [ws]
        self._global_ws: list[WebSocket] = []  # 全局监听

    def create_run(self, req: TriggerRequest, principal: Principal) -> MobileRunRecord:
        run_id = f"mob-{uuid.uuid4().hex[:12]}"
        trace_id = str(uuid.uuid4())
        record = MobileRunRecord(
            run_id=run_id,
            trace_id=trace_id,
            task=req.task,
            agent_id=req.agent_id,
            priority=req.priority,
            status="pending",
            created_at=datetime.now(UTC).isoformat(),
            notify_on_complete=req.notify_on_complete,
            device_id=req.metadata.get("device_id", ""),
        )
        self._runs[run_id] = record
        return record

    def get_run(self, run_id: str) -> MobileRunRecord | None:
        return self._runs.get(run_id)

    def list_runs(self, device_id: str = "", limit: int = 20) -> list[MobileRunRecord]:
        runs = list(self._runs.values())
        if device_id:
            runs = [r for r in runs if r.device_id == device_id]
        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs[:limit]

    def update_status(self, run_id: str, status: str, **kwargs) -> MobileRunRecord | None:
        record = self._runs.get(run_id)
        if record:
            record.status = status
            for k, v in kwargs.items():
                if hasattr(record, k):
                    setattr(record, k, v)
        return record

    def register_push(self, req: PushRegisterRequest) -> None:
        self._push_tokens[req.device_id] = {
            "platform": req.platform,
            "token": req.push_token,
            "topics": req.topics,
            "registered_at": datetime.now(UTC).isoformat(),
        }

    def unregister_push(self, device_id: str) -> bool:
        return self._push_tokens.pop(device_id, None) is not None

    async def broadcast_status(self, run_id: str, event: dict) -> None:
        """向订阅该 run 的 WebSocket 客户端广播状态."""
        message = json.dumps(event, ensure_ascii=False, default=str)
        # 发送给订阅该 run 的客户端
        dead = []
        for ws in self._ws_clients.get(run_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients[run_id].remove(ws)
        # 发送给全局监听客户端
        dead_global = []
        for ws in self._global_ws:
            try:
                await ws.send_text(message)
            except Exception:
                dead_global.append(ws)
        for ws in dead_global:
            self._global_ws.remove(ws)

    def add_ws_client(self, ws: WebSocket, run_id: str | None = None) -> None:
        if run_id:
            self._ws_clients[run_id].append(ws)
        else:
            self._global_ws.append(ws)

    def remove_ws_client(self, ws: WebSocket, run_id: str | None = None) -> None:
        if run_id and ws in self._ws_clients.get(run_id, []):
            self._ws_clients[run_id].remove(ws)
        elif ws in self._global_ws:
            self._global_ws.remove(ws)


# 单例
_mobile_manager = MobileRunManager()


def get_mobile_manager() -> MobileRunManager:
    return _mobile_manager


# ─── REST 端点 ────────────────────────────────────────────────────────────────


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_agent(req: TriggerRequest, principal: PrincipalDependency):
    """远程触发 Agent 执行.

    移动端通过此接口提交任务, 返回 run_id 用于后续状态查询和 WebSocket 订阅。
    """
    manager = get_mobile_manager()
    record = manager.create_run(req, principal)

    # 异步启动 Agent 执行 (fire-and-forget)
    asyncio.create_task(_execute_mobile_run(record, principal))

    return TriggerResponse(
        run_id=record.run_id,
        trace_id=record.trace_id,
        status="pending",
        created_at=record.created_at,
        estimated_duration_seconds=60,
        ws_url=f"/api/v1/mobile/ws?run_id={record.run_id}",
    )


@router.get("/runs", response_model=list[MobileRunRecord])
async def list_mobile_runs(
    device_id: str = Query("", description="按设备过滤"),
    limit: int = Query(20, ge=1, le=100),
    principal: PrincipalDependency = None,
):
    """列出移动端触发的 runs."""
    manager = get_mobile_manager()
    return manager.list_runs(device_id=device_id, limit=limit)


@router.get("/runs/{run_id}/status", response_model=RunStatusResponse)
async def get_mobile_run_status(run_id: str, principal: PrincipalDependency = None):
    """查询 run 实时状态."""
    manager = get_mobile_manager()
    record = manager.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return RunStatusResponse(
        run_id=record.run_id,
        trace_id=record.trace_id,
        status=record.status,
        progress_percent=_estimate_progress(record),
        current_step=_current_step_desc(record),
        started_at=record.started_at,
        completed_at=record.completed_at,
        result_summary="" if record.status != "completed" else "Task completed",
        error=None,
        iterations=0,
        tool_calls_count=0,
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_mobile_run(run_id: str, principal: PrincipalDependency = None):
    """取消正在执行的 run."""
    manager = get_mobile_manager()
    record = manager.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if record.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Run already in terminal state: {record.status}")

    manager.update_status(run_id, "cancelled", completed_at=datetime.now(UTC).isoformat())
    await manager.broadcast_status(run_id, {
        "event": "status_changed",
        "run_id": run_id,
        "status": "cancelled",
        "timestamp": datetime.now(UTC).isoformat(),
    })
    return {"run_id": run_id, "status": "cancelled"}


# ─── 推送注册 ─────────────────────────────────────────────────────────────────


@router.post("/push/register", response_model=PushRegisterResponse)
async def register_push(req: PushRegisterRequest, principal: PrincipalDependency = None):
    """注册移动端推送 token (APNs/FCM)."""
    manager = get_mobile_manager()
    manager.register_push(req)
    return PushRegisterResponse(
        device_id=req.device_id,
        registered=True,
        topics=req.topics,
    )


@router.delete("/push/unregister")
async def unregister_push(device_id: str = Query(...), principal: PrincipalDependency = None):
    """注销推送 token."""
    manager = get_mobile_manager()
    removed = manager.unregister_push(device_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not registered")
    return {"device_id": device_id, "unregistered": True}


# ─── WebSocket 实时推送 ───────────────────────────────────────────────────────


@router.websocket("/ws")
async def mobile_websocket(websocket: WebSocket, run_id: str | None = Query(None)):
    """WebSocket 实时状态推送.

    客户端连接后可实时接收:
    - status_changed: run 状态变更
    - progress: 进度更新
    - tool_call: 工具调用事件
    - output: Agent 输出片段
    - heartbeat: 心跳保活

    参数:
    - run_id: 可选, 订阅特定 run; 不传则接收所有 run 事件
    """
    await websocket.accept()
    manager = get_mobile_manager()
    manager.add_ws_client(websocket, run_id)

    try:
        # 发送连接确认
        await websocket.send_text(json.dumps({
            "event": "connected",
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }))

        # 保持连接, 接收客户端消息 (ping/subscribe)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "event": "pong",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }))
                elif msg.get("type") == "subscribe" and msg.get("run_id"):
                    # 动态订阅新 run
                    manager.add_ws_client(websocket, msg["run_id"])
                    await websocket.send_text(json.dumps({
                        "event": "subscribed",
                        "run_id": msg["run_id"],
                    }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "message": "Invalid JSON",
                }))
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove_ws_client(websocket, run_id)


# ─── 内部: 异步执行 ──────────────────────────────────────────────────────────


async def _execute_mobile_run(record: MobileRunRecord, principal: Principal) -> None:
    """异步执行移动端触发的 Agent run."""
    manager = get_mobile_manager()
    run_id = record.run_id

    try:
        # 更新状态为 running
        manager.update_status(run_id, "running", started_at=datetime.now(UTC).isoformat())
        await manager.broadcast_status(run_id, {
            "event": "status_changed",
            "run_id": run_id,
            "status": "running",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # 构建 RunContext
        context = RunContext(
            trace_id=record.trace_id,
            tenant_id=getattr(principal, "tenant_id", "default"),
            user_id=getattr(principal, "user_id", "mobile-user"),
        )

        # 调用 AgentLoop 执行
        from backend.app.core.agent import AgentLoop
        agent = AgentLoop()

        # 广播进度
        await manager.broadcast_status(run_id, {
            "event": "progress",
            "run_id": run_id,
            "progress_percent": 10.0,
            "current_step": "Agent started",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        result = await agent.run(task=record.task, context=context)

        # 完成
        manager.update_status(run_id, "completed", completed_at=datetime.now(UTC).isoformat())
        await manager.broadcast_status(run_id, {
            "event": "status_changed",
            "run_id": run_id,
            "status": "completed",
            "result_summary": str(getattr(result, "answer", ""))[:200],
            "timestamp": datetime.now(UTC).isoformat(),
        })

    except asyncio.CancelledError:
        manager.update_status(run_id, "cancelled", completed_at=datetime.now(UTC).isoformat())
    except Exception as e:
        logger.error("Mobile run %s failed: %s", run_id, e, exc_info=True)
        manager.update_status(run_id, "failed", completed_at=datetime.now(UTC).isoformat())
        await manager.broadcast_status(run_id, {
            "event": "status_changed",
            "run_id": run_id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(UTC).isoformat(),
        })


def _estimate_progress(record: MobileRunRecord) -> float:
    """估算进度百分比."""
    if record.status == "completed":
        return 100.0
    if record.status == "failed" or record.status == "cancelled":
        return 0.0
    if record.status == "pending":
        return 0.0
    if record.status == "running":
        # 简单时间估算
        if record.started_at:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(record.started_at)).total_seconds()
            return min(90.0, elapsed / 3.0)  # 假设 300s 完成
    return 0.0


def _current_step_desc(record: MobileRunRecord) -> str:
    """当前步骤描述."""
    status_map = {
        "pending": "Waiting to start",
        "running": "Agent executing",
        "completed": "Done",
        "failed": "Failed",
        "cancelled": "Cancelled",
    }
    return status_map.get(record.status, record.status)
