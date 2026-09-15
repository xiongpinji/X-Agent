"""通知渠道配置 API。

为什么不复用 api/notifications.py
=================================
``api/notifications.py`` 是 **WebSocket 实时推送**模块(``/ws``、``/status``、
Web Push 订阅、``/broadcast/test``), 与「渠道配置 CRUD」是两回事。复用它会把
WS + Web Push 一并带进 ``main.py`` 白名单 —— 那是另一个功能的挂载决策, 不该
被这次顺带决定。

范围
====
1. 配置 CRUD + 手动投递测试 (``/{config_id}/test``)。
2. **事件分发的两个出口** (2026-09-15 接线):

   - ``GET /deliveries`` —— 查投递记录。为什么必须有它, 见
     ``core/notification_dispatch_store`` 的 docstring: 环境里没配真实邮件通道时
     分发只写一行日志, 界面与 API 上都毫无痕迹。
   - ``POST /daily-summary/run`` —— 手动触发 ``daily_summary``。**摘要的计算与投递
     都不在本模块实现**, 而是复用 ``core/daily_summary``: 定时任务走的是同一条路径
     (2026-09-15 接线, 见 ``main.py`` 的调度器常驻块)。两边各写一份聚合必然分叉,
     而分叉的表现是「同一件事两个答案」。这个端点只是「要回执的调用方」。

   真正的事件写入路径 hook (反馈创建 / 解决) 在 ``api/feedback.py``, 用
   ``BackgroundTasks`` 执行 —— 见 ``core/notification_dispatch``。

路由顺序
========
``/{config_id}`` 族的**声明**在表上早于 ``/{config_id}/test`` 之外的具名路由之前
是安全的(本前缀下没有任何单段具名兄弟路由, 遮蔽结构上不可能发生)。仍然把
``/{config_id}`` 放在最后一个声明, 与 ``api/feedback.py`` 的教训保持一致。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

# 摘要的聚合与投递都在 ``core/daily_summary`` —— 定时任务走同一条路径。本模块
# 不再自己数一遍 (那正是分叉的来源), 只负责鉴权 + 把回执渲染成响应模型。
from backend.app.core.daily_summary import run_for_tenant
from backend.app.core.notification_config_store import (
    NotificationConfigRecord,
    NotificationTrigger,
    get_notification_config_store,
)
from backend.app.core.notification_dispatch_store import (
    DeliveryRecord,
    get_notification_dispatch_store,
)
from backend.app.core.notifications import (
    ConsoleNotificationProvider,
    NoopNotificationProvider,
    NotificationMessage,
    WebhookNotificationProvider,
    get_notification_provider,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger("xagent.notification_configs")

router = APIRouter(prefix="/api/v1/notification-configs", tags=["notification-configs"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------

class NotificationConfigCreateRequest(BaseModel):
    """创建通知渠道配置。"""

    type: Literal["email", "slack"]
    target: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="email 时为收件邮箱; slack 时为 Incoming Webhook URL",
    )
    triggers: list[NotificationTrigger] = Field(default_factory=list)
    enabled: bool = True


class NotificationConfigUpdateRequest(BaseModel):
    """局部更新: 只改显式给出的字段。"""

    type: Literal["email", "slack"] | None = None
    target: str | None = Field(None, min_length=1, max_length=2048)
    triggers: list[NotificationTrigger] | None = None
    enabled: bool | None = None


class NotificationConfigResponse(BaseModel):
    """对前端的渠道配置。

    刻意不含 ``tenant_id`` —— 与 ``FeedbackResponse`` 同口径, 不把租户标识
    暴露给客户端。
    """

    id: str
    type: str
    enabled: bool
    target: str
    triggers: list[str]
    created_at: datetime
    updated_at: datetime


class NotificationTestResponse(BaseModel):
    success: bool
    message: str


class DeliveryRecordResponse(BaseModel):
    """对前端的单条投递记录。

    与 ``NotificationConfigResponse`` 同口径, 刻意不含 ``tenant_id``。
    ``target_hint`` 是**已脱敏**的投递目标 (明文邮箱 / Webhook URL 不出后端)。
    """

    id: str
    trigger: str
    config_id: str
    channel: str
    provider: str
    target_hint: str
    delivered: bool
    detail: str
    subject: str
    feedback_id: str | None = None
    created_at: datetime


class DailySummaryResponse(BaseModel):
    """一次手动 daily_summary 触发的完整回执。

    ``delivered_count < active_channels`` 就是「配了渠道但没真发出去」的可观测信号
    —— 每条记录里的 ``detail`` 会说明原因。
    """

    trigger: str = "daily_summary"
    subject: str
    active_channels: int
    delivered_count: int
    records: list[DeliveryRecordResponse]


def _to_response(record: NotificationConfigRecord) -> NotificationConfigResponse:
    return NotificationConfigResponse(
        id=record.id,
        type=record.type,
        enabled=record.enabled,
        target=record.target,
        triggers=list(record.triggers),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_delivery_response(record: DeliveryRecord) -> DeliveryRecordResponse:
    return DeliveryRecordResponse(
        id=record.id,
        trigger=record.trigger,
        config_id=record.config_id,
        channel=record.channel,
        provider=record.provider,
        target_hint=record.target_hint,
        delivered=record.delivered,
        detail=record.detail,
        subject=record.subject,
        feedback_id=record.feedback_id,
        created_at=record.created_at,
    )


def _get_or_404(config_id: str, principal: Principal) -> NotificationConfigRecord:
    """取配置并强制 tenant 收敛: 跨租户一律 404, 避免泄露资源存在性。

    与 ``api/feedback.py::_get_tenant_feedback_or_404`` 同口径。
    """
    record = get_notification_config_store().get(config_id)
    if record is None or record.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification config not found",
        )
    return record


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[NotificationConfigResponse])
async def list_notification_configs(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[NotificationConfigResponse]:
    """当前租户的通知渠道配置列表。"""
    enforce_scope(principal, "notifications:read")
    store = get_notification_config_store()
    return [_to_response(r) for r in store.list_for_tenant(principal.tenant_id)]


@router.post(
    "/",
    response_model=NotificationConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_config(
    request: NotificationConfigCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> NotificationConfigResponse:
    """新建通知渠道配置。``trigger`` 里的非法枚举由模型层直接 422 拒绝。"""
    enforce_scope(principal, "notifications:write")
    record = NotificationConfigRecord(
        type=request.type,
        target=request.target,
        triggers=list(request.triggers),
        enabled=request.enabled,
        tenant_id=principal.tenant_id,
    )
    return _to_response(get_notification_config_store().add(record))


# ⚠️ 声明顺序: 具名尾段路由放在 /{config_id} 族之前
@router.post("/{config_id}/test", response_model=NotificationTestResponse)
async def test_notification_config(
    config_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> NotificationTestResponse:
    """真实投递测试 —— 没真的投出去, 就不许报成功。

    ⚠️ 这里的陷阱: ``ConsoleNotificationProvider.is_configured()`` 返回 True、
    ``send()`` 返回 ``success=True``, 但它只写一行日志, 什么都不发。所以
    **不能**用 ``is_configured()`` 当门槛 —— 那会在未配 SMTP 的环境里得到一张
    完全正常的假绿回执。这里改为对 provider 做类型判别。
    """
    enforce_scope(principal, "notifications:write")
    record = _get_or_404(config_id, principal)

    subject = "X-Agent 通知渠道测试"
    body = f"这是一条来自 X-Agent 的测试通知（渠道：{record.type}）。"

    if record.type == "email":
        provider = get_notification_provider()
        if isinstance(provider, (ConsoleNotificationProvider, NoopNotificationProvider)):
            return NotificationTestResponse(
                success=False,
                message=(
                    f"未配置真实邮件通道（当前 provider={type(provider).__name__}，"
                    "XAGENT_SMTP_HOST 为空），本次未实际投递。"
                ),
            )
        result = await provider.send(
            NotificationMessage(
                to=record.target, subject=subject, body=body, channel="email"
            )
        )
    else:
        # Slack Incoming Webhook 只认 {"text": ...}; 直接发通用结构会被拒为
        # invalid_payload, 所以这里把 provider 切成 slack 载荷格式。
        provider = WebhookNotificationProvider(url=record.target, payload_format="slack")
        result = await provider.send(
            NotificationMessage(
                to=record.target, subject=subject, body=body, channel="slack"
            )
        )

    if result.success:
        message = f"已通过 {result.provider} 投递。"
    else:
        message = f"投递失败（{result.provider}）：{result.error or '未知错误'}"
    return NotificationTestResponse(success=result.success, message=message)


# ⚠️ 具名单段路由 /deliveries 必须声明在 /{config_id} **之前**。反过来的话
#    GET /{config_id} 会先匹配, config_id 收到字面量 "deliveries" 然后 404 ——
#    路由能注册、能启动、只有这个端点静默失效。
@router.get("/deliveries", response_model=list[DeliveryRecordResponse])
async def list_deliveries(
    principal: Annotated[Principal, Depends(get_current_principal)],
    limit: int = Query(50, ge=1, le=200),
    trigger: str | None = Query(None, description="只看某个 trigger"),
    config_id: str | None = Query(None, description="只看某个渠道"),
) -> list[DeliveryRecordResponse]:
    """最近的投递记录（最新在前），强制 tenant 收敛。

    存在的理由：环境未配置真实邮件通道时，分发只会写一行日志。没有这个端点，
    「渠道配好了、事件也发生了、却什么都没收到」在 API 与界面上都不可见。
    """
    enforce_scope(principal, "notifications:read")
    records = get_notification_dispatch_store().list_for_tenant(
        principal.tenant_id, limit=limit, trigger=trigger, config_id=config_id
    )
    return [_to_delivery_response(r) for r in records]


@router.post("/daily-summary/run", response_model=DailySummaryResponse)
async def run_daily_summary(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> DailySummaryResponse:
    """手动触发一次每日摘要投递（当前租户）。

    聚合与投递都走 ``core/daily_summary`` —— 与每天自动发出的定时任务**同一条
    路径**, 保证两边口径一致。这里刻意 **await** 而不是丢进 BackgroundTasks:
    手动触发的人要的就是回执。

    ``delivered_count`` 可能小于 ``active_channels`` —— 那正是本端点的意义所在,
    未配置真实通道时如实报 False, 而不是给一张假绿回执。

    数字口径: 新增量（总量 / 按状态 / 按严重度）按**过去 24 小时**过滤,
    ``critical_open`` 是**当前存量、不限窗口** —— 详见 ``core/daily_summary``。
    """
    enforce_scope(principal, "notifications:write")
    run = await run_for_tenant(principal.tenant_id)
    return DailySummaryResponse(
        subject=run.subject,
        active_channels=run.active_channels,
        delivered_count=run.delivered_count,
        records=[_to_delivery_response(r) for r in run.records],
    )


@router.get("/{config_id}", response_model=NotificationConfigResponse)
async def get_notification_config(
    config_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> NotificationConfigResponse:
    """取单个通知渠道配置。"""
    enforce_scope(principal, "notifications:read")
    return _to_response(_get_or_404(config_id, principal))


@router.patch("/{config_id}", response_model=NotificationConfigResponse)
async def update_notification_config(
    config_id: str,
    request: NotificationConfigUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> NotificationConfigResponse:
    """局部更新通知渠道配置。

    ``exclude_unset``: 没给的字段不动。
    ``exclude_none``: 显式传 ``null`` 也不动 —— 存储记录里没有可空字段, 把 null
    当「清空」只会让校验失败。
    """
    enforce_scope(principal, "notifications:write")
    _get_or_404(config_id, principal)  # tenant 收敛 + 存在性
    changes = request.model_dump(exclude_unset=True, exclude_none=True)
    updated = get_notification_config_store().update(config_id, changes)
    if updated is None:
        # 上面的 _get_or_404 已确认存在 —— 走到这里说明两次调用之间被并发删掉了,
        # 窄竞态, 仍给 404 而不是 500。
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification config not found",
        )
    return _to_response(updated)


# ⚠️ /{config_id} 族最后声明
@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_config(
    config_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    """删除通知渠道配置。跨租户 404。"""
    enforce_scope(principal, "notifications:write")
    _get_or_404(config_id, principal)
    get_notification_config_store().remove(config_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
