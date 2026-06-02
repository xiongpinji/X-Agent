# X-Agent 云端服务实现指南

**版本：** 1.0.0  
**日期：** 2026-05-27

---

## 1. 快速开始

### 1.1 本地开发环境

```bash
# 克隆项目
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install -r cloud/requirements.txt

# 启动Docker容器
docker-compose up -d

# 初始化数据库
python -m alembic upgrade head

# 启动API服务
uvicorn backend.app.main:app --reload --port 8000
```

### 1.2 验证部署

```bash
# 检查健康状态
curl http://localhost:8000/health

# 检查就绪状态
curl http://localhost:8000/ready

# 获取API文档
open http://localhost:8000/docs
```

---

## 2. 核心模块集成

### 2.1 同步服务集成

```python
# backend/app/api/sync.py

from fastapi import APIRouter, Depends, HTTPException
from cloud.sync_service import SyncService, SyncOperation

router = APIRouter(prefix="/sync", tags=["sync"])
sync_service = SyncService()

@router.post("/operations")
async def submit_operation(operation: SyncOperation):
    """提交同步操作"""
    try:
        result = sync_service.submit_operation(operation)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/operations/{operation_id}")
async def get_operation(operation_id: str):
    """获取操作详情"""
    if operation_id not in sync_service.operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    return sync_service.operations[operation_id]

@router.get("/status")
async def get_sync_status(client_id: str):
    """获取同步状态"""
    return sync_service.get_sync_status(client_id)

@router.get("/stats")
async def get_sync_statistics(period: str = "day"):
    """获取同步统计"""
    return sync_service.get_sync_statistics(period)
```

### 2.2 加密服务集成

```python
# backend/app/api/encryption.py

from fastapi import APIRouter, HTTPException
from cloud.encryption_service import EncryptionService, EncryptedData

router = APIRouter(prefix="/encryption", tags=["encryption"])
encryption_service = EncryptionService()

@router.get("/public-key")
async def get_public_key(key_id: str = "master_key_001"):
    """获取公钥"""
    try:
        public_key = encryption_service.get_public_key(key_id)
        return {
            "public_key": public_key,
            "key_id": key_id,
            "algorithm": "RSA-4096"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/encrypt")
async def encrypt_data(data: str, key_id: str = "master_key_001"):
    """加密数据"""
    try:
        encrypted = encryption_service.encrypt_data(data, key_id)
        return encrypted.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/decrypt")
async def decrypt_data(encrypted_data: EncryptedData):
    """解密数据"""
    try:
        plaintext = encryption_service.decrypt_data(encrypted_data)
        return {"data": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 2.3 WebSocket 实时同步

```python
# backend/app/api/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from cloud.sync_service import SyncService

