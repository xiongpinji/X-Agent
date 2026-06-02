"""
计费系统API文档和配置
"""

# API文档

"""
# X-Agent 计费系统 API 文档

## 概述
X-Agent 计费系统提供完整的多租户计费解决方案，支持按量计费、订阅计费和混合计费模型。

## 基础信息
- 基础URL: `/api/v1/billing`
- 认证: Bearer Token (JWT)
- 响应格式: JSON

## 计费模型

### 1. 按量计费 (Pay-as-you-go)
按实际使用量计费，包括：
- API调用次数
- Token消耗量
- 存储空间使用

### 2. 订阅计费 (Subscription)
固定周期（月/年）的订阅费用，包括：
- 基础订阅费
- 包含的配额
- 自动续费选项

### 3. 混合计费 (Hybrid)
结合订阅和按量计费：
- 基础订阅费 + 超额按量计费
- 灵活的配额管理

## API端点

### 1. 获取计费计划
```
GET /api/v1/billing/plans
```

**响应示例:**
```json
[
  {
    "id": "tier-001",
    "tier_name": "basic",
    "billing_model": "subscription",
    "monthly_price": "99.99",
    "monthly_api_calls": 10000,
    "monthly_tokens": 1000000,
    "storage_gb": 100,
    "features": {
      "advanced_analytics": false,
      "api_access": true
    }
  }
]
```

### 2. 订阅计费计划
```
POST /api/v1/billing/subscribe
```

**请求体:**
```json
{
  "pricing_tier_id": "tier-001",
  "payment_method": "stripe",
  "payment_method_id": "pm_1234567890",
  "auto_renew": true,
  "promotion_code": "SAVE20"
}
```

**响应示例:**
```json
{
  "id": "sub-001",
  "status": "active",
  "billing_model": "subscription",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "auto_renew": true,
  "discount_percent": "20"
}
```

### 3. 获取使用统计
```
GET /api/v1/billing/usage?days=30
```

**响应示例:**
```json
[
  {
    "date": "2024-01-15T00:00:00Z",
    "api_calls": 1500,
    "tokens_used": 150000,
    "storage_used_gb": "5.25",
    "estimated_cost": "15.50"
  }
]
```

### 4. 检查配额
```
GET /api/v1/billing/quota
```

**响应示例:**
```json
{
  "has_quota": true,
  "api_calls": {
    "used": 5000,
    "limit": 10000,
    "remaining": 5000,
    "warning": false
  },
  "tokens": {
    "used": 500000,
    "limit": 1000000,
    "remaining": 500000,
    "warning": false
  },
  "storage": {
    "used": "50.00",
    "limit": 100,
    "remaining": 50,
    "warning": false
  }
}
```

### 5. 获取发票列表
```
GET /api/v1/billing/invoices?skip=0&limit=10
```

**响应示例:**
```json
[
  {
    "id": "inv-001",
    "invoice_number": "INV-TEST-20240115-ABC123",
    "period_start": "2024-01-01T00:00:00Z",
    "period_end": "2024-01-31T23:59:59Z",
    "issue_date": "2024-02-01T00:00:00Z",
    "due_date": "2024-03-02T00:00:00Z",
    "subtotal": "199.99",
    "tax": "20.00",
    "discount": "40.00",
    "total": "179.99",
    "status": "paid",
    "line_items": [
      {
        "description": "Professional 订阅费",
        "quantity": 1,
        "unit_price": "199.99",
        "amount": "199.99"
      }
    ]
  }
]
```

### 6. 处理支付
```
POST /api/v1/billing/payment
```

**请求体:**
```json
{
  "amount": "179.99",
  "payment_method": "stripe",
  "payment_method_id": "pm_1234567890",
  "invoice_id": "inv-001"
}
```

**响应示例:**
```json
{
  "id": "pay-001",
  "amount": "179.99",
  "status": "completed",
  "payment_date": "2024-02-01T10:30:00Z",
  "transaction_id": "ch_1234567890"
}
```

### 7. 应用促销代码
```
POST /api/v1/billing/apply-promo-code?code=SAVE20
```

**响应示例:**
```json
{
  "success": true,
  "discount_type": "percentage",
  "discount_value": "20"
}
```

### 8. 获取当前订阅
```
GET /api/v1/billing/subscription
```

**响应示例:**
```json
{
  "id": "sub-001",
  "status": "active",
  "billing_model": "subscription",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-01T00:00:00Z",
  "renewal_date": "2024-02-01T00:00:00Z",
  "auto_renew": true,
  "discount_percent": "0"
}
```

### 9. 取消订阅
```
POST /api/v1/billing/cancel-subscription
```

**响应示例:**
```json
{
  "success": true,
  "message": "Subscription cancelled successfully"
}
```

## 支付方式

### 支持的支付方式
1. **Stripe** - 信用卡、借记卡
2. **支付宝** - 中国用户
3. **微信支付** - 中国用户
4. **银行转账** - 企业用户

### 支付流程
1. 获取计费计划
2. 订阅计费计划
3. 处理支付
4. 生成发票
5. 自动续费（如启用）

## 错误处理

### 常见错误码
- `400` - 请求参数错误
- `401` - 未授权
- `402` - 支付失败
- `404` - 资源不存在
- `500` - 服务器错误

### 错误响应示例
```json
{
  "detail": "Unsupported payment method: invalid_method"
}
```

## 配额管理

### 配额警告
- 当使用量达到限制的80%时，触发警告
- 当使用量达到100%时，拒绝新请求

### 配额重置
- 按月重置（订阅计费）
- 按年重置（年度订阅）
- 按量计费无限制

## 发票管理

### 发票生成
- 自动生成月度发票
- 支持自定义发票周期
- 支持多种发票格式（PDF、JSON）

### 发票状态
- `draft` - 草稿
- `issued` - 已发行
- `paid` - 已支付
- `overdue` - 逾期
- `cancelled` - 已取消

## 促销代码

### 促销代码类型
- 百分比折扣（percentage）
- 固定金额折扣（fixed_amount）

### 促销代码限制
- 有效期限制
- 使用次数限制
- 适用层级限制
- 最低金额限制

## 安全性

### 认证
- 所有请求需要有效的JWT Token
- Token包含租户ID和用户ID

### 多租户隔离
- 数据严格按租户隔离
- 用户只能访问自己的数据
- 支持租户级别的权限控制

### 数据加密
- 支付信息加密存储
- 敏感数据不在日志中记录
- 支持PCI DSS合规

## 限流

### 限流规则
- API调用限流：100请求/分钟
- 支付请求限流：10请求/分钟
- 发票生成限流：5请求/分钟

## 最佳实践

### 1. 使用异步处理
```python
# 异步处理支付
payment = await billing_engine.process_payment(...)
```

### 2. 实现重试机制
```python
# 支付失败重试
for attempt in range(3):
    try:
        payment = await process_payment(...)
        break
    except PaymentError:
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)
```

### 3. 监控配额
```python
# 定期检查配额
quota = await billing_engine.check_quota(tenant_id, user_id)
if quota['api_calls']['warning']:
    # 发送警告通知
    send_quota_warning(user_id)
```

### 4. 审计日志
```python
# 所有计费操作都记录在BillingHistory表中
# 支持完整的审计追踪
```

## 示例代码

### Python示例
```python
from backend.app.core.billing_engine import get_billing_engine
from decimal import Decimal

billing_engine = get_billing_engine()

# 记录使用
usage = await billing_engine.record_usage(
    tenant_id="tenant-001",
    user_id="user-001",
    api_calls=100,
    tokens_used=1000,
    storage_gb=Decimal("1.5"),
)

# 生成发票
invoice = await billing_engine.generate_invoice(
    tenant_id="tenant-001",
    user_id="user-001",
    period_start=datetime.now(UTC) - timedelta(days=30),
    period_end=datetime.now(UTC),
)

# 处理支付
payment = await billing_engine.process_payment(
    tenant_id="tenant-001",
    user_id="user-001",
    amount=Decimal("199.99"),
    payment_method="stripe",
    payment_method_id="pm_1234567890",
)
```

## 常见问题

### Q: 如何处理支付失败？
A: 系统会自动重试，失败后返回错误信息。用户可以重新尝试或联系支持。

### Q: 如何升级/降级订阅？
A: 取消当前订阅，然后订阅新的计费计划。

### Q: 如何获取发票？
A: 通过 GET /api/v1/billing/invoices 端点获取发票列表。

### Q: 支持退款吗？
A: 支持，通过支付提供商的退款API处理。

## 联系支持
- 邮件: billing@xagent.com
- 文档: https://docs.xagent.com/billing
"""

