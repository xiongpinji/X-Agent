# X-Agent 配置管理系统文档

## 概述

X-Agent 配置管理系统提供了一个完整的、企业级的配置解决方案，支持：

- **环境隔离**：开发、测试、生产环境的独立配置
- **配置验证**：启动时的全面验证和类型检查
- **敏感配置加密**：使用 Fernet 加密敏感数据
- **动态配置更新**：支持配置文件热更新和回滚
- **远程配置中心**：支持 Consul 和 Etcd 集成
- **可观测性**：完整的日志、追踪和监控配置

## 架构

```
backend/app/core/config/
├── __init__.py           # 模块入口
├── base.py              # 基础配置和环境检测
├── database.py          # 数据库配置
├── cache.py             # 缓存配置
├── security.py          # 安全配置
├── observability.py     # 可观测性配置
├── settings.py          # 统一设置类
├── validator.py         # 配置验证器
├── encryption.py        # 加密模块
├── reload.py            # 热更新模块
└── remote.py            # 远程配置中心
```

## 配置文件

### 环境配置文件

- `.env.development` - 开发环境配置
- `.env.test` - 测试环境配置
- `.env.production` - 生产环境配置

### 环境检测

系统通过 `XAGENT_ENVIRONMENT` 环境变量自动检测当前环境：

```bash
# 开发环境
export XAGENT_ENVIRONMENT=development

# 测试环境
export XAGENT_ENVIRONMENT=test

# 生产环境
export XAGENT_ENVIRONMENT=production
```

## 配置项说明

### 基础配置 (BaseConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `app_name` | X-Agent | 应用名称 |
| `app_version` | 0.1.0 | 应用版本 |
| `environment` | development | 部署环境 |
| `debug` | false | 调试模式 |
| `project_root` | 自动检测 | 项目根目录 |
| `data_dir` | data/ | 数据目录 |
| `logs_dir` | logs/ | 日志目录 |

### 数据库配置 (DatabaseConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `database_url` | sqlite:///./data/xagent.db | 数据库连接 URL |
| `database_pool_size` | 20 | 连接池大小 |
| `database_max_overflow` | 10 | 最大溢出连接数 |
| `postgres_enable_vector_search` | false | 启用 pgvector |
| `postgres_vector_dimensions` | 1536 | 向量维度 |
| `audit_hmac_secret` | 无 | 审计日志 HMAC 密钥 |

**推荐值**：

- **开发环境**：SQLite（简单快速）
- **测试环境**：SQLite 内存数据库
- **生产环境**：PostgreSQL + pgvector

### 缓存配置 (CacheConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `redis_url` | 无 | Redis 连接 URL |
| `redis_db` | 0 | Redis 数据库号 |
| `cache_ttl_default` | 3600 | 默认缓存 TTL（秒） |
| `cache_ttl_short` | 300 | 短期缓存 TTL（秒） |
| `cache_ttl_long` | 86400 | 长期缓存 TTL（秒） |
| `memory_cache_max_size` | 1000 | 内存缓存最大项数 |

**推荐值**：

- **开发环境**：无 Redis（使用内存缓存）
- **测试环境**：无 Redis（使用内存缓存）
- **生产环境**：Redis（必需）

### 安全配置 (SecurityConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `jwt_secret` | 开发默认值 | JWT 签名密钥（最少 32 字符） |
| `jwt_algorithm` | HS256 | JWT 算法 |
| `jwt_access_token_expire_minutes` | 15 | 访问令牌过期时间 |
| `encryption_key` | 开发默认值 | 加密密钥（最少 32 字符） |
| `bcrypt_cost` | 12 | Bcrypt 成本因子 |
| `require_api_key` | false | 是否需要 API 密钥 |
| `cors_origins` | localhost | CORS 允许的源 |
| `rate_limit_default` | 100 | 默认速率限制 |
| `require_https` | false | 是否需要 HTTPS |

**推荐值**：

- **开发环境**：宽松的安全设置
- **测试环境**：中等安全设置
- **生产环境**：严格的安全设置

### 可观测性配置 (ObservabilityConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `log_level` | INFO | 日志级别 |
| `log_format` | json | 日志格式 |
| `log_output` | stdout | 日志输出 |
| `trace_enabled` | true | 启用追踪 |
| `trace_sample_rate` | 1.0 | 追踪采样率 |
| `prometheus_enabled` | false | 启用 Prometheus |
| `sentry_enabled` | false | 启用 Sentry |

## 使用示例

### 基本使用

```python
from backend.app.core.config import get_settings

# 获取配置
settings = get_settings()

# 访问配置项
print(settings.app_name)
print(settings.database_url)
print(settings.jwt_secret)

# 获取特定配置部分
db_config = settings.get_database_config()
cache_config = settings.get_cache_config()
security_config = settings.get_security_config()
```

### 环境检测

```python
from backend.app.core.config import get_settings

settings = get_settings()

if settings.is_production():
    # 生产环境特定逻辑
    pass
elif settings.is_development():
    # 开发环境特定逻辑
    pass
```

### 配置验证

