# X-Agent 云端服务数据库 Schema 设计

**版本：** 1.0.0  
**日期：** 2026-05-27  
**数据库**：PostgreSQL 16+

---

## 1. 核心表设计

### 1.1 同步操作表 (sync_operations)

```sql
CREATE TABLE sync_operations (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    client_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    operation VARCHAR(20) NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 数据
    data JSONB NOT NULL,
    data_checksum VARCHAR(64) NOT NULL,
    
    -- 版本控制
    vector_clock JSONB NOT NULL,
    version_id VARCHAR(255),
    
    -- 加密
    encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    encryption_key_id VARCHAR(255),
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'applied', 'conflicted', 'failed')),
    error_message TEXT,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    request_id VARCHAR(255),
    
    -- 索引
    CONSTRAINT sync_ops_entity_unique UNIQUE (entity_type, entity_id, version_id)
);

-- 索引
CREATE INDEX idx_sync_ops_client_id ON sync_operations(client_id);
CREATE INDEX idx_sync_ops_entity ON sync_operations(entity_type, entity_id);
CREATE INDEX idx_sync_ops_status ON sync_operations(status);
CREATE INDEX idx_sync_ops_created_at ON sync_operations(created_at DESC);
CREATE INDEX idx_sync_ops_tenant_id ON sync_operations(tenant_id);
CREATE INDEX idx_sync_ops_vector_clock ON sync_operations USING GIN(vector_clock);
```

---

### 1.2 版本快照表 (version_snapshots)

```sql
CREATE TABLE version_snapshots (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 版本信息
    version_id VARCHAR(255) NOT NULL UNIQUE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    
    -- 版本关系
    parent_version_id VARCHAR(255),
    
    -- 数据
    data JSONB NOT NULL,
    diff JSONB,
    data_checksum VARCHAR(64) NOT NULL,
    
    -- 元数据
    author_id VARCHAR(255),
    message TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL,
    
    -- 索引
    CONSTRAINT version_snapshots_entity_unique UNIQUE (entity_type, entity_id, version_id)
);

-- 索引
CREATE INDEX idx_version_snapshots_entity ON version_snapshots(entity_type, entity_id);
CREATE INDEX idx_version_snapshots_created_at ON version_snapshots(created_at DESC);
CREATE INDEX idx_version_snapshots_parent ON version_snapshots(parent_version_id);
CREATE INDEX idx_version_snapshots_tenant_id ON version_snapshots(tenant_id);
```

---

### 1.3 冲突记录表 (conflict_records)

```sql
CREATE TABLE conflict_records (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 冲突信息
    conflict_id VARCHAR(255) NOT NULL UNIQUE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    conflict_type VARCHAR(50) NOT NULL CHECK (conflict_type IN (
        'concurrent_modification',
        'delete_update',
        'data_mismatch',
        'version_mismatch'
    )),
    
    -- 冲突的操作
    operation_ids UUID[] NOT NULL,
    
    -- 冲突详情
    details JSONB NOT NULL,
    
    -- 解决信息
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'manual_review')),
    resolution_strategy VARCHAR(50),
    resolution JSONB,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_conflict_records_entity ON conflict_records(entity_type, entity_id);
CREATE INDEX idx_conflict_records_status ON conflict_records(status);
CREATE INDEX idx_conflict_records_created_at ON conflict_records(created_at DESC);
CREATE INDEX idx_conflict_records_tenant_id ON conflict_records(tenant_id);
```

---

### 1.4 同步状态表 (sync_state)

```sql
CREATE TABLE sync_state (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 客户端信息
    client_id VARCHAR(255) NOT NULL UNIQUE,
    device_type VARCHAR(50),
    device_id VARCHAR(255),
    
    -- 同步状态
    status VARCHAR(20) NOT NULL DEFAULT 'synced' CHECK (status IN ('synced', 'syncing', 'pending', 'error')),
    
    -- 向量时钟
    vector_clock JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- 最后同步信息
    last_sync_at TIMESTAMP WITH TIME ZONE,
    last_sync_operation_id UUID,
    
    -- 待同步操作
    pending_operations_count INTEGER NOT NULL DEFAULT 0,
    
    -- 冲突信息
    pending_conflicts_count INTEGER NOT NULL DEFAULT 0,
    
    -- 错误信息
    error_message TEXT,
    error_count INTEGER NOT NULL DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_sync_state_client_id ON sync_state(client_id);
CREATE INDEX idx_sync_state_status ON sync_state(status);
CREATE INDEX idx_sync_state_tenant_id ON sync_state(tenant_id);
```

---

### 1.5 加密密钥表 (encryption_keys)

