# X-Agent 配置最佳实践指南

## 1. 密钥管理

### 1.1 生成强密钥

```bash
# 生成所有必需的密钥
python scripts/generate_secrets.py

# 生成并保存到文件
python scripts/generate_secrets.py --output secrets.txt

# 生成 JSON 格式
python scripts/generate_secrets.py --format json

# 直接更新 .env 文件
python scripts/generate_secrets.py --env-file .env.production
```

### 1.2 密钥存储

**开发环境**：
- 使用 `.env.development` 文件
- 可以使用较弱的密钥（仅用于开发）
- 不要提交到版本控制

**生产环境**：
- 使用密钥管理系统（KMS）
- 或使用环境变量
- 定期轮换密钥
- 使用强密钥（最少 64 字符）

### 1.3 密钥轮换

```python
# 定期轮换密钥
from backend.app.core.config.encryption import generate_encryption_key

new_key = generate_encryption_key()
# 更新配置
# 重新加密所有敏感数据
```

## 2. 环境隔离

### 2.1 环境配置文件

```bash
# 开发环境
export XAGENT_ENVIRONMENT=development
source .env.development

# 测试环境
export XAGENT_ENVIRONMENT=test
source .env.test

# 生产环境
export XAGENT_ENVIRONMENT=production
source .env.production
```

### 2.2 环境特定配置

```python
from backend.app.core.config import get_settings

settings = get_settings()

if settings.is_production():
    # 生产环境特定配置
    db_pool_size = 50
    cache_ttl = 3600
    enable_monitoring = True
elif settings.is_development():
    # 开发环境特定配置
    db_pool_size = 5
    cache_ttl = 300
    enable_monitoring = False
```

### 2.3 环境验证

```python
from backend.app.core.config import get_settings

settings = get_settings()

# 自动验证所有配置
# 如果验证失败，会抛出 ConfigValidationError
print(f"Environment: {settings.environment}")
print(f"Debug mode: {settings.debug}")
print(f"Database: {settings.database_url}")
```

## 3. 配置验证

### 3.1 启动时验证

```python
from backend.app.core.config import get_settings
from backend.app.core.config.validator import ConfigValidationError

try:
    settings = get_settings()
    print("Configuration validated successfully")
except ConfigValidationError as e:
    print(f"Configuration validation failed: {e}")
    exit(1)
```

### 3.2 自定义验证

```python
from backend.app.core.config.validator import ConfigValidator
from backend.app.core.config import Settings

validator = ConfigValidator()

# 验证特定配置
settings = Settings()
db_config = settings.get_database_config()
security_config = settings.get_security_config()

# 执行验证
try:
    validator.validate_all(
        settings,
        db_config,
        settings.get_cache_config(),
        security_config,
        settings.get_observability_config(),
    )
except Exception as e:
    print(f"Validation error: {e}")
```

## 4. 敏感数据加密

### 4.1 加密单个值

```python
from backend.app.core.config.encryption import ConfigEncryption

encryption = ConfigEncryption("your-encryption-key-min-32-chars")

# 加密
api_key = "sk-1234567890"
encrypted = encryption.encrypt(api_key)

# 解密
decrypted = encryption.decrypt(encrypted)
assert decrypted == api_key
```

### 4.2 加密配置字典

```python
from backend.app.core.config.encryption import ConfigEncryption

encryption = ConfigEncryption("your-encryption-key-min-32-chars")

config_data = {
    "database_url": "postgresql://user:pass@localhost/db",
    "api_key": "sk-1234567890",
    "public_key": "pk-public",
}

# 加密敏感字段
encrypted_data = encryption.encrypt_dict(
    config_data,
    ["database_url", "api_key"],
)

# 解密
decrypted_data = encryption.decrypt_dict(
    encrypted_data,
    ["database_url", "api_key"],
)
```

### 4.3 加密配置文件

```bash
# 加密 .env 文件中的敏感值
python -c "
from backend.app.core.config.encryption import ConfigEncryption
import os

encryption = ConfigEncryption(os.getenv('XAGENT_ENCRYPTION_KEY'))

# 读取 .env 文件
with open('.env.production', 'r') as f:
    content = f.read()

# 加密敏感值
# ... 实现加密逻辑 ...

# 写入加密后的 .env 文件
with open('.env.production.encrypted', 'w') as f:
    f.write(content)
"
```

## 5. 动态配置更新

### 5.1 监听配置文件变化

```python
from backend.app.core.config.reload import ConfigReloader, ConfigChangeListener
from pathlib import Path

# 创建重载器
reloader = ConfigReloader(Path(".env"))

# 定义变更监听器
def on_config_change(changes):
    print(f"Configuration changed: {changes}")
    # 重新加载配置
    from backend.app.core.config import reload_settings
    settings = reload_settings()

listener = ConfigChangeListener(on_config_change)
reloader.add_listener(listener)

# 开始监听
reloader.start_watching()

# ... 应用运行 ...

# 停止监听
reloader.stop_watching()
```

### 5.2 配置回滚

```python
from backend.app.core.config.reload import ConfigRollbackManager

rollback_manager = ConfigRollbackManager(max_snapshots=10)

# 创建快照
current_config = {"database_url": "postgresql://..."}
rollback_manager.create_snapshot(current_config)

# 修改配置
new_config = {"database_url": "postgresql://new..."}
rollback_manager.create_snapshot(new_config)

# 回滚到上一个配置
previous_config = rollback_manager.rollback_to_previous()

# 列出所有快照
snapshots = rollback_manager.list_snapshots()
for snapshot in snapshots:
    print(f"Snapshot {snapshot['index']}: {snapshot['timestamp']}")
```

