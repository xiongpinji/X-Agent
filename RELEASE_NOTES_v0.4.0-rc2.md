# X-Agent v0.4.0-rc2 — Release Notes

**日期**: 2026-09-05 · **状态**: Release Candidate（本地全量实测验证；CI 门禁随本版转 blocking，首个 push 完成托管验证）

rc1 之后的两个大批次收口：**商用交付冲刺**（21 个测试失败清零 + MCP 真握手 + 前端测试基础设施 + 仓库治理）与 **A+B 双方向推进**（多端入口 + 学习闭环，对标 Codex/Hermes）。

## 本版核心变化

### 批次一：商用交付冲刺（测试门禁清零）

- **21 个测试失败全部清零**（4 个首轮审计回归 + 17 个全量暴露）：含 AGENTS.md fast-path 绕过（产品级 bug）、测试假件接口过时、宿主环境渗入、性能阈值校准
- **MCP 协议真握手**：官方 SDK（stdio）完整 initialize→initialized→tools/list→tools/call 生命周期，fail-closed 错误分层（握手/传输/工具），超时可配，ToolRegistry 桥接 `plugin_mcp__` 前缀；16 新测试，MCP 相关 316 测试绿
- **前端测试基础设施从零到一**：vitest + RTL，90 用例（含 API key 拦截器回归），修复 4 个 jest 时代遗留测试文件
- **Checkpoint 三缺陷修复**：撕裂行容错加载、append fsync、磁盘压缩 + mark_completed 落盘（崩溃恢复可用性）
- **仓库治理**：根目录 158 个临时/练习产物归档或删除

### 批次二 A：多端入口（对标 Codex 五端一核）

- **A1 CLI 真流式**：`/agent/run/stream` 桥接 AgentLoop 事件回调，SSE 细粒度协议（plan/iteration/tool_call/tool_result/approval_required）；CLI 切真流式 + **@文件引用** + 斜杠命令（/resume /approvals /approve /reject /model 等）+ 流中内联 y/n 审批；37 新测试，真机 uvicorn 端到端验证
- **A2 浏览器扩展接通**：从零通信到装上即用——设置存储 + 连通性测试、popup 对话（自动附页面上下文，可选流式）、右键"分析此页"+ 系统通知；115 测试（基线 29 全挂）+ 跨平台打包
- **A3 沙盒任务持久化**："assign and come back"重启不丢结果（JSONL 落盘 + 回灌 + GET 回退）

### 批次二 B：学习闭环（对标 Hermes 自我改进）

- **B1 skill 自动创建+自改进**：轨迹→沉淀→落盘 custom-skills/→SkillLoader 热加载→ToolRegistry 可执行→usage 统计→成功率<0.7 自动 LLM 改写落盘新版本；修复 ReflectionRecord 字段错配空壳 bug，反思 JSONL 持久化
- **B2 记忆全文搜索**：FTS5 接入主路径（BM25 top-50 候选 + 三层降级安全），**3000 条搜索 65ms→4.7ms（13.9x）**；中文分词生效，修 bm25 列权重错位既有 bug
- **B3 调度器常驻化**：cron 循环 + workflow run_due（lease 抢占）+ task_queue worker（agent.run handler）三路启动接线；挂载 skill_sediment/memory_advanced/scheduler 路由（439→471）；修复 /queue/enqueue 既有 TypeError

### CI 门禁转 blocking（本版起生效）

- `test.yml` unit/integration job 去除 `continue-on-error`；纯计时/压测（5 文件 + 1 类，~72 用例）挂 `performance` 标记拆入 advisory job（共享 runner 阈值放宽 2x）
- `frontend-ci.yml` vitest 转 blocking（ESLint 存量 33 错误清零前保持 advisory）；`quality-gate.yml` core tests 去 `|| true`
- 单测密闭性：conftest 默认关闭调度常驻循环（`XAGENT_SCHEDULER_ENABLED=false`）

## 验证状态

- 后端全量套件（~7000 用例）：blocking 选择集 0 失败（性能 advisory 集单跑通过）
- 前端：tsc 0 错误 + vite build 通过；vitest 90/90
- 扩展：115/115 + zip 打包
- 启动冒烟：471 路由 / `/health` 200 / 流式端点挂载正确
- B3 端到端：定时投递→真实 AgentLoop 执行→completed + trace_id

## 已知边界（沿用 rc1 口径并更新）

1. **桌面端 Tauri**：结构可构建但未做本机 Rust 工具链冒烟（下个独立任务）；Rust 命令层与主 React 前端的适配层未接
2. **移动端**：仍是占位 API 域名的完整壳，未联调
3. **Cloud Tasks 完整形态**：统一任务实体（DB 状态机 + 取消 + 通知）未做，本版仅落地结果持久化
4. **CI blocking 首验**：门禁转 blocking 随本 tag 落地，托管运行需 push 后首个 Actions run 验证
5. **ESLint 存量**：前端 33 错误/248 警告未清零（advisory 债务）

## 升级与部署

- 版本单一事实源: `pyproject.toml`（0.4.0-alpha，RC 标签 **v0.4.0-rc2**）
- 新增环境变量：`XAGENT_SCHEDULER_ENABLED`（默认 true）、`XAGENT_MEMORY_FTS_PATH`、`XAGENT_MCP_PLUGIN_START_TIMEOUT`/`_REQUEST_TIMEOUT`、`XAGENT_SANDBOX_TASKS_PATH`、`XAGENT_CUSTOM_SKILLS_DIR`、`XAGENT_PERF_THRESHOLD_MULTIPLIER`
- 生产部署要求同 rc1（外部存储 fail-fast 清单不变）
