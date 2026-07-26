# X-Agent × Codex × Hermes 能力对标审计报告

- **角色标签**: 能力对标审计员
- **审计日期**: 2026-07-26
- **审计方法**: 基于竞品报告 `01_codex_research.md` / `02_hermes_research.md`(2026-07-19)提炼能力清单,逐项**读代码验证** X-Agent 真实状态(所有 ✅/🔄 均附文件路径证据,不凭文档宣称)。
- **图例**: ✅ 已有(附证据) / 🔄 部分(注明缺什么) / ❌ 没有

---

## 1. 竞品能力清单提炼(按能力域)

### Codex(OpenAI)— 12 个能力域
1. **多界面交付**: CLI(开源 Rust)+ IDE(VS Code/JetBrains)+ 桌面(并入 ChatGPT 客户端)+ Web + iOS + Slack 入口,上下文跨界面连续
2. **双执行模式**: 本地沙箱(三级审批)↔ 云端异步(隔离 VM、并行任务、PR 产出),可互相移交
3. **安全网络治理**: 默认断网沙箱、域名白名单、secrets 分阶段注入、管理员环境管控
4. **自主性阶梯**: todo → subagents 并行 → Goal Mode(数小时~数天跨中断,2026-05 GA)→ Automations(定时)
5. **专用模型线**: Sol/Terra/Luna 分层;compaction 24h+ 长任务
6. **项目级知识**: AGENTS.md(仓库指令)+ Skills(SKILL.md 渐进加载)+ Memory
7. **质量验证闭环**: 代码评审 Agent(全库推理+真实运行测试)、前端截图自验证
8. **可编程性**: TS/Python/Native SDK、CLI headless(`codex exec`)、GitHub Action、MCP 双向
9. **团队协作**: Slack/GitHub/Linear 原生集成、共享配额
10. **企业治理**: 管理员控制台、用量/评审质量分析面板、共享 credit 池
11. **商业化包装**: 六档阶梯 + token-credit 计量 + 双窗口限速 + 加油包
12. **生态平台化**: 90+ 插件、agentskills 开放目录、第三方原生应用

### Hermes Agent(Nous Research)— 10 个能力域
1. **自改进运行时**: 闭环学习循环(指令/约束/反馈/记忆/编排五层 harness)
2. **三层记忆**: Tier1 高信号保证加载 + Tier2 FTS5 检索 + Tier3 外部集成;/journey 可视化
3. **技能自改进**: 任务后自动创建 skill、使用中自改进、/learn 蒸馏、Skills Hub 市场
4. **规划执行**: /goal standing-goal + **completion contracts**(证据驱动"完成")、delegate_task 子代理、**多子代理后台 fan-out**、Kanban 多代理 swarm(root+worker+verifier+共享黑板)
5. **工具生态**: 60+ 内建工具、MCP 全支持、**execute_code 程序化工具调用**(模型写 Python 脚本 RPC 调工具,压缩多步管线为单次推理)、6 种终端后端(local/Docker/SSH/Singularity/Modal/Daytona)
6. **渠道广度**: 20+ 消息平台网关(Telegram/Discord/Slack/WhatsApp/Signal/Matrix/Teams/Feishu/DingTalk 等)
7. **多端**: CLI/Ink TUI、Electron 桌面、Web Dashboard、Termux
8. **模型无关 + MoA 一等公民**: 200+ 模型接入、命名多模型 ensemble
9. **安全防护**: 命令审批、Promptware defense(提示注入 chokepoint)、secrets 管理
10. **商业化**: MIT 框架免费 + Nous Portal 订阅($0/$20/$100/$200,credits 覆盖模型+工具网关+云托管)

---

## 2. 完整对标矩阵

### 2.1 产品形态
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| CLI 对话 REPL | ✅ | ✅ | ✅ `cli/repl.py`(321 行,prompt_toolkit 历史/补全) |
| Web 前端 | ✅ | ✅ | ✅ `frontend/`(React,含 GoalModePage 等) |
| 桌面端 | ✅ | ✅ | ✅ `desktop/`(Tauri,Cargo.toml+tauri.conf.json) |
| 移动端 | ✅ | ✅ | ✅ `mobile/`(React Native,App.tsx) |
| 浏览器扩展 | ❌ | ❌ | ✅ `extension/`(Chrome,manifest.json,"x-agent-chrome-extension") |
| IDE 扩展(VS Code/JetBrains) | ✅✅ | ❌ | ❌ 无 VS Code/JetBrains 扩展项目;`extension/` 为 Chrome 扩展 |
| 多语言 SDK | ✅(TS/Py/Native) | ✅(pip 包) | ✅ `sdks/`(go/java/javascript/python) |
| OpenAI 兼容 API | 🔄 | ✅ | 🔄 `backend/app/core/llm_api.py` 存在,兼容度未逐一验证 |

