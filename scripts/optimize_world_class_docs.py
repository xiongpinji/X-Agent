from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def p(rel: str) -> Path:
    return ROOT / rel


def write(rel: str, content: str) -> None:
    path = p(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def append_once(rel: str, marker: str, content: str) -> None:
    path = p(rel)
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")


def baseline_for(rel: str) -> tuple[str, str, str]:
    if rel.startswith("17-"):
        return ("OpenClaw + BrowserGym/WebArena", "本地自动化安全、视觉可靠性、外部副作用审计", "RPA/多模态能力")
    if rel.startswith("18-") or rel.startswith("13-"):
        return ("Hermes Agent + OpenClaw + MCP", "技能供应链、manifest、沙箱、签名、导入兼容", "技能生态能力")
    if rel.startswith("19-"):
        return ("企业 IM 平台 + OpenAI Agents SDK guardrails", "消息发送审批、PII 扫描、审计留痕", "企业通讯能力")
    if rel.startswith("20-"):
        return ("OpenAI Agents SDK + LangGraph + SWE-bench", "开发者体验、trace、CI gate、benchmark", "智能开发工具能力")
    if rel.startswith("21-"):
        return ("2026 前沿研究 track", "先证明收益，再进入产品路线", "前沿研究能力")
    if rel.startswith("16-"):
        return ("LangGraph durable execution", "checkpoint、resume、retry、compensation", "工作流能力")
    if rel.startswith("06-"):
        return ("X-Agent 文档治理标准", "学习路径、FAQ、发布日志职责分离", "文档治理能力")
    return ("2026 一线 Agent 框架", "工程化、评测、安全、生态", "通用能力")


def enrich_doc(rel: str) -> None:
    path = p(rel)
    text = path.read_text(encoding="utf-8")
    if "## 世界级补强字段" in text:
        return
    baseline, gap, capability = baseline_for(rel)
    title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else rel
    enrichment = f"""
## 世界级补强字段

| 字段 | 内容 |
|---|---|
| 对标对象 | {baseline} |
| 能力归属 | {capability} |
| 当前差距 | {gap} |
| 发布等级 | 未完成实现前最高为 L0/L1；通过自动化验收、安全审计和回归评测后才能提升到 L2/L3 |

## 接口与数据要求

- 必须接入 `RunContext`，携带 `trace_id`、`tenant_id`、`user_id`、`permission_scope`、预算和风险等级。
- 所有外部副作用必须先通过 `ToolPolicy` 或等价策略引擎判定。
- 产出数据必须结构化，至少包含 `status`、`result`、`error`、`trace_id`、`created_at`。
- 与其他模块交互时优先使用 `模块接口契约.md` 中的统一错误码和审计事件。

## 安全门槛

- 默认最小权限，任何高危操作必须显式授权。
- 记录输入、策略判定、执行结果和失败原因，审计日志不可被普通业务流程修改。
- 处理用户数据、企业数据、截图、通讯内容时必须做敏感信息检测和租户隔离。
- 第三方依赖、技能、脚本或模型接入前必须经过来源校验和回滚设计。

## 自动化评测

| 指标 | 最低要求 |
|---|---|
| 正确性 | 覆盖核心 happy path 和至少 3 类失败路径 |
| 稳定性 | 连续 100 次 smoke run 无状态泄漏 |
| 可观测性 | 每个失败样例能通过 trace 定位到输入、策略、工具或外部系统 |
| 回归 | 新版不得让既有基准成功率下降超过 3% |

## 降级与回滚

- 策略失败时回退到上一个稳定版本。
- 外部系统不可用时返回可解释错误，不吞掉失败。
- 涉及写操作时必须提供补偿动作、人工处理步骤或明确的不可回滚说明。

## 交付清单

- [ ] 设计文档字段完整。
- [ ] API/CLI/配置入口明确。
- [ ] 单元测试、集成测试、benchmark 样例齐全。
- [ ] 安全审查通过。
- [ ] 运维指标和告警规则明确。

## 文档状态

本文档已从重复模板拆分为独立主题：`{title}`。后续修改不得重新复制其他主题正文，只能通过链接引用公共标准。
"""
    path.write_text(text.rstrip() + "\n\n" + enrichment.strip() + "\n", encoding="utf-8")


WORLD_CLASS_BASELINE = """# X-Agent 2026 世界级对标与补强路线图

## 用途

本文档是 X-Agent 后续所有设计、开发、验收的最高优先级基准。任何模块进入实现前，都必须回答三个问题：

1. 与 2026 年一线 Agent 框架相比，X-Agent 解决了什么独特问题。
2. 安全、可观测、评测、回滚、生态兼容是否达到可上线标准。
3. 如果能力无法量化验证，是否应降级为研究实验而不是核心承诺。

## 2026 对标框架能力矩阵

| 对标对象 | 一线能力 | X-Agent 当前文档短板 | 补强要求 |
|---|---|---|---|
| OpenClaw | 多入口个人助手、技能生态、本地自动化、桌面/移动/消息渠道、Canvas、语音、沙箱 | 生态愿景强但缺少技能供应链治理、host 权限分级、公开实例风险控制 | 所有技能必须签名、SBOM、权限 manifest、风险等级、运行审计；RPA 默认最小权限 |
| Hermes Agent | 学习循环、技能系统、记忆、MCP、cron、容器隔离、危险命令审批、会话搜索 | 记忆设计宏大但缺少实测指标；技能学习缺少沙箱评测闭环 | 以“可学习、可验证、可回滚”为技能生命周期主线；学习前后必须跑基准集 |
| LangGraph | durable execution、checkpoint、interrupt/human-in-the-loop、多 Agent 图编排 | 工作流文档偏 UI/概念，缺少持久化执行语义 | 工作流节点必须支持 checkpoint、resume、retry、compensation、人工审批 |
| OpenAI Agents SDK | handoffs、guardrails、tracing、tool execution、run lifecycle | 缺少统一 tracing schema 与 guardrail policy | 每次 Agent run 必须有 trace_id、span、tool call、policy verdict、cost、latency |
| Microsoft AutoGen / Agent Framework | 多 Agent 角色协作、群聊、工具化、企业生态 | 多 Agent 协作有示意，但缺少死锁、预算、冲突和结果仲裁规则 | 子代理调度必须有 DAG、预算、权限、超时、仲裁和失败合并 |
| CrewAI / Dify | 易用角色编排、可视化流程、企业集成、低代码工作流 | 开发者体验和业务用户体验不足 | CLI、UI、模板、示例、导入导出、版本化 workflow 都要成为一等能力 |

## 世界级一线标准

| 维度 | 必达标准 | 阻断条件 |
|---|---|---|
| 可运行性 | `docker compose up` 后 10 分钟内跑通首个 Agent 任务 | 没有一键启动或 health check 失败 |
| 可靠性 | Agent run 支持 checkpoint、取消、恢复、幂等工具调用 | 长任务中断后无法恢复 |
| 安全 | 工具权限、技能签名、沙箱隔离、Prompt 注入防护、审计日志全覆盖 | 高危工具可无审批执行 |
| 评测 | GAIA/BrowserGym/SWE-bench Lite/内部中文企业任务集定期跑分 | 没有基线、没有回归趋势 |
| 可观测 | tracing、cost、latency、token、tool verdict、memory hit 全链路可查 | 失败任务无法定位原因 |
| 生态 | 技能 manifest 标准化，兼容 Hermes/OpenClaw/MCP，支持导入、扫描、隔离、发布 | 第三方技能可绕过权限模型 |
| 企业就绪 | 多租户、RBAC、RLS、数据加密、备份恢复、SLO、升级回滚 | 租户数据可能串读 |
| 开发体验 | CLI、SDK、模板、示例、文档测试、迁移指南齐全 | 新开发者无法在 1 小时内新增工具 |

## 能力分级

| 级别 | 定义 | 可发布状态 |
|---|---|---|
| L0 文档概念 | 只有设计说明或提示词 | 不发布，只能标记为 research |
| L1 原型 | 单机可运行，手动测试通过 | demo 可用，不进企业版 |
| L2 产品功能 | 有测试、审计、配置、失败处理 | 可进入 beta |
| L3 生产能力 | 有 SLO、权限、回滚、监控、红队测试 | 可商用上线 |
| L4 一线能力 | 有公开 benchmark、生态兼容、长期兼容策略 | 可对标全球一线 |

## 优先级重排

1. 先做 AgentCore、ToolRegistry、LLMRouter、Memory L1-L4、API、Web UI，形成可运行闭环。
2. 再做 tracing、guardrails、sandbox、benchmark、cost router，把安全和评测前置。
3. 然后做技能系统、MCP、Hermes/OpenClaw 适配、工作流 checkpoint。
4. 自我进化、十层高阶记忆、情感智能、量子/元宇宙等默认归入 research，只有通过量化评测后才能进入核心路线。

## 每项文档必须补齐的字段

- 对标对象：本模块主要对标哪个一线框架能力。
- 差距说明：X-Agent 当前不足是什么。
- 设计补强：具体新增接口、数据模型、策略或流程。
- 安全门槛：权限、沙箱、审计、数据隔离、人工审批。
- 评测指标：至少 3 个可自动化检测的指标。
- 降级/回滚：失败时如何恢复到稳定状态。
- 发布等级：L0/L1/L2/L3/L4。
"""


REFERENCE_DOC = """# X-Agent 参考资料与学习路径 [31] v6.0

## 目标

本文件只维护学习路径和官方资料入口，不再混入 FAQ 或更新日志模板。

## 2026 必读框架

| 类别 | 资料 | 学习重点 |
|---|---|---|
| Agent SDK | OpenAI Agents SDK | handoffs、guardrails、tracing、tool lifecycle |
| 工作流编排 | LangGraph | durable execution、checkpoint、interrupt、state graph |
| 多 Agent | AutoGen / Microsoft Agent Framework | 角色协作、群聊、工具调用、企业治理 |
| 技能生态 | Hermes Agent | 学习循环、技能验证、容器隔离、MCP |
| 本地自动化 | OpenClaw | 多入口助手、RPA、技能供应链安全 |
| 可视化工作流 | Dify / CrewAI | 低代码编排、角色模板、企业集成 |

## 论文与评测

| 方向 | 推荐资料 | 用途 |
|---|---|---|
| 工具推理 | ReAct、Toolformer | AgentLoop 与工具调用策略 |
| 多路径推理 | Tree of Thoughts、Graph of Thoughts | ToT/MCTS 模块边界 |
| 自我修正 | Reflexion、Self-Consistency | Reflection 与回归评测 |
| 通用 Agent 评测 | GAIA、AgentBench | 综合任务基线 |
| 浏览器/RPA | BrowserGym、WebArena | 浏览器自动化基线 |
| 代码 Agent | SWE-bench Lite、HumanEval | 代码生成与修复基线 |

## 学习顺序

1. 先读 `2026世界级对标与补强路线图.md`，明确一线标准。
2. 再读 `开发总控索引.md`，只实现 Phase 0 的最小闭环。
3. 阅读 `模块接口契约.md`，确保接口、trace、权限、错误模型一致。
4. 对每个模块先写验收测试，再实现代码。

## 资料维护规则

- 优先引用官方文档、论文、仓库 README。
- 不把营销文章作为架构依据。
- 每季度复核一次对标框架能力，更新差距矩阵。
"""


FAQ_DOC = """# X-Agent FAQ 常见问题 [32] v6.0

## 架构范围

### Q: 十层记忆是否必须一次性实现？

A: 不必须。Phase 0 只实现 L1-L4：感知、工作、短期、情景/向量记忆。L5-L10 必须先证明能提升 memory hit rate、task success rate 或用户留存，否则保持 research 状态。

### Q: 自我进化可以自动改生产策略吗？

A: 默认不可以。任何影响 prompt、工具权限、模型路由、记忆写入策略的变更都必须经过 sandbox benchmark、A/B 验证和可回滚快照。生产环境只允许 L1 参数微调自动化，L2/L3 需要人工批准。

### Q: 为什么要对标 Hermes 和 OpenClaw？

A: Hermes 代表技能学习、记忆和安全层实践；OpenClaw 代表大规模个人 AI 助手和本地自动化生态。X-Agent 要进入一线，必须同时补齐“产品可用性”和“安全治理”。

### Q: 什么功能可以砍掉？

A: 量子级记忆、元宇宙、全感官多模态、生物启发等前沿主题默认不进入 MVP。它们只有在有真实用户场景、工程依赖和评测指标后才进入 roadmap。

## 安全与合规

### Q: 高危工具如何执行？

A: 所有 `shell`、文件写入、浏览器登录态操作、企业通讯发送、外部 webhook、RPA 点击都必须经过 ToolPolicy 判定。高危操作默认需要人工确认，并写入不可变审计日志。

### Q: 第三方技能如何接入？

A: 必须有 manifest、签名、SBOM、权限声明、网络域名白名单、资源限制、测试报告。OpenClaw/Hermes 技能迁移只能进入隔离区，扫描通过后才能发布。

## 开发流程

### Q: 世界级标准的最小可验收版本是什么？

A: 不是功能最多，而是闭环可运行、trace 可查、权限可控、失败可恢复、评测可复现。Phase 0 必须先达成这些底线。

### Q: 文档中的 Codex 提示词能直接生成生产代码吗？

A: 不能直接视为生产实现。提示词只能作为脚手架输入，生成结果必须经过接口契约、单元测试、集成测试、安全扫描和 benchmark gate。
"""


CHANGELOG_DOC = """# X-Agent 更新日志模板 [33] v6.0

## 版本格式

采用 `YYYY.MM.patch`，例如 `2026.05.1`。每个版本必须关联评测结果、安全影响和回滚方式。

## 模板

```markdown
# Release 2026.05.1

## Summary
- 本次发布解决什么用户/工程问题。

## Added
- 新增功能，必须标注发布等级 L1/L2/L3/L4。

## Changed
- 行为变更、接口变更、配置变更。

## Fixed
- 缺陷修复。

## Security
- 权限、沙箱、Prompt 注入、数据隔离、供应链相关变化。

## Benchmark
| 套件 | 上版 | 本版 | 变化 |
|---|---:|---:|---:|
| GAIA subset | 0.00 | 0.00 | 0.00 |
| BrowserGym subset | 0.00 | 0.00 | 0.00 |
| SWE-bench Lite subset | 0.00 | 0.00 | 0.00 |

## Rollback
- 回滚命令、数据迁移回退、配置恢复方式。

## Known Risks
- 尚未解决的风险和观测指标。
```

## 强制规则

- 没有 benchmark diff 的 Agent 能力不得标记为增强。
- 没有安全说明的工具/技能/RPA 变更不得发布。
- 数据库迁移必须给出 forward 和 rollback。
"""


WORKFLOW_EXECUTOR_DOC = """# X-Agent 工作流执行引擎设计 [69] v6.0

## 对标目标

对标 LangGraph 的 durable execution 与 OpenAI Agents SDK 的 run lifecycle，目标是让长任务可恢复、可观测、可审批。

## 核心语义

| 能力 | 要求 |
|---|---|
| Checkpoint | 每个节点执行前后保存状态、输入、输出、trace_id |
| Resume | 进程重启后从最近成功节点恢复 |
| Retry | 节点级退避重试，支持幂等键 |
| Compensation | 外部副作用工具必须定义补偿动作或人工处理流程 |
| Human-in-the-loop | 高风险节点进入 pending_approval 状态 |
| Deterministic replay | 相同输入、相同版本、mock LLM 下可复放 |

## 数据模型

```python
class WorkflowNodeRun:
    run_id: str
    workflow_id: str
    node_id: str
    status: str  # pending | running | succeeded | failed | skipped | pending_approval
    input_hash: str
    output_ref: str | None
    idempotency_key: str
    trace_id: str
    retry_count: int
```

## 验收指标

- 100 节点 DAG 恢复成功率 >= 99%。
- Worker 随机 kill 后无重复高危副作用。
- 节点 P95 调度延迟 < 100ms。
- 每次失败都能通过 trace 定位到节点、输入、工具和策略。

## 发布等级

L3 之前不得承载企业审批、支付、生产数据写入等高风险工作流。
"""


WORKFLOW_TEMPLATE_DOC = """# X-Agent 工作流模板与最佳实践 [70] v6.0

## 目标

提供可复用、可测试、可审计的业务工作流模板，而不是复制执行引擎设计。

## 标准模板结构

```yaml
name: daily-market-report
version: 1.0.0
risk_level: medium
inputs:
  topic: string
nodes:
  - id: collect
    type: agent_task
    timeout_seconds: 120
  - id: verify
    type: evaluator
  - id: send
    type: enterprise_message
    approval: required
outputs:
  report_url: string
```

## 内置模板

| 模板 | 场景 | 风险控制 |
|---|---|---|
| daily-report | 定时收集、分析、发送日报 | 发送前人工确认 |
| code-review | 代码审查、测试建议、风险摘要 | 仅读权限 |
| web-research | 网页调研、引用整理、摘要 | 来源白名单 |
| rpa-form-fill | 表单填写与截图留证 | 高危点击审批 |
| incident-brief | Sentry/日志摘要、处置建议 | 不自动执行修复 |

## 最佳实践

- 所有模板必须有 `risk_level`、`timeout_seconds`、`approval`、`rollback` 字段。
- Agent 节点输出必须结构化，禁止把自由文本直接作为下游条件表达式。
- 模板发布前至少跑 20 条回归样例。
"""


RPA_DOCS = {
    "17-企业级RPA与多模态/72-多模态识别系统设计.md": """# X-Agent 多模态识别系统设计 [72] v6.0

## 对标目标

对标 OpenClaw 的本地自动化体验和 BrowserGym/WebArena 的可测浏览器任务，重点补齐视觉定位可靠性。

## 范围

- OCR：PaddleOCR/Tesseract/云 OCR 可切换。
- 视觉 grounding：DOM 优先，截图坐标只作为 fallback。
- ASR：Faster-Whisper，本地优先。
- 图像理解：多模态 LLM 只做解释，不直接执行高危操作。

## 安全门槛

- 识别结果置信度 < 0.85 时禁止自动点击。
- 登录、支付、删除、发送消息等动作必须二次确认。
- 所有截图脱敏后再进入云模型。

## 评测

| 指标 | 目标 |
|---|---:|
| OCR 字段准确率 | >= 95% |
| UI 元素定位准确率 | >= 90% |
| 低置信度拦截率 | >= 99% |
""",
    "17-企业级RPA与多模态/73-内置浏览器自动化设计.md": """# X-Agent 内置浏览器自动化设计 [73] v6.0

## 对标目标

对标 OpenClaw 浏览器自动化和 LangGraph checkpoint 思路，做到可恢复、可审计、可重放。

## 架构

- Playwright 驱动浏览器上下文。
- BrowserSession 隔离 cookie、storage、proxy、下载目录。
- ActionPlan 先生成计划，再经 ToolPolicy 判定后执行。
- 每步保存 DOM snapshot、screenshot hash、network summary、trace span。

## 禁止项

- 默认禁止使用用户主浏览器登录态。
- 禁止绕过网站安全、验证码、付费墙。
- 禁止无确认提交表单、发送消息、购买、删除数据。

## 验收

- BrowserGym 子集成功率 >= 60% 起步，逐版本提升。
- 每个失败任务都有 trace、截图和 DOM 证据。
- 长任务中断后可恢复到最近安全 checkpoint。
""",
    "17-企业级RPA与多模态/74-企业级安全与合规.md": """# X-Agent RPA 企业级安全与合规 [74] v6.0

## 安全模型

RPA 是最高风险能力之一，默认按零信任设计。

| 层级 | 控制 |
|---|---|
| 身份 | 用户、租户、Agent、工具实例均有独立身份 |
| 权限 | 文件、浏览器、网络、剪贴板、键鼠、企业通讯分开授权 |
| 审批 | 高危动作 pending_approval |
| 隔离 | 容器/虚拟桌面/独立浏览器 profile |
| 审计 | 操作前后截图、DOM、输入参数、审批人、trace_id |

## 合规要求

- PII 自动识别和脱敏。
- 审计日志不可被普通管理员修改。
- 支持租户级数据保留和删除策略。
- 技能供应链扫描必须覆盖依赖、脚本、网络域名、权限申请。

## 红队测试

- Prompt 注入诱导执行 shell。
- 恶意网页隐藏按钮诱导点击。
- 技能包窃取 cookie。
- 企业通讯误发敏感数据。
""",
    "17-企业级RPA与多模态/75-RPA任务编排与调度.md": """# X-Agent RPA 任务编排与调度 [75] v6.0

## 目标

把 RPA 从“脚本执行”升级为可排队、可暂停、可恢复、可审批的生产任务。

## 调度模型

```python
class RpaJob:
    id: str
    workflow_id: str
    tenant_id: str
    risk_level: str
    status: str
    checkpoint_ref: str | None
    max_runtime_seconds: int
    approval_policy: str
```

## 队列

- low risk：可自动执行。
- medium risk：关键节点审批。
- high/critical：必须人工确认每个外部副作用。

## 验收

- 任务超时后自动释放浏览器/桌面资源。
- 重试不会重复提交表单。
- 调度器重启后任务状态一致。
""",
    "17-企业级RPA与多模态/76-企业级部署与运维.md": """# X-Agent RPA 企业级部署与运维 [76] v6.0

## 部署形态

| 形态 | 场景 | 约束 |
|---|---|---|
| 本地单机 | 个人助手、开发测试 | 默认无公网入口 |
| 容器沙箱 | 浏览器任务、低风险工具 | 限制网络和文件系统 |
| 虚拟桌面池 | 企业 RPA | 每租户隔离 profile |
| K8s Worker | 大规模低交互任务 | 禁止访问宿主机敏感路径 |

## 运维指标

- active_sessions、failed_actions、approval_waiting、sandbox_escape_attempts。
- P95 action latency、browser crash rate、memory leak trend。
- 每日生成高危操作审计报告。

## 灾备

- 长任务 checkpoint 持久化。
- 浏览器 profile 加密备份。
- Worker 滚动升级前 drain 任务。
""",
}


SKILL_AND_ENTERPRISE_DOCS = {
    "18-Skillhub集成/77-Skillhub技能商店集成指南.md": """# X-Agent Skillhub 技能商店集成指南 [77] v6.0

## 目标

Skillhub 是技能来源之一，不直接等同可信来源。所有外部技能必须进入隔离导入流程。

## 导入流程

1. 拉取 manifest、源码、依赖、许可证。
2. 生成 SBOM。
3. 扫描网络域名、文件访问、shell 调用、环境变量读取。
4. 在沙箱运行 smoke tests。
5. 转换为 X-Agent SkillManifest。
6. 进入待审核区。

## 验收

- 100% 技能有 manifest、权限、版本、签名或来源证明。
- 高危权限默认拒绝。
- 技能安装、升级、卸载均可审计和回滚。
""",
    "18-Skillhub集成/78-统一技能市场设计文档.md": """# X-Agent 统一技能市场设计 [78] v6.0

## 对标目标

对标 Hermes 的技能学习/内置技能生态与 OpenClaw 的大规模技能分发，同时补齐供应链安全。

## 核心能力

- 多源：local、Skillhub、Hermes、OpenClaw、MCP server。
- 统一 manifest：名称、版本、权限、输入输出、风险等级、测试报告。
- 发布治理：签名、审核、评分、漏洞下架、版本冻结。
- 运行隔离：容器/Wasm/进程沙箱按风险选择。

## 评分体系

| 维度 | 权重 |
|---|---:|
| 任务成功率 | 30% |
| 安全评分 | 25% |
| 维护活跃度 | 15% |
| 文档和示例 | 15% |
| 性能和成本 | 15% |
""",
    "19-企业通讯集成/79-企业通讯平台集成指南.md": """# X-Agent 企业通讯平台集成指南 [79] v6.0

## 范围

飞书、钉钉、企业微信作为企业入口，必须统一为 MessageGateway。

## 统一接口

```python
class MessageGateway:
    async def send_message(self, channel: str, target: str, content: dict) -> str: ...
    async def request_approval(self, action: dict) -> str: ...
    async def receive_event(self, payload: dict) -> dict: ...
```

## 安全要求

- 企业通讯发送属于外部副作用，默认进入 ToolPolicy。
- 敏感内容发送前做 PII 扫描。
- 审批消息必须防重放，含 nonce、expires_at、approver_id。
""",
    "19-企业通讯集成/80-微信开放平台集成文档.md": """# X-Agent 微信开放平台集成文档 [80] v6.0

## 场景

微信登录、公众号消息、小程序入口、企业微信互通。

## 设计原则

- OAuth token 加密存储，按租户隔离。
- 不把个人微信作为默认自动化渠道。
- 所有用户主动授权都有 scope、expires_at、撤销入口。

## 验收

- OAuth 回调防 CSRF。
- token refresh 失败可恢复。
- 消息发送前通过审计和内容策略。
""",
    "19-企业通讯集成/81-企业通讯最佳实践.md": """# X-Agent 企业通讯最佳实践 [81] v6.0

## 通知分级

| 级别 | 示例 | 策略 |
|---|---|---|
| info | 日报、摘要 | 可静默合并 |
| action | 需要用户确认 | 明确按钮和超时 |
| risk | 高危操作审批 | 二次确认、审计 |
| incident | 安全/生产事故 | 多渠道升级 |

## 内容规范

- 结论先行，附 trace 链接。
- 不在消息里泄露密钥、完整 PII、内部 token。
- 审批按钮必须显示影响范围和回滚方式。
""",
    "20-智能开发工具/82-Codex集成与代码生成系统.md": """# X-Agent Codex 集成与代码生成系统 [82] v6.0

## 目标

Codex 只作为工程助手，不作为未审核代码直接进入生产的通道。

## 流程

1. 从模块文档生成任务卡。
2. Codex 生成补丁和测试。
3. 运行 lint、type check、unit、integration。
4. 安全扫描和许可证扫描。
5. 人工 review 后合并。

## 评测

- SWE-bench Lite 子集。
- 项目内回归测试通过率。
- 生成代码的缺陷密度和回滚率。
""",
    "20-智能开发工具/83-知识库与RAG系统设计.md": """# X-Agent 知识库与 RAG 系统设计 [83] v6.0

## 对标目标

对标企业级 RAG 的可追溯、权限继承、引用准确性。

## 架构

- Ingestion：解析、切块、去重、PII 检测。
- Index：pgvector/Milvus + BM25 + metadata filter。
- Retrieval：hybrid search + RRF rerank。
- Answer：必须返回引用和置信度。

## 验收

- 检索权限 100% 继承源文档 ACL。
- citation precision >= 90%。
- 无引用回答默认降级为“无法确认”。
""",
    "20-智能开发工具/84-开发者工具链完整指南.md": """# X-Agent 开发者工具链完整指南 [84] v6.0

## 一线开发体验目标

新开发者 60 分钟内完成：启动环境、创建工具、注册技能、跑测试、查看 trace。

## 工具链

- `xagent dev up`：启动依赖。
- `xagent tool create`：创建工具模板。
- `xagent skill validate`：校验 manifest、权限和测试。
- `xagent trace open`：打开某次 Agent run。
- `xagent benchmark run`：运行本地基准。

## 验收

- CLI 输出稳定 JSON，便于 CI 使用。
- 每个模板都有最小测试。
- 文档示例可被自动执行验证。
""",
    "20-智能开发工具/85-CI_CD与DevOps实践.md": """# X-Agent CI/CD 与 DevOps 实践 [85] v6.0

## Pipeline Gate

| 阶段 | 阻断条件 |
|---|---|
| lint/type | ruff/mypy/eslint 失败 |
| tests | 单元或关键集成失败 |
| security | 依赖高危漏洞、secret 泄露、危险权限无审批 |
| benchmark | 关键任务成功率下降超过 3% |
| docs | 接口契约和 OpenAPI 不一致 |

## 发布策略

- canary 优先。
- 自动回滚条件：P95 延迟、失败率、成本、policy violation 任一超阈值。
- 每次发布附 benchmark diff 和安全变更说明。
""",
}


FRONTIER_DOCS = {
    "21-前沿技术/91-社交智能系统设计.md": """# X-Agent 社交智能系统设计 [91] v6.0

## 发布等级

默认 L0 research。只有在企业协作场景证明能提升沟通效率且不侵犯隐私时进入 L2。

## 范围

- 组织关系图谱只使用授权数据。
- 沟通风格适配必须可关闭。
- 不推断敏感属性。

## 评测

- 用户满意度、误判率、隐私投诉率。
""",
    "21-前沿技术/92-主动探索学习系统.md": """# X-Agent 主动探索学习系统 [92] v6.0

## 目标

让 Agent 主动发现知识缺口，但不能擅自访问敏感系统或产生外部副作用。

## 策略

- 探索任务必须在 allowlist 数据源内执行。
- 每个探索都要有 hypothesis、budget、stop condition。
- 新知识进入候选记忆，验证后才巩固。

## 评测

- 新知识可用率、错误巩固率、成本收益比。
""",
    "21-前沿技术/94-区块链与Web3集成.md": """# X-Agent 区块链与 Web3 集成 [94] v6.0

## 安全定位

默认只读分析。任何签名、转账、合约部署都属于 critical risk，必须人工离线确认。

## 能力

- 链上数据检索。
- 合约 ABI 解释。
- 风险扫描摘要。

## 禁止

- 自动托管私钥。
- 自动签名交易。
- 绕过用户钱包确认。
""",
    "21-前沿技术/95-量子计算准备方案.md": """# X-Agent 量子计算准备方案 [95] v6.0

## 定位

Research only。当前不进入核心产品路线。

## 可保留范围

- 量子算法学习资料索引。
- 与 Qiskit/Cirq 的实验性 notebook。
- 对优化问题的模拟 benchmark。

## 进入路线条件

必须证明在具体任务上优于经典算法或能服务真实客户需求。
""",
    "21-前沿技术/96-生物启发式计算系统.md": """# X-Agent 生物启发式计算系统 [96] v6.0

## 定位

Research only。不得包装成核心智能能力。

## 可实验方向

- 蚁群/遗传算法用于工作流调度。
- Hebbian-like 策略用于记忆权重实验。

## 验收

只有在成本、稳定性或成功率显著优于基线时进入 roadmap。
""",
    "21-前沿技术/97-元宇宙智能集成.md": """# X-Agent 元宇宙智能集成 [97] v6.0

## 定位

可作为虚拟培训、数字展厅、3D 操作教学的垂直插件，不进入核心 Agent 内核。

## 最小能力

- 3D 场景问答。
- 虚拟角色展示 Agent 输出。
- 操作步骤可视化。

## 风险

隐私、沉浸式误导、内容安全，需要单独审核。
""",
    "21-前沿技术/98-边缘计算与IoT系统.md": """# X-Agent 边缘计算与 IoT 系统 [98] v6.0

## 目标

把 Agent 能力部署到边缘设备时保持离线、安全和可运维。

## 架构

- 边缘节点只运行轻量模型和规则。
- 中心云下发签名策略和技能。
- 离线日志回传后统一审计。

## 验收

- 断网 24 小时内核心任务可继续。
- 设备密钥硬件隔离。
- OTA 可回滚。
""",
}


README_ALIAS = """# X-Agent 开发总控索引别名

本文件曾与 `开发总控索引.md` 完全重复。为避免双入口维护，唯一规范入口改为：

- [开发总控索引.md](./开发总控索引.md)

所有开发顺序、Phase、模块依赖、世界级 gate 都以该文件为准。
"""


def main() -> None:
    write("2026世界级对标与补强路线图.md", WORLD_CLASS_BASELINE)
    write("README_开发总控索引.md", README_ALIAS)
    write("06-附加文档/31-参考资料与学习路径.md", REFERENCE_DOC)
    write("06-附加文档/32-FAQ常见问题.md", FAQ_DOC)
    write("06-附加文档/33-更新日志模板.md", CHANGELOG_DOC)
    write("16-工作流编排/69-工作流执行引擎设计.md", WORKFLOW_EXECUTOR_DOC)
    write("16-工作流编排/70-工作流模板与最佳实践.md", WORKFLOW_TEMPLATE_DOC)

    for rel, content in RPA_DOCS.items():
        write(rel, content)
    for rel, content in SKILL_AND_ENTERPRISE_DOCS.items():
        write(rel, content)
    for rel, content in FRONTIER_DOCS.items():
        write(rel, content)

    rewritten = [
        "06-附加文档/31-参考资料与学习路径.md",
        "06-附加文档/32-FAQ常见问题.md",
        "06-附加文档/33-更新日志模板.md",
        "16-工作流编排/69-工作流执行引擎设计.md",
        "16-工作流编排/70-工作流模板与最佳实践.md",
        *RPA_DOCS.keys(),
        *SKILL_AND_ENTERPRISE_DOCS.keys(),
        *FRONTIER_DOCS.keys(),
    ]
    for rel in rewritten:
        enrich_doc(rel)

    append_once(
        "README.md",
        "## 2026 世界级对标基准",
        """## 2026 世界级对标基准

新增最高优先级文档：[2026世界级对标与补强路线图.md](./2026世界级对标与补强路线图.md)。

后续所有模块必须补齐：对标对象、差距说明、设计补强、安全门槛、评测指标、降级/回滚、发布等级。重复模板文档已拆分为独立职责文档，Phase 2 之后的前沿能力默认按 research 管理，未通过量化评测不得进入核心路线。""",
    )

    append_once(
        "开发总控索引.md",
        "## 2026 世界级 Gate",
        """## 2026 世界级 Gate

在执行任何 Phase 前，先阅读 [2026世界级对标与补强路线图.md](./2026世界级对标与补强路线图.md)。每个模块必须满足以下 gate：

| Gate | 要求 |
|---|---|
| G1 可运行 | 模块有最小可运行路径和 health check |
| G2 可观测 | trace_id、span、latency、token、cost、tool verdict 全记录 |
| G3 可控 | ToolPolicy、权限、审批、租户隔离明确 |
| G4 可评测 | 有 benchmark 或回归样例，能比较上版和本版 |
| G5 可恢复 | checkpoint、retry、rollback 或人工补偿路径明确 |

Phase 0 增补顺序：

1. 先实现 AgentLoop、LLMRouter、ToolRegistry、Memory L1-L4、API、Web UI。
2. 同步实现 tracing、guardrails、cost router、error taxonomy。
3. 任何 shell/RPA/企业通讯工具在无 ToolPolicy 前不得默认启用。
4. 自我进化、十层高阶记忆、前沿技术统一标记为 research，等评测通过后再提升发布等级。""",
    )

    append_once(
        "模块接口契约.md",
        "## 世界级运行契约补强",
        """## 世界级运行契约补强

所有跨模块调用必须携带 `RunContext`，用于对齐 OpenAI Agents SDK tracing、LangGraph checkpoint、Hermes/OpenClaw 技能治理经验。

```python
class RunContext:
    trace_id: str
    tenant_id: str
    user_id: str
    agent_id: str
    request_id: str
    permission_scope: list[str]
    budget_tokens: int
    budget_usd: float
    risk_level: str  # low | medium | high | critical
```

### ToolPolicy 判定

```python
class ToolPolicyVerdict:
    allowed: bool
    requires_approval: bool
    sandbox_profile: str
    reason: str
    audit_required: bool = True
```

所有工具执行必须先调用 `policy_engine.evaluate(context, tool, arguments)`。高危工具禁止绕过审批。

### Trace 事件

每个 Agent run 至少记录：

- `agent.started`
- `memory.search`
- `llm.request`
- `tool.policy_verdict`
- `tool.started`
- `tool.completed`
- `agent.completed`
- `agent.failed`

### Checkpoint 契约

长任务、工作流、RPA、子代理必须实现 checkpoint：

```python
await checkpoint_store.save(run_context, state)
state = await checkpoint_store.load(trace_id)
```

无法 checkpoint 的模块最高只能标记为 L1 原型。""",
    )

    append_once(
        "01-项目规划/05-开发计划与里程碑.md",
        "## 2026 重排后的关键里程碑",
        """## 2026 重排后的关键里程碑

为达到世界级一线标准，里程碑从“功能数量优先”调整为“闭环、治理、评测优先”。

| 月份 | 必须完成 | 不达标则延后 |
|---|---|---|
| M1 | Monorepo、docker compose、health check、首个 Agent run | 所有 Phase 1 能力 |
| M2 | ToolPolicy、trace、基础 benchmark、LLM fallback | RPA 和企业通讯写操作 |
| M3 | Memory L1-L4、API、Web UI、成本统计、回归测试 | 十层高阶记忆 |
| M6 | 插件/技能沙箱、MCP、Hermes/OpenClaw 只读适配 | 技能市场开放发布 |
| M9 | 工作流 checkpoint/resume、人工审批、RAG 权限继承 | 自我进化上线 |
| M12 | 多 Agent DAG、预算和仲裁、红队测试 | 自动执行高危任务 |

Phase 2 之后所有前沿能力必须先在 research track 证明收益，再进入产品 track。""",
    )

    append_once(
        "05-项目管理/29-项目交付清单.md",
        "## 2026 世界级交付门槛",
        """## 2026 世界级交付门槛

| 交付项 | 最低门槛 |
|---|---|
| AgentCore | 10 个标准任务可复现，失败有 trace |
| ToolRegistry | 权限、审批、沙箱、审计全覆盖 |
| Memory | hit rate、latency、错误巩固率可统计 |
| Workflow | checkpoint、resume、retry、compensation |
| Skills | manifest、签名/SBOM、隔离运行、回滚 |
| RPA | BrowserGym/WebArena 子集评测，所有副作用可审计 |
| Enterprise | 多租户、RBAC、RLS、备份恢复、SLO |

任何模块如果没有自动化验收脚本，只能算文档完成，不算交付完成。""",
    )

    append_once(
        "01-项目规划/06-风险评估与应对.md",
        "## 2026 对标后新增风险",
        """## 2026 对标后新增风险

| ID | 风险 | 对标来源 | 应对 |
|---|---|---|---|
| R11 | 技能供应链投毒 | OpenClaw/Hermes 技能生态 | 签名、SBOM、沙箱、权限 manifest、漏洞下架 |
| R12 | 本地高权限自动化误操作 | OpenClaw RPA/桌面助手 | ToolPolicy、审批、截图留证、补偿流程 |
| R13 | 长任务不可恢复 | LangGraph durable execution | checkpoint、resume、idempotency key |
| R14 | 黑盒失败难定位 | OpenAI Agents SDK tracing | 全链路 trace、span、policy verdict、cost 记录 |
| R15 | 评测缺失导致虚假进步 | 2026 Agent benchmark 实践 | GAIA/BrowserGym/SWE-bench Lite/内部任务集回归 |

新增阻断规则：安全、trace、benchmark、rollback 任一缺失时，不允许标记为生产能力。""",
    )


if __name__ == "__main__":
    main()
