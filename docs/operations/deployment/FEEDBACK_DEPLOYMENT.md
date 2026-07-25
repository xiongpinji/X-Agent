# 反馈系统部署指南

## 快速开始

### 1. 环境准备

#### 系统要求
- Python 3.10+
- PostgreSQL 12+
- 4GB RAM最小
- 2GB磁盘空间

#### 依赖安装

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装TextBlob并下载语料库
pip install textblob
python -m textblob.download_corpora

# 验证安装
python -c "from textblob import TextBlob; print(TextBlob('test').sentiment)"
```

### 2. 数据库配置

#### 创建数据库

```bash
# 连接到PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE xagent_feedback;

# 创建用户
CREATE USER feedback_user WITH PASSWORD 'secure_password';

# 授予权限
GRANT ALL PRIVILEGES ON DATABASE xagent_feedback TO feedback_user;
```

#### 创建表结构

```bash
# 使用SQLAlchemy自动创建表
python -c "
from backend.app.models.feedback import Base, FeedbackModel, FeedbackAnalysisModel
from backend.app.core.session import SessionManager
import asyncio

async def init_db():
    async with SessionManager.get_session() as session:
        await session.run_sync(Base.metadata.create_all)

asyncio.run(init_db())
"

# 或手动执行SQL
psql -U feedback_user -d xagent_feedback < schema.sql
```

#### 创建索引

```sql
-- 反馈表索引
CREATE INDEX idx_feedback_user_tenant ON feedback(user_id, tenant_id);
CREATE INDEX idx_feedback_status_created ON feedback(status, created_at);
CREATE INDEX idx_feedback_severity_priority ON feedback(severity, priority_score);

-- 分析表索引
CREATE INDEX idx_analysis_feedback ON feedback_analysis(feedback_id);
CREATE INDEX idx_analysis_category ON feedback_analysis(category);
```

### 3. 环境变量配置

创建 `.env` 文件：

```bash
# 数据库配置
DATABASE_URL=postgresql://feedback_user:secure_password@localhost:5432/xagent_feedback

# 应用配置
APP_NAME=X-Agent Feedback System
APP_MODE=development
DEBUG=true

# API配置
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# 认证配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS配置
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# 反馈系统配置
FEEDBACK_ANALYSIS_TIMEOUT=30
FEEDBACK_MAX_DESCRIPTION_LENGTH=5000
FEEDBACK_ENABLE_SENTIMENT_ANALYSIS=true
FEEDBACK_ENABLE_AUTO_CATEGORIZATION=true
```

### 4. 启动应用

#### 开发环境

```bash
# 使用uvicorn启动
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用Python直接运行
python -m uvicorn backend.app.main:app --reload
```

#### 生产环境

```bash
# 使用gunicorn + uvicorn
gunicorn backend.app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info

# 或使用Docker
docker build -t xagent-feedback .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e JWT_SECRET_KEY=... \
  xagent-feedback
```

### 5. 验证安装

```bash
# 检查API健康状态
curl http://localhost:8000/api/v1/health/live

# 检查就绪状态
curl http://localhost:8000/api/v1/health/ready

# 创建测试反馈
curl -X POST http://localhost:8000/api/v1/feedback/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{
    "feedback_type": "bug",
    "title": "Test Bug",
    "description": "This is a test bug",
    "severity": "high"
  }'
```

## 配置详解

### 数据库配置

```python
# backend/app/settings.py
DATABASE_URL = "postgresql://user:password@host:port/database"

# 连接池配置
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 40
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_PRE_PING = True
```

### 日志配置

```python
# 日志级别
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# 日志格式
LOG_FORMAT = "json"  # json, text

# 日志输出
LOG_FILE = "/var/log/xagent/feedback.log"
LOG_MAX_BYTES = 10485760  # 10MB
LOG_BACKUP_COUNT = 10
```

### 性能配置

```python
# 缓存配置
CACHE_ENABLED = True
CACHE_TTL = 3600  # 1小时

# 异步配置
ASYNC_WORKERS = 4
ASYNC_QUEUE_SIZE = 1000

# 分析配置
ANALYSIS_TIMEOUT = 30  # 秒
ANALYSIS_BATCH_SIZE = 100
```

## 监控和维护

### 性能监控

```bash
# 监控API响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/v1/feedback/

# 监控数据库连接
psql -U feedback_user -d xagent_feedback -c "SELECT count(*) FROM pg_stat_activity;"

# 监控磁盘使用
du -sh /var/lib/postgresql/data/xagent_feedback
```

### 数据库维护

```bash
# 分析表
ANALYZE feedback;
ANALYZE feedback_analysis;

# 重建索引
REINDEX TABLE feedback;
REINDEX TABLE feedback_analysis;

# 清理死行
VACUUM ANALYZE feedback;
VACUUM ANALYZE feedback_analysis;

# 备份数据库
pg_dump -U feedback_user xagent_feedback > backup.sql

# 恢复数据库
psql -U feedback_user xagent_feedback < backup.sql
```

### 日志管理

```bash
# 查看最近的日志
tail -f /var/log/xagent/feedback.log

# 搜索错误
grep ERROR /var/log/xagent/feedback.log

# 按日期查看日志
grep "2026-05-29" /var/log/xagent/feedback.log

# 日志轮转配置 (/etc/logrotate.d/xagent-feedback)
/var/log/xagent/feedback.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 xagent xagent
    sharedscripts
    postrotate
        systemctl reload xagent-feedback > /dev/null 2>&1 || true
    endscript
}
```

## 故障排除

### 常见问题

#### 1. 数据库连接失败

```
错误: could not connect to server: Connection refused
```

**解决方案:**
```bash
# 检查PostgreSQL是否运行
systemctl status postgresql

