# 用户反馈系统 API 文档

## 概述

X-Agent 用户反馈系统提供了完整的反馈收集、分析和管理功能。系统支持多种反馈类型、自动情感分析、智能分类和优先级计算。

## 基础信息

- **基础URL**: `/api/v1/feedback`
- **认证**: 需要有效的API密钥或用户令牌
- **内容类型**: `application/json`
- **响应格式**: JSON

## 数据模型

### 反馈类型 (FeedbackType)

```
- bug: 缺陷报告
- feature: 功能请求
- improvement: 改进建议
- other: 其他
```

### 严重程度 (Severity)

```
- low: 低
- medium: 中等
- high: 高
- critical: 严重
```

### 反馈状态 (Status)

```
- new: 新建
- acknowledged: 已确认
- in_progress: 进行中
- resolved: 已解决
- closed: 已关闭
```

### 情感类型 (Sentiment)

```
- positive: 正面
- neutral: 中立
- negative: 负面
```

## API 端点

### 1. 创建反馈

**请求**

```http
POST /api/v1/feedback/
Content-Type: application/json
Authorization: Bearer <token>

{
  "feedback_type": "bug",
  "title": "应用程序启动时崩溃",
  "description": "在Windows 10上启动应用程序后立即崩溃",
  "severity": "critical",
  "metadata": {
    "os": "Windows 10",
    "version": "1.0.0",
    "browser": "Chrome"
  }
}
```

**响应** (201 Created)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "feedback_type": "bug",
  "title": "应用程序启动时崩溃",
  "description": "在Windows 10上启动应用程序后立即崩溃",
  "severity": "critical",
  "status": "new",
  "sentiment": "negative",
  "sentiment_score": -0.85,
  "priority_score": 0.92,
  "category": "functionality",
  "tags": ["crash", "startup", "windows"],
  "created_at": "2026-05-29T10:30:00Z",
  "updated_at": "2026-05-29T10:30:00Z",
  "resolved_at": null
}
```

**参数说明**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| feedback_type | string | 是 | 反馈类型: bug, feature, improvement, other |
| title | string | 是 | 反馈标题 (1-500字符) |
| description | string | 是 | 反馈描述 (1-5000字符) |
| severity | string | 是 | 严重程度: low, medium, high, critical |
| metadata | object | 否 | 额外元数据 |

**错误响应**

```json
{
  "detail": "Invalid feedback_type. Must be one of: ['bug', 'feature', 'improvement', 'other']"
}
```

---

### 2. 获取反馈详情

**请求**

```http
GET /api/v1/feedback/{feedback_id}
Authorization: Bearer <token>
```

**响应** (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "feedback_type": "bug",
  "title": "应用程序启动时崩溃",
  "description": "在Windows 10上启动应用程序后立即崩溃",
  "severity": "critical",
  "status": "new",
  "sentiment": "negative",
  "sentiment_score": -0.85,
  "priority_score": 0.92,
  "category": "functionality",
  "tags": ["crash", "startup", "windows"],
  "created_at": "2026-05-29T10:30:00Z",
  "updated_at": "2026-05-29T10:30:00Z",
  "resolved_at": null
}
```

**错误响应**

```json
{
  "detail": "Feedback not found"
}
```

---

### 3. 列出反馈

**请求**

```http
GET /api/v1/feedback/?feedback_type=bug&status=new&severity=critical&skip=0&limit=100
Authorization: Bearer <token>
```

**响应** (200 OK)

```json
{
  "total": 42,
  "skip": 0,
  "limit": 100,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user-123",
      "feedback_type": "bug",
      "title": "应用程序启动时崩溃",
      "description": "在Windows 10上启动应用程序后立即崩溃",
      "severity": "critical",
      "status": "new",
      "sentiment": "negative",
      "sentiment_score": -0.85,
      "priority_score": 0.92,
      "category": "functionality",
      "tags": ["crash", "startup", "windows"],
      "created_at": "2026-05-29T10:30:00Z",
      "updated_at": "2026-05-29T10:30:00Z",
      "resolved_at": null
    }
  ]
}
```

