# X-Agent 云端服务 OpenAPI 规范

**版本：** 1.0.0  
**日期：** 2026-05-27

---

## API 概览

### 基础信息

```yaml
openapi: 3.0.0
info:
  title: X-Agent Cloud Sync API
  version: 1.0.0
  description: 支持三端同步的云端服务API
  contact:
    name: X-Agent Team
    url: https://x-agent.io
  license:
    name: MIT

servers:
  - url: https://api.x-agent.io/v1
    description: 生产环境
  - url: https://staging-api.x-agent.io/v1
    description: 测试环境
  - url: http://localhost:8000/v1
    description: 本地开发

security:
  - bearerAuth: []
  - apiKeyAuth: []
```

---

## 1. 认证与授权

### 1.1 Bearer Token

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT令牌认证
```

**请求示例**：
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  https://api.x-agent.io/v1/sync/operations
```

### 1.2 API Key

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: API密钥认证
```

**请求示例**：
```bash
curl -H "X-API-Key: sk_live_..." \
  https://api.x-agent.io/v1/sync/operations
```

---

## 2. 同步操作 API

### 2.1 提交同步操作

**端点**：`POST /sync/operations`

**描述**：客户端提交数据变更操作

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          client_id:
            type: string
            description: 客户端ID
          entity_type:
            type: string
            enum: [memory, workflow, run, agent, tool]
            description: 实体类型
          entity_id:
            type: string
            description: 实体ID
          operation:
            type: string
            enum: [create, update, delete]
            description: 操作类型
          data:
            type: object
            description: 变更数据
          vector_clock:
            type: object
            additionalProperties:
              type: integer
            description: 向量时钟
          timestamp:
            type: string
            format: date-time
            description: 操作时间戳
          checksum:
            type: string
            description: 数据校验和
          encrypted:
            type: boolean
            description: 是否加密
        required:
          - client_id
          - entity_type
          - entity_id
          - operation
          - data
          - vector_clock
          - timestamp
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 操作成功
    content:
      application/json:
        schema:
          type: object
          properties:
            operation_id:
              type: string
              description: 操作ID
            status:
              type: string
              enum: [accepted, applied, conflicted]
              description: 操作状态
            version:
              type: string
              description: 新版本号
            conflict:
              type: object
              description: 冲突信息（如果有）
              properties:
                conflict_id:
                  type: string
                type:
                  type: string
                  enum: [concurrent_modification, delete_update, data_mismatch]
                resolution_strategy:
                  type: string
                  enum: [lww, crdt, manual, merge]
                details:
                  type: object
            timestamp:
              type: string
              format: date-time
```

**错误响应**：
```yaml
  '400':
    description: 请求格式错误
  '401':
    description: 认证失败
  '403':
    description: 权限不足
  '409':
    description: 冲突
  '500':
    description: 服务器错误
```

**示例请求**：
```json
{
  "client_id": "client_123",
  "entity_type": "memory",
  "entity_id": "mem_456",
  "operation": "update",
  "data": {
    "content": "Updated memory content",
    "tags": ["important", "recent"]
  },
  "vector_clock": {
    "client_123": 5,
    "client_789": 3
  },
  "timestamp": "2026-05-27T10:30:00Z",
  "checksum": "abc123def456",
  "encrypted": false
}
```

**示例响应**：
```json
{
  "operation_id": "op_789",
  "status": "applied",
  "version": "v2.5",
  "timestamp": "2026-05-27T10:30:01Z"
}
```

---

### 2.2 获取同步操作

**端点**：`GET /sync/operations/{operation_id}`

**描述**：获取指定操作的详细信息

**参数**：
```yaml
parameters:
  - name: operation_id
    in: path
    required: true
    schema:
      type: string
    description: 操作ID
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 操作详情
    content:
      application/json:
        schema:
          type: object
          properties:
            operation_id:
              type: string
            client_id:
              type: string
            entity_type:
              type: string
            entity_id:
              type: string
            operation:
              type: string
            data:
              type: object
            vector_clock:
              type: object
            timestamp:
              type: string
              format: date-time
            status:
              type: string
            version:
              type: string
```

---

