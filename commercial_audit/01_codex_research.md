# OpenAI Codex 竞品调研报告（截至 2026 年中）

> **角色标签**：Codex竞品研究员
> **任务范围**：联网调研 OpenAI Codex 产品线截至 2026 年 7 月的最新功能与商业化状态，覆盖云端 Agent、CLI、IDE 扩展、SDK、Slack/GitHub 集成、代码审查、AGENTS.md 机制、定价档位、GA 状态、近 12 个月重大里程碑，并提炼 Codex 作为"完整商用交付"产品的能力全景图。
> **调研日期**：2026-07-19
> **调研方式**：WebSearch + FetchURL，优先采用 OpenAI 官方博客/文档，辅以第三方评测与开发者社区信息；每条关键事实附来源与日期，无法独立验证的内容明确标注"待验证/不确定"。

---

## 0. 一句话结论

Codex 已从 2025 年 5 月的"云端编码 Agent 研究预览"演变为 OpenAI 的**多界面、多模型、企业级 Agent 平台**：覆盖 CLI / IDE / 桌面 / Web / 移动端 / Slack / GitHub 七大入口，拥有专用编码模型线（GPT-5-Codex → GPT-5.6 Sol/Terra/Luna）、开源 CLI（Apache-2.0）、云端并行沙箱、SDK 与 GitHub Action 可编程接入、企业级治理与分析面板，并于 2025-10-06 宣布 GA、2026-05 被 Gartner 评为企业级 AI 编码 Agent 魔力象限领导者。2026-07-09，独立 Codex 桌面应用并入新版 ChatGPT 桌面客户端（Chat / Work / Codex 三模式），Codex 正从"编码工具"升级为 ChatGPT 超级应用中的"工作执行层"。

---

## 1. 产品定位与形态总览

Codex 当前由 **3+3 个产品面** 组成（官方仓库 README 口径）：

| 产品面 | 形态 | 入口 |
|---|---|---|
| Codex CLI | 开源终端 Agent（Rust 实现，Apache-2.0） | `codex` 命令 / npm `@openai/codex` |
| Codex IDE 扩展 | VS Code、Cursor、Windsurf 等 VS Code 系 fork；2026 年扩展至 JetBrains | IDE 市场 |
| Codex Cloud（Web） | 云端异步 Agent，chatgpt.com/codex | 浏览器 |
| 桌面端 | 原独立 Codex App（2026-02-02 macOS、2026-03-04 Windows），2026-07-09 起并入 ChatGPT 桌面客户端成为 "Codex 模式" | 桌面 |
| 移动端 | ChatGPT iOS App 内使用 Codex | iOS |
| 集成面 | Slack（@Codex）、GitHub（代码审查 + Action）、Linear、MCP、90+ 插件 | 第三方 |

