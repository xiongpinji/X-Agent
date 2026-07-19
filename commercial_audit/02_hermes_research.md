# Hermes Agent 竞品调研报告

- **角色标签**: Hermes竞品研究员
- **任务范围**: 考证 2026 年语境下 "Hermes Agent" 的指向产品，并对最可能候选做深度调研（架构、核心能力、模型与推理、部署形态、开源协议与社区、商业模式与定价、最新版本）。
- **调研日期**: 2026-07-19
- **数据时效说明**: 本报告基于 2026 年 4–7 月可检索到的公开资料（官方 GitHub、官方文档站、第三方评测），关键事实均标注来源与日期。

---

## 1. 产品考证：2026 年的 "Hermes Agent" 指什么？

### 1.1 结论（主线选定）

2026 年语境下，"Hermes Agent" 最可能指 **Nous Research 于 2026 年 2 月 25 日发布的同名开源自主 Agent 框架**（GitHub: `NousResearch/hermes-agent`，MIT 协议）。依据：

- 该框架 2026 年 2 月 25 日发布后 4 个月内获得 17.5 万+ GitHub stars，是 2026 年上半年增长最快的开源 agent 项目之一 [来源: aibuilderclub.com, 2026-06-02]。
- 2026 年 5 月 10 日，Hermes Agent 在 OpenRouter 日应用榜以 2240 亿日 tokens 超过 OpenClaw（1860 亿）登顶 [来源: techjacksolutions.com, 2026-07-02；该页面抓取返回 403，数据来自其搜索摘要，标注为**待二次验证**]。
- 多家 2026 年中的对比评测（Nodesify 2026-06-06、LeanVPS 2026-05-29 等）均以 "Hermes Agent by Nous Research" 为默认所指。

与 X-Agent Core 的竞品可比性：两者同为"通用自主 Agent 框架 + 多端部署 + 云端/沙箱执行"，定位高度重叠，可比性强。

### 1.2 其他同名候选（简述）

| 候选 | 说明 | 排除理由 |
|---|---|---|
| **Nous Research Hermes 模型系列**（Hermes 3 8B/14B/70B/405B 等） | Nous 的微调模型家族，以工具调用/agentic 能力著称 | 是"模型"而非"agent 产品"；但它正是 Hermes Agent 框架的同门底座，正文中会提及 |
| **OpenHermes / Nous Hermes 2 等早期模型** | 2023–2024 年的老模型，仍有 API 计费页面 | 非 agent 框架，属历史产品 [来源: pricepertoken.com, 2026-07] |
| **加密交易/物流等领域的 "Hermes" 命名产品** | 检索中出现的 "Hermes Agent crypto guide" 等内容实际仍指向 Nous 的 Hermes Agent（应用于加密场景），未发现独立成规模的同名商用 agent 产品 [来源: aurpay.net, 2026-05-26] | 非独立产品 |

**说明**: 是否存在其他小众商用 "Hermes Agent"（如企业内部产品），本次检索未发现可靠证据，标注为**不确定**。

---

## 2. 产品概览

- **名称**: Hermes Agent（官方口号："The self-improving AI agent built by Nous Research" / "the agent that grows with you"）
- **开发方**: Nous Research（ Hermes、Nomos、Psyche 模型家族背后的开源实验室）
- **首次发布**: 2026-02-25 [来源: aibuilderclub.com, 2026-06-02; hermesatlas.com, 2026-04-11]
- **开源协议**: MIT（完全开源，数据默认存于本地 `~/.hermes/`）[来源: GitHub 仓库 README, 2026-07 抓取]
- **最新版本**: v0.18.2（v2026.7.7.2，2026-07-07 发布；WhatsApp 依赖修复补丁）。此前 v0.18.0 "The Judgment Release"（2026-07-01）为大版本 [来源: GitHub Releases, 2026-07 抓取]
- **发布节奏**: 极高频。v0.13→v0.18 每个 minor 版本间隔约 1–2 周，单版本合并 PR 量在 500–1000 量级（v0.18.0：998 个 PR、949 个 issue 关闭、370+ 社区贡献者）[来源: GitHub Releases, 2026-07 抓取]

---

## 3. 架构设计

### 3.1 总体架构：Runtime-centric 自改进运行时

Hermes Agent 是 **Python 编写的"自改进运行时"**，而非网关型产品。其架构核心是官方所称的"闭环学习循环"（closed learning loop），覆盖五层"Harness（脚手架）"（对照人工 Harness Engineering）[来源: heyuan110.com 深度评测, 2026-04-14；GitHub README, 2026-07]：

