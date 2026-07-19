# 03 · 行业基准调研：2026  autonomous/coding agent 赛道「完整商用交付」标尺

> **角色标签**: 行业基准研究员
> **任务范围**: 联网调研 2026 年 autonomous/coding agent 赛道代表产品(Claude Code / Claude Agent SDK、GitHub Copilot coding agent、Devin、Cursor 含 background agents、Windsurf/Devin Desktop、Google Jules)的关键功能、定价档位、企业级能力(SSO/SAML、SOC2、审计日志、数据驻留、沙箱隔离)、SLA 与支持体系, 并产出「完整商用交付能力 checklist」(功能/安全合规/部署运维/开发者体验/商业化 五大维度, P0/P1/P2 分级), 作为后续审计 X-Agent Core 的标尺。
> **调研日期**: 2026-07-19
> **方法**: WebSearch + FetchURL, 来源以官方文档/定价页为最高优先级, 其次为 2025-2026 年第三方评测与行业分析。每条关键事实标注来源与日期; 无法从官方渠道二次确认的内容标注「待验证」。
> **注意**: 本报告只建立"行业标尺", 不涉及 X-Agent 代码审计(由其他角色完成)。

---

## 一、赛道总览: 2026 年的三个结构性变化

在逐产品分析之前, 先确立三个 2026 年已成立的宏观判断, 它们直接决定 checklist 的形状:

1. **"席位订阅 + 用量计量"双层计费成为行业标准。** GitHub Copilot 于 2026-06-01 将 chat/agent mode/code review/CLI 全面切换为按量计费的 AI Credits(超额 $0.01/credit, 无默认上限) [来源: llmgateway.io, 2026-07-12, https://llmgateway.io/blog/microsoft-copilot-enterprise-pricing]; Cursor 自 2025 年 6 月起按底层模型 API 实际 token 成本计费 [来源: Vantage, 2026-03-04, https://www.vantage.sh/blog/cursor-pricing-explained]; Anthropic 曾宣布 2026-06-15 起为 Agent SDK 设立独立月度信用额(Pro $20 / Max 5x $100 / Max 20x $200), 但在生效当日(2026-06-16)暂停, 现状仍是消耗订阅额度 [来源: totalum.app, 2026-06-22, https://www.totalum.app/blog/claude-agent-sdk-credits-2026; webotit.ai, 2026-06-07 更新 06-23, https://www.webotit.ai/blog/agents-ia/pricing/claude-code-agent-sdk-15-juin-2026-cadrer-budget-dsi]。**结论: 任何商用 agent 产品都必须同时具备"席位管理"与"用量计量/超额计费"两套商业管道。**

2. **异步后台 agent(cloud agent / background agent)从差异化功能变成标配入口。** GitHub Copilot cloud agent 在所有付费档可用, 跑在 GitHub Actions 驱动的临时开发环境中 [来源: GitHub 官方文档, 抓取于 2026-07-19, https://docs.github.com/en/copilot/concepts/about-copilot-coding-agent]; Cursor Pro 档即含 Cloud Agents [来源: NxCode, 2026-03-24, https://www.nxcode.io/resources/news/cursor-ai-pricing-plans-guide-2026]; Windsurf Pro 档含 cloud sessions/Devin Cloud [来源: devin.ai/pricing, 抓取于 2026-07-19]。**"本地 IDE 内同步辅助 + 云端异步委派"双形态已是基准线。**

3. **企业采购决策点已从"模型能力"转向"治理面(governance plane)"。** 2026-07-10 的团队采购指南将决策轴归纳为: 席位价与最低席位数、SSO 与管理控制、数据治理书面承诺、与代码评审流程的整合、退出成本 [来源: YixScout, 2026-07-10, https://yixscout.com/resources/columns/best-ai-coding-tools-for-teams]。企业 MVP 基准(2026): 传输 TLS 1.3 + 静态 AES-256、SAML 2.0 + MFA、SOC 2 Type II、完整审计追踪、季度渗透测试 + bug bounty、99.9% 起步的 uptime SLA(优选 99.99%)、API p95 < 200ms、24 小时内完整数据导出 [来源: StartupBricks, 2026-01-16, https://www.startupbricks.in/blog/building-mvp-for-enterprise-clients]。

---

## 二、代表产品逐一画像

### 2.1 Claude Code / Claude Agent SDK (Anthropic)

**产品形态**: 终端原生 coding agent(CLI) + IDE 扩展(VS Code/JetBrains) + Web/桌面 + GitHub Actions + 可编程 Claude Agent SDK(供第三方构建 agent) + 2026-04-08 公测的 Claude Managed Agents(托管 agent 运行时, $0.08/session-hour + token 费用) [来源: CodeMySpec, 2026-03-25, https://codemyspec.com/blog/claude-code-review-2026]。

**定价档位**(2026 年中核实):
- Pro $20/月; Max 5x $100/月; Max 20x $200/月(个人)
- Team $20/席/月(年付) 或 $25/席/月(月付), 含 Claude Code; Enterprise 定制价
- API/SDK 按 token 计费; Agent SDK 库本身免费(Anthropic Commercial Terms), 信用额拆分方案 2026-06-16 暂停
[来源: YixScout 2026-07-10(同上); developersdigest.tech, 2026-06-11, https://www.developersdigest.tech/blog/claude-agent-sdk-vs-langgraph; totalum.app, 2026-06-22(同上)]

**企业级能力**(依据官方管理员文档, 抓取于 2026-07-19, https://code.claude.com/docs/en/admin-setup, 页面日期 2026-07-18):
- **身份**: Enterprise 档 SSO(SAML/OIDC)、SCIM、强制登录方式/组织(`forceLoginMethod`/`forceLoginOrgUUID`, 覆盖终端、VS Code、Agent SDK)
- **策略下发**: 四级 managed settings(claude.ai 管理控制台 server-managed > plist/HKLM 注册表 > 文件 > HKCU), 托管配置优先于开发者本地配置, 每小时刷新
- **执行隔离**: OS 级沙箱(文件系统+网络隔离, 域名 allowlist); 权限规则 allow/ask/deny; 可禁用 `--dangerously-skip-permissions`; MCP 服务器/插件市场/hook 全量管控; 模型可用列表与版本下限强制
- **数据**: Team/Enterprise/API 均不训练; Enterprise 合格账号可选 Zero Data Retention(ZDR, 请求完成即不存储); 500K 上下文(Enterprise chat)
- **可观测**: OpenTelemetry 导出(会话/工具/token)、analytics dashboard、per-user 用量与成本 API、spend limits; 自托管 Claude apps gateway 提供带 IdP 身份的逐请求审计日志
- **多云合规继承**: 可经 Amazon Bedrock / Google Cloud Agent Platform / Microsoft Foundry 接入, 继承对应云的合规姿态与账单
- **认证**: SOC 2 Type II、ISO 27001、ISO 42001、HIPAA 可配置 [来源: systemprompt.io 对比, 2026-07-18, https://systemprompt.io/guides/claude-code-vs-cursor]
- **SLA**: Enterprise API 99.9% 月度 uptime SLA(2026 年 1 月起生效, 覆盖 Messages/Batch/Files API, beta 功能除外, 未达标自动发放服务额度) [来源: claudebeat.ai, 2026-01-24, https://claudebeat.ai/articles/2026/01/2026-01-24.html — 二手行业媒体, 建议以 Anthropic 合同文本为准, 标注**待验证**]

**对 X-Agent 的启示**: Anthropic 把"agent 运行治理"做成了可远程下发、不可被开发者覆盖的策略层, 并把 SDK(让别人造 agent)与托管运行时(Managed Agents)作为上层产品售卖 —— 这是"框架型"产品(X-Agent 的自我定位)的直接对标。

### 2.2 GitHub Copilot coding agent / cloud agent (GitHub/Microsoft)

**产品形态**: IDE 内补全/chat/agent mode + **cloud agent**(后台异步: 研究仓库→建计划→在分支上改代码→可选直接开 PR; 可从 GitHub.com agents 面板、Issue、VS Code、Azure Boards/JIRA/Linear/Slack/Teams 触发; 支持 @copilot 评论驱动、定时/事件驱动 automations、安全告警修复) [来源: GitHub 官方文档, 抓取于 2026-07-19(同上)]。

**定价档位**(2026-07-10 核实):
- Free(2,000 completions/月); Pro(个人, 约 $10 档); Business $19/用户/月; Enterprise $39/用户/月 —— 但 Enterprise 实际需叠加 GitHub Enterprise Cloud($21/用户/月), 实付约 $60/席
- Copilot Max $100/月(2026 年中暂停新注册)
- 2026-06-01 起 chat/agent/code review/CLI 计量 AI Credits, 超额 $0.01/credit
[来源: YixScout 2026-07-10(同上); aiflowreview.com, 2026-07-06, https://aiflowreview.com/github-copilot-pricing/; llmgateway.io, 2026-07-12(同上); techjacksolutions.com, 2026-06-16, https://techjacksolutions.com/ai-tools/github-copilot/github-copilot-pricing/]

**企业级能力**:
- **沙箱架构**: cloud agent 在 GitHub Actions 驱动的**临时(ephemeral)开发环境**中运行; 单会话硬上限 59 分钟; 单任务单分支单 PR; 默认仅能访问当前仓库上下文(可经 MCP 设置放宽); 支持自定义 `copilot-setup-steps.yml` 环境配置与超时 [来源: GitHub 官方文档(同上)]
- **可定制**: custom instructions、MCP servers(默认启用 GitHub MCP 与 Playwright MCP)、custom agents、hooks(执行期 shell 钩子, 可加验证/日志/安全扫描)、skills、Copilot Memory(公测)
- **治理**: Business/Enterprise 需管理员开启 cloud agent 策略; 组织级策略管理; 组织审计日志含 `action:copilot` 事件过滤 [来源: 官方文档(同上); USC 教材摘录 GitHub 官方文档, https://bytes.usc.edu/cs572/s25-555-sear-ch/lectures/Misc1/docs/ProgWithCopilot_6tfVV.pdf]; Copilot 用量度量 API(含 agent 创建/合并 PR 数、合并时长中位数)
- **合规**: GitHub 整体 SOC 1 Type 2 / SOC 2 Type 2 年度审计(合同条款级承诺) [来源: DLT 转引 GitHub Enterprise 协议, https://www.dlt.com/sites/default/files/documents/2021-03/Github-Enterprise-Subscription.pdf]
- **SLA**: 99.9% **季度** uptime, 仅覆盖 GitHub Enterprise Cloud(Issues/PR/Git/API/webhooks/Pages), Free/Team 档无 SLA, Enterprise Server 不在范围 [来源: DevHelm, 抓取于 2026-07, https://devhelm.io/sla/github]
- **值得注意的限制**: cloud agent **不遵守 content exclusions**(管理员配置的文件排除对 cloud agent 无效) —— 说明即便头部厂商, "异步 agent 与既有治理规则的一致性"仍是难点 [来源: GitHub 官方文档(同上)]

**对 X-Agent 的启示**: GitHub 的杀手锏是"agent 行为全部落在 PR/branch/log 上, 天然可审计可评审"; 且把沙箱复用为既有 CI 基础设施(Actions), 运维成本与信任成本都极低。

### 2.3 Devin (Cognition)

**产品形态**: 全自动 AI 软件工程师 —— web 界面/Slack/API 触发, 在专属 workspace(shell+浏览器+编辑器)中执行任务; 架构分为 **Brain**(推理, 永远在 Cognition 云)与 **Devbox**(执行沙箱) [来源: Devin 官方企业部署文档, 抓取于 2026-07-19, 页面日期 2026-07-16, https://docs.devin.ai/enterprise/deployment/overview]。

**定价档位**(2026 年 Cognition 统一定价页, 抓取于 2026-07-19, https://devin.ai/pricing —— 注意该页已将 Devin 与 Windsurf/Devin Desktop 合并呈现):
- Free $0(轻量配额); Pro $20/月(含 OpenAI/Claude/Gemini 前沿模型、SWE 1.7 与开源模型免费额度、Devin Cloud 云 agent); Max $200/月
- Teams: $80/月团队基础费 + $40/全开发席位(集中计费、管理 dashboard、优先支持)
- Enterprise: 定制(SAML/OIDC SSO、集中管理控制、专属部署、专属客户经理)
- 历史锚点: Devin 2.0(2025-04)从 $500/月降至 $20 起步按量 [来源: VentureBeat, 2025-04-03, https://venturebeat.com/technology/devin-2-0-is-here-cognition-slashes-price-of-ai-software-engineer-to-20-per-month-from-500]

**企业级能力**:
- **双部署模型**: ① Enterprise Cloud(Cognition 多租户云, 分钟级开通, 每会话独立隔离机器); ② Customer Dedicated Deployment(单租户 VPC, AWS PrivateLink 或 IPSec 隧道接入客户内网, 支持 OpenVPN/MFA VPN 访问内网资源) [来源: Devin 官方企业部署文档(同上)]
- **会话隔离**: 临时沙箱, 会话结束即销毁; 短期限定域凭证; 日志中密钥脱敏 [来源: augmentcode.com, 2026-06-23, https://www.augmentcode.com/tools/jetbrains-central-alternatives]
- **身份/治理**: Enterprise 档 SAML SSO [来源: onyx.app, 2026-05-08, https://onyx.app/insights/best-enterprise-openclaw-options-2026]; 但 Brain 始终在 Cognition 云 —— 即"执行可在客户 VPC, 编排不出厂商云", 这是与完全自托管方案(如 Ona/OpenHands)的关键差异 [来源: ona.com/compare/devin, https://ona.com/compare/devin]
- **SOC2/审计日志/SLA 细节**: 官方部署文档未在抓取内容中明示; 第三方称 Enterprise 提供 VPC 部署与 SAML SSO [同上 onyx.app]。**SOC2 证书范围、审计日志粒度、SLA 数字: 待验证(需直接向 Cognition 索取)。**

**对 X-Agent 的启示**: Devin 定义了"企业 agent 部署"的两档基线(多租户 SaaS 快开 / 单租户 VPC 私接内网), 并明确"编排层 vs 执行层"分离的架构话术 —— X-Agent 的"云沙箱"叙事必须回答同样的问题: 编排数据落在哪? 执行沙箱能否进客户 VPC?

### 2.4 Cursor (Anysphere, 含 background/cloud agents)

**产品形态**: AI 原生 IDE(VS Code fork) + Agent + **Cloud Agents(后台 agent)** + Bugbot(agentic 代码评审) + MCP/skills/hooks [来源: NxCode, 2026-03-24(同上); YixScout 2026-07-10(同上)]。

**定价档位**(2026 年核实):
- Hobby 免费; Pro $20/月(含 $20 API 用量); Pro+ $60/月(约 $70 用量); Ultra $200/月(约 $400 用量)
- Teams $40/用户/月(每用户 $20 agent 用量、集中计费、用量分析、SAML/OIDC SSO); Enterprise 定制(用量池化、发票/PO 付款、SCIM、优先支持)
- 计费模式: 2025-06 起按底层模型 API 实际成本(Auto 模式约 $0.25/M cache read、$1.25/M input、$6/M output), 超额同价按量
[来源: Vantage, 2026-03-04(同上); techjacksolutions.com, 2026-06-16, https://techjacksolutions.com/ai-tools/cursor/cursor-pricing/; finout.io, https://www.finout.io/blog/what-happened-to-cursor-pricing-2026-guide-5-cost-cutting-tips(其中 Standard $40 / Premium $120 的席位划分与其他来源不一致, **待验证**, 以官网 $40 Teams 为准)]

**企业级能力**:
- **隐私**: Privacy Mode(与 OpenAI/Anthropic/Fireworks/Together 等模型方签零数据保留 ZDR 协议; Teams/Enterprise 默认强制开启, 系统每 5 分钟校验一次, 校验失败自动回退隐私模式); Privacy Mode (Legacy) 更严格(Cursor 自身也不存代码) [来源: MintMCP, 2026-04-12, https://www.mintmcp.com/blog/cursor-security; jellyfish.co, 2026-04-13, https://jellyfish.co/library/cursor-ai-monitoring/]
- **身份/治理**: SAML/OIDC SSO、SCIM 2.0、模型/MCP/agent 规则集中配置、AI 代码追踪、审计日志(登录、成员/角色变更、API key 生命周期、团队设置、Privacy Mode 变更等; 可过滤、CSV 导出、SIEM 流式对接) [来源: jellyfish.co(同上); shuaiguan.io, 2026-07-06, https://shuaiguan.io/blog/cursor-statistics]
- **合规**: SOC 2 Type II(年度渗透测试); **无 HIPAA、无 FedRAMP** [来源: beyondscale.tech, 2026-04-13, https://beyondscale.tech/blog/ai-coding-assistant-security-enterprise-guide]; 基础设施主 AWS(US), 辅 Cloudflare/Azure/GCP [来源: neura.market, 2026-04-23, https://www.neura.market/directories/cursor/guides/cursor-privacy-and-security-keeping-your-code-safe]
- **数据驻留**: 纯云, 无自托管选项; 代码索引以分块上传计算 embedding, 明文处理后即弃, 但 embedding 与元数据存于 Cursor 服务器; 未提供澳大利亚等区域驻留 [来源: aurascape.ai, 2026-06-25, https://aurascape.ai/answers/does-cursor-store-retain-or-train-on-source-code/; aivy.com.au, 2026-07-11, https://aivy.com.au/resources/cursor-vs-windsurf-devin-desktop/]
- **风险记录**: 2025 年 v1.3 修复 5 个高危 RCE CVE; Electron 版本陈旧导致 94+ Chromium n-day 未修(OX Security 披露) —— 桌面端供应链安全是 IDE 形态产品的共同短板 [来源: beyondscale.tech(同上)]

**对 X-Agent 的启示**: Cursor 示范了"隐私模式可强制、可验证、可回退"的治理细节, 也暴露了桌面 IDE 形态(对比 X-Agent 的桌面端)在漏洞暴露面上的代价。

### 2.5 Windsurf → Devin Desktop (Cognition)

**产品形态**: AI 原生 IDE(Cascade agent, 正迁移至 Devin Local agent) + 自研 SWE-1.5/1.6 模型 + Agent Command Center(并行 agent 会话看板) + Spaces(git worktree 上下文捆绑) + 云 sessions; 2025 年被 Cognition 收购(传 $250M), 2026-06-02 起品牌并入 Devin Desktop [来源: AITrendTool, 2026-07-03, https://aitrendtool.com/tools/windsurf; ToolNav, 2026-06-03, https://toolnav.io/review/windsurf/; The Dev Brief, 2026-05-25, https://thedevbrief.com/windsurf-vs-cursor-2026/]。

**定价档位**(2026-03-19 改版后): Free $0; Pro $20/月(自 $15 上调); Max $200/月; Teams $40/用户/月(最新官方页为 $80 团队基础费 + $40/席位); Enterprise 定制。配额制(每日/每周自动刷新)取代旧 credit 池; Tab 补全全档无限; 年付约省 17% [来源: nocode.mba, 2026-06-26, https://www.nocode.mba/articles/windsurf-pricing; dynalord.com, 2026-07-15, https://dynalord.com/blog/windsurf-pricing; devin.ai/pricing(同上)]

**企业级能力**(本产品的差异化核心):
- **零数据保留**: 付费席位默认 ZDR, 推理后代码即弃 [来源: Layer3 Labs, 2026-07-07, https://www.layer3labs.io/guides/windsurf-for-business]
- **自托管/混合部署**: Enterprise 档支持, 可断网(air-gapped)运行, 出站仅连可信模型端点 —— 在本赛道中稀缺 [同上]
- **合规**: 历史持有 SOC 2 Type II, 可为合格客户支持 HIPAA; 收购后认证延续性需与厂商书面确认(**待验证**) [同上]
- **治理**: SSO、RBAC、审计日志、集中计费与用量 dashboard(Teams 起) [同上]
- **风险提示**: 并入 Cognition 后路线图/定价/数据条款处于过渡期, 采购指南明确建议"把零保留与自托管承诺写进合同而非营销页" [同上]

**对 X-Agent 的启示**: Windsurf 证明"代码不出边界(自托管 + ZDR)"本身就是可卖高价的企业买点; 对宣称"云沙箱"的 X-Agent 而言, 这是最高优先级的对标维度。

### 2.6 Google Jules

**产品形态**: 异步 coding agent —— 克隆仓库至 Google Cloud VM, 自主改码、跑测试、开 PR; 深度绑定 GitHub(Issues/Projects/Discussions/Actions); 底层 Gemini 模型; 无官方移动端 App; 有 Jules CLI(`@google/jules`) [来源: agent-finder.co 评测, 2026-07-01, https://agent-finder.co/reviews/jules-by-google; cosyra.com, 2026-06-11, https://cosyra.com/guides/cosyra-vs-jules.html]。

**定价档位**(第三方评测口径, 2026-07 核实):
- 免费档(有限任务数); Individual $20/月(500 issues/月, 3 并发, 无限仓库); Team $50/用户/月(1,000 issues/月, 10 并发, 优先支持, 工作流定制); Enterprise 定制(无限 issues, 专属支持, **自托管选项**)
- 全档 14 天试用; 强制 GitHub OAuth
[来源: agent-finder.co(同上) — 第三方评测, 其中"2026 年 2 月发布"等表述与公开记录(Jules 2025 年已进入 public beta)存在出入, **定价细节建议以 Google 官方页面复核, 标注待验证**]

**企业级能力**: Enterprise 档宣称专属支持与自托管选项 [同上, 待验证]; 继承 GitHub 权限模型(用户无权访问的仓库 Jules 同样无权); 测试不通过则不开 PR 的质量门; 第三方实测 34 个 issue 成功 23 个(68%), 单 issue 节省约 45-90 分钟 [来源: agent-finder.co(同上)]。SLA、SOC2、审计日志等企业细节未在公开渠道检索到 —— **待验证**。

**对 X-Agent 的启示**: Jules 是"平台巨头以生态位(GitHub + Google Cloud)切入"的样本: 功能未必最强, 但分发与基础设施成本优势极大; 其"强制 OAuth + 继承宿主权限模型"是低摩擦企业采纳的范本。

---

## 三、横向对比总表

> 价格均为公开牌价(2026-06/07 核实), 企业档均为定制价。"—"表示公开渠道未确认。

| 维度 | Claude Code/Agent SDK | GitHub Copilot | Devin | Cursor | Windsurf/Devin Desktop | Google Jules |
|---|---|---|---|---|---|---|
| 个人入门档 | Pro $20 | Free / Pro ~$10 | Free / Pro $20 | Hobby / Pro $20 | Free / Pro $20 | 免费档 / $20 |
| 团队档 | Team $20-25/席 | Business $19/席 | $80 基础+$40/席 | Teams $40/席 | Teams $40/席(+$80 基础) | Team $50/席(待验证) |
| 高档/重度 | Max $100/$200 | Enterprise $39(实付~$60) / Max $100 | Max $200 | Pro+ $60 / Ultra $200 | Max $200 | Enterprise 定制 |
| 用量计量 | API 按 token; SDK 信用额(暂停) | AI Credits(2026-06 起) | 超额按 API 价 | 按模型 API 实价 | 日/周配额+超额按 API 价 | 按 issue 数配额 |
| 异步后台 agent | GitHub Actions / Managed Agents | cloud agent(全付费档) | 原生核心形态 | Cloud Agents | Devin Cloud sessions | 原生核心形态 |
| 沙箱隔离 | OS 级沙箱+域名白名单 | Actions 临时环境, 59 分钟硬上限 | 每会话独立机器, 会话结束销毁 | 云 agent(细节未公开) | 云 sessions | Google Cloud VM |
| SSO/SAML | Enterprise ✓ | 经 GitHub EMU/IdP ✓ | Enterprise ✓ | Teams 起 ✓ | Enterprise ✓ | 经 GitHub OAuth(部分) |
| SCIM/席位管理 | Enterprise ✓ | ✓(GitHub 组织) | 企业档(集中管理) | Enterprise ✓ | 企业档 ✓ | —(待验证) |
| 审计日志 | 经 apps gateway 逐请求(含 IdP 身份) | 组织审计日志 action:copilot | —(待验证) | ✓(可导 CSV/SIEM) | 企业档 ✓ | —(待验证) |
| SOC 2 Type II | ✓(+ISO 27001/42001, HIPAA 可配) | ✓(GitHub 整体, SOC1/2) | 待验证 | ✓(无 HIPAA/FedRAMP) | ✓(历史上, 延续待验证) | —(待验证) |
| 数据驻留/自托管 | 经 Bedrock/GCP/Azure 继承区域; ZDR 可选 | GitHub 区域选项; 无自托管 | 单租户 VPC(PrivateLink/IPSec) | 无(纯云 AWS-US) | 自托管/混合/air-gapped ✓ | Enterprise 自托管(待验证) |
| 不训练承诺 | ✓(Team/Ent/API) | ✓(Business/Ent) | ✓ | ✓(Privacy Mode 强制+5 分钟校验) | ✓(付费档默认 ZDR) | —(待验证) |
| SLA | Enterprise API 99.9% 月(待合同确认) | 99.9% 季度(仅 Ent Cloud) | —(待验证) | —(未见公开 SLA) | —(待验证) | —(待验证) |
| 支持体系 | Enterprise 客户团队/Anthropic Academy | 标准 GitHub 支持分级 | Enterprise 专属客户经理 | Enterprise 优先支持 | Enterprise 专属客户经理 | Team 优先支持/Ent 专属(待验证) |

---

## 四、「完整商用交付能力」Checklist(审计 X-Agent 的标尺)

分级定义: **P0 = 无此项即不构成"可销售的商用产品"**(阻断性); **P1 = 企业采购流程中会被明确要求、缺失即丢单**; **P2 = 头部产品已有、构成竞争力与溢价, 但非入门必需**。

### A. 功能维度(产品能力本体)

| # | 能力项 | 级别 | 行业依据 |
|---|---|---|---|
| A1 | 同步交互式编码辅助(终端/IDE 内对话式改码) | P0 | 全部 6 款产品标配 |
| A2 | 异步后台任务 agent(委派任务→自主执行→产出 PR/结果) | P0 | Copilot cloud agent、Devin、Jules、Cursor Cloud Agents、Windsurf cloud sessions 均已标配; 2026 年已是入场券 |
| A3 | 任务全生命周期工件(计划、diff、日志、测试结果、PR 描述)可追溯可评审 | P0 | GitHub 将每步落在 commit/log; Jules 强制 PR 摘要模板 |
| A4 | 沙箱内可执行 shell/测试/lint/浏览器, 支持自定义环境初始化脚本 | P0 | Copilot `copilot-setup-steps.yml`; Devin Devbox(shell+浏览器+编辑器) |
| A5 | 多模型路由(前沿商业模型 + 开源/自研模型), 管理员可限制可用模型列表 | P1 | Claude `availableModels`; Cursor 多模型+Auto; Windsurf 自研 SWE 系列 |
| A6 | MCP/工具生态接入 + 自定义指令/技能(agents/skills/hooks) | P1 | 6 家全部支持 MCP; Copilot 有 hooks+skills+custom agents; Claude 有 managed CLAUDE.md |
| A7 | 并行 agent 会话管理(看板/多任务并发+队列) | P1 | Windsurf Agent Command Center; Jules 3/10/无限并发配额; Devin parallel sessions |
| A8 | 代码评审 agent(自动 review PR、安全告警修复) | P2 | Cursor Bugbot; Copilot code review + 安全活动修复 |
| A9 | 移动端触发/监控 agent 任务 | P2 | 竞品普遍薄弱(Jules 无官方 App); 是 X-Agent 移动端差异化机会 |
| A10 | 长任务记忆(跨会话仓库知识沉淀) | P2 | Copilot Memory(公测); 各家均在早期 |

### B. 安全与合规维度

| # | 能力项 | 级别 | 行业依据 |
|---|---|---|---|
| B1 | 传输 TLS 1.3 + 静态 AES-256 加密 | P0 | 企业 MVP 基准(StartupBricks 2026-01-16); Devin/Claude 均明示 |
| B2 | 不训练客户数据的书面承诺(分档明确, 可强制执行) | P0 | Anthropic/OpenAI/Cursor/Windsurf 全部提供; 采购要求"拿书面" |
| B3 | 零数据保留(ZDR)选项或 Privacy Mode, 且组织可强制开启 | P0(企业销售) | Cursor 强制+周期校验; Windsurf 付费档默认 ZDR; Claude Enterprise ZDR |
| B4 | 执行沙箱隔离: 每任务/会话独立临时环境, 任务结束销毁, 凭证短期限定域, 日志密钥脱敏 | P0 | Devin(独立机器+销毁+脱敏); Copilot(ephemeral+59 分钟); Claude(OS 级沙箱) |
| B5 | 网络出站控制(域名 allowlist / 防火墙) | P0 | Claude sandbox.network.allowedDomains; Copilot 环境网络受控 |
| B6 | 权限分级与人审闸门(allow/ask/deny; 高危动作强制人工批准; 禁止"跳过权限"模式被滥用) | P0 | Claude 三级权限+禁用 bypass; 企业托管规则不可被开发者覆盖 |
| B7 | SSO/SAML(OIDC) | P0(企业) | 除 Jules 外全部企业/团队档标配; Cursor Teams $40 即含 |
| B8 | SOC 2 Type II 报告(可向客户提供) | P1(首次企业销售前必须启动, 18 个月内拿到) | Claude/Cursor/Windsurf/GitHub 均持证; SOC2 首年成本 $83k-188k、周期 6-12 个月(100x Engineering, 2026-01-28) |
| B9 | 审计日志: 管理员行为+agent 行为全量记录, 可导出(CSV/SIEM), 含操作者身份 | P1 | Cursor(可导 CSV/SIEM); GitHub(action:copilot); Claude(apps gateway 带 IdP 身份) |
| B10 | SCIM 2.0 自动席位供给/回收 | P1 | Cursor Enterprise、Claude Enterprise、GitHub 标配 |
| B11 | 内容排除/敏感文件保护(.env、密钥 pattern 禁读; 且对异步 agent 同样生效) | P1 | Copilot 有 content exclusions 但 cloud agent 不生效(头部也踩坑); Claude 有 deny 规则 |
| B12 | 秘密管理(agent 运行时密钥注入、不入上下文/日志) | P1 | Devin 日志脱敏; 各沙箱方案的共同要求 |
| B13 | 渗透测试(年度起)+ 漏洞披露渠道 + 桌面端依赖(Electron 等)CVE 治理 | P1 | Cursor 年度 pen test; 其 Electron n-day 问题是反面教材 |
| B14 | 数据驻留选项(区域选择/客户 VPC/单租户) | P1(面向大客户) | Devin 单租户 VPC; Windsurf 自托管; Anthropic 经 Bedrock/GCP/Azure; Cursor 无(被诟病的点) |
| B15 | GDPR DPA / 删除权; HIPAA BAA(若触医疗); ISO 27001/42001(加分) | P2(按目标行业) | Claude 已拿 ISO 27001/42001+HIPAA 可配; Windsurf HIPAA 限定客户 |
| B16 | 提示注入/工具投毒威胁模型文档与防御(MCP 服务器白名单、插件市场管控) | P1 | Claude allowedMcpServers/strictKnownMarketplaces; 2026 年企业安全审查常规项 |

### C. 部署与运维维度

| # | 能力项 | 级别 | 行业依据 |
|---|---|---|---|
| C1 | 多租户 SaaS 分钟级开通 | P0 | Devin Enterprise Cloud; 所有 SaaS 竞品 |
| C2 | 托管云沙箱 fleet: 按需起停、会话隔离、镜像可定制、资源配额(并发/时长上限) | P0 | Copilot(59 分钟硬上限+自定义超时); Devin Devbox; Jules 并发配额 |
| C3 |  uptime SLA 合同化(≥99.9% 月/季)+ 未达标服务额度赔付机制 | P1 | Anthropic 99.9% 月(自动赔付); GitHub 99.9% 季度; 企业基准 99.9% 起步 |
| C4 | 状态页 + 事故通报流程 | P1 | 各厂商标配(商业惯例) |
| C5 | 用量/成本可观测: per-user 用量、token/费用 API、spend limits、超额告警 | P1 | Claude Analytics API+spend limits; GitHub 用量度量 API; Cursor 用量分析 |
| C6 | OpenTelemetry/日志导出对接客户观测栈 | P2 | Claude OTel 导出为标杆 |
| C7 | 企业专属部署选项(单租户 VPC / PrivateLink / 自托管 / air-gapped) | P2(决定能否做 >$100k 单) | Devin Customer Dedicated; Windsurf 自托管; Tabnine+Dell 断网方案为极端参照 |
| C8 | 版本治理: 强制最低版本、灰度更新、WSL/容器内行为一致性 | P2 | Claude minimumVersion/requiredMinimumVersion |
| C9 | 数据导出(24 小时内完整导出)与删除 SLA | P1 | 企业 MVP 基准(StartupBricks) |
| C10 | 性能基线: API p95 < 200ms; 10x 负载无劣化 | P2 | 企业 MVP 基准(同上) |

### D. 开发者体验维度

| # | 能力项 | 级别 | 行业依据 |
|---|---|---|---|
| D1 | 5 分钟内完成安装→首个任务跑通(quickstart) | P0 | Claude Quickstart; Jules 30 分钟上手 |
| D2 | 文档体系: 概念/操作/管理员部署/安全白皮书分册 | P0 | code.claude.com、docs.devin.ai 的结构即模板 |
| D3 | 可编程 SDK/CLI headless 模式(嵌入 CI 与第三方产品) | P1 | Claude Agent SDK 与 `claude -p`; Jules CLI; 这是"框架"定位的入场券 |
| D4 | API 优先的任务触发(web/Slack/IM/外部系统集成) | P1 | Devin web/Slack/API; Copilot 从 JIRA/Linear/Slack 触发 |
| D5 | 与 Git 宿主深度集成(PR 模板、分支保护兼容、权限继承) | P1 | Jules/Copilot 继承 GitHub 权限模型; Copilot ruleset bypass actor |
| D6 | 失败可恢复: 会话断点续跑、超时行为明确、部分结果保留 | P1 | Copilot 超时即停(反面教材); 行业无完美方案, 做好即是差异 |
| D7 | 模板/示例库与最佳实践课程 | P2 | Anthropic Academy; Copilot Skills exercise |
| D8 | 成本透明: 任务前预估、任务后账单明细 | P1 | 2025-2026 各厂定价改版风波(Cursor 道歉事件、Anthropic 信用额暂停)证明成本不透明是用户流失首因 |

### E. 商业化维度

| # | 能力项 | 级别 | 行业依据 |
|---|---|---|---|
| E1 | 清晰分档: 免费档(获客) + $20 个人档 + $40 上下团队档 + 定制企业档 | P0 | 6 家价格惊人收敛: 个人 $20、团队 $19-50、企业定制 |
| E2 | 席位管理 + 集中计费 + 用量计量/超额计费双管道 | P0 | GitHub AI Credits、Cursor API 实价、Windsurf 配额制 |
| E3 | 年付折扣(约 17-20%)+ 发票/PO 付款(企业档) | P1 | Windsurf 年付 -17%; Cursor 年付 -20%; Enterprise 支持 PO |
| E4 | 免费试用(7-14 天全功能) | P1 | Jules 14 天; 行业惯例 |
| E5 | 企业增值清单可售卖: SSO、审计日志、专属部署、专属客户经理、优先/专属支持 | P1 | 各家 Enterprise 档话术高度一致(即本 checklist 的 B/C 维 P1 项) |
| E6 | 支持分级与响应 SLA(如 Enterprise 4 小时响应、 named CSM) | P1 | 行业惯例(参照 Momental 4h 响应、Devin 专属客户经理) |
| E7 | 用量分析 dashboard 供客户自查(降低续约摩擦) | P1 | Cursor/Claude/Windsurf 团队档均含 |
| E8 | 防止"账单惊吓"机制: 默认预算上限、超额需显式 opt-in | P1 | GitHub credits 无默认上限被点名批评(反面教材); Anthropic 超额 opt-in(正面) |
| E9 | 市场/生态分发(GitHub Marketplace、IDE 插件市场、IM 应用目录) | P2 | Copilot/Jules 借 GitHub; Devin 借 Slack |

---

## 五、要点摘要(供主审计引用)

1. **定价形态已收敛**: 个人 $20 / 团队 $19-50 / 企业定制 + 用量计量(2026 年全面转向 AI credits/配额+API 实价超额)。X-Agent 若无可计量的用量管道与分档席位体系, 即不满足 P0 商业基准。
2. **异步后台 agent + 云沙箱是 2026 入场券**: 6 家中有 6 家提供; 基准配置 = 临时隔离环境、任务级销毁、时长/并发硬上限、自定义初始化、产出 PR 可评审。X-Agent 的"云沙箱"需逐项对标(隔离级别、凭证生命周期、日志脱敏、网络白名单)。
3. **企业治理面(governance plane)决定 B 端生死**: SSO/SAML(P0)、强制隐私模式/ZDR(P0)、审计日志可导出(P1)、SCIM(P1)、管理员策略不可被终端用户覆盖(P1, Claude managed settings 为最佳范本)。
4. **合规证书是时间最长的硬门槛**: SOC 2 Type II 需 6-12 个月 + $83k-188k 首年成本; Claude/Cursor/Windsurf/GitHub 均已持证。X-Agent 若 12 个月内要做企业销售, 现在就必须启动。
5. **部署分两层叙事**: "编排层在厂商云 + 执行沙箱进客户 VPC"(Devin 单租户 VPC)与"完全自托管/air-gapped"(Windsurf)是两个价位档; X-Agent 至少要能回答"编排数据落在哪"。
6. **SLA 与支持是合同级承诺**: 行业基准 99.9%(Anthropic 月度+自动赔付为最优范本, GitHub 仅季度且限 Enterprise Cloud); 配套状态页、赔付机制、分级响应(Enterprise 4h)。
7. **头部产品的公开短板 = X-Agent 的机会窗**: Copilot cloud agent 不遵守 content exclusions 且 59 分钟硬超时; Cursor 无自托管/无 HIPAA/Electron CVE 堆积; Jules 无移动端; Devin 编排层不可自托管。移动端触发、断点续跑、完全自托管是可差异化点。
8. **成本透明是留存变量**: Cursor 2025-07 公开道歉退款、Anthropic 2026-06 信用额方案临阵暂停, 均因计费沟通翻车。X-Agent 的计费设计应默认预算上限+超额 opt-in+任务级账单明细。

---

*报告完 · 行业基准研究员 · 2026-07-19*