# 检查连接字符串
echo $DATABASE_URL

# 测试连接
psql -U feedback_user -d xagent_feedback -c "SELECT 1"
```

#### 2. TextBlob语料库缺失

```
错误: LookupError: Resource punkt not found
```

**解决方案:**
```bash
# 下载语料库
python -m textblob.download_corpora

# 或手动下载
python -c "
import nltk
nltk.download('punkt')
nltk.download('brown')
"
```

#### 3. 内存不足

```
错误: MemoryError: Unable to allocate memory
```

**解决方案:**
```bash
# 增加连接池大小限制
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_MAX_OVERFLOW = 20

# 启用查询缓存
CACHE_ENABLED = True

# 减少工作进程数
ASYNC_WORKERS = 2
```

#### 4. 性能缓慢

```
问题: API响应时间 > 1000ms
```

**解决方案:**
```bash
# 检查数据库索引
psql -U feedback_user -d xagent_feedback -c "
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE tablename IN ('feedback', 'feedback_analysis');"

# 分析查询性能
EXPLAIN ANALYZE SELECT * FROM feedback WHERE status = 'new';

# 增加缓存
CACHE_TTL = 7200

# 启用查询优化
SQLALCHEMY_ECHO = False
```

## 安全加固

### 1. 数据库安全

```bash
# 创建只读用户
CREATE USER feedback_readonly WITH PASSWORD 'readonly_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO feedback_readonly;

# 启用SSL连接
postgresql.conf:
ssl = on
ssl_cert_file = '/etc/postgresql/server.crt'
ssl_key_file = '/etc/postgresql/server.key'

# 配置pg_hba.conf
hostssl all feedback_user 0.0.0.0/0 md5
```

### 2. API安全

```python
# 启用HTTPS
HTTPS_ENABLED = True
SSL_CERT_FILE = "/etc/ssl/certs/server.crt"
SSL_KEY_FILE = "/etc/ssl/private/server.key"

# 启用速率限制
RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 60

# 启用CORS限制
CORS_ORIGINS = ["https://example.com"]
CORS_ALLOW_CREDENTIALS = False
```

### 3. 认证和授权

```python
# JWT配置
JWT_SECRET_KEY = "your-very-secure-secret-key"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# 多租户隔离
TENANT_ISOLATION_ENABLED = True
ENFORCE_TENANT_ISOLATION = True
```

## 扩展和优化

### 1. 缓存层

```python
# 使用Redis缓存
CACHE_BACKEND = "redis"
REDIS_URL = "redis://localhost:6379/0"
CACHE_TTL = 3600

# 缓存策略
CACHE_FEEDBACK_LIST = True
CACHE_FEEDBACK_STATS = True
CACHE_ANALYSIS_RESULTS = True
```

### 2. 消息队列

```python
# 使用Celery处理异步任务
CELERY_BROKER_URL = "redis://localhost:6379/1"
CELERY_RESULT_BACKEND = "redis://localhost:6379/2"

# 异步任务
@celery.task
def analyze_feedback_async(feedback_id):
    # 后台分析反馈
    pass
```

### 3. 搜索引擎

```python
# 使用Elasticsearch进行全文搜索
ELASTICSEARCH_ENABLED = True
ELASTICSEARCH_HOST = "localhost"
ELASTICSEARCH_PORT = 9200

# 索引配置
ELASTICSEARCH_INDEX = "feedback"
ELASTICSEARCH_REFRESH_INTERVAL = "1s"
```

## 监控和告警

### Prometheus指标

```python
# 导出Prometheus指标
from prometheus_client import Counter, Histogram

feedback_created = Counter('feedback_created_total', 'Total feedback created')
feedback_analysis_duration = Histogram('feedback_analysis_duration_seconds', 'Analysis duration')
```

### 告警规则

```yaml
# prometheus.yml
groups:
  - name: feedback
    rules:
      - alert: HighErrorRate
        expr: rate(feedback_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate in feedback API"
      
      - alert: SlowResponse
        expr: histogram_quantile(0.95, feedback_response_time) > 1
        for: 5m
        annotations:
          summary: "Slow response time in feedback API"
```

## 备份和恢复

### 自动备份

```bash
# 创建备份脚本 (backup.sh)
#!/bin/bash
BACKUP_DIR="/backups/xagent"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump -U feedback_user xagent_feedback | gzip > $BACKUP_DIR/feedback_$DATE.sql.gz

# 保留最近30天的备份
find $BACKUP_DIR -name "feedback_*.sql.gz" -mtime +30 -delete

# 添加到crontab
0 2 * * * /path/to/backup.sh
```

### 恢复流程

```bash
# 恢复数据库
gunzip < /backups/xagent/feedback_20260529_020000.sql.gz | \
  psql -U feedback_user xagent_feedback

# 验证恢复
psql -U feedback_user xagent_feedback -c "SELECT COUNT(*) FROM feedback;"
```

## 版本升级

### 升级步骤

```bash
# 1. 备份数据库
pg_dump -U feedback_user xagent_feedback > backup_pre_upgrade.sql

# 2. 停止应用
systemctl stop xagent-feedback

# 3. 更新代码
git pull origin main

# 4. 安装新依赖
pip install -r requirements.txt

# 5. 运行迁移
alembic upgrade head

# 6. 启动应用
systemctl start xagent-feedback

# 7. 验证
curl http://localhost:8000/api/v1/health/ready
```

## 支持和反馈

如有问题或建议，请联系开发团队或提交Issue。
