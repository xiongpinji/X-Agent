# X-Agent 本地端同步模块 - 快速开始指南

**版本**: 1.0  
**日期**: 2026-05-27  
**目标受众**: 开发者、运维人员

---

## 1. 概述

本指南帮助你快速集成和使用X-Agent本地端同步模块。集成过程分为5个步骤，预计耗时30分钟。

---

## 2. 前置条件

### 2.1 系统要求

```
✓ Python >= 3.11
✓ FastAPI 0.115.0+
✓ SQLite 3.35+
✓ 磁盘空间 >= 1GB
✓ 内存 >= 512MB
```

### 2.2 依赖检查

```bash
# 检查Python版本
python --version

# 检查FastAPI
pip show fastapi

# 检查SQLite
sqlite3 --version

# 检查磁盘空间
df -h ~
```

### 2.3 权限检查

```bash
# 检查主目录可写
touch ~/.xagent/test.txt && rm ~/.xagent/test.txt

# 检查数据库目录
mkdir -p ~/.xagent
chmod 755 ~/.xagent
```

---

## 3. 安装步骤

### 步骤1: 复制文件 (5分钟)

```bash
# 1. 复制API模块
cp backend/app/api/sync.py backend/app/api/

# 2. 复制中间件
mkdir -p backend/app/middleware
cp backend/app/middleware/sync_middleware.py backend/app/middleware/

# 3. 复制迁移脚本
cp backend/local/migration.py backend/local/

# 4. 复制配置文件
mkdir -p config
cp config/xagent_local_config.json config/

# 验证文件
ls -la backend/app/api/sync.py
ls -la backend/app/middleware/sync_middleware.py
ls -la backend/local/migration.py
ls -la config/xagent_local_config.json
```

### 步骤2: 初始化数据库 (5分钟)

```bash
# 1. 创建数据库目录
mkdir -p ~/.xagent

# 2. 初始化数据库
python -c "
from backend.local.migration import initialize_local_database
db = initialize_local_database()
print('Database initialized successfully')
"

# 3. 验证数据库
sqlite3 ~/.xagent/local.db ".tables"
```

### 步骤3: 配置应用 (5分钟)

#### 3.1 更新web.py

编辑 `backend/app/web.py`:

```python
from backend.app.api import sync
from backend.app.middleware.sync_middleware import (
    SyncMiddleware,
    OfflineModeMiddleware,
    SyncMetricsMiddleware,
)
from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.config import ConfigManager

# 初始化本地数据库
config = ConfigManager.get_config()
db_config = DatabaseConfig(
    db_path=config.db_path,
    timeout=config.db_timeout,
    enable_wal=config.db_enable_wal,
    enable_foreign_keys=config.db_enable_foreign_keys,
)
local_db = LocalDatabase(db_config)
local_db.initialize()

# 添加中间件
app.add_middleware(SyncMiddleware, db=local_db)
app.add_middleware(OfflineModeMiddleware)
app.add_middleware(SyncMetricsMiddleware)

# 注册路由
app.include_router(sync.router)
```

#### 3.2 更新dependencies.py

编辑 `backend/app/dependencies.py`:

```python
from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.config import ConfigManager
from backend.local.sync_client import SyncClient

def get_local_database() -> LocalDatabase:
    """Get local database instance."""
    config = ConfigManager.get_config()
    db_config = DatabaseConfig(
        db_path=config.db_path,
        timeout=config.db_timeout,
        enable_wal=config.db_enable_wal,
        enable_foreign_keys=config.db_enable_foreign_keys,
    )
    db = LocalDatabase(db_config)
    db.initialize()
    return db

def get_sync_client(db: LocalDatabase = Depends(get_local_database)) -> SyncClient:
    """Get sync client instance."""
    # TODO: Inject cloud API client
    return SyncClient(db, None)
```

### 步骤4: 加载配置 (3分钟)

```bash
# 1. 设置环境变量
export XAGENT_LOCAL_DB_PATH=~/.xagent/local.db
export XAGENT_SYNC_ENABLED=true
export XAGENT_ENCRYPTION_ENABLED=true

# 2. 加载配置
python -c "
from backend.local.config import ConfigManager
ConfigManager.load_from_file('config/xagent_local_config.json')
config = ConfigManager.get_config()
print(f'Config loaded: {config.db_path}')
"

# 3. 验证配置
cat config/xagent_local_config.json | python -m json.tool
```

### 步骤5: 启动应用 (7分钟)

```bash
# 1. 启动应用
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

# 2. 在另一个终端验证
curl http://localhost:8000/health

# 3. 检查同步API
curl http://localhost:8000/api/v1/sync/stats

# 4. 查看日志
tail -f ~/.xagent/logs/sync.log
```

---

## 4. 基本使用

### 4.1 入队同步操作

