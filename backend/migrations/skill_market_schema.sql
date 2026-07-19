-- 技能市场完整数据库架构

-- ==================== 技能表 ====================
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL DEFAULT '1.0.0',
    author TEXT NOT NULL,
    description TEXT,
    description_zh TEXT,
    long_description TEXT,
    long_description_zh TEXT,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    risk_level TEXT NOT NULL DEFAULT 'medium',

    -- 中文化内容
    what_is_it TEXT,
    who_is_it_for TEXT,
    how_to_use TEXT,
    tutorial TEXT,

    -- 统计信息
    downloads INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0.0,
    rating_count INTEGER DEFAULT 0,
    installed_count INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,

    -- 源信息
    source_repo TEXT,
    source_url TEXT,
    source_type TEXT DEFAULT 'github',

    -- 元数据
    icon_emoji TEXT,
    icon_url TEXT,
    homepage TEXT,
    repository TEXT,
    license TEXT DEFAULT 'MIT',
    keywords TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    capabilities TEXT[] DEFAULT '{}',
    permissions TEXT[] DEFAULT '{}',
    entry_point TEXT,

    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,

    CONSTRAINT skills_category_check CHECK (category IN (
        'office', 'design', 'development', 'data', 'automation',
        'learning', 'search', 'creativity'
    )),
    CONSTRAINT skills_status_check CHECK (status IN (
        'draft', 'published', 'installing', 'installed', 'updating', 'disabled', 'error'
    )),
    CONSTRAINT skills_risk_check CHECK (risk_level IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX idx_skills_tenant_category ON skills(tenant_id, category);
CREATE INDEX idx_skills_tenant_status ON skills(tenant_id, status);
CREATE INDEX idx_skills_rating ON skills(rating DESC);
CREATE INDEX idx_skills_downloads ON skills(downloads DESC);
CREATE INDEX idx_skills_created ON skills(created_at DESC);
CREATE INDEX idx_skills_name_trgm ON skills USING gin(name gin_trgm_ops);
CREATE INDEX idx_skills_name_zh_trgm ON skills USING gin(name_zh gin_trgm_ops);

-- ==================== 技能版本表 ====================
CREATE TABLE IF NOT EXISTS skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    release_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changelog TEXT,
    compatibility TEXT,
    deprecated BOOLEAN DEFAULT FALSE,
    download_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(skill_id, version)
);

CREATE INDEX idx_skill_versions_skill_id ON skill_versions(skill_id);
CREATE INDEX idx_skill_versions_version ON skill_versions(version DESC);

-- ==================== 技能评论表 ====================
CREATE TABLE IF NOT EXISTS skill_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title TEXT NOT NULL,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    helpful_count INTEGER DEFAULT 0,
    unhelpful_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_reviews_status_check CHECK (status IN ('pending', 'approved', 'rejected', 'hidden'))
);

CREATE INDEX idx_skill_reviews_skill_id ON skill_reviews(skill_id);
CREATE INDEX idx_skill_reviews_user_id ON skill_reviews(user_id);
CREATE INDEX idx_skill_reviews_rating ON skill_reviews(rating DESC);
CREATE INDEX idx_skill_reviews_created ON skill_reviews(created_at DESC);

-- ==================== 技能依赖表 ====================
CREATE TABLE IF NOT EXISTS skill_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    dep_skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    version_spec TEXT,
    dep_type TEXT NOT NULL DEFAULT 'required',
    optional BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_dependencies_type_check CHECK (dep_type IN ('required', 'optional', 'peer'))
);

CREATE INDEX idx_skill_dependencies_skill_id ON skill_dependencies(skill_id);
CREATE INDEX idx_skill_dependencies_dep_skill_id ON skill_dependencies(dep_skill_id);

-- ==================== 技能安装表 ====================
CREATE TABLE IF NOT EXISTS skill_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'installed',
    config JSONB DEFAULT '{}',
    install_path TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(tenant_id, user_id, skill_id),
    CONSTRAINT skill_installations_status_check CHECK (status IN ('installing', 'installed', 'updating', 'uninstalling', 'error'))
);

CREATE INDEX idx_skill_installations_tenant_user ON skill_installations(tenant_id, user_id);
CREATE INDEX idx_skill_installations_skill_id ON skill_installations(skill_id);
CREATE INDEX idx_skill_installations_status ON skill_installations(status);

-- ==================== 技能使用记录表 ====================
CREATE TABLE IF NOT EXISTS skill_usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'success',
    error TEXT,
    duration_ms INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_usage_records_status_check CHECK (status IN ('success', 'error', 'timeout', 'cancelled'))
);

