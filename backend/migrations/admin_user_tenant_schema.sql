-- ============================================================================
-- P1-03: 用户/租户管理存储 Postgres 表结构
-- ----------------------------------------------------------------------------
-- 对应代码: backend/app/core/admin_store.py
--   - AdminUserModel   -> admin_users
--   - AdminTenantModel -> admin_tenants
-- 消费方: backend/app/core/admin.py 的 user_store / tenant_store
--   (XAGENT_ADMIN_STORE_BACKEND=postgres 时切换为 SQL 后端)
-- 特性:
--   - 幂等: CREATE ... IF NOT EXISTS, 可在迁移窗口内重复执行
--   - 多实例共享: 状态外置到 Postgres, 替代进程内存字典
--   - 唯一约束: (email, tenant_id) 防并发重复注册(check-then-insert 竞态兜底)
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_tenants (
    id          VARCHAR(36)  PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    plan        VARCHAR(50)  NOT NULL DEFAULT 'free',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_tenants_updated_at
    ON admin_tenants (updated_at DESC);

CREATE TABLE IF NOT EXISTS admin_users (
    id                     VARCHAR(36)  PRIMARY KEY,
    email                  VARCHAR(255) NOT NULL,
    display_name           VARCHAR(255) NOT NULL DEFAULT 'User',
    role                   VARCHAR(50)  NOT NULL DEFAULT 'developer',
    tenant_id              VARCHAR(36)  NOT NULL DEFAULT 'default',
    password_hash          VARCHAR(255),
    -- JSON 数组字符串: 最近 5 次密码哈希(防复用), 与内存版 password_history 对齐
    password_history_json  TEXT         NOT NULL DEFAULT '[]',
    failed_login_attempts  INTEGER      NOT NULL DEFAULT 0,
    locked_until           TIMESTAMPTZ,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_admin_users_email_tenant UNIQUE (email, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email
    ON admin_users (email);

CREATE INDEX IF NOT EXISTS idx_admin_users_tenant_id
    ON admin_users (tenant_id);

CREATE INDEX IF NOT EXISTS idx_admin_users_updated_at
    ON admin_users (updated_at DESC);
