# X-Agent Environment Configuration Files

> P0-03 更正说明(2026-07-19): 旧版此文件把 `ENVIRONMENT` / `DEBUG` / `SECRET_KEY` /
> `API_WORKERS` / `PROMETHEUS_ENABLED` 等列为应用变量 —— **后端并不读取这些名字**,
> 按旧说明部署会以 sqlite 默认值启动。以下为与代码一致的修正版。

## 两层变量, 不要混淆

### 1. Compose 插值变量(不带 XAGENT_ 前缀)

仅供 `docker-compose*.yml` 的 `${VAR:-default}` 插值, 以及 postgres/redis/neo4j
官方镜像自身的原生变量(如 `POSTGRES_USER`)。它们**不会被后端进程直接读取**:

```bash
# Database (compose 插值 + postgres 镜像原生变量)
DB_USER=xagent
DB_PASSWORD=change_me
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=change_me
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=change_me
QDRANT_PORT=6333

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me
NEO4J_PORT=7687

# API 对外发布端口 (compose ports 插值)
API_PORT=8000
```

### 2. 应用变量(必须带 XAGENT_ 前缀)

后端主配置为 `backend/app/settings.py` 的 `Settings`(pydantic-settings,
`env_prefix="XAGENT_"`, `extra="ignore"`)。**所有应用配置必须以 `XAGENT_` 开头**,
未定义的 `XAGENT_*` 变量会被忽略而非报错。

例外: `LOG_LEVEL` 保持不带前缀 —— 它由 `backend/app/monitoring/__init__.py`
与 `backend/app/core/config.py` 的 `LogSettings`(`env_prefix="LOG_"`)直接读取。

## Development Environment (.env.development)

```bash
# --- Compose 插值变量 (见上节) ---
DB_USER=xagent
DB_PASSWORD=xagent_dev
DB_NAME=xagent_db
DB_PORT=5432
REDIS_PASSWORD=redis_dev
REDIS_PORT=6379
QDRANT_API_KEY=qdrant_dev_key
QDRANT_PORT=6333
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_dev
NEO4J_PORT=7687
API_PORT=8000

# --- 应用变量 (XAGENT_ 前缀) ---
XAGENT_APP_MODE=development
XAGENT_DEBUG=true
XAGENT_DATABASE_URL=postgresql+asyncpg://xagent:xagent_dev@localhost:5432/xagent_db
XAGENT_REDIS_URL=redis://:redis_dev@localhost:6379/0
XAGENT_QDRANT_URL=http://localhost:6333
XAGENT_QDRANT_API_KEY=qdrant_dev_key
XAGENT_LLM_BACKEND=mock
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
LOG_LEVEL=DEBUG
```

## Staging Environment (.env.staging)

```bash
# --- Compose 插值变量 ---
DB_USER=xagent
DB_PASSWORD=staging_secure_password_here
DB_NAME=xagent_db
DB_PORT=5432
REDIS_PASSWORD=staging_secure_password_here
REDIS_PORT=6379
QDRANT_API_KEY=staging_secure_key_here
QDRANT_PORT=6333
NEO4J_USER=neo4j
NEO4J_PASSWORD=staging_secure_password_here
NEO4J_PORT=7687
API_PORT=8000

# --- 应用变量 (XAGENT_ 前缀) ---
XAGENT_APP_MODE=staging
XAGENT_DEBUG=false
XAGENT_DATABASE_URL=postgresql+asyncpg://xagent:staging_secure_password_here@postgres:5432/xagent_db
XAGENT_REDIS_URL=redis://:staging_secure_password_here@redis:6379/0
XAGENT_QDRANT_URL=http://qdrant:6333
XAGENT_QDRANT_API_KEY=staging_secure_key_here
XAGENT_JWT_SECRET=staging_strong_random_secret_min_32_chars
XAGENT_ENCRYPTION_KEY=staging_strong_random_key_min_32_chars
XAGENT_LLM_BACKEND=openai
XAGENT_OPENAI_API_KEY=sk-...
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
LOG_LEVEL=INFO
```

## Production Environment (.env.production)

```bash
# --- Compose 插值变量 ---
DB_USER=xagent
DB_PASSWORD=production_very_secure_password_here
DB_NAME=xagent_db
DB_PORT=5432
REDIS_PASSWORD=production_very_secure_password_here
REDIS_PORT=6379
QDRANT_API_KEY=production_very_secure_key_here
QDRANT_PORT=6333
NEO4J_USER=neo4j
NEO4J_PASSWORD=production_very_secure_password_here
NEO4J_PORT=7687
API_PORT=8000

# --- 应用变量 (XAGENT_ 前缀) ---
XAGENT_APP_MODE=production
XAGENT_DEBUG=false
XAGENT_DATABASE_URL=postgresql+asyncpg://xagent:production_very_secure_password_here@postgres:5432/xagent_db
XAGENT_REDIS_URL=redis://:production_very_secure_password_here@redis:6379/0
XAGENT_QDRANT_URL=http://qdrant:6333
XAGENT_QDRANT_API_KEY=production_very_secure_key_here
# 生产模式强制校验: 以下两者必须为非默认强随机值, >=32 字符且包含大写字母与数字,
# 否则 Settings 校验失败、进程拒绝启动 (backend/app/settings.py  validator)
XAGENT_JWT_SECRET=production_strong_random_secret_min_32_chars
XAGENT_ENCRYPTION_KEY=production_strong_random_key_min_32_chars
XAGENT_AUDIT_HMAC_SECRET=production_strong_random_hmac_secret
XAGENT_LLM_BACKEND=openai
XAGENT_OPENAI_API_KEY=sk-...
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
LOG_LEVEL=WARNING
```

## 已删除的误导变量

| 旧变量名 | 状态 | 说明 |
|---|---|---|
| `ENVIRONMENT` | 删除 | 改用 `XAGENT_APP_MODE` |
| `DEBUG` | 删除 | 改用 `XAGENT_DEBUG` |
| `SECRET_KEY` | 删除 | 改用 `XAGENT_JWT_SECRET`(并补 `XAGENT_ENCRYPTION_KEY`) |
| `API_HOST` / `API_PORT` / `API_WORKERS`(容器内) | 无效 | uvicorn 启动参数在 `Dockerfile` CMD 中固定; compose 层的 `${API_PORT}` 仅用于端口发布插值 |
| `PROMETHEUS_ENABLED` / `GRAFANA_ENABLED` | 删除 | 后端不读取; 监控接线见审计 P0-04 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | 删除 | 后端无 Celery 应用; worker/beat 编排命令已改为 `python -m backend.app.workflow_worker`。`requirements.txt` 中 celery 依赖保留但标注未使用, 待真 Celery 返工 |
