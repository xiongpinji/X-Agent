# X-Agent 升级指南

**版本**: 1.0  
**最后更新**: 2026-05-27  
**文档状态**: Published

---

## 目录

1. [升级概览](#升级概览)
2. [升级前检查](#升级前检查)
3. [升级步骤](#升级步骤)
4. [版本升级路径](#版本升级路径)
5. [破坏性变更](#破坏性变更)
6. [迁移脚本](#迁移脚本)
7. [回滚步骤](#回滚步骤)
8. [常见问题](#常见问题)

---

## 升级概览

### 版本策略

X-Agent 遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范：

- **主版本** (X.0.0) - 破坏性变更
- **次版本** (0.X.0) - 新功能，向后兼容
- **补丁版本** (0.0.X) - 错误修复

### 升级类型

| 类型 | 说明 | 风险 | 停机时间 |
|------|------|------|---------|
| 补丁升级 | 0.1.0 → 0.1.1 | 低 | 无 |
| 次版本升级 | 0.1.0 → 0.2.0 | 中 | 无 |
| 主版本升级 | 0.x.0 → 1.0.0 | 高 | 可能需要 |

---

## 升级前检查

### 检查清单

```bash
#!/bin/bash
# pre-upgrade-check.sh

echo "=== X-Agent 升级前检查 ==="

# 1. 检查当前版本
echo "当前版本:"
grep version pyproject.toml

# 2. 检查磁盘空间
echo "磁盘空间:"
df -h

# 3. 检查数据库连接
echo "数据库连接:"
python -c "from backend.app.core.database import engine; engine.connect()"

# 4. 检查备份
echo "最近备份:"
ls -lh /backups/xagent/ | tail -5

# 5. 检查依赖
echo "依赖检查:"
pip check

# 6. 检查运行中的任务
echo "运行中的任务:"
ps aux | grep uvicorn

echo "=== 检查完成 ==="
```

### 备份数据库

```bash
# PostgreSQL备份
pg_dump -U postgres -d xagent -F c -f xagent_backup_$(date +%Y%m%d_%H%M%S).dump

# 验证备份
pg_restore -l xagent_backup_20260527_120000.dump | head -20
```

### 测试升级

```bash
# 在测试环境进行升级测试
docker run -e DATABASE_URL=postgresql://... xagent:new-version

# 运行测试套件
pytest tests/ -v
```

---

## 升级步骤

### 1. 停止服务

```bash
# 使用systemd
sudo systemctl stop xagent

# 或使用Docker
docker stop xagent

# 或使用Kubernetes
kubectl scale deployment xagent --replicas=0
```

### 2. 备份当前版本

```bash
# 备份代码
cp -r /opt/xagent /opt/xagent.backup.$(date +%Y%m%d_%H%M%S)

# 备份配置
cp -r /etc/xagent /etc/xagent.backup.$(date +%Y%m%d_%H%M%S)

# 备份数据库
pg_dump -U postgres -d xagent -F c -f xagent_backup_$(date +%Y%m%d_%H%M%S).dump
```

### 3. 下载新版本

```bash
# 从GitHub下载
wget https://github.com/xagent/xagent/releases/download/v0.2.0/xagent-0.2.0.tar.gz

# 或克隆仓库
git clone https://github.com/xagent/xagent.git
cd xagent
git checkout v0.2.0
```

### 4. 安装依赖

```bash
# 更新依赖
pip install -r requirements.txt --upgrade

# 或使用Poetry
poetry install
```

### 5. 运行迁移

```bash
# 数据库迁移
alembic upgrade head

# 或使用管理命令
python -m backend.app.cli migrate
```

### 6. 验证升级

```bash
# 检查版本
python -c "import backend; print(backend.__version__)"

# 运行健康检查
curl http://localhost:8000/health

# 运行测试
pytest tests/ -v
```

### 7. 启动服务

```bash
# 使用systemd
sudo systemctl start xagent

# 或使用Docker
docker start xagent

# 或使用Kubernetes
kubectl scale deployment xagent --replicas=3
```

### 8. 监控升级

```bash
# 查看日志
tail -f /var/log/xagent/app.log

# 监控性能
watch -n 1 'curl http://localhost:8000/metrics | grep http_requests_total'

# 检查错误
grep ERROR /var/log/xagent/app.log
```

---

## 版本升级路径

### 推荐升级路径

```
0.1.0 → 0.1.1 → 0.1.2 → 0.2.0 → 0.3.0 → 1.0.0
```

### 跳过版本升级

```bash
# 不支持跳过主版本升级
# 0.1.0 → 1.0.0 需要先升级到 0.x.x 的最新版本

# 支持跳过次版本升级
# 0.1.0 → 0.3.0 可以直接升级
```

### 版本兼容性矩阵

| 从版本 | 到版本 | 兼容性 | 说明 |
|--------|--------|--------|------|
| 0.1.x | 0.1.y | 完全兼容 | 补丁升级 |
| 0.1.x | 0.2.x | 向后兼容 | 次版本升级 |
| 0.x.x | 1.0.0 | 需要迁移 | 主版本升级 |

---

## 破坏性变更

### v0.2.0 破坏性变更

#### 1. API端点变更

```
旧: POST /api/agents
新: POST /api/v1/agents

旧: GET /api/agents/{id}
新: GET /api/v1/agents/{id}
```

**迁移步骤**:
```bash
# 更新客户端代码
sed -i 's|/api/agents|/api/v1/agents|g' client.py

# 或使用兼容层
# 在 main.py 中添加重定向
@app.get("/api/agents")
async def redirect_agents():
    return RedirectResponse(url="/api/v1/agents")
```

#### 2. 数据库字段变更

```sql
-- 旧字段
ALTER TABLE agents DROP COLUMN legacy_field;

-- 新字段
ALTER TABLE agents ADD COLUMN new_field VARCHAR(255);
```

**迁移脚本**:
```python
# alembic/versions/002_migrate_agents.py
def upgrade():
    # 复制数据
    op.execute("""
        UPDATE agents 
        SET new_field = legacy_field 
        WHERE new_field IS NULL
    """)
    
    # 删除旧字段
    op.drop_column('agents', 'legacy_field')

def downgrade():
    op.add_column('agents', sa.Column('legacy_field', sa.String(255)))
```

#### 3. 配置变更

```env
# 旧配置
XAGENT_LOG_LEVEL=INFO

# 新配置
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**迁移步骤**:
```python
# 在 settings.py 中添加兼容性代码
import os

log_level = os.getenv('LOG_LEVEL') or os.getenv('XAGENT_LOG_LEVEL', 'INFO')
```

#### 4. 依赖版本变更

```
旧: fastapi>=0.100.0
新: fastapi>=0.115.0

旧: pydantic>=2.0.0
新: pydantic>=2.7.0
```

**迁移步骤**:
```bash
# 更新 requirements.txt
pip install -r requirements.txt --upgrade

# 测试兼容性
pytest tests/ -v
```

---

## 迁移脚本

### 自动迁移脚本

```python
# scripts/migrate.py
import asyncio
from backend.app.core.database import engine, Base
from sqlalchemy import text

async def migrate_v0_1_to_v0_2():
    """从 v0.1 迁移到 v0.2"""
    
    async with engine.begin() as conn:
        # 1. 添加新表
        await conn.run_sync(Base.metadata.create_all)
        
        # 2. 迁移数据
        await conn.execute(text("""
            INSERT INTO agents_v2 (id, name, description, config)
            SELECT id, name, description, config FROM agents
        """))
        
        # 3. 验证数据
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM agents_v2
        """))
        count = result.scalar()
        print(f"迁移了 {count} 条Agent记录")
        
        # 4. 删除旧表
        await conn.execute(text("DROP TABLE agents"))
        await conn.execute(text("ALTER TABLE agents_v2 RENAME TO agents"))

if __name__ == "__main__":
    asyncio.run(migrate_v0_1_to_v0_2())
```

### 数据验证

```python
# scripts/validate_migration.py
from backend.app.core.database import SessionLocal
from backend.app.models import Agent, Run

def validate_migration():
    """验证迁移是否成功"""
    
    db = SessionLocal()
    
    try:
        # 检查Agent数据
        agents = db.query(Agent).all()
        print(f"Agent数量: {len(agents)}")
        
        # 检查Run数据
        runs = db.query(Run).all()
        print(f"Run数量: {len(runs)}")
        
        # 检查数据完整性
        for agent in agents:
            assert agent.id is not None
            assert agent.name is not None
            print(f"✓ Agent {agent.id} 数据完整")
        
        print("✓ 迁移验证成功")
        
    finally:
        db.close()

if __name__ == "__main__":
    validate_migration()
```

---

## 回滚步骤

### 快速回滚

```bash
#!/bin/bash
# rollback.sh

echo "开始回滚..."

# 1. 停止服务
sudo systemctl stop xagent

# 2. 恢复代码
cp -r /opt/xagent.backup.20260527_120000/* /opt/xagent/

# 3. 恢复数据库
pg_restore -U postgres -d xagent -F c xagent_backup_20260527_120000.dump

# 4. 启动服务
sudo systemctl start xagent

# 5. 验证
curl http://localhost:8000/health

echo "回滚完成"
```

### 数据库回滚

```bash
# 使用Alembic回滚
alembic downgrade -1  # 回滚一个版本
alembic downgrade base  # 回滚到初始状态

# 或手动恢复备份
pg_restore -U postgres -d xagent -F c xagent_backup_20260527_120000.dump
```

### 验证回滚

```bash
# 检查版本
python -c "import backend; print(backend.__version__)"

# 检查数据
psql -U postgres -d xagent -c "SELECT COUNT(*) FROM agents;"

# 检查服务
curl http://localhost:8000/health
```

---

## 常见问题

### Q1: 升级过程中出现数据库错误

**A**: 
1. 检查数据库连接
2. 查看迁移日志
3. 手动运行迁移脚本
4. 如果失败，恢复备份

```bash
# 查看迁移日志
alembic current
alembic history

# 手动运行迁移
alembic upgrade head -v
```

### Q2: 升级后API不兼容

**A**:
1. 检查API版本
2. 更新客户端代码
3. 使用兼容层

```python
# 添加兼容层
@app.get("/api/agents")
async def get_agents_v1():
    return await get_agents_v2()
```

### Q3: 升级后性能下降

**A**:
1. 检查索引
2. 分析查询性能
3. 优化配置

```sql
-- 重建索引
REINDEX DATABASE xagent;

-- 分析表
ANALYZE;
```

### Q4: 如何跳过某个版本升级

**A**: 不建议跳过版本升级，但如果必须：

```bash
# 查看迁移历史
alembic history

# 手动应用迁移
alembic upgrade <revision>
```

### Q5: 升级失败如何恢复

**A**:
1. 立即停止服务
2. 恢复备份
3. 检查错误日志
4. 联系支持

```bash
# 恢复备份
cp -r /opt/xagent.backup.20260527_120000/* /opt/xagent/
pg_restore -U postgres -d xagent -F c xagent_backup_20260527_120000.dump

# 启动服务
sudo systemctl start xagent
```

---

## 升级检查清单

- [ ] 备份数据库
- [ ] 备份代码和配置
- [ ] 在测试环境验证升级
- [ ] 停止生产服务
- [ ] 下载新版本
- [ ] 安装依赖
- [ ] 运行数据库迁移
- [ ] 验证升级
- [ ] 启动服务
- [ ] 监控日志和性能
- [ ] 通知用户升级完成

---

## 相关资源

- [版本发布](https://github.com/xagent/xagent/releases)
- [更新日志](../CHANGELOG.md)
- [迁移指南](../../concepts/architecture/DATABASE.md#迁移指南)
- [故障排查](../support/TROUBLESHOOTING_GUIDE.md)

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 发布团队  
**许可证**: MIT
