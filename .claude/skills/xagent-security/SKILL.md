# X-Agent 安全审计与修复

## 描述

基于项目深度审计报告，X-Agent 存在 9 个高危安全问题需要修复。本 Skill 提供安全编码规范和修复指导。

## 适用场景

- 修复已知安全漏洞
- 新增功能时的安全审查
- 安全策略配置
- 依赖安全更新

## 已知高危问题（来自审计报告）

### 1. 命令注入风险

**位置**: `desktop.py`, `browser.py` 等自动化模块

**问题**: 用户输入直接拼接到系统命令中。

**修复**:
```python
# 错误
os.system(f"playwright {user_url}")

# 正确
import shlex
from pathlib import Path

safe_url = shlex.quote(user_url)
subprocess.run(
    ["playwright", "open", safe_url],
    capture_output=True,
    timeout=30
)
```

### 2. SQL 注入风险

**位置**: `memory_postgres.py`, `tracing_postgres.py`

**修复**: 所有 SQL 必须使用参数化查询：

```python
# 错误
cursor.execute(f"SELECT * FROM memories WHERE key = '{user_input}'")

# 正确
cursor.execute(
    "SELECT * FROM memories WHERE key = $1",
    (user_input,)
)
```

### 3. 敏感信息泄露

**位置**: `.env.example`, 日志, 错误响应

**修复**:
- 日志中绝不打印 API Key、数据库密码
- 错误响应不暴露内部堆栈（生产环境）
- 使用 `pydantic.SecretStr` 处理敏感字段

```python
from pydantic import SecretStr, BaseSettings

class Settings(BaseSettings):
    openai_api_key: SecretStr
    database_url: SecretStr

    class Config:
        env_file = ".env"

settings = Settings()
# 使用时
api_key = settings.openai_api_key.get_secret_value()
```

### 4. 不安全的反序列化

**位置**: `agent_serializers.py`

**修复**: 禁用 pickle，使用 JSON + Pydantic 验证：

```python
import json
from pydantic import BaseModel, validator

class AgentState(BaseModel):
    data: dict

    @validator('data')
    def validate_no_callables(cls, v):
        for key, value in v.items():
            if callable(value):
                raise ValueError(f"Callable not allowed in state: {key}")
        return v

# 序列化
state_json = json.dumps(state.dict())
# 反序列化
state = AgentState.parse_raw(state_json)
```

### 5. 路径遍历风险

**位置**: 文件上传、工具执行模块

**修复**:
```python
from pathlib import Path

UPLOAD_DIR = Path("/safe/uploads")

def save_upload(filename: str, content: bytes):
    # 规范化路径并检查
    target = (UPLOAD_DIR / filename).resolve()
    if not str(target).startswith(str(UPLOAD_DIR)):
        raise ValueError("Path traversal detected")
    target.write_bytes(content)
```

### 6. 不安全的依赖版本

**位置**: `pyproject.toml`

**修复**: 锁定版本，定期审计：

```bash
# 生成锁定文件
pip freeze > requirements.lock

# 安全审计
pip-audit -r requirements.lock

# 或使用 poetry
poetry add package@latest
poetry lock
```

## 安全编码 checklist

- [ ] 所有外部输入经过验证（Pydantic / 正则）
- [ ] 系统命令使用列表传参 + `subprocess.run`
- [ ] SQL 完全参数化
- [ ] 敏感配置使用 `SecretStr`
- [ ] 文件路径经过 `resolve()` 和前缀检查
- [ ] API 响应不包含内部堆栈（生产环境）
- [ ] 依赖版本已锁定并定期审计
- [ ] CORS 配置限制具体域名（非 `*`）
- [ ] 认证中间件保护管理接口

## 安全测试

```bash
# 运行安全相关测试
pytest tests/security/ -v

# 静态分析
bandit -r backend/

# 依赖审计
pip-audit

# 类型检查
mypy backend/ --strict
```