## 6. 远程配置中心

### 6.1 Consul 集成

```python
import asyncio
from backend.app.core.config.remote import ConsulConfigProvider, RemoteConfigManager

async def main():
    # 创建 Consul 提供者
    provider = ConsulConfigProvider(
        host="consul.example.com",
        port=8500,
        datacenter="dc1",
    )
    manager = RemoteConfigManager(provider)

    # 获取配置
    db_url = await manager.get("xagent/database_url")
    print(f"Database URL: {db_url}")

    # 设置配置
    await manager.set("xagent/database_url", "postgresql://new...")

    # 监听配置变化
    async def on_change(value):
        print(f"Config changed: {value}")

    await manager.watch("xagent/database_url", on_change)

    # 关闭
    await manager.close()

asyncio.run(main())
```

### 6.2 Etcd 集成

```python
import asyncio
from backend.app.core.config.remote import EtcdConfigProvider, RemoteConfigManager

async def main():
    # 创建 Etcd 提供者
    provider = EtcdConfigProvider(
        host="etcd.example.com",
        port=2379,
    )
    manager = RemoteConfigManager(provider)

    # 获取配置
    db_url = await manager.get("xagent/database_url")
    print(f"Database URL: {db_url}")

    # 设置配置
    await manager.set("xagent/database_url", "postgresql://new...")

    # 监听配置变化
    async def on_change(value):
        print(f"Config changed: {value}")

    await manager.watch("xagent/database_url", on_change)

    # 关闭
    await manager.close()

asyncio.run(main())
```

## 7. 日志和监控

### 7.1 配置日志

```python
from backend.app.core.config import get_settings

settings = get_settings()

# 获取日志配置
observability = settings.get_observability_config()

print(f"Log level: {observability.log_level}")
print(f"Log format: {observability.log_format}")
print(f"Log output: {observability.log_output}")
print(f"Log file: {observability.log_file}")
```

### 7.2 启用追踪

```python
from backend.app.core.config import get_settings

settings = get_settings()
observability = settings.get_observability_config()

if observability.trace_enabled:
    # 初始化追踪
    print(f"Tracing enabled with sample rate: {observability.trace_sample_rate}")
```

### 7.3 启用监控

```python
from backend.app.core.config import get_settings

settings = get_settings()
observability = settings.get_observability_config()

if observability.prometheus_enabled:
    # 初始化 Prometheus
    print(f"Prometheus enabled on port {observability.prometheus_port}")

if observability.sentry_enabled:
    # 初始化 Sentry
    print(f"Sentry enabled with DSN: {observability.sentry_dsn}")
```

## 8. 故障排除

### 8.1 配置验证失败

**问题**：启动时出现 `ConfigValidationError`

**解决方案**：
```bash
# 检查配置文件
cat .env

# 验证配置
python -c "from backend.app.core.config import get_settings; settings = get_settings()"

# 查看详细错误
python -c "
from backend.app.core.config import get_settings
from backend.app.core.config.validator import ConfigValidationError
try:
    settings = get_settings()
except ConfigValidationError as e:
    print(f'Error: {e}')
"
```

### 8.2 敏感配置解密失败

**问题**：`EncryptionError: Decryption failed`

**解决方案**：
```python
# 检查加密密钥
from backend.app.core.config import get_settings

settings = get_settings()
security = settings.get_security_config()

print(f"Encryption key length: {len(security.encryption_key)}")
print(f"Encryption algorithm: {security.encryption_algorithm}")

# 验证加密密钥
from backend.app.core.config.encryption import ConfigEncryption

try:
    encryption = ConfigEncryption(security.encryption_key)
    print("Encryption key is valid")
except Exception as e:
    print(f"Encryption key error: {e}")
```

### 8.3 配置热更新不工作

**问题**：配置文件变化未被检测

**解决方案**：
```python
# 检查文件监听器
from backend.app.core.config.reload import ConfigReloader
from pathlib import Path

reloader = ConfigReloader(Path(".env"))

# 验证文件存在
if Path(".env").exists():
    print(".env file exists")
else:
    print(".env file not found")

# 启动监听
try:
    reloader.start_watching()
    print("File watcher started successfully")
except Exception as e:
    print(f"Error starting file watcher: {e}")
```

## 9. 安全检查清单

- [ ] 生成强密钥（最少 64 字符）
- [ ] 不要在代码中硬编码密钥
- [ ] 使用环境变量或密钥管理系统
- [ ] 定期轮换密钥
- [ ] 在生产环境中启用 HTTPS
- [ ] 配置 CORS 白名单（不使用通配符）
- [ ] 启用速率限制
- [ ] 启用审计日志
- [ ] 启用监控和告警
- [ ] 定期备份配置
- [ ] 测试配置回滚
- [ ] 文档化所有配置项

## 10. 参考资源

- [配置管理文档](./CONFIG_MANAGEMENT.md)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Cryptography 库](https://cryptography.io/)
- [Watchdog 文件监听](https://watchdog.readthedocs.io/)
- [Consul 文档](https://www.consul.io/docs)
- [Etcd 文档](https://etcd.io/docs/)