**查询参数**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| feedback_type | string | 否 | 反馈类型过滤 |
| status | string | 否 | 状态过滤 |
| severity | string | 否 | 严重程度过滤 |
| skip | integer | 否 | 跳过数量 (默认: 0) |
| limit | integer | 否 | 限制数量 (默认: 100, 最大: 1000) |

---

### 4. 获取反馈分析

**请求**

```http
GET /api/v1/feedback/{feedback_id}/analysis
Authorization: Bearer <token>
```

**响应** (200 OK)

```json
{
  "feedback_id": "550e8400-e29b-41d4-a716-446655440000",
  "sentiment_type": "negative",
  "sentiment_score": -0.85,
  "category": "functionality",
  "subcategory": null,
  "tags": ["crash", "startup", "windows", "error"],
  "priority_score": 0.92,
  "urgency_score": 0.95,
  "impact_score": 0.89,
  "keywords": ["application", "crashes", "startup", "windows"],
  "entities": {
    "features": [],
    "components": ["application"],
    "errors": ["crash"]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| feedback_id | string | 反馈ID |
| sentiment_type | string | 情感类型: positive, neutral, negative |
| sentiment_score | number | 情感分数 (-1.0 到 1.0) |
| category | string | 反馈分类 |
| subcategory | string | 子分类 |
| tags | array | 标签列表 |
| priority_score | number | 优先级分数 (0.0 到 1.0) |
| urgency_score | number | 紧急程度分数 (0.0 到 1.0) |
| impact_score | number | 影响程度分数 (0.0 到 1.0) |
| keywords | array | 提取的关键词 |
| entities | object | 提取的实体 |

---

### 5. 更新反馈状态

**请求**

```http
PATCH /api/v1/feedback/{feedback_id}?status=in_progress
Authorization: Bearer <token>
```

**响应** (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "feedback_type": "bug",
  "title": "应用程序启动时崩溃",
  "description": "在Windows 10上启动应用程序后立即崩溃",
  "severity": "critical",
  "status": "in_progress",
  "sentiment": "negative",
  "sentiment_score": -0.85,
  "priority_score": 0.92,
  "category": "functionality",
  "tags": ["crash", "startup", "windows"],
  "created_at": "2026-05-29T10:30:00Z",
  "updated_at": "2026-05-29T10:35:00Z",
  "resolved_at": null
}
```

**查询参数**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| status | string | 是 | 新状态: new, acknowledged, in_progress, resolved, closed |

---

### 6. 获取反馈统计

**请求**

```http
GET /api/v1/feedback/stats/summary
Authorization: Bearer <token>
```

**响应** (200 OK)

```json
{
  "total": 156,
  "by_status": {
    "new": 42,
    "acknowledged": 28,
    "in_progress": 35,
    "resolved": 45,
    "closed": 6
  },
  "by_severity": {
    "low": 32,
    "medium": 58,
    "high": 48,
    "critical": 18
  },
  "by_type": {
    "bug": 89,
    "feature": 42,
    "improvement": 20,
    "other": 5
  },
  "average_priority_score": 0.62,
  "critical_count": 18
}
```

---

## 分析引擎

### 情感分析

系统使用TextBlob库进行情感分析，支持英文和中文。

- **正面情感** (sentiment_score > 0.1): 用户满意或赞赏
- **中立情感** (-0.1 <= sentiment_score <= 0.1): 客观描述
- **负面情感** (sentiment_score < -0.1): 用户不满意或投诉

### 自动分类

系统根据反馈内容自动分类为以下类别：

- **performance**: 性能相关
- **usability**: 可用性相关
- **functionality**: 功能相关
- **compatibility**: 兼容性相关
- **documentation**: 文档相关
- **security**: 安全相关
- **general**: 其他

### 优先级计算

优先级基于以下因素计算：

