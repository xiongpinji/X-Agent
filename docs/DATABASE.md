# X-Agent 数据库设计文档

**版本**: 1.0  
**最后更新**: 2026-05-27  
**文档状态**: Published

---

## 目录

1. [数据库概览](#数据库概览)
2. [表结构设计](#表结构设计)
3. [关系图](#关系图)
4. [索引策略](#索引策略)
5. [迁移指南](#迁移指南)
6. [备份恢复](#备份恢复)
7. [性能优化](#性能优化)

---

## 数据库概览

### 支持的数据库

- **SQLite** - 开发环境(默认)
- **PostgreSQL** - 生产环境(推荐)
- **MySQL** - 可选

### 数据库配置

```env
# SQLite (开发)
DATABASE_URL=sqlite:///./data/xagent.db

# PostgreSQL (生产)
DATABASE_URL=postgresql://user:password@localhost:5432/xagent

# MySQL
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/xagent
```

### 核心表

| 表名 | 说明 | 行数估计 |
|------|------|---------|
| users | 用户表 | 1K-10K |
| tenants | 租户表 | 10-100 |
| agents | Agent表 | 100-1K |
| runs | 执行记录 | 10K-100K |
| traces | 追踪记录 | 100K-1M |
| memory | 记忆数据 | 10K-100K |
| workflows | 工作流 | 100-1K |
| audit_logs | 审计日志 | 100K-1M |

---

## 表结构设计

### 1. Users 表

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    last_login TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_role CHECK (role IN ('admin', 'developer', 'operator', 'viewer')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'suspended'))
);

CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
```

### 2. Agents 表

```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    config JSONB NOT NULL DEFAULT '{}',
    capabilities TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'archived'))
);

CREATE INDEX idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_created_at ON agents(created_at DESC);
CREATE INDEX idx_agents_tenant_status ON agents(tenant_id, status);
```

### 3. Runs 表

```sql
CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    input JSONB NOT NULL,
    output JSONB,
    error TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX idx_runs_agent_id ON runs(agent_id);
CREATE INDEX idx_runs_tenant_id ON runs(tenant_id);
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX idx_runs_agent_status ON runs(agent_id, status);
```

### 4. Traces 表

```sql
CREATE TABLE traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id),
    agent_id UUID NOT NULL REFERENCES agents(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    step_number INTEGER NOT NULL,
    action VARCHAR(255) NOT NULL,
    input JSONB,
    output JSONB,
    error TEXT,
    duration_ms INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_action CHECK (action IN ('tool_call', 'llm_call', 'decision', 'action'))
);

CREATE INDEX idx_traces_run_id ON traces(run_id);
CREATE INDEX idx_traces_agent_id ON traces(agent_id);
CREATE INDEX idx_traces_tenant_id ON traces(tenant_id);
CREATE INDEX idx_traces_timestamp ON traces(timestamp DESC);
```

### 5. Memory 表

```sql
CREATE TABLE memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    agent_id UUID REFERENCES agents(id),
    type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_type CHECK (type IN ('short_term', 'long_term', 'episodic', 'semantic'))
);

CREATE INDEX idx_memory_tenant_id ON memory(tenant_id);
CREATE INDEX idx_memory_agent_id ON memory(agent_id);
CREATE INDEX idx_memory_type ON memory(type);
CREATE INDEX idx_memory_embedding ON memory USING ivfflat (embedding vector_cosine_ops);
```

### 6. Workflows 表

```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    definition JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_status CHECK (status IN ('draft', 'published', 'archived'))
);

CREATE INDEX idx_workflows_tenant_id ON workflows(tenant_id);
CREATE INDEX idx_workflows_status ON workflows(status);
```

### 7. Audit Logs 表

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    event_type VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255),
    resource_id UUID,
    action VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_status CHECK (status IN ('success', 'failure'))
);

CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
```

---

## 关系图

```
Users (1) ──────────── (N) Agents
  │                        │
  │                        ├─── (N) Runs
  │                        │      │
  │                        │      └─── (N) Traces
  │                        │
  │                        └─── (N) Memory
  │
  └─ (N) Audit Logs

Tenants (1) ──────────── (N) Users
  │                        
  ├─ (N) Agents
  │
  ├─ (N) Workflows
  │
  └─ (N) Audit Logs
```

