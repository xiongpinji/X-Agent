# X-Agent 本地端集成指南

**版本**: 1.0  
**日期**: 2026-05-27

---

## 1. 快速开始

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 初始化本地端

```python
from backend.local import (
    LocalConfig,
    ConfigManager,
    DatabaseConfig,
    LocalDatabase,
    EncryptionManager,
    SyncClient,
)

# 1. 配置
config = LocalConfig(
    db_path="~/.xagent/local.db",
    sync_enabled=True,
    encryption_enabled=True,
)
ConfigManager.initialize(config)

# 2. 初始化数据库
db_config = DatabaseConfig(db_path=config.db_path)
db = LocalDatabase(db_config)
db.initialize()

# 3. 初始化加密
encryption_manager = EncryptionManager()
encryption_manager.generate_master_key()

# 4. 初始化同步客户端
sync_client = SyncClient(db, cloud_api_client)
```

---

## 2. 核心功能使用

### 2.1 本地数据管理

#### 设置元数据

```python
metadata_id = db.set_metadata(
    entity_type="memory",
    entity_id="mem-123",
    local_version=1,
    cloud_version=0,
    is_encrypted=False,
    checksum="abc123",
)
```

#### 获取元数据

```python
metadata = db.get_metadata("memory", "mem-123")
print(metadata)
```

#### 更新同步状态

```python
db.update_sync_state(
    entity_type="memory",
    entity_id="mem-123",
    state="synced",
)
```

### 2.2 加密操作

#### 加密数据

```python
from backend.local import EncryptionManager

encryption_manager = EncryptionManager()
encryption_manager.generate_master_key()

plaintext = {"api_key": "secret123", "token": "abc"}
encrypted = encryption_manager.encrypt(plaintext)

print(encrypted)
# {
#     "encrypted_data": "...",
#     "iv": "...",
#     "salt": "...",
#     "algorithm": "AES-256-GCM",
# }
```

#### 解密数据

```python
decrypted = encryption_manager.decrypt_to_dict(
    encrypted["encrypted_data"],
    encrypted["iv"],
    encrypted["salt"],
)

print(decrypted)  # {"api_key": "secret123", "token": "abc"}
```

#### 敏感数据分类

```python
from backend.local import SensitiveDataClassifier

# 检查是否敏感
is_sensitive = SensitiveDataClassifier.is_sensitive({"api_key": "secret"})
print(is_sensitive)  # True

# 分类敏感级别
sensitivity = SensitiveDataClassifier.classify({"api_key": "secret"})
print(sensitivity)  # "secret"
```

### 2.3 同步操作

#### 入队同步操作

```python
import asyncio

async def sync_example():
    # 入队操作
    queue_id = await sync_client.enqueue_operation(
        entity_type="memory",
        entity_id="mem-123",
        operation="UPDATE",
        data={"content": "test"},
        priority=1,
    )
    
    print(f"Operation queued: {queue_id}")

asyncio.run(sync_example())
```

#### 执行同步

```python
async def perform_sync():
    batch = await sync_client.sync()
    
    print(f"Sync batch: {batch.id}")
    print(f"Status: {batch.status}")
    print(f"Operations: {len(batch.operations)}")
    print(f"Conflicts: {len(batch.conflicts)}")

asyncio.run(perform_sync())
```

#### 离线模式

```python
# 进入离线模式
sync_client.set_offline_mode(True)

# 离线时操作会加入离线队列
queue_id = await sync_client.enqueue_operation(
    entity_type="memory",
    entity_id="mem-123",
    operation="UPDATE",
    data={"content": "test"},
)

# 恢复连接
sync_client.set_offline_mode(False)

# 同步离线操作
await sync_client.sync_offline_operations()
```

### 2.4 冲突处理

#### 记录冲突

```python
conflict_id = db.log_conflict(
    entity_type="memory",
    entity_id="mem-123",
    conflict_type="UPDATE_CONFLICT",
    local_data={"content": "local"},
    cloud_data={"content": "cloud"},
    local_version=2,
    cloud_version=1,
)
```

#### 获取未解决的冲突

```python
conflicts = db.get_unresolved_conflicts()
for conflict in conflicts:
    print(f"Conflict: {conflict['entity_id']}")
    print(f"Type: {conflict['conflict_type']}")
```

#### 解决冲突

```python
db.resolve_conflict(
    conflict_id=conflict_id,
    resolution_strategy="LAST_WRITE_WINS",
    resolved_data={"content": "resolved"},
    resolved_by="system",
)
```

### 2.5 缓存管理

#### 设置缓存

