-- ============================================================================
-- X-Agent RBAC Multi-Tenant Tables (P0-05)
-- Migration 008: Add tenant_id to RBAC tables for multi-tenant isolation
-- ============================================================================
-- This migration extends the base rbac_schema.sql with tenant isolation support.
-- Safe to run idempotently (IF NOT EXISTS / IF EXISTS guards).

-- 1. Add tenant_id to rbac_roles if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rbac_roles' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE rbac_roles ADD COLUMN tenant_id VARCHAR(128) NOT NULL DEFAULT 'default';
    END IF;
END $$;

-- 2. Add tenant_id to rbac_user_roles if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rbac_user_roles' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE rbac_user_roles ADD COLUMN tenant_id VARCHAR(128) NOT NULL DEFAULT 'default';
    END IF;
END $$;

-- 3. Add granted_at / granted_by to rbac_user_roles if not present (alias for assigned_at/assigned_by)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rbac_user_roles' AND column_name = 'granted_at'
    ) THEN
        ALTER TABLE rbac_user_roles ADD COLUMN granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rbac_user_roles' AND column_name = 'granted_by'
    ) THEN
        ALTER TABLE rbac_user_roles ADD COLUMN granted_by VARCHAR(128) DEFAULT 'system';
    END IF;
END $$;

-- 4. Tenant-scoped indexes for efficient per-tenant queries
CREATE INDEX IF NOT EXISTS idx_rbac_roles_tenant_id ON rbac_roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_tenant_id ON rbac_user_roles(tenant_id);

-- 5. Composite unique: role name is unique per tenant (not globally)
-- Drop the old global unique constraint if it exists, replace with tenant-scoped
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'rbac_roles_name_key' AND conrelid = 'rbac_roles'::regclass
    ) THEN
        ALTER TABLE rbac_roles DROP CONSTRAINT rbac_roles_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rbac_roles_name_tenant
    ON rbac_roles(name, tenant_id);

-- 6. Composite unique: user can only have a role once per tenant
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'rbac_user_roles_user_id_role_id_key'
              AND conrelid = 'rbac_user_roles'::regclass
    ) THEN
        ALTER TABLE rbac_user_roles DROP CONSTRAINT rbac_user_roles_user_id_role_id_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rbac_user_roles_user_role_tenant
    ON rbac_user_roles(user_id, role_id, tenant_id);

-- 7. Updated_at trigger for rbac_roles
CREATE OR REPLACE FUNCTION update_rbac_roles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rbac_roles_updated_at ON rbac_roles;
CREATE TRIGGER trg_rbac_roles_updated_at
    BEFORE UPDATE ON rbac_roles
    FOR EACH ROW
    EXECUTE FUNCTION update_rbac_roles_updated_at();

-- 8. Insert default tenant-scoped roles (idempotent)
INSERT INTO rbac_roles (id, name, description, permissions, parent_roles, tenant_id)
VALUES
    ('role-admin-default', 'Administrator', 'Full system access',
     '[{"resource_type": "*", "action": "*"}]'::jsonb, '{}', 'default'),
    ('role-user-default', 'User', 'Standard user access',
     '[{"resource_type": "agent", "action": "run"}, {"resource_type": "workflow", "action": "read"}, {"resource_type": "workflow", "action": "execute"}]'::jsonb, '{}', 'default'),
    ('role-viewer-default', 'Viewer', 'Read-only access',
     '[{"resource_type": "*", "action": "read"}]'::jsonb, '{}', 'default')
ON CONFLICT (id) DO NOTHING;

-- Comments
COMMENT ON COLUMN rbac_roles.tenant_id IS 'Tenant isolation: role belongs to this tenant';
COMMENT ON COLUMN rbac_user_roles.tenant_id IS 'Tenant isolation: assignment scoped to tenant';
COMMENT ON COLUMN rbac_user_roles.granted_at IS 'When the role was granted (alias for assigned_at)';
COMMENT ON COLUMN rbac_user_roles.granted_by IS 'Who granted the role (alias for assigned_by)';
