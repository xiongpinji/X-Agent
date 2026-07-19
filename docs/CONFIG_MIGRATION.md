# X-Agent 配置系统迁移指南

## 概述

本指南说明如何从旧的配置系统迁移到新的企业级配置管理系统。

## 迁移步骤

### 步骤 1：备份现有配置

```bash
# 备份旧的配置文件
cp backend/app/settings.py backend/app/settings.py.backup
cp .env .env.backup
```

### 步骤 2：生成新的环境配置文件

```bash
# 复制模板文件
cp .env.development .env
cp .env.test .env.test
cp .env.production .env.production

# 编辑配置文件，填入实际值
nano .env
nano .env.test
nano .env.production
```

### 步骤 3：生成安全密钥

```bash
# 生成所有必需的密钥
python scripts/generate_secrets.py

# 或直接更新 .env.production
python scripts/generate_secrets.py --env-file .env.production
```

### 步骤 4：更新应用代码

#### 旧代码示例

```python
# 旧方式
from backend.app.settings import get_settings

settings = get_settings()
db_url = settings.database_url
jwt_secret = settings.jwt_secret
```

#### 新代码示例

```python
# 新方式
from backend.app.core.config import get_settings

settings = get_settings()
db_url = settings.database_url
jwt_secret = settings.jwt_secret

# 获取特定配置部分
db_config = settings.get_database_config()
security_config = settings.get_security_config()
```

### 步骤 5：更新导入语句

**搜索并替换**：

```bash
# 在所有 Python 文件中
find . -name "*.py" -type f -exec sed -i \
  's/from backend\.app\.settings import/from backend.app.core.config import/g' {} \;
```

### 步骤 6：验证配置

```bash
# 测试配置加载
python -c "
from backend.app.core.config import get_settings
settings = get_settings()
print(f'Environment: {settings.environment}')
print(f'App name: {settings.app_name}')
print(f'Database: {settings.database_url}')
print('Configuration loaded successfully!')
"
```

### 步骤 7：运行测试

```bash
# 运行配置测试
pytest tests/test_config.py -v

# 运行所有测试
pytest tests/ -v
```

### 步骤 8：部署

```bash
# 开发环境
export XAGENT_ENVIRONMENT=development
python -m backend.app.web

# 测试环境
export XAGENT_ENVIRONMENT=test
python -m pytest tests/

# 生产环境
export XAGENT_ENVIRONMENT=production
python -m backend.app.web
```

## 配置项映射

### 旧配置 → 新配置

| 旧配置项 | 新配置项 | 位置 |
|---------|---------|------|
| `app_mode` | `environment` | BaseConfig |
| `database_url` | `database_url` | DatabaseConfig |
| `redis_url` | `redis_url` | CacheConfig |
| `jwt_secret` | `jwt_secret` | SecurityConfig |
| `encryption_key` | `encryption_key` | SecurityConfig |
| `cors_origins` | `cors_origins` | SecurityConfig |
| `log_level` | `log_level` | ObservabilityConfig |
| `langfuse_public_key` | `langfuse_public_key` | ObservabilityConfig |

### 新增配置项

以下是新系统中新增的重要配置项：

- `environment` - 环境类型（development/test/production）
- `postgres_enable_vector_search` - 启用 pgvector
- `cache_ttl_short` - 短期缓存 TTL
- `cache_ttl_long` - 长期缓存 TTL
- `require_https` - 生产环境强制 HTTPS
- `trace_sample_rate` - 追踪采样率
- `prometheus_enabled` - 启用 Prometheus
- `sentry_enabled` - 启用 Sentry

## 环境变量前缀

新系统使用 `XAGENT_` 前缀作为所有环境变量的前缀。

### 示例

```bash
# 旧方式
export DATABASE_URL=postgresql://...
export JWT_SECRET=...

# 新方式
export XAGENT_DATABASE_URL=postgresql://...
export XAGENT_JWT_SECRET=...
```

## 配置验证

新系统在启动时自动验证所有配置。

### 验证规则

**开发环境**：
- 宽松的验证
- 允许使用默认密钥
- 不需要 HTTPS

**生产环境**：
- 严格的验证
- 必须使用强密钥
- 必须启用 HTTPS
- 必须配置审计日志

### 处理验证错误

```python
from backend.app.core.config import get_settings
from backend.app.core.config.validator import ConfigValidationError

try:
    settings = get_settings()
except ConfigValidationError as e:
    print(f"Configuration validation failed: {e}")
    # 查看详细错误信息
    import logging
    logging.basicConfig(level=logging.DEBUG)
    # 重新尝试
    settings = get_settings()
```