```bash
# 使用curl
curl -X POST http://localhost:8000/api/v1/sync/enqueue \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "entity_type": "memory",
    "entity_id": "mem_123",
    "operation": "UPDATE",
    "data": {"content": "updated content"},
    "priority": 1
  }'

# 使用Python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/sync/enqueue",
    json={
        "entity_type": "memory",
        "entity_id": "mem_123",
        "operation": "UPDATE",
        "data": {"content": "updated content"},
        "priority": 1,
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
print(response.json())
```

### 4.2 获取同步状态

```bash
# 使用curl
curl http://localhost:8000/api/v1/sync/status/queue_123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 使用Python
response = requests.get(
    "http://localhost:8000/api/v1/sync/status/queue_123",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
print(response.json())
```

### 4.3 查看冲突

```bash
# 列出所有冲突
curl http://localhost:8000/api/v1/sync/conflicts \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取特定冲突
curl http://localhost:8000/api/v1/sync/conflicts/conflict_123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4.4 解决冲突

```bash
# 使用curl
curl -X POST http://localhost:8000/api/v1/sync/conflicts/conflict_123/resolve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "resolution_strategy": "last_write_wins",
    "resolved_data": {"content": "resolved"}
  }'

# 使用Python
response = requests.post(
    "http://localhost:8000/api/v1/sync/conflicts/conflict_123/resolve",
    json={
        "resolution_strategy": "last_write_wins",
        "resolved_data": {"content": "resolved"},
    },
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
print(response.json())
```

### 4.5 离线模式

```bash
# 启用离线模式
curl -X POST http://localhost:8000/api/v1/sync/offline/enable \
  -H "Authorization: Bearer YOUR_TOKEN"

# 禁用离线模式
curl -X POST http://localhost:8000/api/v1/sync/offline/disable \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取离线状态
curl http://localhost:8000/api/v1/sync/offline/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4.6 查看统计信息

```bash
# 获取同步统计
curl http://localhost:8000/api/v1/sync/stats \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取同步历史
curl http://localhost:8000/api/v1/sync/history \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取系统健康状态
curl http://localhost:8000/api/v1/sync/health \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 5. 常见任务

### 5.1 迁移现有数据

```python
from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.migration import DataMigration
import psycopg2

# 连接PostgreSQL
pg_conn = psycopg2.connect(
    host="localhost",
    database="xagent_db",
    user="xagent",
    password="password"
)

# 初始化本地数据库
db_config = DatabaseConfig()
db = LocalDatabase(db_config)
db.initialize()

# 执行迁移
data_migration = DataMigration(db, pg_conn)
stats = data_migration.migrate_memories()
print(f"Migrated {stats} memories")
```

### 5.2 启用加密

```python
from backend.local.encryption import EncryptionManager, EncryptionConfig

# 创建加密管理器
config = EncryptionConfig()
manager = EncryptionManager(config)

# 生成主密钥
master_key = manager.generate_master_key()
print(f"Master key generated: {master_key.hex()}")

# 加密数据
plaintext = b"sensitive data"
ciphertext, iv, salt = manager.encrypt(plaintext)
print(f"Encrypted: {ciphertext.hex()}")

# 解密数据
decrypted = manager.decrypt(ciphertext, iv, salt)
print(f"Decrypted: {decrypted}")
```

### 5.3 配置缓存

```python
from backend.local.database import LocalDatabase, DatabaseConfig

db_config = DatabaseConfig()
db = LocalDatabase(db_config)

# 设置缓存
db.set_cache(
    entity_type="memory",
    entity_id="mem_123",
    cache_key="summary",
    cache_value={"summary": "cached data"},
    ttl_seconds=3600,
)

# 获取缓存
cached = db.get_cache("summary")
print(f"Cached: {cached}")

# 清理过期缓存
deleted = db.cleanup_expired_cache()
print(f"Deleted {deleted} expired entries")
```

### 5.4 监控性能

```python
from backend.local.database import LocalDatabase, DatabaseConfig

db_config = DatabaseConfig()
db = LocalDatabase(db_config)

# 获取统计信息
stats = db.get_sync_stats()
print(f"Pending syncs: {stats['pending_syncs']}")
print(f"Failed syncs: {stats['failed_syncs']}")
print(f"Conflicts: {stats['unresolved_conflicts']}")

# 获取数据库大小
size_info = db.get_database_size()
print(f"Database size: {size_info['database_size_mb']}MB")

# 获取同步历史
history = db.get_sync_history(limit=10)
for record in history:
    print(f"{record['entity_type']}: {record['status']}")
```

---

## 6. 故障排查

### 6.1 数据库初始化失败

**错误**: `Failed to initialize database`

**解决方案**:

```bash
# 1. 检查目录权限
ls -la ~/.xagent/

# 2. 检查磁盘空间
df -h ~/.xagent/

# 3. 删除损坏的数据库
rm ~/.xagent/local.db

# 4. 重新初始化
python -c "from backend.local.migration import initialize_local_database; initialize_local_database()"
```

### 6.2 API端点不可用

**错误**: `404 Not Found`

**解决方案**:

```bash
# 1. 检查路由注册
grep "include_router(sync" backend/app/web.py

# 2. 检查中间件
grep "SyncMiddleware" backend/app/web.py

# 3. 重启应用
systemctl restart xagent

# 4. 验证端点
curl http://localhost:8000/api/v1/sync/stats
```

### 6.3 权限错误

**错误**: `Permission denied`

**解决方案**:

```bash
# 1. 检查权限
ls -la ~/.xagent/local.db

# 2. 修改权限
chmod 644 ~/.xagent/local.db

# 3. 检查用户
whoami

# 4. 修改所有者
chown $USER:$USER ~/.xagent/local.db
```

### 6.4 性能问题

**症状**: 响应缓慢

**解决方案**:

```bash
# 1. 检查数据库大小
ls -lh ~/.xagent/local.db

# 2. 优化数据库
sqlite3 ~/.xagent/local.db "VACUUM; ANALYZE;"

# 3. 清理缓存
rm -rf ~/.xagent/cache/*

# 4. 检查系统资源
top -b -n 1 | head -20
```

---

## 7. 测试

### 7.1 运行单元测试

```bash
# 运行所有测试
pytest tests/test_local_sync_integration.py -v

# 运行特定测试
pytest tests/test_local_sync_integration.py::TestLocalDatabase::test_database_initialization -v

# 运行带覆盖率
pytest tests/test_local_sync_integration.py --cov=backend.local --cov-report=html
```

### 7.2 运行API测试

```bash
# 运行API测试
pytest tests/test_sync_api_integration.py -v

# 运行特定API测试
pytest tests/test_sync_api_integration.py::TestSyncAPI::test_enqueue_sync -v
```

### 7.3 性能测试

```bash
# 运行性能测试
pytest tests/test_local_sync_integration.py::TestPerformance -v

# 基准测试
python -c "
import time
from backend.local.database import LocalDatabase, DatabaseConfig

db_config = DatabaseConfig()
db = LocalDatabase(db_config)

start = time.time()
for i in range(100):
    db.enqueue_sync('memory', f'mem_{i}', 'UPDATE', {'content': f'test_{i}'})
duration = time.time() - start

print(f'Enqueued 100 operations in {duration:.2f}s')
print(f'Average: {duration/100*1000:.2f}ms per operation')
"
```

---

## 8. 部署

### 8.1 开发环境

```bash
# 启动开发服务器
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000
```

### 8.2 生产环境

```bash
# 使用Gunicorn
gunicorn backend.app.web:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -

# 使用systemd
sudo systemctl start xagent
sudo systemctl enable xagent
```

### 8.3 Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "backend.app.web:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# 构建镜像
docker build -t xagent:latest .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v ~/.xagent:/root/.xagent \
  xagent:latest
```

---

## 9. 下一步

### 9.1 推荐阅读

- [集成方案](INTEGRATION_PLAN.md) - 详细的集成步骤
- [验证报告](INTEGRATION_VERIFICATION_REPORT.md) - 集成验证结果
- [回滚方案](ROLLBACK_PLAN.md) - 应急回滚步骤

### 9.2 高级功能

- 实现同步调度器
- 配置监控告警
- 优化性能
- 扩展功能

### 9.3 获取帮助

```
文档: https://docs.xagent.com/
论坛: https://forum.xagent.com/
邮件: support@xagent.com
Slack: #xagent-support
```

---

## 10. 常见问题

### Q: 如何重置本地数据库?

A: 删除数据库文件并重新初始化:
```bash
rm ~/.xagent/local.db
python -c "from backend.local.migration import initialize_local_database; initialize_local_database()"
```

### Q: 如何禁用同步?

A: 编辑配置文件:
```bash
vi ~/.xagent/config.json
# 修改: "sync_enabled": false
```

### Q: 如何查看同步日志?

A: 查看日志文件:
```bash
tail -f ~/.xagent/logs/sync.log
```

### Q: 如何处理冲突?

A: 使用API解决冲突:
```bash
curl -X POST http://localhost:8000/api/v1/sync/conflicts/{id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution_strategy": "last_write_wins", "resolved_data": {...}}'
```

### Q: 如何迁移现有数据?

A: 使用迁移脚本:
```python
from backend.local.migration import DataMigration
data_migration = DataMigration(db, pg_connection)
data_migration.migrate_memories()
```

---

**文档维护者**: X-Agent集成团队  
**最后更新**: 2026-05-27  
**版本**: 1.0