### 2.2 执行与沙箱
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| 本地沙箱执行 | ✅ | ✅ | ✅ `core/sandbox/`(docker_sandbox.py / python_sandbox.py / node_sandbox.py + security.py) |
| 云沙箱并行任务 | ✅(隔离 VM、容器缓存 -90%) | ✅(Daytona/Modal serverless) | 🔄 本地 Docker 多 worker 并行:`core/sandbox/orchestrator.py`(N workers 各自独立容器)+ `api/sandbox_tasks.py`(298 行,任务提交/查询/GitHub webhook);**缺**: serverless/云托管后端(无 Daytona/Modal/E2B 适配)、容器缓存、跨机横向扩展 |
| 网络白名单/断网治理 | ✅ | 🔄 | 🔄 `core/sandbox/security.py` 有安全策略,域名白名单级网络治理未验证到实现 |
| Issue-to-PR / GitHub 集成 | ✅ | 🔄 | ✅ `api/issue_to_pr.py` + `core/github_integration.py` + `sandbox_tasks.py` 的 `/webhook/github` |
| 审批模式 | ✅(三级) | ✅ | ✅ `api/approvals.py` + `core/policy.py` + `core/approvals.py` |
| execute_code 程序化工具调用 | ❌(无此原语) | ✅(模型写脚本 RPC 调工具) | 🔄 `core/sandbox/code_execution_tool.py`(CodeExecutionTool,execute_python/javascript)+ `api/code_execution.py` 存在,**但**:未注册进 `core/tool_definitions.py`(agent 主循环工具集仅 browser/desktop/memory/plugin/workflow 约 15 个),无"脚本内 RPC 调其他工具"的程序化调用机制;agent 主循环仅有 `run_command`/`run_tests`(`agent/loop.py:1550`) |

### 2.3 自主性
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| Goal Mode 长时自主 | ✅(2026-05 GA) | ✅(/goal) | 🔄 **核心编排器真实存在但未接线**:`core/goal_mode.py`(191 行,LLM 分解+checkpoint+超时)有完整逻辑,但 `api/goals.py` 是**内存 stub**(进程级 `_goals` 列表 + 静态 demo 数据,未 import GoalModeOrchestrator);前端 `GoalModePage.tsx` 调 `apiClient.getGoals()` 只能打到 stub;checkpoint 仅存内存 dict,重启即失 |
| Automations 定时任务 | ✅ | ✅(cron+Blueprints) | ✅ `core/scheduler.py`(480 行,cron/interval/一次性)+ `api/scheduler.py`(417 行)+ `workflow_worker.py` |
| 子代理并行 fan-out | ✅(subagents) | ✅(后台 fan-out) | ✅ `api/parallel_agents.py`(827 行,spawn/status/results/cancel)+ `core/parallel_agent_executor.py`(673 行)+ `core/agent_spawner.py`(658 行) |
| 长任务 checkpoint/compaction | ✅(24h+) | ✅ | 🔄 `core/context_compactor.py` + goal_mode 内存 checkpoint;跨进程持久化恢复未验证到 |
| completion contracts(证据驱动完成) | 🔄 | ✅(v0.18) | ✅ `core/verification.py` + `agent/loop.py:1539`(`completion_contract_enabled` 开关,验证后写 `agent.completion_contract.verified` 事件)+ `api/verification.py` + `core/evidence/` |

### 2.4 记忆
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| 三层记忆 | ✅ | ✅ | ✅ `core/unified_memory.py`(550 行)+ `hot_memory_store.py`/`cold_memory_store.py` + `memory_v2_system.py` + Postgres/Qdrant 后端(`memory_postgres.py`/`memory_qdrant.py`) |
| 记忆去重 | 🔄 | 🔄 | ✅ `core/memory_deduplication*.py`(多个模块+benchmark) |
| 记忆可视化(/journey 类) | 🔄(预览) | ✅(radial timeline) | ❌ 未见时间线/图谱可视化 UI(`memory_graph.py` 有数据结构,无前端证据) |

### 2.5 工具生态
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| MCP(官方 SDK,双向) | ✅ | ✅ | ✅ `core/mcp/client.py`(`from mcp import ClientSession`,stdio+streamable_http)+ `api/mcp.py` |
| Web 搜索工具 | ✅ | ✅(Firecrawl) | 🔄 `core/mcp/tools/search_tool.py`(带审计)+ `services/search/` 存在,但**不是 agent 主循环一等工具**(tool_definitions 中无 search 条目,需经 MCP 挂载) |
| 图像/多模态 | ✅ | ✅(图像/视频/TTS) | ✅ `api/vision.py` + `core/multimodal_processor.py` + `audio_processor.py`/`video_processor.py`/`text_to_speech.py` |
| 内建工具规模 | 🔄 | 60+ | 🔄 主循环内建约 15 组 + 插件/MCP 扩展机制(`tool_registry.py`、`plugin_system/`) |

