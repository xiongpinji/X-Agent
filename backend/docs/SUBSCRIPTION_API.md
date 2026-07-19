# X-Agent 订阅管理系统 API 文档

## 概述

X-Agent 订阅管理系统提供完整的用户订阅生命周期管理、配额控制和自动化流程。

## 基础信息

- **基础URL**: `/api/v1/subscriptions`
- **认证**: Bearer Token (JWT)
- **内容类型**: application/json

## 数据模型

### 订阅状态

- `ACTIVE` - 活跃订阅
- `PAUSED` - 暂停订阅
- `CANCELLED` - 已取消
- `EXPIRED` - 已过期

### 计费模型

- `subscription` - 订阅计费
- `pay_as_you_go` - 按量计费
- `hybrid` - 混合计费

### 试用期类型

- `7_days` - 7天试用
- `14_days` - 14天试用
- `30_days` - 30天试用

## API 端点

### 1. 创建订阅

**请求**
```
POST /api/v1/subscriptions
```

**请求体**
```json
{
  "pricing_tier_id": "tier_123",
  "payment_method": "stripe",
  "payment_method_id": "pm_test_123",
  "auto_renew": true,
  "trial_period": "14_days",
  "promotion_code": "PROMO2024"
}
```

**响应 (201)**
```json
{
  "id": "sub_123",
  "status": "active",
  "pricing_tier_id": "tier_123",
  "billing_model": "subscription",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "auto_renew": true,
  "payment_method": "stripe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 2. 获取当前订阅

**请求**
```
GET /api/v1/subscriptions
```

**响应 (200)**
```json
{
  "id": "sub_123",
  "status": "active",
  "pricing_tier_id": "tier_123",
  "billing_model": "subscription",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "auto_renew": true,
  "payment_method": "stripe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 3. 获取订阅详情

**请求**
```
GET /api/v1/subscriptions/{subscription_id}
```

**响应 (200)**
```json
{
  "id": "sub_123",
  "status": "active",
  "pricing_tier_id": "tier_123",
  "billing_model": "subscription",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "auto_renew": true,
  "payment_method": "stripe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 4. 暂停订阅

**请求**
```
POST /api/v1/subscriptions/{subscription_id}/pause
```

**响应 (200)**
```json
{
  "success": true,
  "subscription_id": "sub_123",
  "status": "paused"
}
```

### 5. 恢复订阅

**请求**
```
POST /api/v1/subscriptions/{subscription_id}/resume
```

**响应 (200)**
```json
{
  "success": true,
  "subscription_id": "sub_123",
  "status": "active"
}
```

### 6. 取消订阅

**请求**
```
POST /api/v1/subscriptions/{subscription_id}/cancel?reason=too_expensive
```

**响应 (200)**
```json
{
  "success": true,
  "subscription_id": "sub_123",
  "status": "cancelled"
}
```

### 7. 升级订阅

**请求**
```
POST /api/v1/subscriptions/{subscription_id}/upgrade
```

**请求体**
```json
{
  "pricing_tier_id": "tier_456",
  "effective_immediately": true
}
```

**响应 (200)**
```json
{
  "success": true,
  "subscription_id": "sub_123",
  "status": "active",
  "pricing_tier_id": "tier_456"
}
```

### 8. 降级订阅

**请求**
```
POST /api/v1/subscriptions/{subscription_id}/downgrade
```

**请求体**
```json
{
  "pricing_tier_id": "tier_789",
  "effective_immediately": false
}
```

**响应 (200)**
```json
{
  "success": true,
  "subscription_id": "sub_123",
  "status": "active",
  "pricing_tier_id": "tier_789"
}
```

### 9. 获取配额信息

**请求**
```
GET /api/v1/subscriptions/{subscription_id}/quota
```

**响应 (200)**
```json
{
  "subscription_id": "sub_123",
  "period_start": "2024-01-01T00:00:00Z",
  "period_end": "2024-02-01T00:00:00Z",
  "api_calls": {
    "used": 5000,
    "limit": 10000,
    "remaining": 5000,
    "usage_percent": 50.0,
    "alert_level": null
  },
  "tokens": {
    "used": 500000,
    "limit": 1000000,
    "remaining": 500000,
    "usage_percent": 50.0,
    "alert_level": null
  },
  "storage": {
    "used": 25.5,
    "limit": 100,
    "remaining": 74.5,
    "usage_percent": 25.5,
    "alert_level": null
  }
}
```

### 10. 获取使用情况

**请求**
```
GET /api/v1/subscriptions/{subscription_id}/usage
```

**响应 (200)**
```json
[
  {
    "quota_type": "api_calls",
    "used": 5000,
    "limit": 10000,
    "remaining": 5000,
    "usage_percent": 50.0,
    "alert_level": null
  },
  {
    "quota_type": "tokens",
    "used": 500000,
    "limit": 1000000,
    "remaining": 500000,
    "usage_percent": 50.0,
    "alert_level": null
  },
  {
    "quota_type": "storage",
    "used": 25.5,
    "limit": 100,
    "remaining": 74.5,
    "usage_percent": 25.5,
    "alert_level": null
  }
]
```

## 错误处理

### 常见错误码

| 状态码 | 错误 | 说明 |
|--------|------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 402 | PAYMENT_REQUIRED | 配额不足 |
| 403 | PERMISSION_DENIED | 无权限访问 |
| 404 | RESOURCE_NOT_FOUND | 资源不存在 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

### 错误响应示例

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid pricing tier",
    "details": {
      "pricing_tier_id": "tier_invalid"
    }
  }
}
```

## 配额告警

系统会在以下情况发送告警：

- **80% 使用率**: 警告级别告警
- **90% 使用率**: 严重级别告警
- **100% 使用率**: 关键级别告警

告警通过以下方式发送：
- 邮件通知
- 站内信通知
- API 响应中的 `alert_level` 字段

## 自动化流程

### 自动续费

- **触发时间**: 每日 UTC 00:00
- **续费条件**: 订阅状态为 ACTIVE 且 auto_renew=true 且 renewal_date <= 今天
- **重试机制**: 支付失败最多重试 3 次
- **重试间隔**: 1 天、3 天、7 天

### 过期提醒

- **7 天前**: 发送续费提醒
- **3 天前**: 发送续费提醒
- **1 天前**: 发送最后提醒

### 订阅过期处理

- **触发时间**: 每日 UTC 00:00
- **处理条件**: 订阅状态为 ACTIVE 且 renewal_date < 今天
- **处理方式**: 将订阅状态更新为 EXPIRED

## 使用示例

### Python 示例

```python
import httpx
import asyncio

async def create_subscription():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.xagent.com/api/v1/subscriptions",
            json={
                "pricing_tier_id": "tier_123",
                "payment_method": "stripe",
                "payment_method_id": "pm_test_123",
                "auto_renew": True,
                "trial_period": "14_days"
            },
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        return response.json()

async def get_quota():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.xagent.com/api/v1/subscriptions/sub_123/quota",
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        return response.json()

# 运行示例
asyncio.run(create_subscription())
asyncio.run(get_quota())
```

### cURL 示例

```bash
# 创建订阅
curl -X POST https://api.xagent.com/api/v1/subscriptions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pricing_tier_id": "tier_123",
    "payment_method": "stripe",
    "payment_method_id": "pm_test_123",
    "auto_renew": true,
    "trial_period": "14_days"
  }'

# 获取配额
curl -X GET https://api.xagent.com/api/v1/subscriptions/sub_123/quota \
  -H "Authorization: Bearer YOUR_TOKEN"

# 升级订阅
curl -X POST https://api.xagent.com/api/v1/subscriptions/sub_123/upgrade \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pricing_tier_id": "tier_456",
    "effective_immediately": true
  }'
```

## 最佳实践

1. **定期检查配额**: 在执行关键操作前检查配额
2. **处理告警**: 监听配额告警并及时升级计划
3. **自动续费**: 启用自动续费避免服务中断
4. **升级策略**: 使用 `effective_immediately=false` 在下期生效，避免立即扣费
5. **错误处理**: 实现重试逻辑处理临时性错误

## 限流

- API 请求限流: 1000 请求/分钟
- 配额消费限流: 无限制（受配额限制）

## 版本历史

### v1.0.0 (2024-01-01)
- 初始版本
- 支持订阅创建、暂停、恢复、取消
- 支持升级、降级
- 支持配额管理
- 支持自动续费