| Harness 层 | Hermes 内建系统 |
|---|---|
| 指令 Instructions | Skill 系统（Markdown，自动创建 + 使用中自改进） |
| 约束 Constraints | 工具权限 + 沙箱执行 + 按需加载 toolset |
| 反馈 Feedback | 任务后反思的自改进学习循环（post-turn fork） |
| 记忆 Memory | 三层记忆 + Honcho 用户建模 |
| 编排 Orchestration | `delegate_task` 子代理 + cron 调度 + Kanban 多代理看板 |

### 3.2 代码结构与工程化

- 2026-05-28 的 v0.15.0 "Velocity Release" 完成核心重构：16,083 行的 `run_agent.py` 缩减为 3,821 行（-76%），拆分为 `agent/` 下 14 个内聚模块 [来源: GitHub Releases v0.15.0, 2026-05-28]。
- 冷启动优化显著：Termux 冷启动 2.9s→0.8s；每轮函数调用数减少 47% [来源: 同上]。
- 支持 `pip install hermes-agent`（PyPI 正式包，v0.14.0 起）[来源: GitHub Releases v0.14.0, 2026-05-16]。
- 提供 OpenAI 兼容 API server（`/v1/chat/completions`，v0.4.0 起）及 `hermes proxy`（把 OAuth 订阅供应商包装成 OpenAI 兼容端点，供 Codex CLI/Aider/Cline 等调用）[来源: petronellatech.com, 2026-04-16; GitHub Releases v0.14.0]。

### 3.3 多端界面层

- **CLI / Ink TUI**：多行编辑、斜杠命令自动补全、中断重定向、多会话切换编排 [来源: GitHub README, 2026-07]。
- **Messaging Gateway**：单进程网关接入 20+ 消息平台（Telegram、Discord、Slack、WhatsApp（Baileys 桥 + 官方 Business Cloud API）、Signal、Matrix、Mattermost、Email、SMS、DingTalk、Feishu、WeCom、Weixin、QQ Bot、Yuanbao、iMessage（Photon）、Microsoft Teams、Google Chat、LINE、SimpleX、ntfy、Home Assistant 等）[来源: GitHub README 与官方文档站, 2026-07; Releases v0.13–v0.17]。
- **Hermes Desktop**（v0.16.0，2026-06-05）：Electron 桌面应用（macOS/Linux/Windows），应用内自更新、拖拽文件、状态栏模型选择、多 profile 并发会话、完整简体中文 i18n、可连接远程 Hermes 网关（OAuth 或用户名密码）[来源: GitHub Releases v0.16.0]。
- **Web Dashboard**：v0.16.0 起成为完整管理面板（渠道配置、MCP 目录、凭据、webhook、记忆、OIDC/账密登录、Skills Hub 浏览）[来源: GitHub Releases v0.16.0]。

---

## 4. 核心能力

### 4.1 工具调用

- 内建 60+ 工具（文档站口径；2026-04 第三方评测口径为 40+，随版本增加），覆盖终端、文件、浏览器自动化、代码执行、图像生成/编辑、视频生成/分析、TTS、网页搜索等 [来源: 官方文档站, 2026-07; heyuan110.com, 2026-04-14]。
- 全面支持 **MCP（Model Context Protocol）**，可接入任意 MCP server（6,000+ 应用可达）；官方维护 Nous 批准的 MCP 目录与交互式选择器 [来源: GitHub README; heyuan110.com, 2026-04]。
- **Programmatic Tool Calling**：`execute_code` 让模型写 Python 脚本经 RPC 调用工具，将多步管线压缩为单次推理调用（官方称"零上下文成本轮次"）[来源: GitHub README, 2026-07]。
- 六种终端后端：local、Docker、SSH、Singularity、Modal、Daytona（后两者为 serverless 持久化，空闲休眠、按需唤醒）[来源: GitHub README, 2026-07]。

### 4.2 记忆系统（核心差异化）

三层记忆架构 [来源: aibuilderclub.com, 2026-06-02; heyuan110.com, 2026-04-14]：

| 层级 | 机制 | 内容 | 约束 |
|---|---|---|---|
| Tier 1 高信号状态 | USER.md + MEMORY.md | 用户画像、偏好、项目惯例 | 1,375 + 2,200 字符预算，每会话保证加载 |
| Tier 2 跨会话检索 | SQLite + FTS5 全文索引 + LLM 摘要 | 完整会话历史 | 无硬上限；v0.15.0 重写 session_search 后无需 LLM、提速 4,500 倍 |
| Tier 3 外部集成 | 可选 mem0 / 自定义向量库 | 外部知识 | 视供应商 |

