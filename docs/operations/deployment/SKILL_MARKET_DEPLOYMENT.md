# 技能市场部署和配置指南

## 目录

1. [系统要求](#系统要求)
2. [数据库设置](#数据库设置)
3. [后端部署](#后端部署)
4. [前端部署](#前端部署)
5. [配置](#配置)
6. [监控和维护](#监控和维护)
7. [故障排查](#故障排查)

## 系统要求

### 硬件要求

- CPU: 4核或以上
- 内存: 8GB 或以上
- 存储: 100GB 或以上（用于技能存储）
- 网络: 100Mbps 或以上

### 软件要求

- Python 3.9+
- Node.js 16+
- PostgreSQL 12+
- Redis 6+
- Docker (可选)

## 数据库设置

### 1. 创建数据库

```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE xagent_skill_market;

# 创建用户
CREATE USER skill_market_user WITH PASSWORD 'secure_password';

# 授予权限
GRANT ALL PRIVILEGES ON DATABASE xagent_skill_market TO skill_market_user;
```

### 2. 运行迁移

```bash
# 运行初始化脚本
psql -U skill_market_user -d xagent_skill_market -f backend/migrations/init_schema.sql

# 运行技能市场架构脚本
psql -U skill_market_user -d xagent_skill_market -f backend/migrations/skill_market_schema.sql
```

### 3. 验证数据库

```bash
# 连接到数据库
psql -U skill_market_user -d xagent_skill_market

# 查看表
\dt

# 查看视图
\dv
```

## 后端部署

### 1. 安装依赖

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 数据库
DATABASE_URL=postgresql://skill_market_user:secure_password@localhost:5432/xagent_skill_market

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# 认证
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256

# 技能存储
SKILL_STORAGE_PATH=/var/lib/xagent/skills
SKILL_CACHE_PATH=/var/cache/xagent/skills

# 日志
LOG_LEVEL=INFO
LOG_FILE=/var/log/xagent/skill_market.log

# 功能开关
ENABLE_SKILL_REVIEW=true
ENABLE_SKILL_RECOMMENDATIONS=true
ENABLE_USAGE_TRACKING=true
```

### 3. 启动后端服务

```bash
# 开发环境
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

# 生产环境
gunicorn -w 4 -b 0.0.0.0:8000 backend.app.web:app
```

### 4. 使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "backend.app.web:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
# 构建镜像
docker build -t xagent-skill-market:latest .

# 运行容器
docker run -d \
  --name xagent-skill-market \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  xagent-skill-market:latest
```

## 前端部署

### 1. 安装依赖

```bash
cd frontend

npm install
```

### 2. 配置环境变量

创建 `.env.production` 文件：

```env
VITE_API_URL=https://api.x-agent.com
VITE_SKILL_MARKET_URL=https://skills.x-agent.com
VITE_LOG_LEVEL=info
```

### 3. 构建前端

```bash
# 开发环境
npm run dev

# 生产环境
npm run build

# 预览生产构建
npm run preview
```

### 4. 部署到 CDN

```bash
# 构建
npm run build

# 上传到 CDN
aws s3 sync dist/ s3://xagent-skill-market-cdn/

# 清除 CDN 缓存
aws cloudfront create-invalidation --distribution-id E123456 --paths "/*"
```

## 配置

### 技能市场配置

编辑 `config/skill_market.yaml`：

```yaml
# 技能市场配置
skill_market:
  # 最大技能数
  max_skills: 200

  # 最大安装时间（秒）
  max_install_time: 3

  # 最大搜索响应时间（秒）
  max_search_time: 1

  # 技能存储路径
  storage_path: /var/lib/xagent/skills

  # 缓存配置
  cache:
    enabled: true
    ttl: 3600
    max_size: 1000

  # 搜索配置
  search:
    enabled: true
    index_type: postgresql
    batch_size: 100

  # 推荐配置
  recommendations:
    enabled: true
    algorithm: collaborative_filtering
    min_similarity: 0.5

  # 审核配置
  review:
    enabled: true
    auto_approve: false
    require_reviewer: true

  # 使用跟踪
  usage_tracking:
    enabled: true
    batch_size: 100
    flush_interval: 60

  # 安全配置
  security:
    enable_sandboxing: true
    max_execution_time: 300
    max_memory: 512
    allowed_modules:
      - json
      - logging
      - datetime
      - typing
```

### 日志配置

编辑 `config/logging.yaml`：

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: /var/log/xagent/skill_market.log
    maxBytes: 10485760  # 10MB
    backupCount: 10

loggers:
  backend.app.core.skill_market:
    level: DEBUG
    handlers: [console, file]

root:
  level: INFO
  handlers: [console, file]
```

## 监控和维护

### 1. 健康检查

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 检查数据库连接
curl http://localhost:8000/health/db

# 检查缓存连接
curl http://localhost:8000/health/cache
```

### 2. 性能监控

```bash
# 查看技能市场统计
curl http://localhost:8000/api/v1/skill-market/stats

# 查看使用统计
curl http://localhost:8000/api/v1/skill-market/skills/{skill_id}/usage-stats
```

### 3. 日志分析

```bash
# 查看最近的错误
tail -f /var/log/xagent/skill_market.log | grep ERROR

# 统计错误数量
grep ERROR /var/log/xagent/skill_market.log | wc -l

# 查看特定技能的日志
grep "skill_id=xxx" /var/log/xagent/skill_market.log
```

### 4. 数据库维护

```bash
# 分析表
ANALYZE skills;
ANALYZE skill_reviews;
ANALYZE skill_installations;

# 重建索引
REINDEX TABLE skills;
REINDEX TABLE skill_reviews;

# 清理过期数据
DELETE FROM skill_usage_records WHERE created_at < NOW() - INTERVAL '90 days';
```

### 5. 备份和恢复

```bash
# 备份数据库
pg_dump -U skill_market_user xagent_skill_market > backup.sql

# 恢复数据库
psql -U skill_market_user xagent_skill_market < backup.sql

# 备份技能文件
tar -czf skills_backup.tar.gz /var/lib/xagent/skills/

# 恢复技能文件
tar -xzf skills_backup.tar.gz -C /
```

## 故障排查

### 问题1: 数据库连接失败

**症状**: `psycopg2.OperationalError: could not connect to server`

**解决方案**:

```bash
# 检查 PostgreSQL 是否运行
systemctl status postgresql

# 检查连接字符串
echo $DATABASE_URL

# 测试连接
psql -U skill_market_user -d xagent_skill_market -c "SELECT 1"
```

### 问题2: 搜索响应缓慢

**症状**: 搜索耗时 >1 秒

**解决方案**:

```bash
# 检查索引
SELECT * FROM pg_stat_user_indexes WHERE relname = 'skills';

# 重建索引
REINDEX TABLE skills;

# 分析表
ANALYZE skills;

# 检查查询计划
EXPLAIN ANALYZE SELECT * FROM skills WHERE name ILIKE '%test%';
```

### 问题3: 安装失败

**症状**: 技能安装失败，返回错误

**解决方案**:

```bash
# 检查技能文件
ls -la /var/lib/xagent/skills/

# 检查权限
chmod 755 /var/lib/xagent/skills/

# 查看错误日志
tail -f /var/log/xagent/skill_market.log | grep "install"
```

### 问题4: 内存泄漏

**症状**: 内存使用不断增加

**解决方案**:

```bash
# 监控内存使用
watch -n 1 'ps aux | grep python'

# 启用内存分析
export PYTHONUNBUFFERED=1
python -m memory_profiler backend/app/web.py

# 检查缓存大小
redis-cli INFO memory
```

### 问题5: 高并发下性能下降

**症状**: 并发请求时响应缓慢

**解决方案**:

```bash
# 增加 worker 数量
gunicorn -w 8 -b 0.0.0.0:8000 backend.app.web:app

# 启用连接池
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# 启用缓存
CACHE_ENABLED=true
CACHE_TTL=3600

# 使用负载均衡
# 配置 Nginx 或 HAProxy
```

## 性能优化建议

### 1. 数据库优化

- 定期运行 VACUUM 和 ANALYZE
- 使用连接池
- 启用查询缓存
- 优化索引

### 2. 缓存优化

- 使用 Redis 缓存热门技能
- 缓存搜索结果
- 缓存用户推荐

### 3. 前端优化

- 启用代码分割
- 使用懒加载
- 压缩资源
- 启用 CDN

### 4. API 优化

- 使用分页
- 启用 gzip 压缩
- 使用 HTTP 缓存头
- 实施速率限制

## 安全建议

1. **认证和授权**
   - 使用 JWT 令牌
   - 实施角色基访问控制
   - 定期轮换密钥

2. **数据保护**
   - 使用 HTTPS
   - 加密敏感数据
   - 定期备份

3. **输入验证**
   - 验证所有输入
   - 防止 SQL 注入
   - 防止 XSS 攻击

4. **审计日志**
   - 记录所有操作
   - 监控异常活动
   - 定期审查日志
