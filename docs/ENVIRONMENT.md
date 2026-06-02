# X-Agent 环境变量参考

**版本**: 1.0  
**最后更新**: 2026-05-27  
**文档状态**: Published

---

## 目录

1. [环境变量概览](#环境变量概览)
2. [核心配置](#核心配置)
3. [数据库配置](#数据库配置)
4. [LLM配置](#llm配置)
5. [安全配置](#安全配置)
6. [可观测性配置](#可观测性配置)
7. [示例配置](#示例配置)
8. [验证配置](#验证配置)

---

## 环境变量概览

### 配置方式

X-Agent 支持多种配置方式，优先级从高到低：

1. **环境变量** - 最高优先级
2. **.env文件** - 本地开发
3. **配置文件** - 生产环境
4. **默认值** - 最低优先级

### 加载.env文件

```python
# 自动加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

# 或指定路径
load_dotenv('/etc/xagent/.env')
```

---

## 核心配置

### 应用配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `APP_NAME` | 应用名称 | X-Agent | X-Agent |
| `APP_VERSION` | 应用版本 | 0.1.0 | 0.1.0 |
| `ENVIRONMENT` | 运行环境 | development | production |
| `DEBUG` | 调试模式 | false | false |
| `LOG_LEVEL` | 日志级别 | INFO | DEBUG |
| `LOG_FORMAT` | 日志格式 | text | json |

```env
# .env
APP_NAME=X-Agent
APP_VERSION=0.1.0
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 服务器配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `HOST` | 监听地址 | 0.0.0.0 | 0.0.0.0 |
| `PORT` | 监听端口 | 8000 | 8000 |
| `WORKERS` | 工作进程数 | 4 | 4 |
| `RELOAD` | 热重载 | false | false |
| `TIMEOUT` | 请求超时(秒) | 60 | 60 |

```env
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=false
TIMEOUT=60
```

---

## 数据库配置

### 数据库连接

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `DATABASE_URL` | 数据库连接字符串 | sqlite:///./data/xagent.db | postgresql://user:pass@localhost/xagent |
| `DATABASE_POOL_SIZE` | 连接池大小 | 20 | 20 |
| `DATABASE_MAX_OVERFLOW` | 最大溢出连接 | 40 | 40 |
| `DATABASE_POOL_RECYCLE` | 连接回收时间(秒) | 3600 | 3600 |
| `DATABASE_ECHO` | SQL日志 | false | false |

```env
# SQLite (开发)
DATABASE_URL=sqlite:///./data/xagent.db

# PostgreSQL (生产)
DATABASE_URL=postgresql://xagent:secure_password@db.example.com:5432/xagent
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_RECYCLE=3600
DATABASE_ECHO=false
```

### 向量数据库配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `QDRANT_URL` | Qdrant服务地址 | http://localhost:6333 | http://qdrant.example.com:6333 |
| `QDRANT_API_KEY` | Qdrant API密钥 | - | your-api-key |
| `QDRANT_COLLECTION` | 集合名称 | xagent_memory | xagent_memory |

```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION=xagent_memory
```

### Redis配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `REDIS_URL` | Redis连接字符串 | redis://localhost:6379/0 | redis://redis.example.com:6379/0 |
| `REDIS_PASSWORD` | Redis密码 | - | secure_password |
| `REDIS_DB` | Redis数据库 | 0 | 0 |

```env
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=secure_password
REDIS_DB=0
```

---

## LLM配置

### OpenAI配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `OPENAI_API_KEY` | OpenAI API密钥 | - | sk-... |
| `OPENAI_MODEL` | 默认模型 | gpt-4 | gpt-4 |
| `OPENAI_TEMPERATURE` | 温度参数 | 0.7 | 0.7 |
| `OPENAI_MAX_TOKENS` | 最大令牌数 | 2000 | 2000 |

```env
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2000
```

### DeepSeek配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 | - | your-api-key |
| `DEEPSEEK_MODEL` | 默认模型 | deepseek-chat | deepseek-chat |
| `DEEPSEEK_BASE_URL` | API基础URL | https://api.deepseek.com | https://api.deepseek.com |

```env
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 嵌入模型配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `EMBEDDING_MODEL` | 嵌入模型 | text-embedding-3-small | text-embedding-3-small |
| `EMBEDDING_DIMENSION` | 嵌入维度 | 1536 | 1536 |

```env
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

---

## 安全配置

### JWT配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `JWT_SECRET` | JWT密钥 | - | your-secret-key-min-32-chars |
| `JWT_ALGORITHM` | JWT算法 | HS256 | HS256 |
| `JWT_EXPIRATION_HOURS` | JWT过期时间(小时) | 24 | 24 |

```env
JWT_SECRET=your-secret-key-min-32-chars-long
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

### CORS配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `CORS_ORIGINS` | 允许的源 | http://localhost:3000 | https://app.example.com,https://admin.example.com |
| `CORS_CREDENTIALS` | 允许凭证 | true | true |
| `CORS_METHODS` | 允许的方法 | GET,POST,PUT,DELETE | GET,POST,PUT,DELETE |

```env
# 开发环境
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# 生产环境
CORS_ORIGINS=https://app.example.com,https://admin.example.com
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE
```

### 加密配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `ENCRYPTION_KEY` | 加密密钥 | - | your-encryption-key |
| `ENCRYPTION_ALGORITHM` | 加密算法 | AES-256-GCM | AES-256-GCM |

```env
ENCRYPTION_KEY=your-encryption-key-base64-encoded
ENCRYPTION_ALGORITHM=AES-256-GCM
```

### 认证配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `AUTH_PROVIDER` | 认证提供商 | local | local |
| `OAUTH_GOOGLE_CLIENT_ID` | Google OAuth客户端ID | - | your-client-id |
| `OAUTH_GOOGLE_CLIENT_SECRET` | Google OAuth客户端密钥 | - | your-client-secret |

```env
AUTH_PROVIDER=local
OAUTH_GOOGLE_CLIENT_ID=your-client-id
OAUTH_GOOGLE_CLIENT_SECRET=your-client-secret
```

---

## 可观测性配置

### Langfuse配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse公钥 | - | pk_... |
| `LANGFUSE_SECRET_KEY` | Langfuse密钥 | - | sk_... |
| `LANGFUSE_HOST` | Langfuse主机 | https://cloud.langfuse.com | https://cloud.langfuse.com |

```env
LANGFUSE_PUBLIC_KEY=pk_your-public-key
LANGFUSE_SECRET_KEY=sk_your-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 日志配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `LOG_FILE` | 日志文件路径 | /var/log/xagent/app.log | /var/log/xagent/app.log |
| `LOG_MAX_SIZE` | 日志文件最大大小(MB) | 100 | 100 |
| `LOG_BACKUP_COUNT` | 日志备份数量 | 10 | 10 |

```env
LOG_FILE=/var/log/xagent/app.log
LOG_MAX_SIZE=100
LOG_BACKUP_COUNT=10
```

### 审计日志配置

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `AUDIT_LOG_ENABLED` | 启用审计日志 | true | true |
| `AUDIT_LOG_LEVEL` | 审计日志级别 | INFO | INFO |
| `AUDIT_LOG_RETENTION_DAYS` | 审计日志保留天数 | 90 | 90 |

```env
AUDIT_LOG_ENABLED=true
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_RETENTION_DAYS=90
```

---

## 示例配置

### 开发环境配置

```env
# .env.development
APP_NAME=X-Agent
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text

HOST=0.0.0.0
PORT=8000
WORKERS=1
RELOAD=true

DATABASE_URL=sqlite:///./data/xagent.db
REDIS_URL=redis://localhost:6379/0

OPENAI_API_KEY=sk-your-dev-key
OPENAI_MODEL=gpt-3.5-turbo

JWT_SECRET=dev-secret-key-min-32-chars-long
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

LANGFUSE_PUBLIC_KEY=pk_dev_key
LANGFUSE_SECRET_KEY=sk_dev_key
```

### 生产环境配置

```env
# .env.production
APP_NAME=X-Agent
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=false
TIMEOUT=60

DATABASE_URL=postgresql://xagent:secure_password@db.example.com:5432/xagent
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
REDIS_URL=redis://redis.example.com:6379/0
REDIS_PASSWORD=secure_password

OPENAI_API_KEY=sk-your-prod-key
OPENAI_MODEL=gpt-4

JWT_SECRET=prod-secret-key-min-32-chars-long-and-secure
CORS_ORIGINS=https://app.example.com,https://admin.example.com
CORS_CREDENTIALS=true

ENCRYPTION_KEY=your-encryption-key-base64-encoded
LANGFUSE_PUBLIC_KEY=pk_prod_key
LANGFUSE_SECRET_KEY=sk_prod_key

AUDIT_LOG_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=90
```

---

## 验证配置

### 配置检查脚本

```python
# scripts/validate_config.py
import os
from dotenv import load_dotenv

def validate_config():
    """验证配置是否完整"""
    
    load_dotenv()
    
    required_vars = [
        'DATABASE_URL',
        'JWT_SECRET',
        'OPENAI_API_KEY',
    ]
    
    optional_vars = [
        'REDIS_URL',
        'LANGFUSE_PUBLIC_KEY',
    ]
    
    errors = []
    warnings = []
    
    # 检查必需变量
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"缺少必需变量: {var}")
    
    # 检查可选变量
    for var in optional_vars:
        if not os.getenv(var):
            warnings.append(f"缺少可选变量: {var}")
    
    # 验证JWT_SECRET长度
    jwt_secret = os.getenv('JWT_SECRET', '')
    if len(jwt_secret) < 32:
        errors.append("JWT_SECRET长度必须至少32个字符")
    
    # 验证数据库连接
    try:
        from sqlalchemy import create_engine
        engine = create_engine(os.getenv('DATABASE_URL'))
        engine.connect()
        print("✓ 数据库连接成功")
    except Exception as e:
        errors.append(f"数据库连接失败: {e}")
    
    # 输出结果
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    if warnings:
        print("⚠️  配置警告:")
        for warning in warnings:
            print(f"  - {warning}")
    
    print("✓ 配置验证成功")
    return True

if __name__ == "__main__":
    validate_config()
```

### 运行验证

```bash
# 验证配置
python scripts/validate_config.py

# 输出示例
# ✓ 数据库连接成功
# ✓ 配置验证成功
```

---

## 安全注意事项

### 密钥管理

- 不要在代码中硬编码密钥
- 使用环境变量或密钥管理服务
- 定期轮换密钥
- 使用强密钥(最少32个字符)

### 文件权限

```bash
# 设置.env文件权限
chmod 600 .env

# 设置日志文件权限
chmod 640 /var/log/xagent/app.log
```

### 敏感信息

- 不要在日志中记录敏感信息
- 不要在错误消息中暴露密钥
- 定期审计配置文件

---

## 相关资源

- [配置管理](CONFIG_MANAGEMENT.md)
- [安全指南](SECURITY_GUIDE.md)
- [部署指南](DEPLOYMENT_GUIDE.md)

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 配置团队  
**许可证**: MIT