```python
db.set_cache(
    entity_type="memory",
    entity_id="mem-123",
    cache_key="memory-content",
    cache_value={"content": "test"},
    ttl_seconds=3600,
)
```

#### 获取缓存

```python
cached = db.get_cache("memory-content")
if cached:
    print(f"Cache hit: {cached}")
```

#### 清理过期缓存

```python
deleted_count = db.cleanup_expired_cache()
print(f"Deleted {deleted_count} expired entries")
```

---

## 3. 配置管理

### 3.1 创建配置

```python
from backend.local import LocalConfig

config = LocalConfig(
    db_path="~/.xagent/local.db",
    sync_enabled=True,
    sync_interval_seconds=300,
    encryption_enabled=True,
    cache_enabled=True,
    offline_queue_enabled=True,
)
```

### 3.2 保存配置

```python
config.save_to_file("~/.xagent/config.json")
```

### 3.3 加载配置

```python
from backend.local import LocalConfig

config = LocalConfig.from_file("~/.xagent/config.json")
```

### 3.4 使用配置管理器

```python
from backend.local import ConfigManager

# 初始化
ConfigManager.initialize(config)

# 获取配置
current_config = ConfigManager.get_config()

# 更新配置
ConfigManager.update_config(sync_enabled=False)

# 保存配置
ConfigManager.save_config("~/.xagent/config.json")
```

---

## 4. 监控与统计

### 4.1 同步统计

```python
stats = db.get_sync_stats()
print(f"Pending syncs: {stats['pending_syncs']}")
print(f"Failed syncs: {stats['failed_syncs']}")
print(f"Unresolved conflicts: {stats['unresolved_conflicts']}")
print(f"Offline operations: {stats['offline_operations']}")
```

### 4.2 同步状态

```python
status = sync_client.get_sync_status()
print(f"Is syncing: {status['is_syncing']}")
print(f"Offline mode: {status['offline_mode']}")
print(f"Last sync: {status['last_sync_time']}")
```

### 4.3 数据库大小

```python
size_info = db.get_database_size()
print(f"Database size: {size_info['database_size_mb']} MB")
```

### 4.4 同步历史

```python
history = db.get_sync_history(entity_type="memory", limit=10)
for record in history:
    print(f"Operation: {record['operation']}")
    print(f"Status: {record['status']}")
    print(f"Duration: {record['duration_ms']}ms")
```

---

## 5. API集成

### 5.1 在FastAPI中集成

```python
from fastapi import FastAPI, Depends
from backend.local import LocalDatabase, SyncClient

app = FastAPI()

# 初始化
db = LocalDatabase(db_config)
db.initialize()
sync_client = SyncClient(db, cloud_api_client)

@app.on_event("startup")
async def startup():
    """启动时初始化"""
    pass

@app.on_event("shutdown")
async def shutdown():
    """关闭时清理"""
    db.close()

@app.post("/api/local/sync")
async def trigger_sync():
    """触发同步"""
    batch = await sync_client.sync()
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "operations": len(batch.operations),
        "conflicts": len(batch.conflicts),
    }

@app.get("/api/local/status")
async def get_status():
    """获取本地端状态"""
    return sync_client.get_sync_status()

@app.get("/api/local/conflicts")
async def get_conflicts():
    """获取未解决的冲突"""
    conflicts = db.get_unresolved_conflicts()
    return {"conflicts": conflicts}
```

### 5.2 中间件集成

```python
from fastapi import Request
from backend.local import LocalDatabase

class LocalCacheMiddleware:
    """本地缓存中间件"""
    
    def __init__(self, app, db: LocalDatabase):
        self.app = app
        self.db = db
    
    async def __call__(self, request: Request, call_next):
        # 检查缓存
        cache_key = f"{request.method}:{request.url.path}"
        cached = self.db.get_cache(cache_key)
        
        if cached:
            return cached
        
        response = await call_next(request)
        
        # 缓存响应
        if response.status_code == 200:
            self.db.set_cache(
                entity_type="api_response",
                entity_id=request.url.path,
                cache_key=cache_key,
                cache_value=response.body,
                ttl_seconds=300,
            )
        
        return response

# 使用中间件
app.add_middleware(LocalCacheMiddleware, db=db)
```

---

## 6. 最佳实践

### 6.1 数据安全

```python
# 1. 始终加密敏感数据
from backend.local import EncryptedDataStore

store = EncryptedDataStore(encryption_manager)

sensitive_data = {"api_key": "secret"}
stored = store.encrypt_and_store(
    data=sensitive_data,
    entity_type="config",
    entity_id="cfg-123",
    data_type="api_key",
)

# 2. 定期轮换密钥
from backend.local import KeyRotationManager

rotation_manager = KeyRotationManager(encryption_manager)
new_key = os.urandom(32)
new_version = rotation_manager.rotate_key(new_key)
```