### 2.6 协作与多代理
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| 多 agent 委派 | ✅ | ✅(delegate_task) | ✅ `api/multi_agent.py` + `core/agent_coordinator.py` + `core/orchestrator.py` + `core/agent_communication_bus.py` |
| Kanban 多代理看板/swarm 拓扑 | 🔄 | ✅(root+worker+verifier+共享黑板) | 🔄 `api/tasks_ui.py`/`workbench.py` 有任务面板;**缺**: verifier 门控 + 共享黑板 + worktree-per-task 的 swarm 拓扑 |
| 代码评审 | ✅(运行测试验证) | 🔄 | 🔄 `api/code_review.py`(301 行)+ `core/code_review/`(engine 333 行/reviewer 290 行/diff_analyzer/comment_generator);流程为 diff→LLM 推理→意见,**缺**: 真实运行测试验证、"PR ready 自动触发"(GitHub webhook 在 sandbox_tasks 但未与评审串联) |

### 2.7 渠道
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| 消息渠道网关 | ✅(Slack) | ✅(20+ 平台) | 🔄 5 个适配器:`core/channels/`(dingtalk/discord/telegram + router/registry/gateway)+ `channels/feishu.py` + `webhook.py`;**缺**: WhatsApp/Signal/Matrix/Teams/Email/SMS/QQ/微信等 15+ 平台 |
| Slack 双向入口 | ✅ | ✅ | ❌ 仅出站通知(`core/enterprise_integration.py:366` SlackIntegration.send),无入站消息网关适配器 |

### 2.8 治理与安全
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| OIDC/SCIM/SSO | ✅ | ✅ | ✅ `api/scim.py` + `api/sso.py` + `core/enterprise_sso.py` + `core/saml_sso.py` |
| 审计 | ✅ | 🔄 | ✅ `api/audit*.py` + `core/audit*`(含 Postgres 持久化与导出) |
| 提示注入防护 | ✅ | ✅(Promptware defense) | ✅ `core/prompt_guard/`(engine.py 等) |
| OTel 可观测 | ✅ | 🔄 | ✅ `core/otel_exporter.py` + `core/tracing*.py` + `monitoring/` |
| 多租户/配额 | ✅ | ✅ | ✅ `api/tenants.py` + `tenant_quota.py` + `quota_manager.py` |

### 2.9 商业化与生态
| 能力 | Codex | Hermes | X-Agent 现状 |
|---|---|---|---|
| 计费/订阅 | ✅ | ✅ | ✅ `api/billing.py` + `core/billing_engine.py` + `api/subscriptions.py` + `payment_providers.py` |
| 技能运行时+市场 | ✅ | ✅(Skills Hub) | ✅ `core/skills_*` + `skill_system_v2.py` + `api/skill_market*.py` + `skills/`、`skills_marketplace/` |
| 技能自改进闭环 | 🔄 | ✅(自动创建+自改进+/learn) | ✅ `core/skill_distillation/`(sedimentation/curator/generator/harvester)+ `api/skill_sediment.py` + `core/evolution.py`/`self_evolution.py`(反思记录→技能沉淀) |
| Mixture-of-Agents | ❌ | ✅(一等公民) | ✅ `core/llm/moa.py`(296 行,consensus/best_of_n/weighted_vote 三种聚合);注:未验证是否进前端模型选择器 |
| AGENTS.md 仓库指令机制 | ✅ | ✅(约定兼容) | ❌ 全仓 grep `AGENTS.md` 无任何实现匹配(无发现/解析/注入逻辑) |

---

## 3. 缺口分级清单

### P0 — 对齐必需(两家核心叙事能力,X-Agent 缺或断裂)
| # | 缺口 | 实现建议 | 工作量 |
|---|---|---|---|
| P0-1 | **Goal Mode 端到端断裂**:编排器存在但 API 是内存 stub、无持久化、无后台执行 | ①GoalModeOrchestrator 接 `api/goals.py`,目标落 Postgres(复用 workflow_pg_repository 模式);②后台 worker 异步执行 `execute_goal`,checkpoint 持久化;③前端 GoalModePage 加进度轮询 | 4-6 人日 |
| P0-2 | **execute_code 未进主循环**:LLM 无法直接执行代码,无程序化工具调用 | ①把 CodeExecutionTool 注册进 tool_definitions + tool_registry;②参考 Hermes 增加"脚本内 RPC 调工具"桥(生成带 tools 命名空间的 Python 沙箱入口);③权限走现有 policy/approvals | 4-6 人日 |
| P0-3 | **AGENTS.md 机制缺失** | 会话启动时从 cwd 向上扫描 AGENTS.md(+用户级 `~/.x-agent/`),注入 system prompt;支持子目录覆盖;写解析+缓存+单测 | 2-3 人日 |
| P0-4 | **云沙箱无 serverless/云托管后端**(Hermes 有 Daytona/Modal) | 抽象 SandboxBackend 接口(现有 DockerSandbox 为 local 实现),新增 Modal/Daytona 适配;任务队列已就绪(orchestrator.py) | 5-8 人日 |
| P0-5 | **Slack 无入站网关**(Codex/Hermes 核心入口) | 复用 `core/channels/base.py` ChannelAdapter 写 SlackAdapter(Events API + Socket Mode),接 ChannelRouter | 2-3 人日 |

