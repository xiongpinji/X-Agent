# 插件系统现状说明（P1-12，2026-07-20）

## 当前状态：MCP 插件框架已接线（Wave A）

| 项目 | 状态 |
|---|---|
| 插件框架 | `backend/app/core/mcp_plugin_adapter.py`（存活代码，未被归档） |
| 运行时 | `backend/plugins/runtime.py`（`PluginRuntime`，扫描本目录） |
| API 路由 | `backend/plugins/router.py`（`/api/v1/plugins`，可挂载，**尚未挂载**，待集成波） |
| 旧插件框架 | 16 个模块已归档至 `archive/dead_code_2026-07-19/`，**不再使用** |

## 本目录内容的真实可用性

| 目录 | 格式 | 状态 |
|---|---|---|
| `filesystem-mcp/` | MCP（manifest.json + main.py） | ✅ 可加载 |
| `database-mcp/` | MCP（manifest.json + main.py） | ✅ 可加载 |
| `github-mcp/` | MCP（manifest.json + main.py） | ✅ 可加载（入口模块依赖 `requests`） |
| `github-plugin/` | 旧格式（plugin.manifest.json） | ⚠️ legacy_unsupported，待 Phase 3 迁移 |
| `automation-plugin/` | 旧格式（plugin.manifest.json） | ⚠️ legacy_unsupported，待 Phase 3 迁移 |
| `data-processor-plugin/` | 旧格式（plugin.manifest.json） | ⚠️ legacy_unsupported，待 Phase 3 迁移 |
| `examples/`、`templates/` | 旧框架示例/模板 | 参考用途，非可加载插件 |

## 诚实性声明

1. **进程拉起 ≠ 可调用**：`PluginRuntime.start()` 仅验证插件子进程可拉起；
   MCP 协议握手在 `mcp_plugin_adapter` 中仍是 TODO，现阶段不能声称
   "插件工具已可通过 MCP 协议被 Agent 调用"。
2. **进程内验证可用**：`PluginRuntime.inspect_entrypoint()` 可真实导入
   插件入口模块、实例化入口类并比对 manifest 声明的工具列表。
3. 本目录下的 `QUICKSTART_ZH.md` / `INSTALLATION_GUIDE_ZH.md` /
   `MARKETPLACE_GUIDE_ZH.md` 等文档描述的是已归档旧框架的
   `xagent plugin install` 等 CLI 流程，**当前不可用**，仅作历史参考。
   插件系统 v2（含市场、CLI）重做计划在 Phase 3 评估。