另有：记忆工具原子批量操作（v0.17.0）、`/journey` 记忆时间线可视化与编辑、桌面端记忆图谱（radial timeline）（v0.18.0）[来源: GitHub Releases v0.17.0/v0.18.0]。

### 4.3 技能系统（程序性记忆 + 自改进）

- Agent 在复杂任务后**自动创建 skill**（Markdown 文件，存于 `~/.hermes/skills/`），使用中自我改进；`/learn <anything>` 可把目录/URL/刚演示过的工作流蒸馏成可复用 skill（v0.18.0）[来源: GitHub README; Releases v0.18.0]。
- Nous 内部基准宣称：积累 20+ 自建 skill 的 agent 完成同类任务快 40%（token 与墙钟时间均降 40%）——注意此为厂商宣称，第三方建议将自动生成的 skill 视为需人工审核的草稿 [来源: aibuilderclub.com, 2026-06-02，含其质疑意见]。
- 兼容 **agentskills.io 开放标准**；Skills Hub 社区市场（OpenAI、Anthropic、HuggingFace、NVIDIA 为默认可信源；第三方目录达 19,932 条目）；skill bundles 一键加载成组技能（v0.15.0）[来源: GitHub Releases v0.15.0/v0.16.0/v0.17.0]。

### 4.4 规划与多步执行

- `/goal`：跨轮锁定目标的 standing-goal 循环（Ralph loop 原语）；v0.18.0 增加 **completion contracts**（声明"完成"的证据标准，agent 通过实际运行项目检查来验证自身工作，而非自称完成）[来源: GitHub Releases v0.13.0/v0.18.0]。
- `delegate_task` 子代理：隔离子代理并行工作流；v0.17.0 起支持后台异步子代理，v0.18.0 支持**多子代理后台 fan-out**（结果汇总为单轮返回）；v0.9.0 时期曾有 3 个并发子代理上限（后期版本是否放宽，**待验证**）[来源: heyuan110.com, 2026-04; GitHub Releases v0.17.0/v0.18.0]。
- **Kanban 多代理看板**（v0.13 起，v0.15 扩展为完整多代理平台，104 个 PR）：任务自动分解为子任务树、swarm 拓扑（root + 并行 worker + 门控 verifier/synthesizer + 共享黑板）、每任务模型覆盖、worktree-per-task、定时启动、僵尸检测、幻觉恢复 [来源: GitHub Releases v0.13.0/v0.15.0]。
- **Cron 调度**：内建 cron，自然语言定义，结果投递到任意消息平台；Automation Blueprints 提供免语法表单化配置（v0.17.0）[来源: GitHub README; Releases v0.17.0]。

### 4.5 安全与防护

- 命令审批、DM 配对、容器隔离；redaction 默认开启（v0.13）；v0.15.0 落地 "Promptware defense"（防 Brainworm 类提示注入：工具输出/召回记忆/存储技能三处 chokepoint，约 15 个新模式）[来源: GitHub Releases v0.13.0/v0.15.0]。
- Bitwarden Secrets Manager 集成（一个 bootstrap token 替代所有 provider key，v0.15.0）；凭据剥离、SSRF 加固、Starlette CVE 修复等安全轮次 [来源: GitHub Releases v0.15.0/v0.16.0]。

---

## 5. 模型与推理

- **模型无关（model-agnostic）**：支持 Nous Portal、OpenRouter（200+ 模型）、NovitaAI、NVIDIA NIM、Xiaomi MiMo、z.ai/GLM、Kimi/Moonshot、MiniMax、Hugging Face、OpenAI、Anthropic、xAI（SuperGrok OAuth）、Google Vertex AI（服务账号 OAuth2 自动换 token）、GitHub Copilot、本地模型（Ollama/vLLM 自定义端点）；`hermes model` 一键切换 [来源: GitHub README, 2026-07; Releases v0.14.0/v0.18.0; aibuilderclub.com, 2026-06]。
- **Mixture-of-Agents（MoA）一等公民**（v0.18.0）：命名的多模型 ensemble 像普通模型一样可选，各参考模型完整推理分块展示，聚合答案流式输出 [来源: GitHub Releases v0.18.0]。
- 跨会话 1 小时 Claude prompt 缓存（v0.14.0）；Fast Mode 降低学习循环 token 开销（v0.9.0）；自改进后台审查改走辅助模型以降成本（v0.18.0）[来源: GitHub Releases v0.14.0/v0.18.0; heyuan110.com, 2026-04]。
- **研究定位**：批量轨迹生成、轨迹压缩、配合 Atropos 的 RL 训练，用于训练下一代工具调用模型（Nous 自家 Hermes 模型家族的飞轮）[来源: GitHub README, 2026-07]。
- 2026-04 注意点：Anthropic 封禁了第三方工具通过 Claude 订阅（Pro/Max）账号访问，需用按量付费 API key（影响成本模型）[来源: heyuan110.com, 2026-04-14]。

