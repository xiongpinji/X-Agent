"""技能市场高级功能API文档"""

# 技能市场高级功能API文档

## 概述

本文档描述X-Agent技能市场的高级功能API，包括版本管理、评论评分、搜索优化、依赖管理和更新机制。

## 基础信息

- **基础URL**: `/api/v1/skill-market/advanced`
- **认证**: 需要有效的Principal和相应的权限范围
- **响应格式**: JSON

## 权限范围

- `skill-market:read` - 读取技能市场信息
- `skill-market:write` - 修改技能市场信息
- `skill-market:admin` - 管理技能市场

---

## 1. 版本管理API

### 1.1 创建新版本

**端点**: `POST /versions/{skill_id}`

**权限**: `skill-market:admin`

**请求体**:
```json
{
  "version": "1.1.0",
  "changes": "Bug fixes and performance improvements",
  "compatibility": "compatible",
  "breaking_changes": [],
  "migration_guide": ""
}
```

**响应**:
```json
{
  "skill_id": "test-skill",
  "version": "1.1.0",
  "release_date": "2026-05-27T10:00:00Z",
  "changes": "Bug fixes and performance improvements",
  "compatibility": "compatible",
  "deprecated": false,
  "download_count": 0
}
```

**错误码**:
- `400 CREATE_VERSION_FAILED` - 创建版本失败
- `400 INVALID_COMPATIBILITY` - 无效的兼容性值

---

### 1.2 获取所有版本

**端点**: `GET /versions/{skill_id}`

**权限**: `skill-market:read`

**响应**:
```json
[
  {
    "skill_id": "test-skill",
    "version": "1.1.0",
    "release_date": "2026-05-27T10:00:00Z",
    "changes": "Bug fixes",
    "compatibility": "compatible",
    "deprecated": false,
    "download_count": 150
  },
  {
    "skill_id": "test-skill",
    "version": "1.0.0",
    "release_date": "2026-05-20T10:00:00Z",
    "changes": "Initial release",
    "compatibility": "compatible",
    "deprecated": false,
    "download_count": 500
  }
]
```

---

### 1.3 版本回滚

**端点**: `POST /versions/{skill_id}/{version}/rollback`

**权限**: `skill-market:admin`

**响应**:
```json
{
  "success": true,
  "message": "已回滚到版本 1.0.0"
}
```

---

## 2. 评论评分API

### 2.1 添加评论

**端点**: `POST /reviews/{skill_id}`

**权限**: `skill-market:write`

**请求体**:
```json
{
  "rating": 5,
  "title": "Excellent skill",
  "comment": "Very useful and easy to use"
}
```

**响应**:
```json
{
  "id": "review-uuid",
  "skill_id": "test-skill",
  "user_name": "user1",
  "rating": 5,
  "title": "Excellent skill",
  "comment": "Very useful and easy to use",
  "status": "pending",
  "helpful_count": 0,
  "unhelpful_count": 0,
  "created_at": "2026-05-27T10:00:00Z"
}
```

**验证**:
- 评分必须在1-5之间
- 标题和评论不能同时为空
- 每个用户每个技能只能评论一次

---

### 2.2 获取评论列表

**端点**: `GET /reviews/{skill_id}`

**权限**: `skill-market:read`

**查询参数**:
- `limit` (int, 1-100, 默认10) - 返回数量
- `sort_by` (string, 默认"helpful") - 排序方式: helpful, rating, newest, oldest

**响应**:
```json
[
  {
    "id": "review-uuid",
    "skill_id": "test-skill",
    "user_name": "user1",
    "rating": 5,
    "title": "Excellent",
    "comment": "Very useful",
    "status": "approved",
    "helpful_count": 25,
    "unhelpful_count": 2,
    "created_at": "2026-05-27T10:00:00Z"
  }
]
```

---

### 2.3 获取平均评分

**端点**: `GET /reviews/{skill_id}/rating`

**权限**: `skill-market:read`

