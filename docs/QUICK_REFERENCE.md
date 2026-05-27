# X-Agent 快速参考卡片

**版本**: 1.0.0  
**最后更新**: 2026-05-27

---

## 目录

1. [常用命令速查](#常用命令速查)
2. [API 端点速查](#api-端点速查)
3. [配置参数速查](#配置参数速查)
4. [错误码速查](#错误码速查)
5. [性能调优速查](#性能调优速查)

---

## 常用命令速查

### 安装和启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 初始化数据库
python -m backend.app.core.migration init

# 启动后端服务
uvicorn backend.app.web:app --reload

# 启动工作流处理器
xagent-workflow-worker

# 启动所有服务（Docker）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

### 开发工具

```bash
# 运行测试
pytest

# 生成覆盖率报告
pytest --cov=backend tests/

# 格式化代码
black backend/

# 检查代码风格
ruff check backend/

# 类型检查
mypy backend/

# 数据库迁移
python -m backend.app.core.migration upgrade
python -m backend.app.core.migration downgrade

# 创建超级用户
python -m backend.app.core.admin create-superuser
```

### Git 工作流

```bash
# 创建功能分支
git checkout -b feature/your-feature

# 提交更改
git commit -m "feat: description"

# 推送分支
git push origin feature/your-feature

# 创建 PR
# 在 GitHub 上创建 PR

# 同步上游代码
git fetch upstream
git rebase upstream/develop

# 合并分支
git merge feature/your-feature
```

---

## API 端点速查

### Agent API

```bash
# 创建 Agent
POST /api/v1/agents
{
  "name": "MyAgent",
  "capabilities": ["run", "memory"]
}

# 列出 Agent
GET /api/v1/agents?page=1&page_size=20

# 获取 Agent 详情
GET /api/v1/agents/{agent_id}

# 更新 Agent
PUT /api/v1/agents/{agent_id}
{
  "name": "UpdatedName"
}

# 删除 Agent
DELETE /api/v1/agents/{agent_id}

# 执行 Agent 任务
POST /api/v1/agents/{agent_id}/run
{
  "task": "task description",
  "timeout": 300
}

# 获取运行状态
GET /api/v1/agents/{agent_id}/runs/{run_id}
```

### Workflow API

```bash
# 创建工作流
POST /api/v1/workflows
{
  "name": "MyWorkflow",
  "nodes": [...],
  "edges": [...]
}

# 列出工作流
GET /api/v1/workflows

# 执行工作流
POST /api/v1/workflows/{workflow_id}/execute
{
  "context": {}
}

# 获取执行结果
GET /api/v1/workflows/{workflow_id}/runs/{run_id}

# 获取执行时间线
GET /api/v1/workflows/{workflow_id}/runs/{run_id}/timeline
```

### Tool API

```bash
# 列出工具
GET /api/v1/tools

# 获取工具详情
GET /api/v1/tools/{tool_id}

# 执行工具
POST /api/v1/tools/{tool_id}/execute
{
  "parameters": {...}
}
```

### Memory API

```bash
# 存储数据
POST /api/v1/memory/store
{
  "key": "key",
  "value": {...}
}

# 检索数据
GET /api/v1/memory/retrieve/{key}

# 搜索数据
POST /api/v1/memory/search
{
  "query": "search query",
  "top_k": 10
}

# 删除数据
DELETE /api/v1/memory/{key}
```

### Approval API

```bash
# 创建审批请求
POST /api/v1/approvals
{
  "action": "delete_agent",
  "resource_id": "agent_123"
}

# 列出审批请求
GET /api/v1/approvals

# 批准请求
POST /api/v1/approvals/{approval_id}/approve
{
  "comment": "Approved"
}

# 拒绝请求
POST /api/v1/approvals/{approval_id}/reject
{
  "reason": "Not approved"
}
```

### Audit API

```bash
# 获取审计日志
GET /api/v1/audit/logs?resource_type=agent&action=create

# 获取资源历史
GET /api/v1/audit/history/{resource_type}/{resource_id}
```

---

## 配置参数速查

### 数据库配置

```bash
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/xagent
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_ECHO=false

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_key
QDRANT_TIMEOUT=30
```

### LLM 配置

```bash
# OpenAI
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2000

# Anthropic
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-3-opus
```

### 应用配置

```bash
# 基本配置
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
SECRET_KEY=your_secret_key

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=4
SERVER_TIMEOUT=300

# 认证配置
JWT_SECRET_KEY=your_secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### 缓存配置

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600
REDIS_MAX_CONNECTIONS=50

# 本地缓存
CACHE_BACKEND=memory
CACHE_MAX_SIZE=1000
```

### 监控配置

```bash
# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Langfuse
LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 错误码速查

### HTTP 状态码

| 码 | 含义 | 解决方案 |
|----|------|---------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 202 | Accepted | 请求已接受 |
| 204 | No Content | 请求成功，无返回内容 |
| 400 | Bad Request | 检查请求参数 |
| 401 | Unauthorized | 检查认证令牌 |
| 403 | Forbidden | 检查权限 |
| 404 | Not Found | 检查资源 ID |
| 409 | Conflict | 资源冲突 |
| 429 | Too Many Requests | 等待后重试 |
| 500 | Internal Server Error | 联系支持 |
| 503 | Service Unavailable | 服务维护中 |

### 应用错误码

| 错误码 | 含义 | 解决方案 |
|-------|------|---------|
| AGENT_NOT_FOUND | Agent 不存在 | 检查 Agent ID |
| WORKFLOW_NOT_FOUND | 工作流不存在 | 检查工作流 ID |
| TOOL_NOT_FOUND | 工具不存在 | 检查工具名称 |
| INVALID_PARAMETERS | 参数无效 | 检查请求参数 |
| EXECUTION_TIMEOUT | 执行超时 | 增加超时时间 |
| INSUFFICIENT_PERMISSIONS | 权限不足 | 检查用户权限 |
| DATABASE_ERROR | 数据库错误 | 检查数据库连接 |
| EXTERNAL_SERVICE_ERROR | 外部服务错误 | 检查外部服务 |

---

## 性能调优速查

### 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_agent_status ON agents(status);
CREATE INDEX idx_workflow_created ON workflows(created_at DESC);

-- 分析表
ANALYZE agents;
ANALYZE workflows;

-- 查看索引使用
SELECT * FROM pg_stat_user_indexes;

-- 查看慢查询
SELECT query, calls, mean_time FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;
```

### 应用优化

```python
# 连接池优化
DATABASE_POOL_SIZE=30
DATABASE_MAX_OVERFLOW=50

# 缓存优化
CACHE_MAX_SIZE=2000
REDIS_CACHE_TTL=7200

# 日志优化
LOG_LEVEL=WARNING  # 生产环境
SQLALCHEMY_ECHO=false
```

### 系统优化

```bash
# 增加文件描述符
ulimit -n 65536

# 调整 TCP 参数
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# 增加虚拟内存
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

### 监控指标

```bash
# CPU 使用率
top -b -n 1 | grep "Cpu(s)"

# 内存使用
free -h

# 磁盘使用
df -h

# 网络连接
netstat -an | grep ESTABLISHED | wc -l

# 数据库连接
psql -d xagent -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## 常见快捷方式

### 开发快捷方式

```bash
# 快速启动开发环境
alias xagent-dev='docker-compose up -d && uvicorn backend.app.web:app --reload'

# 快速运行测试
alias xagent-test='pytest --cov=backend tests/'

# 快速格式化代码
alias xagent-format='black backend/ && ruff check backend/ --fix'

# 快速检查代码质量
alias xagent-lint='ruff check backend/ && mypy backend/'
```

### 数据库快捷方式

```bash
# 连接数据库
alias xagent-db='psql -d xagent'

# 备份数据库
alias xagent-backup='pg_dump -d xagent | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz'

# 恢复数据库
alias xagent-restore='gunzip -c backup.sql.gz | psql -d xagent'
```

### API 快捷方式

```bash
# 获取 API 文档
alias xagent-docs='open http://localhost:8000/docs'

# 测试 API
alias xagent-api='curl -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/v1'

# 查看 API 日志
alias xagent-logs='docker-compose logs -f backend'
```

---

## 常见问题快速解决

### 问题：连接超时

```bash
# 检查服务状态
docker-compose ps

# 重启服务
docker-compose restart backend

# 查看日志
docker-compose logs backend
```

### 问题：内存不足

```bash
# 检查内存使用
free -h

# 清理缓存
redis-cli FLUSHALL

# 重启应用
docker-compose restart backend
```

### 问题：数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose ps postgres

# 检查连接字符串
echo $DATABASE_URL

# 测试连接
psql $DATABASE_URL -c "SELECT 1"
```

### 问题：API 返回 401

```bash
# 检查 API 密钥
echo $API_KEY

# 检查令牌有效期
# 在 JWT 解码器中验证令牌

# 重新生成令牌
curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=user&password=password"
```

---

**X-Agent 快速参考卡片** - 常用命令和参数速查表
