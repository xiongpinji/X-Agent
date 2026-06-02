"""
订阅管理系统集成指南
说明如何在 X-Agent 主应用中集成订阅管理功能
"""

# 集成步骤

## 1. 在主应用中注册路由

# app/web.py
from fastapi import FastAPI
from backend.app.api import subscriptions

app = FastAPI()

# 注册订阅管理 API
app.include_router(subscriptions.router)

# 其他路由...


## 2. 在中间件中检查配额

# app/middleware.py
from fastapi import Request
from backend.app.core.quota_manager import get_quota_manager, QuotaType

async def quota_check_middleware(request: Request, call_next):
    """检查用户配额"""
    # 获取当前用户
    principal = request.state.principal
    if not principal:
        return await call_next(request)
    
    # 检查 API 调用配额
    quota_manager = get_quota_manager()
    quota_check = await quota_manager.check_quota(
        principal.tenant_id,
        principal.user_id,
        QuotaType.API_CALLS,
        amount=1,
    )
    
    if not quota_check.get("has_quota"):
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment required",
                "message": "API calls quota exceeded",
                "quota_info": quota_check,
            }
        )
    
    # 消费配额
    await quota_manager.consume_quota(
        principal.tenant_id,
        principal.user_id,
        QuotaType.API_CALLS,
        amount=1,
    )
    
    response = await call_next(request)
    return response

app.add_middleware(quota_check_middleware)


## 3. 在任务调度中集成自动化流程

# app/tasks/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.app.core.subscription_automation import get_subscription_automation

scheduler = AsyncIOScheduler()

# 每日 00:00 处理自动续费
scheduler.add_job(
    get_subscription_automation().process_auto_renewals,
    'cron',
    hour=0,
    minute=0,
    id='auto_renewal_job',
)

# 每日 09:00 发送过期提醒
scheduler.add_job(
    get_subscription_automation().send_expiration_reminders,
    'cron',
    hour=9,
    minute=0,
    id='expiration_reminder_job',
)

# 每日 01:00 处理过期订阅
scheduler.add_job(
    get_subscription_automation().handle_expired_subscriptions,
    'cron',
    hour=1,
    minute=0,
    id='expired_subscription_job',
)

# 每小时重试失败的支付
scheduler.add_job(
    get_subscription_automation().retry_failed_payments,
    'cron',
    minute=0,
    id='payment_retry_job',
)

scheduler.start()


## 4. 在用户注册时创建默认订阅

# app/services/user_service.py
from backend.app.core.subscription_manager import get_subscription_manager, TrialPeriod

async def create_user(user_data: dict):
    """创建用户并初始化订阅"""
    # 创建用户
    user = await User.create(**user_data)
    
    # 创建默认订阅（免费试用）
    subscription_manager = get_subscription_manager()
    
    # 获取免费层级
    free_tier = await get_free_pricing_tier(user.tenant_id)
    
    subscription = await subscription_manager.create_subscription(
        tenant_id=user.tenant_id,
        user_id=user.id,
        pricing_tier_id=free_tier.id,
        payment_method="free",
        payment_method_id="free",
        trial_period=TrialPeriod.FOURTEEN_DAYS,
    )
    
    return user, subscription


## 5. 在 API 调用中记录使用情况

# app/core/billing_engine.py
from backend.app.core.quota_manager import get_quota_manager, QuotaType

async def record_api_usage(
    tenant_id: str,
    user_id: str,
    api_calls: int = 1,
    tokens_used: int = 0,
):
    """记录 API 使用情况"""
    quota_manager = get_quota_manager()
    
    # 消费 API 调用配额
    if api_calls > 0:
        await quota_manager.consume_quota(
            tenant_id,
            user_id,
            QuotaType.API_CALLS,
            amount=api_calls,
        )
    
    # 消费 Token 配额
    if tokens_used > 0:
        await quota_manager.consume_quota(
            tenant_id,
            user_id,
            QuotaType.TOKENS_INPUT,
            amount=tokens_used,
        )


## 6. 在文件上传时检查存储配额

# app/services/file_service.py
from backend.app.core.quota_manager import get_quota_manager, QuotaType