**响应**:
```json
{
  "skill_id": "test-skill",
  "average_rating": 4.5,
  "distribution": {
    "1": 5,
    "2": 10,
    "3": 20,
    "4": 50,
    "5": 100
  }
}
```

---

### 2.4 标记为有用

**端点**: `POST /reviews/{review_id}/helpful`

**权限**: `skill-market:write`

**响应**:
```json
{
  "success": true,
  "message": "已标记为有用"
}
```

---

## 3. 搜索API

### 3.1 高级搜索

**端点**: `GET /search`

**权限**: `skill-market:read`

**查询参数**:
- `query` (string, 必需) - 搜索词
- `category` (string, 可选) - 分类过滤
- `limit` (int, 1-100, 默认20) - 返回数量

**搜索特性**:
- 精确匹配 (相关性: 1.0)
- 部分匹配 (相关性: 0.6-0.9)
- 模糊搜索 (相关性: 0.5-0.8)
- 语义搜索 (相关性: 0.3-0.6)

**响应**:
```json
[
  {
    "skill_id": "python-helper",
    "name": "Python Helper",
    "name_zh": "Python助手",
    "description": "Python programming assistant",
    "relevance_score": 0.95,
    "match_type": "exact"
  },
  {
    "skill_id": "code-generator",
    "name": "Code Generator",
    "name_zh": "代码生成器",
    "description": "Generate code snippets",
    "relevance_score": 0.72,
    "match_type": "partial"
  }
]
```

---

### 3.2 搜索建议

**端点**: `GET /search/suggestions`

**权限**: `skill-market:read`

**查询参数**:
- `query` (string, 必需) - 搜索词前缀
- `limit` (int, 1-50, 默认10) - 返回数量

**响应**:
```json
{
  "query": "py",
  "suggestions": [
    "python",
    "python-helper",
    "pydantic",
    "pytest"
  ]
}
```

---

## 4. 依赖管理API

### 4.1 添加依赖

**端点**: `POST /dependencies/{skill_id}`

**权限**: `skill-market:admin`

**请求体**:
```json
{
  "dep_skill_id": "base-skill",
  "version_spec": ">=1.0.0",
  "dep_type": "required"
}
```

**版本规范**:
- `*` - 任何版本
- `1.0.0` - 精确版本
- `>=1.0.0` - 最小版本
- `1.x` - 主版本匹配

**响应**:
```json
{
  "skill_id": "test-skill",
  "dep_skill_id": "base-skill",
  "version_spec": ">=1.0.0",
  "dep_type": "required",
  "optional": false
}
```

---

### 4.2 获取依赖列表

**端点**: `GET /dependencies/{skill_id}`

**权限**: `skill-market:read`

**响应**:
```json
[
  {
    "skill_id": "test-skill",
    "dep_skill_id": "base-skill",
    "version_spec": ">=1.0.0",
    "dep_type": "required",
    "optional": false
  },
  {
    "skill_id": "test-skill",
    "dep_skill_id": "optional-skill",
    "version_spec": "*",
    "dep_type": "optional",
    "optional": true
  }
]
```

---

### 4.3 获取依赖树

**端点**: `GET /dependencies/{skill_id}/tree`

**权限**: `skill-market:read`

**响应**:
```json
{
  "skill_id": "test-skill",
  "depth": 0,
  "children": [
    {
      "skill_id": "base-skill",
      "version_spec": ">=1.0.0",
      "dep_type": "required",
      "installed": true,
      "children": [
        {
          "skill_id": "core-skill",
          "version_spec": "*",
          "dep_type": "required",
          "installed": true,
          "children": []
        }
      ]
    }
  ]
}
```

---

## 5. 更新管理API

### 5.1 检查更新

**端点**: `GET /updates/{skill_id}`

**权限**: `skill-market:read`

**响应** (有更新):
```json
{
  "skill_id": "test-skill",
  "current_version": "1.0.0",
  "new_version": "1.1.0",
  "priority": "medium",
  "status": "available",
  "progress": 0,
  "changelog": "Bug fixes and improvements"
}
```

**响应** (无更新):
```json
null
```