来源：[openai/codex GitHub README](https://github.com/openai/codex)（2026-07 抓取）；[OpenAI 官方博客 "Introducing upgrades to Codex"](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）；[StoryForge 安装指南](https://www.octolinkzl.com/articles/openai_codex_2026_updated_installation_guide_for_desktop)（2026-07-13）；[iconpolls Codex Review](https://iconpolls.com/blogs/openai-codex-review-2026-login-pricing-download-documentation-user-experience-and-faqs)（2026）。

---

## 2. Codex 云端 Agent（Codex Cloud）

### 2.1 任务并行与环境隔离
- 每个云端任务运行在**独立的云沙箱**中：预加载用户 GitHub 仓库副本，任务之间完全隔离，可**并行发起多个任务**，各自产出 diff / PR。[OpenAI Codex 发布博客](https://openai.com/index/introducing-codex/)（2025-05，经 kingy.ai 引用）；[MyEngineerPath Codex Guide](https://myengineeringpath.dev/tools/openai-codex/)（2026-03-20）。
- 云端基础设施通过**容器缓存**将新任务与后续任务的中位完成时间降低约 90%；Codex 可自动扫描常见 setup 脚本完成环境自举。[OpenAI "Introducing upgrades to Codex"](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 缓存环境最长保留约 12 小时（文档口径；社区有缓存未复用的 bug 报告）。[GitHub openai/codex issue #25086](https://github.com/openai/codex/issues/25086)（2026-05-29）。

### 2.2 网络访问控制
- **默认沙箱内禁用网络访问**（本地与云端一致），用于防止数据外泄与提示注入；云端可将网络访问限定为**可信域名白名单**，开启后允许 `pip install` 等运行时依赖安装。[OpenAI "Introducing upgrades to Codex"](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 企业治理实践：secrets 仅在 setup 阶段注入，Agent 阶段仅使用普通环境变量；管理员可编辑/删除云端环境。[AI-Coding-Guide-Zh Codex 安全企业指南](https://github.com/KimYx0207/AI-Coding-Guide-Zh/blob/main/docs/codex/CX-13-Codex%E5%AE%89%E5%85%A8%E4%BC%81%E4%B8%9A%E5%AE%8C%E6%95%B4%E6%8C%87%E5%8D%97.md)（2026-05-30）；[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）。

### 2.3 前端/视觉验证能力
- 云端任务可接收图片/截图输入，Agent 能自行启动浏览器查看所构建的页面、迭代并将结果截图附到任务与 GitHub PR 上。[OpenAI "Introducing upgrades to Codex"](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。

---

## 3. Codex CLI（开源终端 Agent）

### 3.1 开源情况
- 仓库 [github.com/openai/codex](https://github.com/openai/codex)，**Apache-2.0 许可证**，Rust 重写（最初 2025-04 发布时为 TypeScript，后迁移至 Rust 以获得性能与低内存占用）。[GitHub README](https://github.com/openai/codex)（2026-07 抓取）；[noxcod Codex 工具页](https://www.noxcod.com/outils-ia/openai-codex)（2026）。
- GitHub Stars：约 62K+（2026-03，[MorphLLM 对比页](https://www.morphllm.com/comparisons/codex-vs-copilot)）；约 85K（2026-05，[Codersera 工程对比](https://codersera.com/blog/claude-code-vs-openai-codex-2026/)）。口径不一，数量级可信。
- 版本节奏：滚动高频发布，2026-07-18 已至 `codex-cli 0.144.6`。[Toolsbase Codex 命令手册](https://toolsbase.dev/en/reference/codex-commands)（2026-07-19）。

### 3.2 核心功能（2026 年中状态）
- **三级审批模式**：只读（逐条批准）/ auto（工作区内自由、工作区外需批准）/ full access（全文件 + 网络）。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 图片输入（截图/线框图）、内置 to-do list、web search 工具、MCP 客户端、会话压缩（compaction）、TUI 全屏界面、`codex exec` 无头模式（CI 脚本化）。[同上 OpenAI 博客；techjacksolutions CLI 指南](https://techjacksolutions.com/ai-tools/openai-codex/openai-codex-cli-guide/)（2026-07-02）。
- **2026 年新增**：原生 subagents（独立上下文窗口的子 Agent 原语）、hooks、auto-review、Goal Mode（`/goal`，见 §9）、Skills 体系（`.agents/skills/` + SKILL.md，渐进式加载，`$skill-name` 显式调用）、Memory、Automations（定时任务）、computer use（桌面端）、云端任务下发（`codex cloud`，长任务移交 Cloud 后台执行）。[CodeGateway Codex CLI 完全指南](https://www.codegateway.dev/en/blog/openai-codex-cli-complete-guide-2026)（2026-05-16）；[Agent Shelf](https://www.agentshelf.dev/blog/best-agents-for-codex)（2026-04-10）；[ChatForest 评测](https://chatforest.com/reviews/openai-codex-cloud-agentic-coding-platform-review/)（2026-05-24）。
- 安装渠道：curl/PowerShell 官方脚本、npm、Homebrew、GitHub Release 二进制（macOS arm64/x64、Linux musl x64/arm64、Windows）。[GitHub README](https://github.com/openai/codex)。
- 认证双轨：ChatGPT 账号登录（随订阅计费）或 API key（按 token 计费）；支持 `config.toml` 自定义 provider（任意 Responses 兼容端点）。[MorphLLM Codex Pricing](https://www.morphllm.com/codex-pricing)（2026-07-13）。

---

## 4. IDE 扩展

- 2025-09-15 随 GPT-5-Codex 一同发布，支持 **VS Code、Cursor 及其他 VS Code fork**；可利用已打开文件/选中代码作为上下文，支持本地改动预览、云端任务创建/跟踪/回顾、云端任务拉回本地续作（上下文不丢失）。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 2026 年已扩展至 **JetBrains**（Goal Mode 稳定性公告覆盖 "VS Code and JetBrains extensions"）。[ToolNav](https://toolnav.io/news/2026-05-25-openai-codex-goal-mode-appshots-stable/)（2026-05-25）；[Codersera 对比表](https://codersera.com/blog/claude-code-vs-openai-codex-2026/)（2026-05-26）。

---

## 5. Codex SDK 与 API 可编程接入

- **Codex SDK**（2025-10-06 GA 时发布）：首发 TypeScript（`@openai/codex-sdk`，Node 18+），本质是**对 Codex CLI 的进程封装**——spawn CLI 并通过 stdin/stdout 交换 JSONL 事件；提供 Thread/Turn 抽象、结构化输出、会话恢复（`resumeThread`）、流式事件（`runStreamed`）。[npm @openai/codex-sdk](https://www.npmjs.com/package/@openai/codex-sdk?activeTab=code)（2026-07-09 抓取）；[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；社区批评其"只是 wrapper"：[stackademic](https://blog.stackademic.com/openai-codex-sdk-for-creating-our-own-codex-agent-bee5ad08fe57)（2025-11-05）。
- **Python SDK（beta）**：`pip install openai-codex`，Python 3.10+。[SegmentFault Codex 进阶教程](https://segmentfault.com/a/1190000048024163)（2026-07-14）。
- **Native SDK**：`@codex-native/sdk`（napi-rs Rust 绑定，免子进程、支持自定义工具注册），2026-01 起可用。[Socket 包分析](https://socket.dev/npm/package/@codex-native/sdk)（2026-01-16）。
- **GitHub Action**：`openai/codex-action`，约 10 行 YAML 接入 CI，做 PR 自动审查与 CI 失败修复（runner 内安装 CLI、headless 执行 `codex exec`）。[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；[byteiota](https://byteiota.com/codex-github-action-ci-pipeline/)（2026-07-06）。
- **API 直用**：GPT-5-Codex 自 2025-09-23 起经 Responses API 开放（与 GPT-5 同价）；后续 Codex 系模型均逐步进入 API。[OpenAI 升级博客 Update](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-23）。
- 编排建议：若 Codex 只是更大工作流中的一环，官方推荐"将 Codex CLI 作为 MCP server 运行 + 用 Agents SDK 编排"。[OpenAI Codex 中文文档](https://www.codex-docs.com/docs/codex-sdk)（2026-07-07）。

---

## 6. 集成生态

- **Slack**：频道/线程中 @Codex，自动从对话收集上下文、选择云端环境、返回任务链接；结果可合并、迭代或拉回本地。[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；[gihyo.jp](https://gihyo.jp/article/2025/10/codex-ga)（2025-10-07）。
- **GitHub**：原生集成——PR 自动代码审查（见 §7）、@codex 提及触发、`openai/codex-action` CI/CD 集成、云端任务直接开 PR。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- **Linear**：Business 及以上档位集成。[MorphLLM Codex Pricing](https://www.morphllm.com/codex-pricing)（2026-07-13）。
- **移动端**：ChatGPT iOS App 内使用 Codex（2025-09 起）。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- **插件/应用生态**：2026-04-16 "Codex for (almost) everything" 更新带来 90+ 插件、应用内浏览器、图像生成、Memory 预览、扩展 Automations；2026-06-02 ZoomInfo GTM.AI 以原生应用（MCP）进入 "Codex for Work"，显示其向非编码知识工作扩张。[buildfastwithai](https://www.buildfastwithai.com/blogs/openai-codex-for-almost-everything-2026)（2026-04-20）；[VentureBeat](https://venturebeat.com/business/openai-announces-native-availability-of-zoominfos-gtm-context-graph-gtmai-in-codex-for-work)（2026-06-02）。
- **MCP**：CLI/IDE 均支持 MCP server 连接（2025-09 起），2026-07 起 MCP 工具可交互式请求 OAuth 认证。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）；[Toolsbase 版本摘要](https://toolsbase.dev/en/reference/codex-commands)（2026-07-19）。

---

## 7. 代码审查能力（Code Review）

- 2025-09-15 上线：针对 GitHub 仓库开启后，PR 从 draft 转为 ready 时**自动审查**并在 PR 上发布分析；可 `@codex review` 显式触发，支持附加指令（如 "review for security vulnerabilities"）；审查建议可让 Codex 直接实施修复。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 技术路线：非静态分析——匹配 PR 声明意图与实际 diff、在全代码库与依赖上推理、**实际运行代码与测试验证行为**（"写代码来验证自己的假设"）。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）；[TeamDay.ai](https://www.teamday.ai/ai/openai-codex-code-review-feature)（2025-11-04）。
- 采用数据：OpenAI 内部 Codex 审查"绝大多数 PR"，每天捕获数百问题；Cisco 代码审查提速最高 50%。[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）。

---

## 8. AGENTS.md 机制

- **仓库级指令文件**：置于 repo 根目录（或子目录），Codex 启动时读取，承载项目约定、测试策略、安全边界、提交规范等；GPT-5-Codex 训练时专门强化了对 AGENTS.md 指令的遵循度。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）。
- 发现机制：从当前工作目录向上扫描至仓库根；另有用户级全局配置（`~/.codex/`）。生态上 AGENTS.md 已成为跨工具开放约定（Claude Code 用 CLAUDE.md、Codex 用 AGENTS.md；第三方 skills 目录 `.agents/skills/` 也被 Cursor、Copilot 等兼容）。[Agent Shelf](https://www.agentshelf.dev/blog/best-agents-for-codex)（2026-04-10）；[Codersera 对比表](https://codersera.com/blog/claude-code-vs-openai-codex-2026/)（2026-05-26）；[oflight AGENTS.md 指南](https://www.oflight.co.jp/en/columns/openai-codex-agents-md-custom-config-guide-2026)（2026-04-07）。

---

## 9. 自主性与长任务：Goal Mode、Computer Use、Automations

- **Goal Mode（/goal）**：2026-05-21/22 由实验转正式（stable/GA），覆盖 Codex App、IDE 扩展、CLI（v0.128+）。用户设定目标（迁移目标、覆盖率阈值、性能基准），Agent 跨会话中断/token 预算重置持续工作数小时至数天。[OpenAI Developers 推文转引, Grenade](https://grenade.tw/blog/codex-goal-openai/)（2026-06-07）；[ToolNav](https://toolnav.io/news/2026-05-25-openai-codex-goal-mode-appshots-stable/)（2026-05-25）。
- **Appshots**：macOS 一键屏幕上下文注入（2026-05-22）。[ToolNav](https://toolnav.io/news/2026-05-25-openai-codex-goal-mode-appshots-stable/)（2026-05-25）。
- **Locked Computer Use**：Mac 锁屏后 Computer Use 任务继续执行（2026-05-22）；Computer Use 本体于 2026-04-16 上线（首发仅 macOS，EU/UK/瑞士除外）。[Devlery](https://devlery.com/en/blog/codex-goal-mode-locked-mac)（2026-05-28）；[buildfastwithai](https://www.buildfastwithai.com/blogs/openai-codex-for-almost-everything-2026)（2026-04-20）。
- **长任务耐力**：GPT-5-Codex 测试中可独立工作 7 小时以上；GPT-5.1-Codex-Max 借 compaction 机制可连续工作 24 小时以上、跨数百万 token 保持上下文。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）；[itecsonline](https://itecsonline.com/post/chatgpt-5-1-codex-max)（2025-11-21）。

---

## 10. 模型演进线（Codex 专用模型）

| 时间 | 模型 | 要点 |
|---|---|---|
| 2025-09-15 | GPT-5-Codex | 首个 Codex 专用模型；动态思考时长；代码审查专训；9-23 进 API。[OpenAI](https://openai.com/index/introducing-upgrades-to-codex/) |
| 2025-11-19 | GPT-5.1-Codex-Max | compaction 长任务（24h+）；SWE-bench Verified 77.9%；首个原生支持 Windows 环境训练的 OpenAI 编码模型；思考 token 降 30%。[itecsonline](https://itecsonline.com/post/chatgpt-5-1-codex-max)（2025-11-21） |
| 2025-12-11 | GPT-5.2-Codex | 随 GPT-5.2 发布，强调 agentic coding 与网络安全。[Ster Software](https://stersoftware.com/news/openai-releases-gpt-52/)（2025-12） |
| 2026-02-05 | GPT-5.3-Codex | SWE-Bench Pro 57%、Terminal-Bench 2.0 77.3%、OSWorld 64%；任务中途可引导（mid-task steering）；同任务 token 消耗不足 5.2 一半、单 token 提速 25%+；基于 NVIDIA GB200 NVL72 训练。另有快速变体 gpt-5.3-codex-spark。[Kompas 转引 Sam Altman](https://tekno.kompas.com/read/2026/02/06/09020037/openai-rilis-gpt-5.3-codex-model-ai-canggih-yang-ngoding-dirinya-sendiri)（2026-02-06） |
| 2026-03 | GPT-5.4 | 通用模型，进入 Codex 模型选择器。[WebCraft Studio](https://webscraft.org/blog/gpt55-v-codex-scho-zminilos-dlya-rozrobnikiv-u-2026?lang=en)（2026-05-10） |
| 2026-04-23 | GPT-5.5（代号 Spud） | Codex 默认模型（5 月底切换）；Terminal-Bench 2.0 82.7%、SWE-Bench Pro 58.6%；API $5/$30/1M tokens；API 上下文 1M，Codex 面 400K。[QCode](https://qcode.cc/en/codex-gpt-5-5-goal-mode-guide)（2026-05-29）；[WebCraft](https://webscraft.org/blog/gpt55-v-codex-scho-zminilos-dlya-rozrobnikiv-u-2026?lang=en)（2026-05-10）；[fernando-nog 成本分析](https://fernando-nog.netlify.app/gpt-coding-model-costs-2026/) |
| 2026-06-25 预览 / 2026-07-09 GA | GPT-5.6（Sol / Terra / Luna 三档） | Sol 旗舰 $5/$30、Terra 默认 $2.50/$15、Luna 高量低价 $1/$6（每 1M tokens）；上下文 272K tokens；随 ChatGPT/Codex/API 同步 GA。[MorphLLM](https://www.morphllm.com/codex-pricing)（2026-07-13）；[Toolsbase](https://toolsbase.dev/en/reference/codex-commands)（2026-07-19）；[simplemetrics](https://simplemetrics.xyz/chatgpt-codex-limits-2026/)（2026-07-12） |

注：GPT-5.5 的 SWE-bench Verified 88.7% 一说来自 [AdsX](https://www.adsx.com/blog/openai-codex-goal-mode-shopify-merchants)（2026-06-20），未见官方页面佐证，**待验证**。

---

## 11. 定价与额度（2026-07 现状）

### 11.1 档位（无独立 Codex 订阅，全部并入 ChatGPT 套餐）

| 档位 | 价格 | Codex 要点 |
|---|---|---|
| Free | $0 | 有限额度，Web + CLI；促销期加成已结束 |
| Go | $8/月 | Web + CLI，比 Free 高 |
| Plus | $20/月 | Web/CLI/IDE/iOS；5 小时窗口约 15–90 条（GPT-5.6 Sol）/ 20–110（Terra）/ 50–280（Luna）；可购 credit 加油包 |
| Pro | $100/月起 | 5x（$100）或 20x（$200）Plus 窗口额度 |
| Business | $20/人/月（年付，月付 $25） | 云功能 + GitHub/Slack/Linear 集成 + 管理控制；单席位额度等同 Plus |
| Enterprise / Edu | 定制 | 共享 credit 池、无固定速率上限、专属支持 |

来源：[MorphLLM Codex Pricing](https://www.morphllm.com/codex-pricing)（2026-07-13）；[Layer3 Labs](https://www.layer3labs.io/guides/openai-codex-pricing)（2026-07-17）；[AI Agent Square](https://aiagentsquare.com/agents/openai-codex)（2026-07-04）。

### 11.2 计量机制（2026-04 起由"按消息数"改为"按 token 折 credit"）
- 双重限速：5 小时滚动窗口 + 每周上限；credit 约 $0.04/个，与 API token 价一一对应（Sol 输入 125 credits/1M、输出 750/1M；输出按输入 6 倍计）。[MorphLLM](https://www.morphllm.com/codex-pricing)（2026-07-13）。
- 典型会话 API 等效成本 $0.50–$2.00。[同上]
- 2026-06-11 起提供一次性 "rate-limit reset banking"；2026-06-24 起 Business 新客不再提供按量付费席位。[同上]
- **API key 路径**：无窗口限制、按 token 计费（gpt-5.6-luna $1/$6 等），但失去云功能与集成。[同上]
- 2025-11 曾发生 credits bug 事故（8 次查询耗尽 5 小时配额），OpenAI 向受影响用户补偿 $200 credits。[MorphLLM 定价历史](https://www.morphllm.com/codex-pricing)（2026-07-13）。

---

## 12. GA 与商业化状态

- **GA**：2025-10-06（DevDay 2025）宣布 Codex 正式 GA，同步发布 Slack 集成、Codex SDK、管理员工具。[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；[WinBuzzer](https://winbuzzer.com/2025/10/07/openais-codex-graduates-to-general-availability-with-new-slack-integration-and-developer-sdk-xcxwbn/)（2025-10-07）。
- **采用度**：GA 时日使用量较 2025-08 增长 10 倍；GPT-5-Codex 发布三周内处理 40 万亿 tokens；客户含 Cisco、Rakuten、Duolingo、Vanta、Instacart、Virgin Atlantic 等。[OpenAI GA 博客](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；[develeap 转引 OpenAI 博客](https://www.develeap.com/news/openai-s-gpt-5-5-and-codex-reach-general-availability-on-ama-e7fd5573/)（2026-06-11，页面 403，仅引用其摘要，**部分待验证**）。
- **行业认可**：2026-05-22 OpenAI 获评 Gartner 2026 企业级 AI 编码 Agent 魔力象限领导者。[develeap 转引 OpenAI 博客](https://www.develeap.com/news/openai-s-gpt-5-5-and-codex-reach-general-availability-on-ama-e7fd5573/)（2026-06-11）——该转引源可信度中等，**建议二次核验**。
- **第三方评分**：Standard Compute 编辑评分 8.2/10（输出质量 9.0、自主性 8.5、可靠性 8.0、性价比 7.5）（2026-07-12）。[Standard Compute Codex CLI Review](https://standardcompute.com/best-ai-agent/codex-cli)。
- **已知短板**（第三方汇总）：速率限制对重度用户不友好；模型选择不透明；复杂架构推理上仍被认为略逊 Claude Code；无 Linux 桌面端；移动端仅预览。[AIUnpacking](https://aiunpacking.com/review/openai-codex/)（2026-05-15）。

---

## 13. 近 12 个月重大更新里程碑（2025-07 → 2026-07）

| 日期 | 事件 |
|---|---|
| 2025-08 | Codex 统一为单一产品体验（ChatGPT 账号打通本地与云端）。[OpenAI 升级博客](https://openai.com/index/introducing-upgrades-to-codex/) |
| 2025-09-15 | GPT-5-Codex + IDE 扩展 + Code Review + CLI 重构（图像输入、todo、MCP、三级审批）。[OpenAI](https://openai.com/index/introducing-upgrades-to-codex/) |
| 2025-09-23 | GPT-5-Codex 进入 Responses API。[OpenAI](https://openai.com/index/introducing-upgrades-to-codex/) |
| 2025-10-06 | **Codex GA**；Slack 集成、Codex SDK（TS）、管理员工具、GitHub Action。[OpenAI](https://openai.com/index/codex-now-generally-available/) |
| 2025-10-20 | 云端任务开始计入套餐用量。[DataQuest](https://www.dqindia.com/data-and-ai/openais-codex-coding-agent-hits-general-availability-with-new-tools-10536361)（2025-10-07） |
| 2025-11-19 | GPT-5.1-Codex-Max（compaction，24h+ 长任务）。[itecsonline](https://itecsonline.com/post/chatgpt-5-1-codex-max) |
| 2025-11 | credits 计量 bug 事故，补偿 $200/人。[MorphLLM](https://www.morphllm.com/codex-pricing) |
| 2025-12-11 | GPT-5.2 / GPT-5.2-Codex。[Ster Software](https://stersoftware.com/news/openai-releases-gpt-52/) |
| 2026-02-02 | **Codex 桌面应用（macOS）**：多 Agent 并行、worktree、技能、Automations、审查队列。[vibecoding.app 评测](https://vibecoding.app/blog/openai-codex-app-review)（2026-06-17）；[iconpolls](https://iconpolls.com/blogs/openai-codex-review-2026-login-pricing-download-documentation-user-experience-and-faqs) |
| 2026-02-05 | GPT-5.3-Codex（mid-task steering，GB200 NVL72）。[Kompas](https://tekno.kompas.com/read/2026/02/06/09020037/openai-rilis-gpt-5.3-codex-model-ai-canggih-yang-ngoding-dirinya-sendiri) |
| 2026-02 | 限时向 Free/Go 开放 Codex（促销）。[iconpolls](https://iconpolls.com/blogs/openai-codex-review-2026-login-pricing-download-documentation-user-experience-and-faqs) |
| 2026-03-04 | 桌面应用支持 Windows。[iconpolls](https://iconpolls.com/blogs/openai-codex-review-2026-login-pricing-download-documentation-user-experience-and-faqs) |
| 2026-03 | 媒体报道 OpenAI 确认将 ChatGPT + Codex + Atlas 合并为统一桌面 "SuperApp"。[digitalstrategy-ai](https://digitalstrategy-ai.com/2026/04/14/exploring-openai-codex-features/)（2026-04-14）——单一二手来源，**待验证** |
| 2026-04-16 | "Codex for (almost) everything"：Computer Use、应用内浏览器、图像生成、Memory 预览、90+ 插件、扩展 Automations。[buildfastwithai](https://www.buildfastwithai.com/blogs/openai-codex-for-almost-everything-2026) |
| 2026-04-23 | GPT-5.5 发布（后于 5 月底成为 Codex 默认）。[WebCraft](https://webscraft.org/blog/gpt55-v-codex-scho-zminilos-dlya-rozrobnikiv-u-2026?lang=en)；[AdsX](https://www.adsx.com/blog/openai-codex-goal-mode-shopify-merchants) |
| 2026-04 | 定价从按消息改为 token-credit 制；Pro 重构为 $100(5x)/$200(20x)。[MorphLLM](https://www.morphllm.com/codex-pricing) |
| 2026-05-21/22 | Goal Mode 转正式；Appshots；Locked Computer Use；管理员分析面板。[ToolNav](https://toolnav.io/news/2026-05-25-openai-codex-goal-mode-appshots-stable/)；[Devlery](https://devlery.com/en/blog/codex-goal-mode-locked-mac) |
| 2026-05-22 | Gartner 企业级 AI 编码 Agent MQ 领导者（转引，**建议二次核验**）。[develeap](https://www.develeap.com/news/openai-s-gpt-5-5-and-codex-reach-general-availability-on-ama-e7fd5573/) |
| 2026-06-02 | ZoomInfo GTM.AI 原生进入 "Codex for Work"，向 GTM/知识工作扩张。[VentureBeat](https://venturebeat.com/business/openai-announces-native-availability-of-zoominfos-gtm-context-graph-gtmai-in-codex-for-work) |
| 2026-06-24 | Business 新客停用按量付费席位。[MorphLLM](https://www.morphllm.com/codex-pricing) |
| 2026-06-25 | GPT-5.6 预览。[MorphLLM](https://www.morphllm.com/codex-pricing) |
| 2026-07-09 | **GPT-5.6 GA（Sol/Terra/Luna）**；**独立 Codex 桌面应用并入新版 ChatGPT 桌面客户端**（Chat/Work/Codex 三模式，macOS+Windows）；CLI/IDE 扩展/Codex Cloud 不受影响。[MorphLLM](https://www.morphllm.com/codex-pricing)；[StoryForge](https://www.octolinkzl.com/articles/openai_codex_2026_updated_installation_guide_for_desktop)（2026-07-13）；[AIToolHunt](https://aitoolhunt.co/blog/chatgpt-codex-merge-2026)（2026-07-10）；[Coursiv](https://coursiv.io/blog/codex-merged-with-chatgpt-app)（2026-07-10） |

---

## 14. Codex 作为"完整商用交付"产品的能力全景图

将 Codex 拆解为一个商用 Agent 产品所需的能力域，供 X-Agent 对标：

1. **多界面交付**：CLI（开源）+ IDE（VS Code/JetBrains）+ 桌面（已并入 ChatGPT 客户端）+ Web + iOS 移动端 + Slack 聊天入口 —— 用户在任何工作环境都能触达同一个 Agent，且上下文跨界面连续。
2. **双执行模式**：本地沙箱执行（三级审批、用户在场）与云端异步执行（隔离 VM、并行任务、PR 产出）并存，可互相移交（CLI→Cloud、Cloud→本地）。
3. **安全与网络治理**：默认断网沙箱、域名白名单、secrets 分阶段注入、危险命令检测（0.144.5 强化）、管理员环境管控。
4. **自主性阶梯**：单轮任务 → todo 跟踪 → subagents 并行 → Goal Mode（数小时~数天、跨中断续跑）→ Automations（定时触发）。
5. **专用模型线**：按任务复杂度分层的模型家族（Sol/Terra/Luna 或旗舰/标准/轻量），Codex 专用训练（AGENTS.md 遵循、代码审查专训、mid-task steering、compaction 长上下文）。
6. **项目级知识机制**：AGENTS.md（仓库指令）+ Skills（SKILL.md 渐进加载）+ Memory（跨会话）——三层次的 Agent 行为定制。
7. **质量验证闭环**：代码审查 Agent（全库推理 + 真实运行测试）、前端截图自验证、任务产出附引用/日志/测试结果。
8. **可编程性**：TS/Python SDK + CLI headless + GitHub Action + MCP（双向：CLI 作 MCP server）+ 自定义 provider。
9. **团队协作与集成**：Slack/GitHub/Linear 原生集成、共享配额、工作区管理。
10. **企业治理**：管理员控制台（环境编辑/删除、托管配置覆盖）、用量与审查质量分析仪表盘、Enterprise 共享 credit 池、合规策略（如 `remote_computer_use=false`）。
11. **商业化包装**：Free→Go→Plus→Pro(5x/20x)→Business→Enterprise 六级阶梯；token-credit 计量 + 双窗口限速 + 加油包；API 按量并行存在；促销（Free/Go 限时开放）拉新。
12. **生态与平台化**：90+ 插件、Skills 开放目录规范、第三方原生应用（ZoomInfo）、并入 ChatGPT 超级应用成为"工作执行层"。

---

## 15. 要点摘要（供主审计引用）

1. **Codex 已 GA 且全面商用**（2025-10-06 GA），并形成 CLI/IDE/桌面/Web/移动/Slack/GitHub 七界面 + 云/本地双执行的完整产品矩阵；2026-07-09 起桌面端并入 ChatGPT 客户端，战略定位从编码工具升级为超级应用内的"执行层"。
2. **云端 Agent 的工程壁垒**在并行隔离沙箱、默认断网+域名白名单、容器缓存（中位完成时间 -90%）、secrets 分阶段治理——这是 X-Agent "云沙箱"直接对标的维度。
3. **自主性已产品化为三级阶梯**：subagents（并行）→ Goal Mode（2026-05 GA，数小时~数天跨中断执行）→ Automations（定时），并辅以 Memory 与 Skills；长任务能力（compaction，24h+）自 GPT-5.1-Codex-Max 起成为核心卖点。
4. **代码审查是独立杀手级功能**：全库推理 + 真实运行测试验证，OpenAI 内部近乎全量 PR 覆盖，Cisco 审查提速 50%；审查质量本身被做成企业分析指标。
5. **开源策略**：CLI Apache-2.0 开源（~85K stars）建立生态与标准（AGENTS.md、`.agents/skills/`），但模型、云执行与治理闭源收费——"开源入口 + 云端变现"的双层结构。
6. **商业化计量精细**：无独立订阅，捆绑 ChatGPT 六档（$0–$200+定制）；2026-04 起改 token-credit 计量（≈$0.04/credit），5 小时+每周双窗口限速，重度用户被引导至 Pro 或 API 按量。
7. **公认短板**：速率限制体验差（大仓库上下文装载也计费）、模型选择不透明、无 Linux 桌面端、移动端弱、复杂架构推理被评略逊 Claude Code——这些是竞品可攻击的缝隙。
8. **待验证项**：GPT-5.5 SWE-bench Verified 88.7%（单一来源）；Gartner MQ 领导者（转引）；2026-03 "SuperApp 官方确认"（二手报道）；Codex for Work 的完整产品边界。

---

## 16. 主要信息来源清单

- OpenAI 官方：[Introducing upgrades to Codex / GPT-5-Codex](https://openai.com/index/introducing-upgrades-to-codex/)（2025-09-15）；[Codex is now generally available](https://openai.com/index/codex-now-generally-available/)（2025-10-06）；[openai/codex GitHub](https://github.com/openai/codex)（2026-07 抓取）
- 定价：[MorphLLM Codex Pricing](https://www.morphllm.com/codex-pricing)（2026-07-13）；[Layer3 Labs](https://www.layer3labs.io/guides/openai-codex-pricing)（2026-07-17）；[simplemetrics](https://simplemetrics.xyz/chatgpt-codex-limits-2026/)（2026-07-12）
- 版本/变更：[Toolsbase Codex 命令手册](https://toolsbase.dev/en/reference/codex-commands)（2026-07-19）；[ToolNav](https://toolnav.io/news/2026-05-25-openai-codex-goal-mode-appshots-stable/)（2026-05-25）
- 模型发布：[itecsonline GPT-5.1-Codex-Max](https://itecsonline.com/post/chatgpt-5-1-codex-max)（2025-11-21）；[Kompas GPT-5.3-Codex](https://tekno.kompas.com/read/2026/02/06/09020037/openai-rilis-gpt-5.3-codex-model-ai-canggih-yang-ngoding-dirinya-sendiri)（2026-02-06）；[QCode GPT-5.5](https://qcode.cc/en/codex-gpt-5-5-goal-mode-guide)（2026-05-29）
- 桌面/整合：[vibecoding.app](https://vibecoding.app/blog/openai-codex-app-review)（2026-06-17）；[iconpolls](https://iconpolls.com/blogs/openai-codex-review-2026-login-pricing-download-documentation-user-experience-and-faqs)；[StoryForge](https://www.octolinkzl.com/articles/openai_codex_2026_updated_installation_guide_for_desktop)（2026-07-13）；[AIToolHunt](https://aitoolhunt.co/blog/chatgpt-codex-merge-2026)（2026-07-10）
- SDK/集成：[npm @openai/codex-sdk](https://www.npmjs.com/package/@openai/codex-sdk?activeTab=code)；[byteiota GitHub Action](https://byteiota.com/codex-github-action-ci-pipeline/)（2026-07-06）；[VentureBeat ZoomInfo](https://venturebeat.com/business/openai-announces-native-availability-of-zoominfos-gtm-context-graph-gtmai-in-codex-for-work)（2026-06-02）
- 评测：[Standard Compute](https://standardcompute.com/best-ai-agent/codex-cli)（2026-07-12）；[AIUnpacking](https://aiunpacking.com/review/openai-codex/)（2026-05-15）；[Codersera](https://codersera.com/blog/claude-code-vs-openai-codex-2026/)（2026-05-26）

*报告完。撰写人：Codex竞品研究员，2026-07-19。*
