# X-Agent 云端服务架构设计

**版本：** v1.0  
**日期：** 2026-05-27  
**目标：** 支持Web、桌面、移动三端同步的云端服务体系

---

## 1. 架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    客户端层 (Client Layer)                   │
│  Web UI · Desktop App · Mobile App · CLI · 第三方集成         │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌──────▼────────┐
│  REST API    │  │  WebSocket    │
│  (同步/查询)  │  │  (实时推送)    │
└───────┬──────┘  └──────┬────────┘
        │                 │
        └────────┬────────┘
                 │
        ┌────────▼────────────────────────────┐
        │    API网关 & 认证授权层              │
        │  (Rate Limit · Auth · CORS)         │
        └────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    │            │            │              │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐  ┌────▼────┐
│ 同步   │  │ 冲突   │  │ 版本   │  │ 加密    │
│ 引擎   │  │ 解决   │  │ 控制   │  │ 服务    │
└───┬────┘  └───┬────┘  └───┬────┘  └────┬────┘
    │           │           │            │
    └───────────┼───────────┼────────────┘
                │           │
        ┌───────▼───────────▼──────────┐
        │   业务逻辑层 (Service Layer)  │
        │  Agent · Memory · Workflow   │
        │  Browser · Tools · Plugins   │
        └───────┬──────────────────────┘
                │
    ┌───────────┼───────────┬──────────────┐
    │           │           │              │
┌───▼────┐  ┌──▼────┐  ┌──▼────┐  ┌────▼────┐
│PostgreSQL│ │Redis  │  │Qdrant │  │ S3/OSS  │
│(关系数据)│ │(缓存) │  │(向量) │  │(对象)   │
└──────────┘ └───────┘  └───────┘  └─────────┘
```

### 1.2 核心特性

- **实时同步**：WebSocket推送，毫秒级延迟
- **冲突解决**：CRDT + 向量时钟 + 最后写入胜利
- **端到端加密**：零知识证明，服务端无法读取用户数据
- **版本控制**：完整的变更历史和回滚能力
- **离线支持**：本地优先，自动同步
- **可扩展性**：微服务架构，支持水平扩展

---

## 2. 核心服务模块

### 2.1 同步服务 (Sync Service)

**职责**：
- 处理客户端数据变更
- 维护同步状态
- 管理版本向量
- 触发冲突检测

**关键流程**：
```
客户端变更 → 版本检查 → 冲突检测 → 应用变更 → 广播更新 → 客户端确认
```

**数据结构**：
```python
class SyncOperation:
    id: str                    # 操作ID
    client_id: str            # 客户端ID
    entity_type: str          # 实体类型 (memory/workflow/run)
    entity_id: str            # 实体ID
    operation: str            # create/update/delete
    timestamp: datetime       # 操作时间戳
    vector_clock: dict        # 向量时钟
    data: dict                # 变更数据
    checksum: str             # 数据校验和
    encrypted: bool           # 是否加密
```

### 2.2 冲突解决服务 (Conflict Resolution)

**冲突检测策略**：
1. **向量时钟**：检测因果关系
2. **时间戳**：最后写入胜利 (LWW)
3. **内容哈希**：检测实际冲突
4. **CRDT**：可交换的数据结构

**冲突类型**：
- 并发修改同一字段
- 删除与修改冲突
- 跨端数据不一致

**解决方案**：
```python
class ConflictResolution:
    STRATEGIES = {
        "lww": "Last Write Wins",           # 最后写入胜利
        "crdt": "Conflict-free RDT",        # 无冲突复制数据类型
        "manual": "Manual Resolution",      # 人工审核
        "merge": "Automatic Merge",         # 自动合并
    }
```

### 2.3 版本控制服务 (Version Control)

**功能**：
- 维护完整的变更历史
- 支持时间点恢复
- 生成变更日志
- 支持分支与合并

**版本模型**：
```python
class VersionSnapshot:
    version_id: str           # 版本ID
    entity_id: str            # 实体ID
    parent_version: str       # 父版本
    timestamp: datetime       # 创建时间
    author: str               # 作者
    message: str              # 变更说明
    data: dict                # 完整数据
    diff: dict                # 差异信息
    checksum: str             # 校验和