async def upload_file(
    tenant_id: str,
    user_id: str,
    file_size_mb: float,
):
    """上传文件并检查存储配额"""
    quota_manager = get_quota_manager()
    
    # 检查存储配额
    quota_check = await quota_manager.check_quota(
        tenant_id,
        user_id,
        QuotaType.STORAGE,
        amount=file_size_mb,
    )
    
    if not quota_check.get("has_quota"):
        raise HTTPException(
            status_code=402,
            detail="Storage quota exceeded",
        )
    
    # 上传文件
    file = await save_file(file_data)
    
    # 消费存储配额
    await quota_manager.consume_quota(
        tenant_id,
        user_id,
        QuotaType.STORAGE,
        amount=file_size_mb,
    )
    
    return file


## 7. 在 WebSocket 连接中检查并发配额

# app/services/websocket_service.py
from backend.app.core.quota_manager import get_quota_manager, QuotaType

async def handle_websocket_connection(
    websocket: WebSocket,
    tenant_id: str,
    user_id: str,
):
    """处理 WebSocket 连接"""
    quota_manager = get_quota_manager()
    
    # 检查并发连接配额
    quota_check = await quota_manager.check_quota(
        tenant_id,
        user_id,
        QuotaType.CONCURRENT_CONNECTIONS,
        amount=1,
    )
    
    if not quota_check.get("has_quota"):
        await websocket.close(code=4002, reason="Concurrent connections quota exceeded")
        return
    
    # 消费并发连接配额
    await quota_manager.consume_quota(
        tenant_id,
        user_id,
        QuotaType.CONCURRENT_CONNECTIONS,
        amount=1,
    )
    
    try:
        await websocket.accept()
        # 处理连接...
    finally:
        # 释放并发连接配额
        # TODO: 实现配额释放机制
        pass


## 8. 在仪表板中显示订阅信息

# app/api/dashboard.py
from backend.app.core.subscription_manager import get_subscription_manager
from backend.app.core.quota_manager import get_quota_manager

@router.get("/dashboard/subscription")
async def get_subscription_dashboard(
    principal: Principal = Depends(get_current_principal),
):
    """获取订阅仪表板信息"""
    subscription_manager = get_subscription_manager()
    quota_manager = get_quota_manager()
    
    # 获取订阅信息
    subscription = await subscription_manager.get_subscription(
        principal.tenant_id,
        principal.user_id,
    )
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription")
    
    # 获取配额信息
    quota_info = await quota_manager.get_quota_info(
        principal.tenant_id,
        principal.user_id,
    )
    
    # 获取价格层级信息
    pricing_tier = await get_pricing_tier(subscription.pricing_tier_id)
    
    return {
        "subscription": {
            "id": subscription.id,
            "status": subscription.status.value,
            "plan": pricing_tier.tier_name,
            "price": str(pricing_tier.monthly_price),
            "renewal_date": subscription.renewal_date.isoformat(),
            "auto_renew": subscription.auto_renew,
        },
        "quota": quota_info,
        "features": pricing_tier.features,
    }


## 9. 处理支付失败和重试

# app/services/payment_service.py
from backend.app.models.billing import Payment, PaymentStatus

async def handle_payment_failure(payment: Payment):
    """处理支付失败"""
    # 记录失败
    payment.status = PaymentStatus.FAILED
    payment.error_message = "Payment processing failed"
    
    # 初始化重试计数
    if not payment.metadata:
        payment.metadata = {}
    
    retry_times = payment.metadata.get("retry_times", 0)
    payment.metadata["retry_times"] = retry_times + 1
    payment.metadata["last_failure_at"] = datetime.now(UTC).isoformat()
    
    # 如果重试次数未超过限制，安排重试
    if retry_times < 3:
        retry_delay = [1, 3, 7][retry_times]  # 天数
        retry_at = datetime.now(UTC) + timedelta(days=retry_delay)
        payment.metadata["retry_at"] = retry_at.isoformat()
    
    await session.commit()


## 10. 集成通知系统

# app/services/notification_service.py
from backend.app.core.subscription_automation import SubscriptionAutomation