### 2.3 批量提交同步操作

**端点**：`POST /sync/operations/batch`

**描述**：批量提交多个同步操作

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          operations:
            type: array
            items:
              $ref: '#/components/schemas/SyncOperation'
            description: 操作列表
          atomic:
            type: boolean
            description: 是否原子性执行
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 批量操作结果
    content:
      application/json:
        schema:
          type: object
          properties:
            results:
              type: array
              items:
                type: object
                properties:
                  operation_id:
                    type: string
                  status:
                    type: string
                  error:
                    type: string
            failed_count:
              type: integer
            success_count:
              type: integer
```

---

## 3. 冲突解决 API

### 3.1 获取待解决冲突

**端点**：`GET /conflicts/pending`

**描述**：获取当前待解决的冲突列表

**查询参数**：
```yaml
parameters:
  - name: entity_type
    in: query
    schema:
      type: string
    description: 实体类型过滤
  - name: limit
    in: query
    schema:
      type: integer
      default: 20
    description: 返回数量限制
  - name: offset
    in: query
    schema:
      type: integer
      default: 0
    description: 分页偏移
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 冲突列表
    content:
      application/json:
        schema:
          type: object
          properties:
            conflicts:
              type: array
              items:
                type: object
                properties:
                  conflict_id:
                    type: string
                  entity_id:
                    type: string
                  entity_type:
                    type: string
                  type:
                    type: string
                    enum: [concurrent_modification, delete_update, data_mismatch]
                  operations:
                    type: array
                    items:
                      type: object
                  created_at:
                    type: string
                    format: date-time
                  status:
                    type: string
                    enum: [pending, resolved, manual_review]
            total:
              type: integer
            limit:
              type: integer
            offset:
              type: integer
```

---

### 3.2 解决冲突

**端点**：`POST /conflicts/{conflict_id}/resolve`

**描述**：提交冲突解决方案

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          strategy:
            type: string
            enum: [lww, crdt, manual, merge]
            description: 解决策略
          resolution:
            type: object
            description: 解决方案
          reason:
            type: string
            description: 解决原因
        required:
          - strategy
          - resolution
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 冲突已解决
    content:
      application/json:
        schema:
          type: object
          properties:
            conflict_id:
              type: string
            status:
              type: string
            resolved_at:
              type: string
              format: date-time
            result:
              type: object
```

---

### 3.3 获取冲突历史

**端点**：`GET /conflicts/history`

**描述**：获取已解决的冲突历史

**查询参数**：
```yaml
parameters:
  - name: entity_id
    in: query
    schema:
      type: string
    description: 实体ID过滤
  - name: start_date
    in: query
    schema:
      type: string
      format: date-time
    description: 开始日期
  - name: end_date
    in: query
    schema:
      type: string
      format: date-time
    description: 结束日期
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 冲突历史
    content:
      application/json:
        schema:
          type: object
          properties:
            conflicts:
              type: array
              items:
                type: object
            total:
              type: integer
```

---

## 4. 版本控制 API

### 4.1 获取版本历史

**端点**：`GET /versions/{entity_id}`

**描述**：获取实体的版本历史

**参数**：
```yaml
parameters:
  - name: entity_id
    in: path
    required: true
    schema:
      type: string
  - name: limit
    in: query
    schema:
      type: integer
      default: 20
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 版本列表
    content:
      application/json:
        schema:
          type: object
          properties:
            versions:
              type: array
              items:
                type: object
                properties:
                  version_id:
                    type: string
                  parent_version:
                    type: string
                  timestamp:
                    type: string
                    format: date-time
                  author:
                    type: string
                  message:
                    type: string
                  checksum:
                    type: string
            total:
              type: integer
```

---

### 4.2 获取版本快照

**端点**：`GET /versions/{entity_id}/{version_id}`

**描述**：获取指定版本的完整数据

**参数**：
```yaml
parameters:
  - name: entity_id
    in: path
    required: true
    schema:
      type: string
  - name: version_id
    in: path
    required: true
    schema:
      type: string
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 版本快照
    content:
      application/json:
        schema:
          type: object
          properties:
            version_id:
              type: string
            entity_id:
              type: string
            data:
              type: object
            diff:
              type: object
            timestamp:
              type: string
              format: date-time
```