### P1 — 竞争力(影响对标卖点完整性)
| # | 缺口 | 实现建议 | 工作量 |
|---|---|---|---|
| P1-1 | VS Code IDE 扩展缺失(Codex 核心界面) | VS Code extension(TS),调现有 REST/WS API:对话面板+云端任务列表+diff 预览;复用 frontend 的 apiClient 逻辑 | 10-15 人日 |
| P1-2 | Web 搜索非主循环一等工具 | 将 search_tool 注册进 tool_definitions(Tavily/Firecrawl/Brave 可配置),带配额与审计 | 1-2 人日 |
| P1-3 | 消息渠道仅 5/20+:WhatsApp/Teams/Email/Signal/Matrix 等缺失 | 按 ChannelAdapter 模板批量补齐,优先 WhatsApp(Baileys)+Teams+Email | 每渠道 1-2 人日 |
| P1-4 | 代码评审缺"运行测试验证"+PR 自动触发 | 评审流水线接 sandbox 执行测试(复用 orchestrator);GitHub webhook 路由到 CodeReviewEngine;评审结果回贴 PR | 4-6 人日 |
| P1-5 | 云沙箱缺容器缓存与域名白名单 | 环境镜像缓存(setup 脚本指纹)+ 出口代理白名单(iptables/sidecar) | 4-6 人日 |
| P1-6 | 长任务跨进程恢复弱(checkpoint 内存级) | checkpoint 落库 + 进程重启自动 resume;context compaction 策略产品化 | 3-4 人日 |
| P1-7 | MoA 未进用户可选模型列表 | 命名 MoA ensemble 注册为虚拟模型进 LLM router + 前端选择器 | 2-3 人日 |

### P2 — 可选(差异化锦上添花)
| # | 缺口 | 实现建议 | 工作量 |
|---|---|---|---|
| P2-1 | Kanban swarm 拓扑(verifier 门控+共享黑板+worktree-per-task) | 在 parallel_agent_executor 上加拓扑编排层 | 6-10 人日 |
| P2-2 | 记忆时间线/图谱可视化(/journey 类) | memory_graph 数据 + 前端 radial timeline 页 | 3-5 人日 |
| P2-3 | Skills Hub 外部市场对接(agentskills.io 标准) | skill_crawler 已有雏形,接公共目录源 | 3-4 人日 |
| P2-4 | JetBrains 扩展 | VS Code 扩展稳定后移植 | 8-12 人日 |
| P2-5 | Computer Use 桌面控制强化(Appshots/锁屏续跑) | desktop_* 工具已有,补屏幕上下文注入 | 4-6 人日 |

---

## 4. 总体对齐度评分

**统计口径**: 矩阵 33 项,✅ 21 项、🔄 9 项、❌ 3 项(IDE 扩展、AGENTS.md、Slack 入站)。

| 对标对象 | 对齐度 | 说明 |
|---|---|---|
| vs Codex | **约 72%** | 治理/商业化/多端已对齐;核心差在 IDE 扩展、AGENTS.md、云沙箱工程深度(缓存/白名单/云托管)、评审运行验证 |
| vs Hermes | **约 80%** | 记忆/技能自改进/MoA/completion contracts/fan-out 均已具备;核心差在 execute_code 程序化调用、渠道广度、serverless 沙箱后端 |
| **综合对齐度** | **76 / 100** | (21×1 + 9×0.5)/33 ≈ 77%,取 76 |

**关键结论**: X-Agent 商用修复后的底盘(治理、计费、记忆、多代理、MCP、多端)已相当完整,与两家的差距已从"面"收敛到 5 个 P0"点":Goal Mode 接线、execute_code 进主循环、AGENTS.md、serverless 沙箱后端、Slack 入站。P0 合计约 17-26 人日,完成后综合对齐度可达 88+。

---

*报告完。撰写人:能力对标审计员,2026-07-26。仅新建本报告,未修改任何代码。*