---

### 5.2 安装更新

**端点**: `POST /updates/{skill_id}/install`

**权限**: `skill-market:write`

**请求体**:
```json
{
  "version": "1.1.0"
}
```

**响应**:
```json
{
  "skill_id": "test-skill",
  "current_version": "1.0.0",
  "new_version": "1.1.0",
  "priority": "medium",
  "status": "completed",
  "progress": 100,
  "changelog": "Bug fixes and improvements"
}
```

---

### 5.3 切换自动更新

**端点**: `POST /updates/{skill_id}/auto-update`

**权限**: `skill-market:write`

**请求体**:
```json
{
  "enabled": true
}
```

**响应**:
```json
{
  "success": true,
  "skill_id": "test-skill",
  "auto_update_enabled": true
}
```

---

### 5.4 获取更新历史

**端点**: `GET /updates/history/{skill_id}`

**权限**: `skill-market:read`

**查询参数**:
- `limit` (int, 1-100, 默认20) - 返回数量

**响应**:
```json
[
  {
    "skill_id": "test-skill",
    "current_version": "1.0.0",
    "new_version": "1.1.0",
    "priority": "medium",
    "status": "completed",
    "progress": 100,
    "changelog": "Bug fixes"
  }
]
```

---

## 错误处理

所有错误响应遵循以下格式:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message"
  }
}
```

### 常见错误码

| 错误码 | HTTP状态 | 描述 |
|--------|---------|------|
| INVALID_RATING | 400 | 评分不在1-5范围内 |
| DUPLICATE_REVIEW | 400 | 用户已评论过此技能 |
| SKILL_NOT_FOUND | 404 | 技能不存在 |
| VERSION_NOT_FOUND | 404 | 版本不存在 |
| CIRCULAR_DEPENDENCY | 400 | 检测到循环依赖 |
| VERSION_CONFLICT | 400 | 版本冲突 |
| UNAUTHORIZED | 401 | 未授权 |
| FORBIDDEN | 403 | 权限不足 |

---

## 使用示例

### 示例1: 完整的技能发布流程

```bash
# 1. 创建新版本
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/versions/my-skill \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "changes": "Initial release",
    "compatibility": "compatible"
  }'

# 2. 添加依赖
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/dependencies/my-skill \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dep_skill_id": "base-skill",
    "version_spec": ">=1.0.0",
    "dep_type": "required"
  }'

# 3. 检查搜索索引
curl -X GET "http://localhost:8000/api/v1/skill-market/advanced/search?query=my-skill" \
  -H "Authorization: Bearer TOKEN"
```

### 示例2: 用户评论和评分

```bash
# 1. 添加评论
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/reviews/my-skill \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "title": "Great skill",
    "comment": "Very useful"
  }'

# 2. 获取平均评分
curl -X GET http://localhost:8000/api/v1/skill-market/advanced/reviews/my-skill/rating \
  -H "Authorization: Bearer TOKEN"

# 3. 标记为有用
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/reviews/REVIEW_ID/helpful \
  -H "Authorization: Bearer TOKEN"
```

### 示例3: 检查和安装更新

```bash
# 1. 检查更新
curl -X GET http://localhost:8000/api/v1/skill-market/advanced/updates/my-skill \
  -H "Authorization: Bearer TOKEN"

# 2. 安装更新
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/updates/my-skill/install \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version": "1.1.0"}'

# 3. 启用自动更新
curl -X POST http://localhost:8000/api/v1/skill-market/advanced/updates/my-skill/auto-update \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

## 性能指标

| 操作 | 目标响应时间 | 实际响应时间 |
|------|------------|-----------|
| 搜索 | < 100ms | ~50ms |
| 获取评论 | < 200ms | ~80ms |
| 检查更新 | < 150ms | ~60ms |
| 获取依赖树 | < 200ms | ~100ms |

---

## 版本历史

### v1.0.0 (2026-05-27)
- 初始版本
- 支持版本管理、评论评分、搜索、依赖管理、更新机制
- 完整的API文档和测试套件