```

### 2.4 加密服务 (Encryption Service)

**加密方案**：
- **传输层**：TLS 1.3
- **存储层**：AES-256-GCM
- **端到端**：RSA-4096 + AES-256
- **密钥管理**：KMS集成

**零知识证明**：
- 服务端无法访问明文数据
- 支持加密数据的搜索
- 支持加密数据的同步

---

## 3. 数据存储架构

### 3.1 PostgreSQL (关系数据)

**主要表**：
- `sync_operations` - 同步操作日志
- `version_snapshots` - 版本快照
- `conflict_records` - 冲突记录
- `sync_state` - 同步状态
- `encryption_keys` - 加密密钥

### 3.2 Redis (缓存层)

**用途**：
- 实时同步队列
- 会话状态
- 冲突检测缓存
- 速率限制

**关键数据**：
```
sync:queue:{client_id}        # 待同步操作队列
sync:state:{entity_id}        # 实体同步状态
conflict:pending:{entity_id}  # 待解决冲突
session:{session_id}          # 会话信息
```

### 3.3 Qdrant (向量数据库)

**用途**：
- 记忆向量存储
- 语义搜索
- 相似度计算

### 3.4 S3/OSS (对象存储)

**用途**：
- 大文件存储
- 备份存档
- 加密数据存储

---

## 4. 实时同步流程

### 4.1 客户端发起同步

```
1. 客户端生成操作
   ├─ 生成操作ID
   ├─ 记录向量时钟
   ├─ 计算数据校验和
   └─ 加密敏感数据

2. 发送到服务器
   ├─ 通过WebSocket或REST
   ├─ 包含认证令牌
   └─ 附加客户端元数据

3. 服务器接收
   ├─ 验证签名
   ├─ 检查权限
   └─ 记录操作时间戳
```

### 4.2 服务器处理

```
1. 冲突检测
   ├─ 检查向量时钟
   ├─ 比较时间戳
   ├─ 验证数据完整性
   └─ 识别冲突

2. 冲突解决
   ├─ 应用解决策略
   ├─ 生成合并结果
   ├─ 记录冲突日志
   └─ 通知相关方

3. 数据持久化
   ├─ 写入PostgreSQL
   ├─ 更新Redis缓存
   ├─ 记录版本快照
   └─ 生成审计日志

4. 广播更新
   ├─ 推送到其他客户端
   ├─ 更新同步状态
   ├─ 触发相关业务逻辑
   └─ 记录同步事件
```

### 4.3 客户端接收

```
1. 接收更新
   ├─ 验证签名
   ├─ 检查版本号
   └─ 解密数据

2. 本地应用
   ├─ 合并到本地状态
   ├─ 更新UI
   ├─ 触发回调
   └─ 记录同步时间

3. 确认同步
   ├─ 发送确认消息
   ├─ 更新本地向量时钟
   └─ 清理本地队列
```

---

## 5. 冲突解决策略

### 5.1 向量时钟

```python
class VectorClock:
    """用于检测因果关系和并发操作"""
    
    def __init__(self, client_id: str):
        self.clock = {client_id: 0}
    
    def increment(self, client_id: str):
        """递增指定客户端的时钟"""
        self.clock[client_id] = self.clock.get(client_id, 0) + 1
    
    def merge(self, other: 'VectorClock'):
        """合并两个向量时钟"""
        for client_id, value in other.clock.items():
            self.clock[client_id] = max(self.clock.get(client_id, 0), value)
    
    def happens_before(self, other: 'VectorClock') -> bool:
        """检查是否发生在other之前"""
        less_or_equal = all(
            self.clock.get(c, 0) <= other.clock.get(c, 0)
            for c in set(self.clock.keys()) | set(other.clock.keys())
        )
        strictly_less = any(
            self.clock.get(c, 0) < other.clock.get(c, 0)
            for c in set(self.clock.keys()) | set(other.clock.keys())
        )
        return less_or_equal and strictly_less
```

### 5.2 CRDT (无冲突复制数据类型)

```python
class CRDTCounter:
    """支持并发增减的计数器"""
    
    def __init__(self):
        self.increments = {}  # {client_id: count}
        self.decrements = {}  # {client_id: count}
    
    def increment(self, client_id: str, amount: int = 1):
        self.increments[client_id] = self.increments.get(client_id, 0) + amount
    
    def decrement(self, client_id: str, amount: int = 1):
        self.decrements[client_id] = self.decrements.get(client_id, 0) + amount
    
    def value(self) -> int:
        """计算当前值，无需冲突解决"""
        return sum(self.increments.values()) - sum(self.decrements.values())
    
    def merge(self, other: 'CRDTCounter'):
        """合并两个计数器"""
        for client_id, count in other.increments.items():
            self.increments[client_id] = max(
                self.increments.get(client_id, 0), count
            )
        for client_id, count in other.decrements.items():
            self.decrements[client_id] = max(
                self.decrements.get(client_id, 0), count
            )
```

### 5.3 最后写入胜利 (LWW)

```python
class LastWriteWins:
    """基于时间戳的冲突解决"""
    
    @staticmethod
    def resolve(operations: list[SyncOperation]) -> SyncOperation:
        """选择最新的操作"""
        return max(operations, key=lambda op: (op.timestamp, op.id))
```

---

## 6. 加密与安全

### 6.1 端到端加密流程

```
客户端明文数据
    ↓
生成会话密钥 (AES-256)
    ↓
加密数据
    ↓
用服务器公钥加密会话密钥 (RSA-4096)
    ↓