```sql
CREATE TABLE encryption_keys (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 密钥信息
    key_id VARCHAR(255) NOT NULL UNIQUE,
    key_type VARCHAR(50) NOT NULL CHECK (key_type IN ('master', 'dek', 'kek')),
    algorithm VARCHAR(50) NOT NULL,
    
    -- 密钥数据（加密存储）
    encrypted_key_material BYTEA NOT NULL,
    key_material_checksum VARCHAR(64) NOT NULL,
    
    -- 密钥元数据
    public_key TEXT,
    key_version INTEGER NOT NULL DEFAULT 1,
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'rotated', 'revoked')),
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_encryption_keys_key_id ON encryption_keys(key_id);
CREATE INDEX idx_encryption_keys_status ON encryption_keys(status);
CREATE INDEX idx_encryption_keys_tenant_id ON encryption_keys(tenant_id);
```

---

### 1.6 同步队列表 (sync_queue)

```sql
CREATE TABLE sync_queue (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 队列信息
    client_id VARCHAR(255) NOT NULL,
    operation_id UUID NOT NULL,
    
    -- 优先级
    priority INTEGER NOT NULL DEFAULT 0,
    
    -- 重试信息
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_sync_queue_client_id ON sync_queue(client_id);
CREATE INDEX idx_sync_queue_status ON sync_queue(status);
CREATE INDEX idx_sync_queue_priority ON sync_queue(priority DESC);
CREATE INDEX idx_sync_queue_created_at ON sync_queue(created_at);
```

---

### 1.7 同步统计表 (sync_statistics)

```sql
CREATE TABLE sync_statistics (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 统计周期
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('hour', 'day', 'week', 'month')),
    
    -- 统计数据
    total_operations INTEGER NOT NULL DEFAULT 0,
    successful_operations INTEGER NOT NULL DEFAULT 0,
    failed_operations INTEGER NOT NULL DEFAULT 0,
    conflicts_detected INTEGER NOT NULL DEFAULT 0,
    conflicts_resolved INTEGER NOT NULL DEFAULT 0,
    
    -- 性能指标
    average_latency_ms NUMERIC(10, 2),
    min_latency_ms NUMERIC(10, 2),
    max_latency_ms NUMERIC(10, 2),
    p95_latency_ms NUMERIC(10, 2),
    p99_latency_ms NUMERIC(10, 2),
    
    -- 成功率
    success_rate NUMERIC(5, 2),
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL,
    
    -- 索引
    CONSTRAINT sync_stats_period_unique UNIQUE (tenant_id, period_start, period_type)
);

-- 索引
CREATE INDEX idx_sync_statistics_period ON sync_statistics(period_start, period_end);
CREATE INDEX idx_sync_statistics_tenant_id ON sync_statistics(tenant_id);
```

---

## 2. 关系表设计

### 2.1 客户端信息表 (sync_clients)

```sql
CREATE TABLE sync_clients (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 客户端信息
    client_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    
    -- 设备信息
    device_type VARCHAR(50) NOT NULL CHECK (device_type IN ('web', 'desktop', 'mobile')),
    device_id VARCHAR(255),
    device_name VARCHAR(255),
    
    -- 客户端版本
    app_version VARCHAR(50),
    sdk_version VARCHAR(50),
    
    -- 连接信息
    last_seen_at TIMESTAMP WITH TIME ZONE,
    is_online BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_sync_clients_user_id ON sync_clients(user_id);
CREATE INDEX idx_sync_clients_device_type ON sync_clients(device_type);
CREATE INDEX idx_sync_clients_tenant_id ON sync_clients(tenant_id);
```

---

### 2.2 同步会话表 (sync_sessions)

```sql
CREATE TABLE sync_sessions (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 会话信息
    session_id VARCHAR(255) NOT NULL UNIQUE,
    client_id VARCHAR(255) NOT NULL,
    
    -- 会话状态
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'closed')),
    
    -- 会话数据
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL
);

-- 索引
CREATE INDEX idx_sync_sessions_client_id ON sync_sessions(client_id);
CREATE INDEX idx_sync_sessions_status ON sync_sessions(status);
CREATE INDEX idx_sync_sessions_tenant_id ON sync_sessions(tenant_id);
```

---

## 3. 审计与日志表

### 3.1 同步审计日志表 (sync_audit_log)

```sql
CREATE TABLE sync_audit_log (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 审计信息
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    
    -- 操作者
    actor_id VARCHAR(255),
    actor_type VARCHAR(50),
    
    -- 变更信息
    changes JSONB,
    
    -- 结果
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 审计
    tenant_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255)
);

-- 索引
CREATE INDEX idx_sync_audit_log_resource ON sync_audit_log(resource_type, resource_id);
CREATE INDEX idx_sync_audit_log_actor ON sync_audit_log(actor_id);
CREATE INDEX idx_sync_audit_log_created_at ON sync_audit_log(created_at DESC);
CREATE INDEX idx_sync_audit_log_tenant_id ON sync_audit_log(tenant_id);
```