router = APIRouter(prefix="/ws", tags=["websocket"])
sync_service = SyncService()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/sync/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket同步端点"""
    await manager.connect(client_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "sync_operation":
                # 处理同步操作
                operation = data["operation"]
                result = sync_service.submit_operation(operation)
                
                # 广播更新
                await manager.broadcast({
                    "type": "sync_update",
                    "result": result
                })
            
            elif data["type"] == "ping":
                # 心跳
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(UTC).isoformat()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
```

---

## 3. 数据库初始化

### 3.1 迁移脚本

```python
# deployment/migrations/001_initial_schema.py

from alembic import op
import sqlalchemy as sa

def upgrade():
    """创建初始表"""
    
    # sync_operations 表
    op.create_table(
        'sync_operations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.String(255), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=False),
        sa.Column('operation', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_sync_ops_client_id', 'sync_operations', ['client_id'])
    op.create_index('idx_sync_ops_entity', 'sync_operations', ['entity_type', 'entity_id'])
    op.create_index('idx_sync_ops_status', 'sync_operations', ['status'])

def downgrade():
    """删除表"""
    op.drop_table('sync_operations')
```

### 3.2 初始化脚本

```bash
#!/bin/bash
# deployment/init_db.sh

set -e

echo "Initializing database..."

# 等待PostgreSQL启动
until pg_isready -h postgres -U xagent; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

# 运行迁移
alembic upgrade head

# 初始化数据
psql -h postgres -U xagent -d xagent_db << EOF
-- 插入默认加密密钥
INSERT INTO encryption_keys (key_id, key_type, algorithm, status)
VALUES ('master_key_001', 'master', 'RSA-4096', 'active');

-- 创建默认租户
INSERT INTO tenants (id, name, status)
VALUES ('default_tenant', 'Default Tenant', 'active');
EOF

echo "Database initialization completed!"
```

---

## 4. 测试套件

### 4.1 单元测试

```python
# tests/test_sync_service.py

import pytest
from cloud.sync_service import SyncService, SyncOperation, VectorClock

@pytest.fixture
def sync_service():
    return SyncService()

def test_submit_operation(sync_service):
    """测试提交操作"""
    op = SyncOperation(
        client_id="client_1",
        entity_type="memory",
        entity_id="mem_123",
        operation="create",
        data={"content": "test"}
    )
    
    result = sync_service.submit_operation(op)
    
    assert result["status"] == "applied"
    assert result["operation_id"] == op.id

def test_conflict_detection(sync_service):
    """测试冲突检测"""
    op1 = SyncOperation(
        client_id="client_1",
        entity_type="memory",
        entity_id="mem_123",
        operation="update",
        data={"content": "version1"}
    )
    
    op2 = SyncOperation(
        client_id="client_2",
        entity_type="memory",
        entity_id="mem_123",
        operation="update",
        data={"content": "version2"},
        vector_clock=VectorClock(clock={"client_1": 1})
    )
    
    sync_service.submit_operation(op1)
    result = sync_service.submit_operation(op2)
    
    assert result["status"] == "conflicted"

def test_conflict_resolution(sync_service):
    """测试冲突解决"""
    # ... 设置冲突 ...
    
    result = sync_service.resolve_conflict(
        conflict_id="conf_123",
        strategy="lww"
    )
    
    assert result["status"] == "resolved"
```

### 4.2 集成测试

```python
# tests/test_api_integration.py

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_sync_operation_api(client):
    """测试同步操作API"""
    response = client.post("/v1/sync/operations", json={
        "client_id": "client_1",
        "entity_type": "memory",
        "entity_id": "mem_123",
        "operation": "create",
        "data": {"content": "test"},
        "vector_clock": {},
        "timestamp": "2026-05-27T10:00:00Z"
    })
    
    assert response.status_code == 200
    assert response.json()["status"] == "applied"

def test_encryption_api(client):
    """测试加密API"""
    # 获取公钥
    response = client.get("/v1/encryption/public-key")
    assert response.status_code == 200
    assert "public_key" in response.json()
    
    # 加密数据
    response = client.post("/v1/encryption/encrypt", json={
        "data": "sensitive data"
    })
    assert response.status_code == 200
    assert "encrypted_data" in response.json()
```

### 4.3 性能测试

```python
# tests/test_performance.py

import time
import pytest
from cloud.sync_service import SyncService, SyncOperation

@pytest.fixture
def sync_service():
    return SyncService()

def test_operation_throughput(sync_service):
    """测试操作吞吐量"""
    start_time = time.time()
    
    for i in range(1000):
        op = SyncOperation(
            client_id=f"client_{i % 10}",
            entity_type="memory",
            entity_id=f"mem_{i}",
            operation="create",
            data={"content": f"test_{i}"}
        )
        sync_service.submit_operation(op)
    
    elapsed = time.time() - start_time
    throughput = 1000 / elapsed
    
    print(f"Throughput: {throughput:.2f} ops/sec")
    assert throughput > 100  # 至少100 ops/sec

def test_conflict_resolution_latency(sync_service):
    """测试冲突解决延迟"""
    # ... 设置冲突 ...
    
    start_time = time.time()
    sync_service.resolve_conflict("conf_123", strategy="lww")
    elapsed = time.time() - start_time
    
    print(f"Conflict resolution latency: {elapsed*1000:.2f}ms")
    assert elapsed < 0.1  # 少于100ms
```

---

## 5. 监控与告警

### 5.1 关键指标

```python
# backend/app/services/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# 同步操作计数
sync_operations_total = Counter(
    'sync_operations_total',
    'Total sync operations',
    ['status']
)

# 同步延迟
sync_latency = Histogram(
    'sync_latency_seconds',
    'Sync operation latency',
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0)
)

# 冲突计数
conflicts_total = Counter(
    'conflicts_total',
    'Total conflicts detected',
    ['type']
)

# 待同步操作
pending_operations = Gauge(
    'pending_operations',
    'Number of pending operations'
)

def record_sync_operation(status: str, latency: float):
    """记录同步操作"""
    sync_operations_total.labels(status=status).inc()
    sync_latency.observe(latency)
```

### 5.2 告警规则

```yaml
# monitoring/prometheus-rules.yml

groups:
- name: xagent
  rules:
  - alert: HighConflictRate
    expr: rate(conflicts_total[5m]) > 0.1
    for: 5m
    annotations:
      summary: "High conflict rate detected"
  
  - alert: HighSyncLatency
    expr: histogram_quantile(0.95, sync_latency_seconds) > 1
    for: 5m
    annotations:
      summary: "High sync latency detected"
  
  - alert: PendingOperationsBacklog
    expr: pending_operations > 1000
    for: 5m
    annotations:
      summary: "Large pending operations backlog"
```

---

## 6. 最佳实践

### 6.1 API设计

- 使用RESTful设计原则
- 版本化API端点 (`/v1/`, `/v2/`)
- 返回一致的错误格式
- 实现速率限制
- 使用JWT令牌认证

### 6.2 数据安全

- 所有敏感数据加密存储
- 使用HTTPS传输
- 实现端到端加密
- 定期轮换密钥
- 审计所有操作

### 6.3 性能优化

- 使用缓存减少数据库查询
- 批量操作
- 异步处理
- 数据库索引优化
- 连接池管理

### 6.4 可靠性

- 实现重试机制
- 优雅降级
- 断路器模式
- 健康检查
- 自动故障转移

---

## 7. 故障排查指南

### 7.1 常见问题

**问题**：同步操作失败
```bash
# 检查日志
docker logs xagent-api | grep ERROR

# 检查数据库连接
docker exec xagent-api python -c "
from backend.app.dependencies import get_db
db = get_db()
print('Database connection OK')
"
```

**问题**：高延迟
```bash
# 检查数据库性能
docker exec xagent-postgres psql -U xagent -d xagent_db -c "
SELECT query, calls, mean_time FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
"

# 检查Redis性能
docker exec xagent-redis redis-cli INFO stats
```

**问题**：内存泄漏
```bash
# 监控内存使用
docker stats xagent-api

# 分析内存
docker exec xagent-api python -m memory_profiler app.py
```

---

## 8. 升级与迁移

### 8.1 版本升级

```bash
# 备份数据
docker exec xagent-postgres pg_dump -U xagent xagent_db > backup.sql

# 停止服务
docker-compose down

# 更新代码
git pull origin main

# 运行迁移
docker-compose run xagent-api alembic upgrade head

# 启动服务
docker-compose up -d
```

### 8.2 数据迁移

```python
# scripts/migrate_data.py

def migrate_sync_operations():
    """迁移同步操作数据"""
    # 从旧系统读取数据
    old_data = read_from_old_system()
    
    # 转换格式
    new_data = transform_data(old_data)
    
    # 写入新系统
    write_to_new_system(new_data)
    
    # 验证
    verify_migration()
```

---

## 9. 文档与支持

### 9.1 API文档

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI规范: `http://localhost:8000/openapi.json`

### 9.2 开发资源

- 架构设计: `cloud/CLOUD_ARCHITECTURE.md`
- API规范: `cloud/OPENAPI_SPEC.md`
- 数据库Schema: `cloud/DATABASE_SCHEMA.md`
- 部署指南: `cloud/DEPLOYMENT_GUIDE.md`

### 9.3 社区支持

- GitHub Issues: https://github.com/x-agent/x-agent/issues
- 讨论区: https://github.com/x-agent/x-agent/discussions
- 文档: https://docs.x-agent.io

---

## 10. 下一步

### 10.1 短期计划

- [ ] 完成WebSocket实时同步
- [ ] 实现完整的冲突解决
- [ ] 添加更多加密算法
- [ ] 性能优化和基准测试

### 10.2 中期计划

- [ ] 多区域部署
- [ ] 高可用性配置
- [ ] 完整的监控和告警
- [ ] 自动化备份和恢复

### 10.3 长期计划

- [ ] 全球分布式部署
- [ ] 机器学习优化
- [ ] 高级分析功能
- [ ] 生态系统集成

---

## 总结

本实现指南提供了X-Agent云端服务的完整开发、部署和运维指南。通过遵循本指南，可以快速构建和部署一个高可用、高性能、安全可靠的云端同步服务。