1. **严重程度** (40%): critical > high > medium > low
2. **反馈类型** (30%): bug > feature > improvement > other
3. **分类** (20%): security > performance > compatibility > functionality > usability > documentation
4. **情感分数** (10%): 负面反馈优先级更高

**优先级分数范围**: 0.0 - 1.0

---

## 错误处理

### 常见错误码

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数无效 |
| 401 | 未授权 (缺少或无效的令牌) |
| 403 | 禁止访问 (权限不足) |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

---

## 使用示例

### Python 示例

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1/feedback"
HEADERS = {
    "Authorization": "Bearer your-token",
    "Content-Type": "application/json"
}

# 创建反馈
feedback_data = {
    "feedback_type": "bug",
    "title": "应用程序启动时崩溃",
    "description": "在Windows 10上启动应用程序后立即崩溃",
    "severity": "critical",
    "metadata": {
        "os": "Windows 10",
        "version": "1.0.0"
    }
}

response = requests.post(BASE_URL, json=feedback_data, headers=HEADERS)
feedback = response.json()
feedback_id = feedback["id"]

# 获取反馈分析
analysis_response = requests.get(
    f"{BASE_URL}/{feedback_id}/analysis",
    headers=HEADERS
)
analysis = analysis_response.json()

print(f"优先级分数: {analysis['priority_score']}")
print(f"情感类型: {analysis['sentiment_type']}")
print(f"分类: {analysis['category']}")

# 列出反馈
list_response = requests.get(
    f"{BASE_URL}/?severity=critical&status=new",
    headers=HEADERS
)
feedbacks = list_response.json()

print(f"总数: {feedbacks['total']}")
for item in feedbacks['items']:
    print(f"- {item['title']} (优先级: {item['priority_score']})")

# 更新反馈状态
update_response = requests.patch(
    f"{BASE_URL}/{feedback_id}?status=in_progress",
    headers=HEADERS
)
updated_feedback = update_response.json()

print(f"新状态: {updated_feedback['status']}")

# 获取统计
stats_response = requests.get(
    f"{BASE_URL}/stats/summary",
    headers=HEADERS
)
stats = stats_response.json()

print(f"总反馈数: {stats['total']}")
print(f"严重反馈数: {stats['critical_count']}")
```

### cURL 示例

```bash
# 创建反馈
curl -X POST http://localhost:8000/api/v1/feedback/ \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_type": "bug",
    "title": "应用程序启动时崩溃",
    "description": "在Windows 10上启动应用程序后立即崩溃",
    "severity": "critical"
  }'

# 获取反馈分析
curl -X GET http://localhost:8000/api/v1/feedback/{feedback_id}/analysis \
  -H "Authorization: Bearer your-token"

# 列出反馈
curl -X GET "http://localhost:8000/api/v1/feedback/?severity=critical&status=new" \
  -H "Authorization: Bearer your-token"

# 更新反馈状态
curl -X PATCH "http://localhost:8000/api/v1/feedback/{feedback_id}?status=in_progress" \
  -H "Authorization: Bearer your-token"

# 获取统计
curl -X GET http://localhost:8000/api/v1/feedback/stats/summary \
  -H "Authorization: Bearer your-token"
```

---

## 性能指标

- **分析准确率**: >= 85%
- **API 响应时间**: < 500ms
- **数据库查询时间**: < 100ms
- **情感分析时间**: < 200ms

---

## 最佳实践

1. **批量操作**: 使用分页获取大量反馈，避免一次性加载所有数据
2. **缓存**: 缓存统计数据，减少数据库查询
3. **异步处理**: 分析操作在后台异步执行，不阻塞API响应
4. **错误处理**: 实现重试机制处理临时性错误
5. **监控**: 监控API性能和错误率

---

## 版本历史

### v1.0.0 (2026-05-29)

- 初始版本
- 支持反馈创建、查询、更新
- 自动情感分析和分类
- 优先级计算
- 统计功能