```python
from backend.app.core.config import get_settings

settings = get_settings()

# 自动验证（在 get_settings() 时执行）
# 如果验证失败，会抛出 ConfigValidationError
```

### 敏感配置加密

```python
from backend.app.core.config.encryption import ConfigEncryption

# 创建加密器
encryption = ConfigEncryption("your-encryption-key-min-32-chars")

# 加密单个值
encrypted = encryption.encrypt("sensitive-data")

# 解密
decrypted = encryption.decrypt(encrypted)

# 加密字典
data = {"api_key": "secret", "public": "value"}
encrypted_data = encryption.encrypt_dict(data, ["api_key"])

# 解密字典
decrypted_data = encryption.decrypt_dict(encrypted_data, ["api_key"])
```

### 配置热更新

```python
from backend.app.core.config.reload import ConfigReloader, ConfigChangeListener
from pathlib import Path

# 创建重载器
reloader = ConfigReloader(Path(".env"))

# 定义变更监听器
def on_config_change(changes):
    print(f"Configuration changed: {changes}")

listener = ConfigChangeListener(on_config_change)
reloader.add_listener(listener)

# 开始监听
reloader.start_watching()

# 停止监听
reloader.stop_watching()
```

### 远程配置中心

```python
import asyncio
from backend.app.core.config.remote import ConsulConfigProvider, RemoteConfigManager

async def main():
    # 创建 Consul 提供者
    provider = ConsulConfigProvider(host="localhost", port=8500)
    manager = RemoteConfigManager(provider)

    # 获取配置
    value = await manager.get("xagent/database_url")

    # 设置配置
    await manager.set("xagent/database_url", "postgresql://...")

    # 监听配置变化
    async def on_change(value):
        print(f"Config changed: {value}")

    await manager.watch("xagent/database_url", on_change)

    # 关闭
    await manager.close()

asyncio.run(main())
```

## 迁移指南

### 从旧配置系统迁移

#### 步骤 1：备份现有配置

```bash
cp backend/app/settings.py backend/app/settings.py.backup
```

#### 步骤 2：生成新的环境配置文件

```bash
# 复制模板
cp .env.development .env
cp .env.test .env.test
cp .env.production .env.production

# 编辑配置文件，填入实际值
nano .env
nano .env.test
nano .env.production
```

#### 步骤 3：更新应用代码

**旧代码**：
```python
from backend.app.settings import get_settings

settings = get_settings()
db_url = settings.database_url
```

**新代码**：
```python
from backend.app.core.config import get_settings

settings = get_settings()
db_url = settings.database_url
```

#### 步骤 4：生成安全密钥

```bash
python scripts/generate_secrets.py
```

输出示例：
```
JWT_SECRET=abc123...
ENCRYPTION_KEY=def456...
AUDIT_HMAC_SECRET=ghi789...
```

将这些值添加到 `.env.production`。

#### 步骤 5：验证配置

```bash
python -c "from backend.app.core.config import get_settings; settings = get_settings(); print('Configuration loaded successfully')"
```

#### 步骤 6：运行测试

```bash
pytest tests/test_config.py -v
```

#### 步骤 7：部署

```bash
# 开发环境
export XAGENT_ENVIRONMENT=development
python -m backend.app.web

# 生产环境
export XAGENT_ENVIRONMENT=production
python -m backend.app.web
```

## 最佳实践

### 1. 密钥管理

- 永远不要在代码中硬编码密钥
- 使用环境变量或密钥管理系统
- 定期轮换密钥
- 在生产环境中使用强密钥

### 2. 环境隔离

- 为每个环境使用独立的配置文件
- 不要在开发环境中使用生产密钥
- 使用不同的数据库和缓存实例

### 3. 配置验证

- 在应用启动时验证所有配置
- 使用类型提示和验证器
- 提供清晰的错误消息

### 4. 敏感数据

- 加密所有敏感配置值
- 不要在日志中输出敏感数据
- 使用 HTTPS 传输配置

### 5. 监控和告警

- 监控配置变化
- 记录所有配置修改
- 设置告警规则

### 6. 文档

- 记录所有配置项
- 提供默认值和推荐值
- 说明环境差异

## 故障排除

### 配置验证失败

**问题**：启动时出现 `ConfigValidationError`

**解决方案**：
1. 检查错误消息
2. 验证所有必需的配置项
3. 检查配置值的格式和范围
4. 查看日志获取详细信息

### 敏感配置解密失败

**问题**：`EncryptionError: Decryption failed`

**解决方案**：
1. 检查加密密钥是否正确
2. 确保加密值未被修改
3. 验证加密算法版本

### 配置热更新不工作

**问题**：配置文件变化未被检测

**解决方案**：
1. 检查文件监听器是否启动
2. 验证文件系统权限
3. 检查文件系统是否支持监听

## 相关文件

- 配置模块：`backend/app/core/config/`
- 测试：`tests/test_config.py`
- 环境文件：`.env.development`, `.env.test`, `.env.production`
- 密钥生成脚本：`scripts/generate_secrets.py`

## 参考资源

- [Pydantic Settings 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Cryptography 库文档](https://cryptography.io/)
- [Watchdog 文件监听库](https://watchdog.readthedocs.io/)
