-- ============================================================================
-- X-Agent RBAC (Role-Based Access Control) Schema
-- P0-05: RBAC 持久化 - 替代内存存储，支持重启后保留角色和权限
-- ============================================================================

-- 角色表
CREATE TABLE IF NOT EXISTS rbac_roles (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    permissions JSONB NOT NULL DEFAULT '[]',
    parent_roles TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 用户角色分配表
CREATE TABLE IF NOT EXISTS rbac_user_roles (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    role_id VARCHAR(64) NOT NULL REFERENCES rbac_roles(id) ON DELETE CASCADE,
    assigned_by VARCHAR(128) NOT NULL DEFAULT 'system',
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    delegated_to TEXT[] NOT NULL DEFAULT '{}',
    scope JSONB NOT NULL DEFAULT '{}',
    UNIQUE(user_id, role_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_user_id ON rbac_user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_role_id ON rbac_user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_expires_at ON rbac_user_roles(expires_at) WHERE expires_at IS NOT NULL;

-- 审计日志表 (可选，用于记录权限变更)
CREATE TABLE IF NOT EXISTS rbac_audit_log (
    id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    user_id VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    result VARCHAR(32) NOT NULL,  -- 'allowed', 'denied', 'error'
    reason TEXT DEFAULT '',
    attributes JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_rbac_audit_log_user_id ON rbac_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_log_timestamp ON rbac_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rbac_audit_log_action ON rbac_audit_log(action);

-- 插入默认角色
INSERT INTO rbac_roles (id, name, description, permissions, parent_roles)
VALUES
    ('role-admin', 'Administrator', 'Full system access', 
     '[{"resource_type": "*", "action": "*"}]'::jsonb, '{}'),
    ('role-user', 'User', 'Standard user access',
     '[{"resource_type": "agent", "action": "run"}, {"resource_type": "workflow", "action": "read"}, {"resource_type": "workflow", "action": "execute"}]'::jsonb, '{}'),
    ('role-viewer', 'Viewer', 'Read-only access',
     '[{"resource_type": "*", "action": "read"}]'::jsonb, '{}')
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE rbac_roles IS 'RBAC角色定义表 - P0-05持久化存储';
COMMENT ON TABLE rbac_user_roles IS '用户角色分配表 - 支持过期时间和委派';
COMMENT ON TABLE rbac_audit_log IS 'RBAC审计日志 - 记录所有权限相关操作';