---

## 4. 性能优化

### 4.1 分区策略

```sql
-- 按时间分区同步操作表
CREATE TABLE sync_operations_2026_05 PARTITION OF sync_operations
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE sync_operations_2026_06 PARTITION OF sync_operations
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

### 4.2 物化视图

```sql
-- 实时同步统计视图
CREATE MATERIALIZED VIEW sync_stats_realtime AS
SELECT
    tenant_id,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_operations,
    COUNT(CASE WHEN status = 'applied' THEN 1 END) as successful_operations,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_operations,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000) as avg_latency_ms
FROM sync_operations
GROUP BY tenant_id, DATE_TRUNC('hour', created_at);

CREATE INDEX idx_sync_stats_realtime_tenant ON sync_stats_realtime(tenant_id);
```

---

## 5. 数据完整性约束

### 5.1 外键约束

```sql
-- 同步操作引用版本快照
ALTER TABLE sync_operations
ADD CONSTRAINT fk_sync_ops_version
FOREIGN KEY (version_id) REFERENCES version_snapshots(version_id);

-- 冲突记录引用同步操作
ALTER TABLE conflict_records
ADD CONSTRAINT fk_conflict_ops
FOREIGN KEY (operation_ids) REFERENCES sync_operations(id);

-- 同步队列引用同步操作
ALTER TABLE sync_queue
ADD CONSTRAINT fk_sync_queue_operation
FOREIGN KEY (operation_id) REFERENCES sync_operations(id);
```

### 5.2 检查约束

```sql
-- 版本快照的时间戳约束
ALTER TABLE version_snapshots
ADD CONSTRAINT check_version_timestamps
CHECK (created_at >= COALESCE(
    (SELECT created_at FROM version_snapshots WHERE version_id = parent_version_id),
    created_at
));

-- 同步统计的时间范围约束
ALTER TABLE sync_statistics
ADD CONSTRAINT check_period_range
CHECK (period_end > period_start);
```

---

## 6. 初始化脚本

### 6.1 创建所有表

```sql
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 创建所有表（按依赖顺序）
-- 1. 基础表
CREATE TABLE sync_operations (...);
CREATE TABLE version_snapshots (...);
CREATE TABLE conflict_records (...);
CREATE TABLE sync_state (...);
CREATE TABLE encryption_keys (...);
CREATE TABLE sync_queue (...);
CREATE TABLE sync_statistics (...);

-- 2. 关系表
CREATE TABLE sync_clients (...);
CREATE TABLE sync_sessions (...);

-- 3. 审计表
CREATE TABLE sync_audit_log (...);

-- 4. 创建索引
-- ... (所有索引)

-- 5. 创建约束
-- ... (所有约束)

-- 6. 创建视图
-- ... (所有视图)
```

### 6.2 初始数据

```sql
-- 插入默认加密密钥
INSERT INTO encryption_keys (
    key_id, key_type, algorithm, encrypted_key_material, key_material_checksum, status
) VALUES (
    'master_key_001',
    'master',
    'AES-256-GCM',
    pgp_sym_encrypt('master_key_data', 'passphrase'),
    'checksum_value',
    'active'
);
```

---

## 7. 备份与恢复

### 7.1 备份策略

```bash
# 完整备份
pg_dump -h localhost -U xagent -d xagent_db > backup_full.sql

# 增量备份
pg_basebackup -h localhost -U xagent -D /backup/base -Xstream -P

# 导出特定表
pg_dump -h localhost -U xagent -d xagent_db -t sync_operations > sync_ops_backup.sql
```

### 7.2 恢复策略

```bash
# 恢复完整备份
psql -h localhost -U xagent -d xagent_db < backup_full.sql

# 恢复特定表
psql -h localhost -U xagent -d xagent_db < sync_ops_backup.sql

# 时间点恢复
pg_restore -h localhost -U xagent -d xagent_db -t sync_operations backup_full.dump
```

---

## 8. 监控与维护

### 8.1 表大小监控

```sql
-- 查看表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 8.2 索引维护

```sql
-- 重建索引
REINDEX TABLE sync_operations;

-- 分析表统计
ANALYZE sync_operations;

-- 清理死行
VACUUM ANALYZE sync_operations;
```

### 8.3 性能调优

```sql
-- 查看慢查询
SELECT query, calls, mean_time, max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- 查看缺失的索引
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY abs(correlation) DESC;
```

---

## 总结

本Schema设计提供了完整的数据库结构，支持：
- 高效的同步操作管理
- 完整的版本控制
- 灵活的冲突解决
- 强大的加密支持
- 详细的审计日志
- 优秀的性能和可扩展性