## 敏感配置加密

新系统支持敏感配置加密。

### 加密敏感值

```bash
# 生成加密密钥
python scripts/generate_secrets.py --format json

# 使用加密密钥加密敏感值
python -c "
from backend.app.core.config.encryption import ConfigEncryption
import os

encryption = ConfigEncryption(os.getenv('XAGENT_ENCRYPTION_KEY'))

# 加密 API 密钥
api_key = 'sk-1234567890'
encrypted = encryption.encrypt(api_key)
print(f'Encrypted: {encrypted}')
"
```

## 配置热更新

新系统支持配置文件热更新。

### 启用热更新

```python
from backend.app.core.config.reload import ConfigReloader, ConfigChangeListener
from pathlib import Path

# 创建重载器
reloader = ConfigReloader(Path(".env"))

# 定义变更监听器
def on_config_change(changes):
    print("Configuration changed, reloading...")
    from backend.app.core.config import reload_settings
    settings = reload_settings()

listener = ConfigChangeListener(on_config_change)
reloader.add_listener(listener)

# 开始监听
reloader.start_watching()
```

## 远程配置中心

新系统支持 Consul 和 Etcd 远程配置中心。

### 配置 Consul

```python
from backend.app.core.config.remote import ConsulConfigProvider, RemoteConfigManager
import asyncio

async def setup_consul():
    provider = ConsulConfigProvider(
        host="consul.example.com",
        port=8500,
    )
    manager = RemoteConfigManager(provider)
    
    # 获取配置
    db_url = await manager.get("xagent/database_url")
    
    # 监听变化
    async def on_change(value):
        print(f"Config changed: {value}")
    
    await manager.watch("xagent/database_url", on_change)

asyncio.run(setup_consul())
```

## 常见问题

### Q1：如何在开发和生产环境之间切换？

```bash
# 开发环境
export XAGENT_ENVIRONMENT=development
source .env.development

# 生产环境
export XAGENT_ENVIRONMENT=production
source .env.production
```

### Q2：如何处理敏感配置？

```python
from backend.app.core.config.encryption import ConfigEncryption

encryption = ConfigEncryption("your-encryption-key")

# 加密
encrypted = encryption.encrypt("sensitive-data")

# 解密
decrypted = encryption.decrypt(encrypted)
```

### Q3：如何验证配置？

```python
from backend.app.core.config import get_settings

# 自动验证（在 get_settings() 时执行）
settings = get_settings()

# 或手动验证
from backend.app.core.config.validator import ConfigValidator
validator = ConfigValidator()
validator.validate_all(...)
```

### Q4：如何监听配置变化？

```python
from backend.app.core.config.reload import ConfigReloader, ConfigChangeListener

reloader = ConfigReloader(Path(".env"))

def on_change(changes):
    print(f"Config changed: {changes}")

listener = ConfigChangeListener(on_change)
reloader.add_listener(listener)
reloader.start_watching()
```

### Q5：如何使用远程配置中心？

```python
from backend.app.core.config.remote import ConsulConfigProvider, RemoteConfigManager

provider = ConsulConfigProvider()
manager = RemoteConfigManager(provider)

# 获取配置
value = await manager.get("xagent/key")

# 设置配置
await manager.set("xagent/key", "value")
```

## 回滚计划

如果迁移出现问题，可以回滚到旧系统：

```bash
# 恢复旧的配置文件
cp backend/app/settings.py.backup backend/app/settings.py
cp .env.backup .env

# 恢复旧的导入语句
find . -name "*.py" -type f -exec sed -i \
  's/from backend\.app\.core\.config import/from backend.app.settings import/g' {} \;

# 重启应用
python -m backend.app.web
```

## 迁移检查清单

- [ ] 备份现有配置
- [ ] 生成新的环境配置文件
- [ ] 生成安全密钥
- [ ] 更新应用代码中的导入语句
- [ ] 验证配置加载
- [ ] 运行所有测试
- [ ] 在开发环境中测试
- [ ] 在测试环境中测试
- [ ] 在生产环境中部署
- [ ] 监控应用日志
- [ ] 验证所有功能正常
- [ ] 删除旧的配置文件备份

## 支持和帮助

如有问题，请参考：

- [配置管理文档](CONFIG_MANAGEMENT.md)
- [配置最佳实践](CONFIG_BEST_PRACTICES.md)
- [测试文件](../tests/test_config.py)
- [配置模块源代码](../backend/app/core/config/)
