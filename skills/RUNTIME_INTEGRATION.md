# 技能运行时集成说明（集成波接线指南）

P1-11 交付物配套文档。目标读者：集成波负责把技能注入 AgentLoop 的工程师。

## 1. 唯一技能运行时

- 契约：`backend.app.core.skills`（`Skill` / `SkillMetadata` / `SkillContext` / `SkillResult`）
- 加载器：`backend.app.core.skills.SkillLoader`
  - 默认扫描项目根 `skills/` 与 `custom-skills/`（`get_default_skills_dirs()`）
  - 技能目录约定：`SKILL.md`（说明）+ `main.py` 或 `skill.py`（导出 `SkillImplementation`）
  - 加载成败见 `loader.load_report`（显式，不静默）
- 注册表：`backend.app.core.skills.SkillRegistry`

## 2. AgentLoop 消费接口（你不许改 AgentLoop，按下面接线）

适配器：`backend/app/core/skill_agent_adapter.py`

```python
from backend.app.core.skill_agent_adapter import (
    register_skills_into_tool_registry,   # 主入口：把所有已加载技能注册进 ToolRegistry
    list_skill_tools,                     # 只读：列出技能工具描述（LLM 可见 schema）
    build_skill_tool_handler,             # 单个技能 → ToolRegistry handler
    SKILL_TOOL_PREFIX,                    # "skill__"
)

# 在构建 AgentLoop 的 ToolRegistry 之后、主循环启动之前：
registered = await register_skills_into_tool_registry(
    tool_registry,                        # backend.app.core.tools.ToolRegistry 实例
    # loader=SkillLoader(),               # 可选：自定义加载器
    # context_defaults={"tenant_id": t, "user_id": u},  # 可选：注入 SkillContext
)
# registered == ["skill__code-review-skill", "skill__data-analysis-skill", ...]
```

接线后 AgentLoop 即可通过工具名 `skill__<skill-name>` 调用技能：
- 工具描述/参数 schema 来自技能类的 `metadata.description` 与可选的
  `parameters_schema` 类属性（未声明时退化为宽松 object schema）。
- handler 约定与 ToolRegistry 一致：`await handler(**arguments) -> dict`，
  返回 `{"success": bool, "data": ..., "error": ...}`，失败显式返回。
- 风险级别默认 `RiskLevel.LOW`，授权 scope 默认 `tools:read`
  （均为 RBAC/ToolRegistry 中真实存在的值）。

### 租户/用户注入说明

`ToolRegistry.execute()` 调用 handler 时不传 `RunContext`，因此技能默认
拿不到租户信息。需要租户隔离时，由集成方在注册处用 `context_defaults`
注入（每个租户/会话一个 registry 或包装 handler）；handler 也接受
保留参数 `_tenant_id` / `_user_id`（会被从技能参数中剥离）。

## 3. skills_api.py（legacy 管理平面 API）

- 已达到可挂载状态：**未挂载**。集成波如需挂载：
  `from backend.app.api.skills_api import router as skills_mgmt_router`
  然后 `app.include_router(skills_mgmt_router)`。
- 安全语义：tenant_id/user_id 以已认证 Principal 为准（不一致 403）；
  匿名主体仅本地开发模式可达。scope：读 `tools:read`、执行 `agent:run`、
  安装/卸载 `tools:*`。
- 注意它服务的是 legacy 扁平栈，不是目录技能运行时；挂载前请评估是否仍需。

## 4. 插件系统（P1-12）

- 运行时：`backend.plugins.runtime.PluginRuntime`（扫描项目根 `plugins/`）
- 路由（可挂载，未挂载）：
  `from backend.plugins.router import router as plugin_runtime_router`
  然后 `app.include_router(plugin_runtime_router)`。
- 现状与限制见 `plugins/STATUS.md`（MCP 协议握手未实现，不得声称可经
  MCP 调用插件工具；`inspect_entrypoint` 提供进程内真实验证）。

## 5. 现有可执行技能

| 技能 | 参数 | 能力边界 |
|---|---|---|
| `code-review-skill` | `code: str`（必需） | 仅 Python（AST）；非 Python 显式报错 |
| `data-analysis-skill` | `csv_text` 或 `file_path`；`has_header` | 仅 CSV 统计画像；不生成图表、不做预测 |