async def send_subscription_notifications():
    """发送订阅相关通知"""
    automation = SubscriptionAutomation()
    
    # 获取需要发送通知的订阅
    subscriptions = await get_subscriptions_for_notification()
    
    for subscription in subscriptions:
        # 获取用户信息
        user = await get_user(subscription.user_id)
        
        # 发送邮件通知
        await send_email(
            to=user.email,
            subject="订阅即将过期",
            template="subscription_expiration_reminder",
            context={
                "user_name": user.name,
                "renewal_date": subscription.renewal_date,
                "plan": subscription.pricing_tier.tier_name,
            }
        )
        
        # 发送站内信通知
        await create_notification(
            user_id=user.id,
            title="订阅即将过期",
            message=f"您的 {subscription.pricing_tier.tier_name} 订阅将在 {subscription.renewal_date} 过期",
            type="subscription_expiration",
        )


# 测试集成

## 单元测试示例

import pytest
from backend.app.core.subscription_manager import get_subscription_manager
from backend.app.core.quota_manager import get_quota_manager

@pytest.mark.asyncio
async def test_subscription_integration():
    """测试订阅系统集成"""
    manager = get_subscription_manager()
    quota_manager = get_quota_manager()
    
    tenant_id = "test_tenant"
    user_id = "test_user"
    
    # 1. 创建订阅
    subscription = await manager.create_subscription(
        tenant_id=tenant_id,
        user_id=user_id,
        pricing_tier_id="tier_professional",
        payment_method="stripe",
        payment_method_id="pm_test",
    )
    assert subscription.id is not None
    
    # 2. 检查配额
    quota_info = await quota_manager.get_quota_info(tenant_id, user_id)
    assert quota_info is not None
    assert quota_info["api_calls"]["limit"] == 10000
    
    # 3. 消费配额
    result = await quota_manager.consume_quota(
        tenant_id,
        user_id,
        QuotaType.API_CALLS,
        amount=100,
    )
    assert result is True
    
    # 4. 验证配额已消费
    quota_info = await quota_manager.get_quota_info(tenant_id, user_id)
    assert quota_info["api_calls"]["used"] == 100
    assert quota_info["api_calls"]["remaining"] == 9900


## 集成测试示例

@pytest.mark.asyncio
async def test_complete_user_journey():
    """测试完整的用户旅程"""
    # 1. 用户注册
    user = await create_user({
        "email": "test@example.com",
        "name": "Test User",
    })
    
    # 2. 获取默认订阅
    subscription = await get_subscription(user.tenant_id, user.id)
    assert subscription.status == "active"
    
    # 3. 使用 API
    for i in range(100):
        await record_api_usage(user.tenant_id, user.id, api_calls=1)
    
    # 4. 检查配额
    quota_info = await get_quota_info(user.tenant_id, user.id)
    assert quota_info["api_calls"]["used"] == 100
    
    # 5. 升级订阅
    upgraded = await upgrade_subscription(
        user.tenant_id,
        user.id,
        "tier_professional",
    )
    assert upgraded.pricing_tier_id == "tier_professional"
    
    # 6. 继续使用 API
    for i in range(500):
        await record_api_usage(user.tenant_id, user.id, api_calls=1)
    
    # 7. 验证新配额
    quota_info = await get_quota_info(user.tenant_id, user.id)
    assert quota_info["api_calls"]["used"] == 600


# 性能考虑

## 缓存策略

- 配额信息缓存 5 分钟
- 订阅信息缓存 10 分钟
- 价格层级信息缓存 1 小时

## 数据库优化

- 为 renewal_date 创建索引
- 为 tenant_id + user_id 创建复合索引
- 定期清理过期的计费历史记录

## 异步处理

- 使用后台任务处理自动续费
- 使用消息队列处理支付重试
- 使用异步邮件发送通知


# 故障处理

## 重试机制

- API 调用失败: 最多重试 3 次
- 支付失败: 最多重试 3 次（间隔 1、3、7 天）
- 数据库连接失败: 使用连接池自动重试

## 降级策略

- 配额检查失败: 允许请求通过（记录日志）
- 通知发送失败: 异步重试（不阻塞主流程）
- 自动续费失败: 发送告警并等待手动处理


# 监控和告警

## 关键指标

- 活跃订阅数
- 自动续费成功率
- 配额超限用户数
- 支付失败率

## 告警规则

- 自动续费失败率 > 10%
- 配额使用率 > 90%
- 支付失败 > 0
- 数据库连接池使用率 > 80%