### 6.2 同步优化

```python
# 1. 使用优先级
await sync_client.enqueue_operation(
    entity_type="memory",
    entity_id="mem-123",
    operation="UPDATE",
    data={"content": "test"},
    priority=10,  # 高优先级
)

# 2. 批量操作
for i in range(100):
    await sync_client.enqueue_operation(
        entity_type="memory",
        entity_id=f"mem-{i}",
        operation="CREATE",
        data={"content": f"test-{i}"},
    )

# 3. 注册回调
def on_sync_completed(event, data):
    print(f"Sync completed: {data['batch_id']}")

sync_client.register_sync_callback(on_sync_completed)
```

### 6.3 错误处理

```python
import asyncio

async def safe_sync():
    try:
        batch = await sync_client.sync()
        
        if batch.status == "failed":
            print(f"Sync failed: {batch.error}")
        elif batch.conflicts:
            print(f"Conflicts detected: {len(batch.conflicts)}")
        else:
            print("Sync successful")
            
    except Exception as e:
        print(f"Sync error: {e}")
        # 进入离线模式
        sync_client.set_offline_mode(True)

asyncio.run(safe_sync())
```

---

## 7. 故障排查

### 7.1 常见问题

#### 问题: 同步失败

**解决方案**:
1. 检查网络连接
2. 查看同步历史: `db.get_sync_history()`
3. 检查错误日志
4. 进入离线模式，稍后重试

#### 问题: 冲突过多

**解决方案**:
1. 检查冲突类型: `db.get_unresolved_conflicts()`
2. 选择合适的解决策略
3. 手动解决关键冲突
4. 自动解决其他冲突

#### 问题: 数据库过大

**解决方案**:
1. 清理过期缓存: `db.cleanup_expired_cache()`
2. 清理同步历史
3. 压缩数据库: `VACUUM`

### 7.2 调试

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

# 查看同步状态
status = sync_client.get_sync_status()
print(json.dumps(status, indent=2))

# 查看数据库统计
stats = db.get_sync_stats()
print(json.dumps(stats, indent=2))

# 查看同步历史
history = db.get_sync_history(limit=20)
for record in history:
    print(f"{record['created_at']}: {record['operation']} - {record['status']}")
```

---

## 8. 性能优化

### 8.1 缓存策略

```python
# 预加载常用数据
from backend.local import LocalDatabase

db.set_cache(
    entity_type="memory",
    entity_id="mem-123",
    cache_key="frequently-accessed",
    cache_value=data,
    ttl_seconds=3600,
)
```

### 8.2 批量操作

```python
# 批量入队
operations = [
    ("memory", f"mem-{i}", "CREATE", {"content": f"test-{i}"})
    for i in range(100)
]

for entity_type, entity_id, operation, data in operations:
    await sync_client.enqueue_operation(
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        data=data,
    )

# 一次性同步
batch = await sync_client.sync()
```

### 8.3 索引优化

```python
# 数据库已预配置索引
# 常用查询:
# - 按entity_type和entity_id查询
# - 按时间戳查询
# - 按状态查询
# - 按优先级查询
```

---

## 9. 扩展性

### 9.1 自定义冲突解决

```python
from backend.local import ConflictResolver, ConflictResolutionStrategy

class CustomConflictResolver(ConflictResolver):
    async def resolve(self, conflict, default_strategy):
        # 自定义逻辑
        if conflict.entity_type == "memory":
            # 对memory使用特殊策略
            return self.Resolution(
                strategy=ConflictResolutionStrategy.MERGE,
                resolved_data=self._merge_memories(
                    conflict.local_data,
                    conflict.cloud_data,
                ),
            )
        else:
            return await super().resolve(conflict, default_strategy)
    
    def _merge_memories(self, local, cloud):
        # 合并逻辑
        return {**cloud, **local}
```

### 9.2 自定义同步策略

```python
class CustomSyncClient(SyncClient):
    async def _upload_changes(self, batch):
        # 自定义上传逻辑
        await super()._upload_changes(batch)
        
        # 额外处理
        for op in batch.operations:
            if op.status == "completed":
                # 发送通知
                await self._notify_callbacks("custom_event", {
                    "operation_id": op.id,
                })
```

---

## 10. 参考资源

- [SQLite文档](https://www.sqlite.org/docs.html)
- [Cryptography库](https://cryptography.io/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [异步编程](https://docs.python.org/3/library/asyncio.html)