# 配置文件

BILLING_CONFIG = {
    # 计费模型
    "billing_models": {
        "pay_as_you_go": {
            "name": "按量计费",
            "description": "按实际使用量计费",
        },
        "subscription": {
            "name": "订阅计费",
            "description": "固定周期订阅费用",
        },
        "hybrid": {
            "name": "混合计费",
            "description": "订阅费 + 超额按量计费",
        },
    },

    # 价格层级
    "pricing_tiers": {
        "basic": {
            "name": "基础版",
            "billing_model": "subscription",
            "monthly_price": 99.99,
            "annual_price": 999.99,
            "monthly_api_calls": 10000,
            "monthly_tokens": 1000000,
            "storage_gb": 100,
            "concurrent_users": 5,
            "features": {
                "api_access": True,
                "advanced_analytics": False,
                "priority_support": False,
                "custom_integration": False,
            },
        },
        "professional": {
            "name": "专业版",
            "billing_model": "hybrid",
            "monthly_price": 199.99,
            "annual_price": 1999.99,
            "api_call_price": 0.01,
            "token_price": 0.0001,
            "storage_price": 0.1,
            "monthly_api_calls": 100000,
            "monthly_tokens": 10000000,
            "storage_gb": 1000,
            "concurrent_users": 50,
            "features": {
                "api_access": True,
                "advanced_analytics": True,
                "priority_support": True,
                "custom_integration": False,
            },
        },
        "enterprise": {
            "name": "企业版",
            "billing_model": "hybrid",
            "monthly_price": 999.99,
            "annual_price": 9999.99,
            "api_call_price": 0.005,
            "token_price": 0.00005,
            "storage_price": 0.05,
            "monthly_api_calls": None,  # 无限制
            "monthly_tokens": None,
            "storage_gb": None,
            "concurrent_users": None,
            "features": {
                "api_access": True,
                "advanced_analytics": True,
                "priority_support": True,
                "custom_integration": True,
                "sso": True,
                "audit_logs": True,
            },
        },
    },

    # 支付方式
    "payment_methods": {
        "stripe": {
            "name": "Stripe",
            "description": "信用卡、借记卡",
            "regions": ["US", "EU", "APAC"],
            "currencies": ["USD", "EUR", "GBP", "JPY"],
        },
        "alipay": {
            "name": "支付宝",
            "description": "中国用户",
            "regions": ["CN"],
            "currencies": ["CNY"],
        },
        "wechat": {
            "name": "微信支付",
            "description": "中国用户",
            "regions": ["CN"],
            "currencies": ["CNY"],
        },
        "bank_transfer": {
            "name": "银行转账",
            "description": "企业用户",
            "regions": ["ALL"],
            "currencies": ["USD", "EUR", "CNY"],
        },
    },

    # 税费配置
    "tax": {
        "default_rate": 0.1,  # 10%
        "by_region": {
            "US": 0.0,  # 由州决定
            "EU": 0.19,  # 19% VAT
            "CN": 0.13,  # 13% VAT
        },
    },

    # 配额警告
    "quota_warning_threshold": 0.8,  # 80%

    # 发票配置
    "invoice": {
        "due_days": 30,
        "auto_generate": True,
        "auto_generate_day": 1,  # 每月1号
    },

    # 促销代码配置
    "promotion": {
        "max_discount_percent": 50,
        "max_discount_amount": 1000,
    },

    # 自动续费配置
    "auto_renewal": {
        "enabled": True,
        "retry_attempts": 3,
        "retry_interval_days": 1,
    },

    # 限流配置
    "rate_limiting": {
        "api_calls_per_minute": 100,
        "payment_requests_per_minute": 10,
        "invoice_generation_per_minute": 5,
    },
}
