---
kind: configuration_system
name: X-Agent 多端配置系统：Pydantic Settings + 环境变量 + 分层配置文件
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/settings.py
    - backend/app/core/config/settings.py
    - backend/app/core/config.py
    - cli/config.py
    - config/model_profiles.yaml
    - config/enterprise-config.yaml
    - config/xagent_local_config.json
    - .env.example
---

## 1. 体系概览

X-Agent 采用 **pydantic-settings** 作为统一配置加载内核，配合 `.env`、YAML/JSON/TOML 文件与 `XAGENT_*` 前缀的环境变量，形成“进程内 Settings 模型 → 各子系统 Settings 子模块”的分层架构。CLI、后端 FastAPI、桌面客户端各自维护独立的 Settings 类，但共享同一套命名约定（`XAGENT_` 前缀）和优先级规则。

## 2. 核心组件与职责

- **后端主 Settings（运行时）**
  - `backend/app/settings.py`：FastAPI 应用启动时读取的权威 Settings，`env_prefix="XAGENT_"`，默认从 `.env` 加载；包含 LLM、记忆、存储路径、安全密钥、CORS、审计 HMAC、Playwright、Langfuse、Qdrant、Redis、工作流/审计/工具执行等所有运行期开关。
  - `backend/app/core/config/settings.py`：面向“配置域对象”的聚合 Settings，组合 DatabaseConfig / CacheConfig / SecurityConfig / ObservabilityConfig 并通过 `ConfigValidator.validate_all()` 做跨段校验；提供 `get_settings()` 缓存单例与 `reload_settings()` 热重载入口。
  - `backend/app/core/config.py`：早期遗留的独立 BaseSettings 片段（LogSettings、DatabaseSettings、CacheSettings、ExecutionSettings、SecuritySettings），仍被部分旧代码引用。

- **CLI Settings（用户态）**
  - `cli/config.py`：`CLIConfig` 使用 `env_prefix="XAGENT_"`，但通过重写 `settings_customise_sources` 仅接受显式传入的 init 参数，由 `load_config()` 自行合并 `~/.xagent/config.toml` < 环境变量 < CLI 参数，避免重复读 env 导致冲突。

- **配置数据文件**
  - `config/model_profiles.yaml`：LLM 模型档案（provider/cost/latency/quality/rate_limit/quota），由 `backend/app/core/llm/profiles.py` 解析，支持 `XAGENT_LLM_MODEL_PROFILES_PATH` 覆盖。
  - `config/enterprise-config.yaml`：企业版功能开关、RBAC 角色、审计策略、订阅计划、监控告警、通知渠道等 YAML 声明式配置。
  - `config/xagent_local_config.json`：本地同步、加密、缓存、离线队列、预加载、监控等 JSON 配置。
  - `config/i18n_config.json`、`config/mcp_servers.example.yaml`：国际化与 MCP 服务器清单示例。

- **环境变量事实源**
  - `.env.example`：完整列出所有 `XAGENT_*` 变量，明确标注“只有带 `XAGENT_` 前缀的变量会被核心设置加载器读取”，并提供开发/生产两套快速起步说明。

## 3. 加载顺序与优先级

| 来源 | 适用范围 | 优先级 |
|---|---|---|
| 函数参数（CLI 显式传参） | CLI `load_config()` | 最高 |
| 环境变量 `XAGENT_*` | 全部（后端 Settings、CLI Config） | 次高 |
| 配置文件（`.env` / `~/.xagent/config.toml` / YAML/JSON） | 对应模块 | 中 |
| Pydantic Field default | 全部 | 最低 |

后端 Settings 在 `app_mode=production` 下触发额外 fail-fast 校验：禁止 sqlite/memory/jsonl/trace_backend=memory/admin_store_backend=memory，强制要求外部化持久化后端。

## 4. 设计决策与约定

- **单一前缀**：所有可配置项统一以 `XAGENT_` 为环境变量前缀，避免与其他库冲突。
- **类型驱动**：每个配置项都有明确的 Python 类型与 `Field(...)` 描述，配合 `field_validator` / `model_validator` 实现强校验（如 JWT/ENCRYPTION_KEY 长度与熵、CORS 通配符禁用、后端枚举白名单）。
- **分段聚合**：`backend/app/core/config/settings.py` 将数据库、缓存、安全、可观测性等拆分为独立 Config 类，再聚合到顶层 Settings，便于单独替换与测试。
- **可热重载**：`reload_settings()` 清除 `@lru_cache` 后重建实例，供开发/调试场景动态刷新。
- **模型档案外置**：LLM 路由与计费依赖的 `model_profiles.yaml` 独立于代码，支持运行时切换路径，不重启即可调整成本/延迟/质量权重。

## 5. 开发者应遵循的规则

1. 新增配置项一律在 `backend/app/settings.py` 或对应的 `core/config/*Config` 中以 `Field(default=..., description=...)` 声明，并补充 `field_validator` 约束。
2. 所有新环境变量必须加 `XAGENT_` 前缀，并在 `.env.example` 中同步添加注释。
3. 涉及生产安全的字段（JWT_SECRET、ENCRYPTION_KEY、AUDIT_HMAC_SECRET 等）必须在 `_validate_production_secrets` 或 model_validator 中做强度检查。
4. 需要按租户/用户覆盖的静态配额、定价等数据放入 `config/*.yaml`，通过 `XAGENT_*_PATH` 环境变量指向自定义文件。
5. CLI 侧新增配置走 `cli/config.py` 的 `load_config()` 合并流程，不要直接读 `os.environ`。

## 关键文件

- `backend/app/settings.py` — 后端主 Settings（XAGENT_* 前缀）
- `backend/app/core/config/settings.py` — 聚合 Settings + 分段 Config + 验证器
- `backend/app/core/config.py` — 遗留分段 Settings（兼容旧代码）
- `cli/config.py` — CLI 配置加载（TOML + env + 参数）
- `config/model_profiles.yaml` — LLM 模型档案
- `config/enterprise-config.yaml` — 企业版 YAML 配置
- `config/xagent_local_config.json` — 本地同步/加密/缓存 JSON 配置
- `.env.example` — 全量 XAGENT_* 环境变量清单