---

### 4.3 恢复到指定版本

**端点**：`POST /versions/{entity_id}/restore`

**描述**：将实体恢复到指定版本

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          version_id:
            type: string
            description: 目标版本ID
          reason:
            type: string
            description: 恢复原因
        required:
          - version_id
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 恢复成功
    content:
      application/json:
        schema:
          type: object
          properties:
            entity_id:
              type: string
            new_version:
              type: string
            restored_at:
              type: string
              format: date-time
```

---

## 5. 加密服务 API

### 5.1 获取公钥

**端点**：`GET /encryption/public-key`

**描述**：获取服务器公钥用于端到端加密

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 公钥信息
    content:
      application/json:
        schema:
          type: object
          properties:
            public_key:
              type: string
              description: PEM格式的公钥
            key_id:
              type: string
              description: 密钥ID
            algorithm:
              type: string
              description: 加密算法
            expires_at:
              type: string
              format: date-time
```

---

### 5.2 加密数据

**端点**：`POST /encryption/encrypt`

**描述**：使用服务器公钥加密数据

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          data:
            type: string
            description: 待加密数据
          algorithm:
            type: string
            enum: [RSA-4096, AES-256-GCM]
            description: 加密算法
        required:
          - data
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 加密结果
    content:
      application/json:
        schema:
          type: object
          properties:
            encrypted_data:
              type: string
            key_id:
              type: string
            algorithm:
              type: string
```

---

### 5.3 解密数据

**端点**：`POST /encryption/decrypt`

**描述**：解密客户端发送的数据

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          encrypted_data:
            type: string
          key_id:
            type: string
          algorithm:
            type: string
        required:
          - encrypted_data
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 解密结果
    content:
      application/json:
        schema:
          type: object
          properties:
            data:
              type: string
```

---

### 5.4 零知识证明

**端点**：`POST /encryption/zkp/prove`

**描述**：生成零知识证明

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          secret_hash:
            type: string
            description: 秘密的哈希值
          challenge:
            type: string
            description: 挑战值
        required:
          - secret_hash
          - challenge
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 证明生成成功
    content:
      application/json:
        schema:
          type: object
          properties:
            proof:
              type: string
            challenge:
              type: string
```

---

### 5.5 验证零知识证明

**端点**：`POST /encryption/zkp/verify`

**描述**：验证零知识证明

**请求体**：
```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        properties:
          proof:
            type: string
          challenge:
            type: string
          public_key:
            type: string
        required:
          - proof
          - challenge
          - public_key
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 验证结果
    content:
      application/json:
        schema:
          type: object
          properties:
            valid:
              type: boolean
            verified_at:
              type: string
              format: date-time
```

---

## 6. 实时同步 WebSocket API

### 6.1 连接WebSocket

**端点**：`WS /sync/ws`

**描述**：建立WebSocket连接用于实时同步

**连接参数**：
```
ws://api.x-agent.io/v1/sync/ws?token=<JWT>&client_id=<CLIENT_ID>
```

**连接消息**：
```json
{
  "type": "connect",
  "client_id": "client_123",
  "version": "1.0",
  "capabilities": ["sync", "conflict_resolution", "encryption"]
}
```

---

### 6.2 发送同步操作

**消息类型**：`sync_operation`

```json
{
  "type": "sync_operation",
  "operation": {
    "client_id": "client_123",
    "entity_type": "memory",
    "entity_id": "mem_456",
    "operation": "update",
    "data": {...},
    "vector_clock": {...},
    "timestamp": "2026-05-27T10:30:00Z"
  }
}
```

---

### 6.3 接收同步更新

**消息类型**：`sync_update`

```json
{
  "type": "sync_update",
  "operation_id": "op_789",
  "entity_type": "memory",
  "entity_id": "mem_456",
  "data": {...},
  "version": "v2.5",
  "timestamp": "2026-05-27T10:30:01Z",
  "from_client": "client_789"
}
```

---

### 6.4 冲突通知

**消息类型**：`conflict_detected`

```json
{
  "type": "conflict_detected",
  "conflict_id": "conf_123",
  "entity_id": "mem_456",
  "type": "concurrent_modification",
  "operations": [...],
  "suggested_resolution": {...}
}
```

---

### 6.5 心跳

**消息类型**：`ping`

```json
{
  "type": "ping",
  "timestamp": "2026-05-27T10:30:00Z"
}
```

**响应**：
```json
{
  "type": "pong",
  "timestamp": "2026-05-27T10:30:01Z"
}
```

---

## 7. 同步状态 API

### 7.1 获取同步状态

**端点**：`GET /sync/status`

**描述**：获取当前同步状态

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 同步状态
    content:
      application/json:
        schema:
          type: object
          properties:
            client_id:
              type: string
            last_sync:
              type: string
              format: date-time
            pending_operations:
              type: integer
            conflicts:
              type: integer
            vector_clock:
              type: object
            status:
              type: string
              enum: [synced, syncing, pending, error]
```