发送到服务器
    ↓
服务器用私钥解密会话密钥
    ↓
用会话密钥解密数据
    ↓
处理数据
    ↓
用客户端公钥加密响应
    ↓
发送回客户端
    ↓
客户端用私钥解密
```

### 6.2 零知识证明

**应用场景**：
- 验证数据完整性而不泄露内容
- 证明拥有某个密钥而不泄露密钥
- 验证计算结果而不泄露中间过程

**实现**：
```python
class ZeroKnowledgeProof:
    """零知识证明实现"""
    
    @staticmethod
    def prove_knowledge_of_secret(secret: bytes, challenge: bytes) -> bytes:
        """证明知道某个秘密而不泄露秘密"""
        # 使用Schnorr协议或类似方案
        pass
    
    @staticmethod
    def verify_proof(proof: bytes, challenge: bytes, public_key: bytes) -> bool:
        """验证零知识证明"""
        pass
```

### 6.3 密钥管理

**密钥类型**：
- **主密钥 (Master Key)**：存储在KMS中
- **数据加密密钥 (DEK)**：用于加密数据
- **密钥加密密钥 (KEK)**：用于加密DEK

**密钥轮换**：
- 定期轮换主密钥
- 自动重新加密数据
- 保留旧密钥用于解密历史数据

---

## 7. 可扩展性设计

### 7.1 水平扩展

**API服务器**：
- 无状态设计
- 负载均衡
- 自动扩展

**数据库**：
- 读写分离
- 分片策略
- 副本集

**缓存层**：
- Redis集群
- 一致性哈希
- 自动故障转移

### 7.2 分片策略

```python
class ShardingStrategy:
    """数据分片策略"""
    
    @staticmethod
    def get_shard_id(entity_id: str, shard_count: int) -> int:
        """根据实体ID计算分片ID"""
        return hash(entity_id) % shard_count
    
    @staticmethod
    def get_shard_key(tenant_id: str, entity_id: str) -> str:
        """生成分片键"""
        return f"{tenant_id}:{entity_id}"
```

---

## 8. 监控与可观测性

### 8.1 关键指标

- **同步延迟**：操作从客户端到服务器的时间
- **冲突率**：发生冲突的操作比例
- **同步成功率**：成功同步的操作比例
- **数据一致性**：客户端与服务器数据的一致性

### 8.2 日志与追踪

```python
class SyncMetrics:
    """同步指标收集"""
    
    def record_sync_operation(self, operation: SyncOperation):
        """记录同步操作"""
        # 记录到Prometheus/Grafana
        pass
    
    def record_conflict(self, conflict: ConflictRecord):
        """记录冲突"""
        pass
    
    def record_latency(self, latency_ms: float):
        """记录延迟"""
        pass
```

---

## 9. 部署拓扑

### 9.1 开发环境

```
单机部署
├─ PostgreSQL
├─ Redis
├─ Qdrant
└─ X-Agent API (单实例)
```

### 9.2 生产环境

```
多区域部署
├─ 主区域
│  ├─ PostgreSQL (主从)
│  ├─ Redis (集群)
│  ├─ Qdrant (集群)
│  └─ X-Agent API (多实例)
├─ 备用区域
│  ├─ PostgreSQL (从)
│  ├─ Redis (从)
│  ├─ Qdrant (从)
│  └─ X-Agent API (多实例)
└─ CDN/缓存层
```

---

## 10. 故障恢复

### 10.1 故障检测

- 心跳检测
- 健康检查
- 异常监控

### 10.2 自动故障转移

- 主从切换
- 副本提升
- 自动重连

### 10.3 数据恢复

- 增量备份
- 时间点恢复
- 跨区域恢复

---

## 11. 性能优化

### 11.1 缓存策略

- 多层缓存
- 缓存预热
- 缓存失效策略

### 11.2 批量操作

- 批量同步
- 批量查询
- 批量更新

### 11.3 异步处理

- 后台任务队列
- 异步通知
- 延迟处理

---

## 12. 安全考虑

### 12.1 认证与授权

- JWT令牌
- API密钥
- OAuth 2.0

### 12.2 速率限制

- 按用户限制
- 按IP限制
- 按操作类型限制

### 12.3 审计日志

- 所有操作记录
- 变更追踪
- 合规性报告

---

## 13. 后续扩展

### 13.1 高级功能

- 实时协作编辑
- 多人同步
- 权限管理
- 审批流程

### 13.2 集成能力

- 第三方API集成
- Webhook支持
- 插件系统
- 工作流自动化

### 13.3 分析能力

- 使用统计
- 性能分析
- 用户行为分析
- 数据挖掘

---

## 总结

本架构设计提供了一个完整的、可扩展的、安全的云端同步服务体系，支持Web、桌面、移动三端的实时同步，具有强大的冲突解决能力和端到端加密保护。