CREATE INDEX idx_skill_usage_records_tenant_user ON skill_usage_records(tenant_id, user_id);
CREATE INDEX idx_skill_usage_records_skill_id ON skill_usage_records(skill_id);
CREATE INDEX idx_skill_usage_records_created ON skill_usage_records(created_at DESC);

-- ==================== 技能搜索索引表 ====================
CREATE TABLE IF NOT EXISTS skill_search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    search_text TEXT NOT NULL,
    search_type TEXT NOT NULL,
    relevance_score DECIMAL(5,4) DEFAULT 1.0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_search_index_type_check CHECK (search_type IN ('name', 'description', 'keyword', 'tag', 'category'))
);

CREATE INDEX idx_skill_search_index_skill_id ON skill_search_index(skill_id);
CREATE INDEX idx_skill_search_index_text_trgm ON skill_search_index USING gin(search_text gin_trgm_ops);

-- ==================== 技能推荐表 ====================
CREATE TABLE IF NOT EXISTS skill_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    similarity_score DECIMAL(5,4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(tenant_id, user_id, skill_id)
);

CREATE INDEX idx_skill_recommendations_tenant_user ON skill_recommendations(tenant_id, user_id);
CREATE INDEX idx_skill_recommendations_skill_id ON skill_recommendations(skill_id);

-- ==================== 技能审核表 ====================
CREATE TABLE IF NOT EXISTS skill_reviews_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_reviews_audit_action_check CHECK (action IN ('submitted', 'approved', 'rejected', 'published', 'unpublished', 'flagged'))
);

CREATE INDEX idx_skill_reviews_audit_skill_id ON skill_reviews_audit(skill_id);
CREATE INDEX idx_skill_reviews_audit_created ON skill_reviews_audit(created_at DESC);

-- ==================== 技能更新表 ====================
CREATE TABLE IF NOT EXISTS skill_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    current_version TEXT NOT NULL,
    new_version TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'available',
    progress INTEGER DEFAULT 0,
    changelog TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT skill_updates_priority_check CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    CONSTRAINT skill_updates_status_check CHECK (status IN ('available', 'installing', 'installed', 'failed', 'cancelled'))
);

CREATE INDEX idx_skill_updates_skill_id ON skill_updates(skill_id);
CREATE INDEX idx_skill_updates_status ON skill_updates(status);
CREATE INDEX idx_skill_updates_created ON skill_updates(created_at DESC);

-- ==================== 技能分类表 ====================
CREATE TABLE IF NOT EXISTS skill_categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    icon TEXT NOT NULL,
    description TEXT,
    description_zh TEXT,
    skill_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO skill_categories (id, name, name_zh, icon, description, description_zh) VALUES
('office', 'Office Assistant', '办公助手', '📝', 'Document processing, spreadsheet operations, presentation creation', '文档处理、表格操作、PPT制作'),
('design', 'Design Tools', '设计助手', '🎨', 'Image processing, video editing, UI design', '图片处理、视频编辑、UI设计'),
('development', 'Development Tools', '编程助手', '💻', 'Code generation, debugging assistant, Git tools', '代码生成、调试助手、Git工具'),
('data', 'Data Analysis', '数据助手', '📊', 'Data cleaning, visualization, report generation', '数据清洗、可视化、报表生成'),
('automation', 'Automation', '自动化助手', '🤖', 'Web automation, desktop automation, scheduled tasks', '网页自动化、桌面自动化、定时任务'),
('learning', 'Learning Assistant', '学习助手', '📚', 'Knowledge base, tutorial generation, Q&A', '知识库、教程生成、问答'),
('search', 'Search Tools', '搜索助手', '🔍', 'Web search, document search, semantic search', '网页搜索、文档搜索、语义搜索'),
('creativity', 'Creativity Tools', '创意助手', '✨', 'Content generation, brainstorming, creative writing', '内容生成、头脑风暴、创意写作')
ON CONFLICT (id) DO NOTHING;

-- ==================== 视图 ====================
CREATE OR REPLACE VIEW skill_stats AS
SELECT
    s.id,
    s.name,
    s.name_zh,
    s.category,
    s.rating,
    s.rating_count,
    s.downloads,
    s.installed_count,
    s.usage_count,
    COUNT(DISTINCT si.id) as active_installations,
    COUNT(DISTINCT sr.id) as total_reviews,
    AVG(sr.rating) as avg_rating
FROM skills s
LEFT JOIN skill_installations si ON s.id = si.skill_id AND si.status = 'installed'
LEFT JOIN skill_reviews sr ON s.id = sr.skill_id AND sr.status = 'approved'
GROUP BY s.id, s.name, s.name_zh, s.category, s.rating, s.rating_count, s.downloads, s.installed_count, s.usage_count;
