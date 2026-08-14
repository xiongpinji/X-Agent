# X-Agent v0.4.0-rc1 — Release Notes

**日期**: 2026-08-14 · **状态**: Release Candidate（商业 RC 门禁 `ready_for_rc_tag`，owner-verified 放行）

这是 X-Agent 首个通过完整商业 RC 证据链验证的候选发布。从 2026-07-19 审计基线（商用就绪度 31/100）到本候选版，全部 P0/P1/P2 工程缺口已闭合并实测验证。

## 验证状态（全部实测，证据在 `.xagent_runtime/reports/`）

- **RC 最终门禁**: `ready_for_rc_tag`（owner-verified 放行，独立复核 exit=0）
- **托管 CI**: Commercial RC Gate run #151 success（commit `53f38c5`）
- **Codex/Hermes 差距矩阵**: 9/9 全绿（first_release / web_chat / telegram_loop / issue_to_pr / skill_curator / gateway / installer / frontend / docs）
- **外部真实验证 5/5**: 真实 LLM provider（Ollama qwen3）、飞书 webhook 契约、GitHub Issue→PR dry-run + execute 预检、托管 Actions
- **回归**: tests/unit + tests/contracts 2292 passed / 0 failed；RC 基线通过
- **依赖安全**: pip-audit 全量清零；npm audit 0 漏洞（react-router-dom 6→7.18.2）

## 核心能力（M1 RC 范围）

- **Agent 核心**: ReAct 主循环 + token 级上下文压缩 + 会话恢复 + fast-path + 控制平面 hooks（AGENT_START/USER_PROMPT_SUBMIT 前置拒绝）
- **执行**: Docker 沙箱 + subprocess 降级 + serverless 后端（Daytona/Modal 适配器）+ execute_code 程序化工具调用（HIGH 风险审批）
- **自主性**: Goal Mode 长时目标（暂停/恢复/取消/持久化）、工作流编排（cron 调度 + 崩溃恢复 checkpoint 续跑）、并行子代理委派（capability 匹配 + 轮询 + PROCESS 隔离）
- **记忆**: 三层混合记忆 + 真实嵌入（sentence-transformers/OpenAI 兼容）+ 写入路径索引化去重（10k 条 5.2s）+ Qdrant/Postgres 后端
- **工具生态**: 官方 MCP SDK（stdio + Streamable HTTP）+ 技能运行时 + 技能自沉淀 + AGENTS.md 机制（prompt_guard 消毒）
- **渠道**: 飞书 / Telegram / Slack / 钉钉 / Discord / webhook
- **治理**: OIDC SSO + SCIM 2.0、RBAC + 租户隔离、审批流（SoD 防自审自批）、审计哈希链 + 轮转 + syslog/webhook 外送、提示注入防御、OTel 导出
- **产品形态**: React Web 管理面（30+ 页面）+ console 子应用 + CLI + 桌面（Tauri 配置）+ 移动端（Expo）+ 浏览器扩展

## 已知边界（交付口径声明）

1. **功能面收窄**: 8 月路由瘦身（2429→332 路由）摘下 30+ 模块挂载（GDPR/备份/反馈等），对应前端为死调用或 coming soon，清单见 `archive/api_templates_2026-08/KEPT_ROUTERS.md`。
2. **未经生产实战**: Docker 沙箱、真实 Postgres/k8s 部署、云端 LLM key 均为配置级验证，无长时运行证据。建议先试点 1-2 周。
3. **外部项未闭环**: SOC2 认证与第三方渗透测试（外部供应商主导，6-12 个月），影响企业采购准入，不阻塞本 RC。
4. **移动端打包**: expo export 受 Windows 环境限制未实测。

## 升级与部署

- 版本单一事实源: `pyproject.toml`（0.4.0-alpha，RC 标签 v0.4.0-rc1）
- 快速开始: `docs/operations/`；部署: `deployment/helm/`（唯一权威清单）
- 生产部署必须显式配置外部存储（生产守卫 fail-fast）：`XAGENT_DATABASE_URL`、`XAGENT_MEMORY_BACKEND=postgres`、`XAGENT_ADMIN_STORE_BACKEND=postgres`、`XAGENT_WORKFLOW_STORE_BACKEND=db`

## 发布物

- 源码包: `.xagent_runtime/release/x-agent-commercial-rc-20260814T*.zip`（115 文件，sha256 校验）
- 证据包: `.xagent_runtime/reports/rc-evidence-pack.json`
- 门禁状态: `commercial_audit/m1_rc_gate_status_2026-08-14.md`