---

## 6. 部署形态

| 形态 | 说明 |
|---|---|
| **本地 CLI/TUI** | Linux、macOS、WSL2、原生 Windows（PowerShell 一键安装，内置便携 Git Bash）、Android/Termux；内存占用 <500MB（不含本地 LLM） |
| **桌面应用** | Electron，macOS/Linux/Windows，应用内自更新，可连远程网关 |
| **自托管服务器** | $5/月 VPS（Hetzner CX22 ~$4、DigitalOcean $5 等）即可 24/7 运行；Docker 官方镜像（amd64+arm64） |
| **Serverless 沙箱** | Daytona、Modal 后端，空闲休眠、按需唤醒，"闲时几乎零成本" |
| **云托管（SaaS 化）** | Nous Portal 一键云托管：Portal 代管你的 agent 全天候运行，服务器费用计入 credit 余额；v0.18.0 网关支持 scale-to-zero 与 drain 协调，面向团队/托管场景的生产化 |
| **Web Dashboard** | 浏览器管理面板，可远程访问 |

[来源: GitHub README 与 Releases v0.16.0/v0.18.0; portal.nousresearch.com, 2026-07 抓取; heyuan110.com, 2026-04]

---

## 7. 开源协议与社区规模

- **协议**: MIT（框架完全免费，无订阅费；用户仅支付所接 LLM 的 token 费用，或用 Ollama 本地模型做到 $0）[来源: GitHub README; aibuilderclub.com, 2026-06]。
- **社区规模**（不同来源口径略有出入，均列示）:
  - 175,000+ stars、390+ 贡献者（2026-06-02，aibuilderclub.com）；
  - 164,000 stars（2026-05，aurpay.net）；
  - 114K+ stars（2026-05-10，techjacksolutions 摘要）；
  - 社区版 Hermes WebUI 另有 11,500+ stars、140 贡献者（aibuilderclub.com, 2026-06）。
  - 单版本社区贡献者 170–370 人（v0.16.0: 170 人；v0.18.0: 370+ 人）[来源: GitHub Releases]。
- **生态**: 官方 Discord、Skills Hub、agentskills.io 开放标准、computer-use-linux MCP server、HermesClaw 微信桥等社区项目；Vercel Labs、Black Forest Labs、Anthropic 等发布过官方/第三方 skill 合集 [来源: GitHub README; hermesatlas.com, 2026-04-11]。

---

## 8. 商业模式与定价

### 8.1 模式：开源免费框架 + Nous Portal 订阅变现

框架本身 MIT 免费；变现通过 **Nous Portal**（模型目录 + Tool Gateway 托管工具 + 云托管的统一订阅）[来源: portal.nousresearch.com, 2026-07 抓取]：

| 档位 | 价格 | 内容 |
|---|---|---|
| Free | $0 | 仅免费模型，标准限速，$0 月度 credits（另一来源称含 $0.10 月度 credits，**口径不一致，待验证** [openclawlaunch.com, 2026-05-18]） |
| Plus | $20/月 | $22 月度 credits（10% 赠送），$10 结转上限，数百模型 + 托管工具 + 高速率 |
| Super | $100/月 | $110 credits，$50 结转上限 |
| Ultra | $200/月 | $220 credits，$100 结转上限 |

- Portal 模型目录 200+ 个（涵盖 Anthropic、OpenAI、Google、DeepSeek、Qwen、Kimi、xAI、Z.ai 等，按量计价，如 Claude Opus 4.8 in $5/out $25 每 1M tokens）[来源: portal.nousresearch.com, 2026-07]。
- **Tool Gateway**：web 搜索（Firecrawl）、图像生成（FAL/Krea）、TTS（OpenAI）、云浏览器（Browser Use）按次计费，与模型共用 credit 余额 [来源: portal.nousresearch.com; GitHub README]。
- **云托管**：一键部署，服务器费用计入 credit 余额 [来源: portal.nousresearch.com, 2026-07]。