---

## 索引策略

### 必需索引

```sql
-- 外键索引
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX idx_runs_agent_id ON runs(agent_id);
CREATE INDEX idx_traces_run_id ON traces(run_id);

-- 查询优化索引
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_memory_type ON memory(type);
CREATE INDEX idx_workflows_status ON workflows(status);

-- 时间范围查询索引
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX idx_traces_timestamp ON traces(timestamp DESC);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- 复合索引
CREATE INDEX idx_runs_agent_status ON runs(agent_id, status);
CREATE INDEX idx_agents_tenant_status ON agents(tenant_id, status);
CREATE INDEX idx_audit_logs_tenant_event ON audit_logs(tenant_id, event_type);
```

### 向量索引(用于相似度搜索)

```sql
-- 创建向量索引
CREATE INDEX idx_memory_embedding ON memory USING ivfflat (
    embedding vector_cosine_ops
) WITH (lists = 100);

-- 查询示例
SELECT id, content, 1 - (embedding <=> query_embedding) as similarity
FROM memory
WHERE tenant_id = 'xxx'
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

---

## 迁移指南

### 初始化数据库

```bash
# 使用Alembic进行迁移
alembic upgrade head

# 或使用SQL脚本
psql -U postgres -d xagent -f schema.sql
```

### 创建迁移

```bash
# 生成新的迁移文件
alembic revision --autogenerate -m "Add new column"

# 编辑迁移文件
# alembic/versions/xxx_add_new_column.py

# 执行迁移
alembic upgrade head
```

### 数据迁移示例

```python
# alembic/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        # ... 其他列
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

def downgrade():
    op.drop_table('users')
```

---

## 备份恢复

### PostgreSQL备份

```bash
# 完整备份
pg_dump -U postgres -d xagent -F c -f xagent_backup.dump

# 恢复备份
pg_restore -U postgres -d xagent -F c xagent_backup.dump

# 增量备份(使用WAL)
pg_basebackup -D /backup/xagent -Ft -z -P
```

### 备份策略

```bash
#!/bin/bash
# backup.sh - 每日备份脚本

BACKUP_DIR="/backups/xagent"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/xagent_$DATE.dump"

# 创建备份
pg_dump -U postgres -d xagent -F c -f "$BACKUP_FILE"

# 压缩
gzip "$BACKUP_FILE"

# 删除7天前的备份
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +7 -delete

# 上传到S3
aws s3 cp "$BACKUP_FILE.gz" s3://xagent-backups/
```

---

## 性能优化

### 查询优化

```sql
-- 使用EXPLAIN分析查询
EXPLAIN ANALYZE
SELECT a.id, a.name, COUNT(r.id) as run_count
FROM agents a
LEFT JOIN runs r ON a.id = r.agent_id
WHERE a.tenant_id = 'xxx'
GROUP BY a.id, a.name;

-- 优化建议
-- 1. 添加索引
CREATE INDEX idx_runs_agent_id ON runs(agent_id);

-- 2. 使用分区(大表)
CREATE TABLE runs_2026_05 PARTITION OF runs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

### 表分区

```sql
-- 按时间分区
CREATE TABLE runs (
    id UUID,
    created_at TIMESTAMP,
    -- ... 其他列
) PARTITION BY RANGE (created_at);

CREATE TABLE runs_2026_05 PARTITION OF runs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE runs_2026_06 PARTITION OF runs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

### 连接池配置

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True
)
```

---

## 数据库维护

### 定期维护任务

```sql
-- 分析表统计信息
ANALYZE;

-- 清理死行
VACUUM ANALYZE;

-- 重建索引
REINDEX DATABASE xagent;

-- 检查表完整性
CHECK TABLE users;
```

### 监控

```sql
-- 查看表大小
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 查看索引使用情况
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 查看慢查询
SELECT query, calls, mean_time, max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 数据库团队  
**许可证**: MIT