---

### 7.2 获取同步统计

**端点**：`GET /sync/stats`

**描述**：获取同步统计信息

**查询参数**：
```yaml
parameters:
  - name: period
    in: query
    schema:
      type: string
      enum: [hour, day, week, month]
      default: day
```

**响应 (200 OK)**：
```yaml
responses:
  '200':
    description: 同步统计
    content:
      application/json:
        schema:
          type: object
          properties:
            total_operations:
              type: integer
            successful_operations:
              type: integer
            failed_operations:
              type: integer
            conflicts_detected:
              type: integer
            conflicts_resolved:
              type: integer
            average_latency_ms:
              type: number
            success_rate:
              type: number
            period:
              type: string
```

---

## 8. 错误处理

### 8.1 错误响应格式

```yaml
components:
  schemas:
    Error:
      type: object
      properties:
        error:
          type: object
          properties:
            code:
              type: string
              description: 错误代码
            message:
              type: string
              description: 错误消息
            details:
              type: object
              description: 错误详情
            timestamp:
              type: string
              format: date-time
            request_id:
              type: string
              description: 请求ID用于追踪
```

### 8.2 常见错误代码

| 代码 | HTTP状态 | 说明 |
|------|---------|------|
| INVALID_REQUEST | 400 | 请求格式错误 |
| UNAUTHORIZED | 401 | 认证失败 |
| FORBIDDEN | 403 | 权限不足 |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 数据冲突 |
| RATE_LIMITED | 429 | 请求过于频繁 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| SERVICE_UNAVAILABLE | 503 | 服务不可用 |

---

## 9. 速率限制

### 9.1 限制规则

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1622160000
```

### 9.2 限制策略

- 按用户：1000请求/小时
- 按IP：10000请求/小时
- 按操作类型：100请求/分钟

---

## 10. 数据模型

### 10.1 SyncOperation

```yaml
components:
  schemas:
    SyncOperation:
      type: object
      properties:
        id:
          type: string
        client_id:
          type: string
        entity_type:
          type: string
        entity_id:
          type: string
        operation:
          type: string
        timestamp:
          type: string
          format: date-time
        vector_clock:
          type: object
        data:
          type: object
        checksum:
          type: string
        encrypted:
          type: boolean
```

### 10.2 ConflictRecord

```yaml
    ConflictRecord:
      type: object
      properties:
        conflict_id:
          type: string
        entity_id:
          type: string
        type:
          type: string
        operations:
          type: array
        created_at:
          type: string
          format: date-time
        status:
          type: string
```

### 10.3 VersionSnapshot

```yaml
    VersionSnapshot:
      type: object
      properties:
        version_id:
          type: string
        entity_id:
          type: string
        parent_version:
          type: string
        timestamp:
          type: string
          format: date-time
        author:
          type: string
        message:
          type: string
        data:
          type: object
        diff:
          type: object
        checksum:
          type: string
```

---

## 总结

本OpenAPI规范定义了X-Agent云端服务的完整API接口，包括同步操作、冲突解决、版本控制、加密服务和实时WebSocket通信。所有接口都遵循RESTful设计原则，支持标准的HTTP方法和状态码。