### 8.2 用户实际成本参考

- 自托管 + 本地模型：仅硬件成本（$5/月 VPS 或自有 GPU），API 成本可为 $0。
- 典型 token 消耗：CLI 模式约 6,000–8,000 tokens/轮；自改进循环带来额外 token 开销（v0.18.0 已针对性降本）[来源: techjacksolutions.com 成本分析, 2026-07-03，经搜索摘要引用，**待二次验证**]。

---

## 9. 最新版本动态（截至 2026-07-19）

| 版本 | 日期 | 要点 |
|---|---|---|
| v0.18.2 (2026.7.7.2) | 2026-07-07 | WhatsApp Baileys 依赖修复补丁 |
| v0.18.1 (2026.7.7) | 2026-07-07 | 滚动 660+ PR 的稳定标签（Windows 安装器自愈、dashboard/网关修复等） |
| **v0.18.0 "The Judgment Release"** | 2026-07-01 | 全仓 P0/P1 清零（~700 项最高优先级问题）；MoA 一等公民；agent 自我验证（证据驱动"完成"）；/goal completion contracts；/learn、/journey；子代理后台 fan-out；桌面端 Projects 编码工作台；网关 scale-to-zero/drain；Vertex AI provider |
| v0.17.0 | 2026-06-19 | iMessage（Photon）、Raft agent 网络、桌面应用大幅增强、后台子代理、图像编辑、Automation Blueprints、Skills Hub 改版、记忆原子批量操作 |
| v0.16.0 "Surface Release" | 2026-06-05 | Electron 桌面应用首发；Web Dashboard 成为完整管理面板；简体中文全量翻译；Nous Portal 快速设置 |

[来源: GitHub Releases, 2026-07 抓取]

---

## 10. 对 X-Agent 的启示（简要）

1. **记忆与自改进是最强差异化**：三层记忆（保证加载的高信号文件 + FTS5 检索 + 外部集成）+ 自动创建/自改进 skill 构成闭环，是 Hermes 增长飞轮的核心，X-Agent 若仅有会话记忆将明显落后。
2. **"证据驱动完成"是 2026 年下半场新标杆**：v0.18.0 的 completion contracts / 自我验证代表从"agent 自称完成"到"agent 证明完成"的范式转移。
3. **渠道广度即护城河**：20+ 消息平台网关 + 桌面 + Web + CLI 全表面覆盖，配合 OpenClaw 迁移工具（`hermes claw migrate`）直接挖竞品用户。
4. **商业化路径清晰**：MIT 框架获客 → Nous Portal（模型聚合 + 工具网关 + 云托管）变现，$20/$100/$200 三档 + credits 机制值得参考。
5. **高频发布与社区运营**：双周 minor 版本、单版本数百社区贡献者、公开 P0/P1 清零运动，是其社区热度的重要来源。

---

## 要点摘要（Executive Summary）

1. **指向确认**: 2026 年 "Hermes Agent" 即 Nous Research 2026-02-25 发布的开源自主 agent 框架（MIT，GitHub `NousResearch/hermes-agent`），4 个月内 17.5 万 stars，OpenRouter 日 token 榜曾登顶。
2. **核心架构**: Python 自改进运行时，"闭环学习循环"覆盖指令/约束/反馈/记忆/编排五层 harness；核心 loop 已从 1.6 万行单文件重构为 14 个模块。
3. **杀手级能力**: 三层记忆（FTS5 + 保证加载）+ 自动生成/自改进 skill（官方宣称提速 40%）+ cron 调度 + 20+ 消息平台 + Kanban 多代理 swarm + 子代理后台 fan-out。
4. **最新进展**: v0.18.0（2026-07-01）实现 P0/P1 清零、MoA 一等公民、证据驱动的自我验证（completion contracts）、/learn、/journey 记忆可视化；最新补丁 v0.18.2（2026-07-07）。
5. **部署**: 本地（含原生 Windows/Termux）、$5 VPS、Docker、Daytona/Modal serverless 沙箱、Nous Portal 云托管（scale-to-zero）。
6. **商业模式**: 框架 MIT 免费；Nous Portal 订阅 $0/$20/$100/$200 四档，credits 覆盖 200+ 模型 + 托管工具 + 云托管，是自托管开源框架 SaaS 变现的样本。
7. **风险/存疑点**: 自动生成的 skill 需人工审核（第三方共识）；厂商 40% 提速宣称未经独立验证；个别数据（OpenRouter 排名、Free 档 credits）来自搜索摘要，已标注待验证。
