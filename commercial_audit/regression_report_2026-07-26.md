# X-Agent 全量回归报告（2026-07-26）

- 执行人：全量回归验证工程师（子代理）
- 项目：`D:\AI编程库\项目库\进行中的项目\X-Agent`
- 基线对比：2026-07-19（4423 收集 / 99.3% 通过率）
- 约束遵守：无 git 写操作；未修改 `backend/`；仅 `tests/` 内 A 类修复；所有数字来自实际运行日志与 JUnit XML。

---

## 1. 收集阶段

```
./venv/Scripts/python.exe -m pytest tests/ --collect-only -q --no-cov
```

| 指标 | 数值 |
|---|---|
| 测试文件数 | 380 |
| 收集用例数 | **7479** |
| 收集错误 | **0** |
| 收集警告 | 5 个 PytestCollectionWarning（`__init__` 构造器的 Test* 类，不收集，属既有）|

## 2. 执行策略

- 既有 `.regression_batches/batch_*.txt` 已过时（115 个新文件未覆盖、18 条 CRLF 粘连行），按每文件用例数 LPT 重新装箱为 **24 批**（`s_00..s_23`，每批 311~312 条）。
- 每批命令模板：`COVERAGE_FILE=.coverage_reg_XX XAGENT_PERF_PORT=599xx ./venv/Scripts/python.exe -m pytest <文件> -q --no-cov -p no:cacheprovider -n 4~8 --timeout=120 --max-worker-restart=10 -rf --tb=no --junitxml=...`
- 两批一对并行执行（32 核机器），单批均控制在 4 分钟内。
- 两个含挂起测试的文件（`test_agent_extended.py`、`test_coverage_branch_coverage.py`）隔离单独容错重跑。
- 失败文件（65 个）在 A 类修复后分 3 组重跑并替换原始结果；重试次数 ≤2。

## 3. 总体结果（修复后最终）

| 指标 | 数值 |
|---|---|
| 总用例 | 7479 |
| **通过** | **7076** |
| 失败 | 79 |
| 错误 | 21（全部为 xdist worker 崩溃，同一 backend 根因）|
| 跳过 | 303（e2e 默认 skip 约 112 条为设计内行为；其余为 Docker/Redis/Postgres 等环境标记跳过）|
| **真实通过率（含跳过）** | **94.61%** |
| **真实通过率（排除跳过）** | **98.61%** |

修复前首轮结果：6861 通过 / 274 失败 / 41 错误 / 303 跳过（91.74%）。A 类修复后回收 215 条。

## 4. 失败分类统计（剩余 100 条 = 79 失败 + 21 错误）

### A 类 — 新契约需对齐（tests/ 范围内，约 34 条）

| 模式 | 数量 | 说明 |
|---|---|---|
| `RedisTaskQueue.enqueue(name=...)` / `.pause` 旧 API | 6 | `test_scheduler.py`，队列类商用重构后签名变更；fixture 已修（见 §5），余 6 条需按新 API 重写 |
| `PostgresMemorySystem.search() got an unexpected keyword argument 'scope'` | 3 | 记忆检索签名变更 |
| `Task.__init__() got an unexpected keyword argument 'task_id'` | 3 | `test_sandbox_orchestrator.py` sandbox Task 数据类变更 |
| `KeyError: 'id'` / `KeyError: 'trace_id'` / `KeyError: 'recovery_hint'` | 10 | workflow run/trace 视图响应结构变更 |
| 503 == 200/401（streaming ×6、telegram ×2、authz ×2、tool_detail ×1）| 11 | 服务端特性门控/未启用项返回 503，测试期望旧响应码（A/C 交界，需确认是否应为环境配置）|
| `test_test_taxonomy` 命名清单 | 1 | e2e 文件清单未含新增文件 |
| `test_rc_supply_chain_gate` 前端 lockfile 校验 | 1 | lockfile 与 package.json 一致性（A/B 交界）|
| `test_workflows` recovery_hint 路由/模板数 | 3 | 执行器路由提示与模板集变更（A/B 交界）|

### B 类 — 既有/backend 问题（约 32 条，仅记录未修）

| 模式 | 数量 | 说明 |
|---|---|---|
| xdist worker 崩溃（`analyze_dependencies` 文件读 C 级阻塞，`backend/app/core/tools.py:1125`）| 21 | Windows 下线程超时无法打断，worker 被杀；涉及 `test_agent_extended.TestAgentLoopIntegration`(3)、`test_coverage_branch_coverage.TestIfElseBranches`(10)、`test_coverage_error_handling`(3)、`test_coverage_exception_cases`(2)、`test_agent_loop`(1)、`test_performance_stress`(1)、`test_billing.TestBillingPerformance`(1)。**禁止修改 backend，仅记录** |
| `collaboration_delegation` `assert 'failed' == 'completed'` | 4 | 委派链路在 mock LLM 下失败，疑似 backend 行为变化 |
| 登录/注册限流未触发（401/400 != 429）| 2 | 测试环境限流器行为（B/C 交界）|
| Stripe provider charge/refund | 2 | 支付 mock 行为（B/C 交界）|
| 其余零散断言 | 3 | `test_sandbox_orchestrator` drain 计数等 |

### C 类 — 环境依赖（约 34 条）

| 模式 | 数量 |
|---|---|
| `asyncpg invalid DSN`（Postgres 未配置，metrics/memory/performance 各文件）| 15 |
| LLM 后端不可用（ollama 连接失败 / 无 API key）| 12 |
| 性能阈值（health 13.4ms>10ms、并发 P99、缓存、hybrid memory、stress）| 5 |
| sandbox 任务停留 `queued`（sandbox worker/Docker 未运行，含 RC 失败的 2 条）| 2 |

> 分类边界说明：503 组、限流组、Stripe 组标为交界项，需 backend 负责人确认是否为预期门控行为；本报告不做臆断。

## 5. 修复记录（A 类，仅 tests/）

1. **`tests/conftest.py`**（新增引导块）：商用修复将 531 条路由的注册移入 FastAPI startup 钩子（`backend/app/main.py: startup_event → _register_all_routers()`），直接 `TestClient(app)` 不触发 startup 导致大面积 404。修复：导入期幂等注册 + 守卫包装防止 startup 二次注册。**回收约 199 条失败**（如 `test_security.py` 20 失败 → 2、`test_audit.py` 3 失败 → 0、API 契约/端点文件大面积转绿）。
2. **`tests/test_scheduler.py`**：fixture 中 `task_queue.queue/.task_map` → `._memory_queue/._memory_status`（RedisTaskQueue 商用重构后属性名）。**回收 16 条**（22 error → 6 failed）。

均已单文件/小组复跑验证。

## 6. RC 基线

```
./venv/Scripts/python.exe scripts/release_candidate_check.py
```

- 退出码：**1（未通过）**
- 结果：`2 failed, 7 passed`；FAILED GROUPS: **sandbox-api**
- 失败项：`test_submit_poll_completes`、`test_failing_command_marks_failed`（任务停留 `queued`，sandbox 执行 worker 未在本环境运行）
- 分类：**C 类环境依赖**，非本次商用修复引入的回归。同组另有 plugin 配置缺失警告（github_token/db 等），属环境配置。

## 7. 与 07-19 基线对比

| 指标 | 07-19 基线 | 07-26 本次 | 变化 |
|---|---|---|---|
| 收集用例 | 4423 | 7479 | **+3056（+69.1%）** |
| 通过率 | 99.3% | 98.61%（排除跳过）/ 94.61%（含跳过）| -0.7pt（口径排除跳过）|
| 收集错误 | — | 0 | — |

解读：套件规模近翻倍（P0×18+P1×23 配套测试大量新增），通过率仅微降；剩余失败中约 1/3 为环境依赖（C），21 条为同一 backend 挂起根因（B），真正的契约对齐余项（A）约 34 条且修复路径明确。

## 8. 未覆盖项与遗留

1. **e2e 默认 skip**（约 112 条）：设计内行为，需 `XAGENT_E2E=1` 放行，本轮未放行。
2. **跳过项其余约 191 条**：Docker/Redis/Postgres/外网标记跳过，本环境未覆盖。
3. **2 个挂起文件**的 agent-loop 集成测试（13 条用例）以 worker 崩溃兜底记为 error，未真正执行断言；根因在 `backend/app/core/tools.py:1125 analyze_dependencies` 的阻塞式文件读，建议 backend 侧加非阻塞/限时读取。
4. 重跑组 0 首轮 290s 超时，按策略拆半后第 2 次尝试完成（未超 2 次重试上限）。
5. A 类余项 34 条（scheduler 6、memory scope 3、sandbox Task 3、workflow 视图 10、503 组 11、taxonomy 1）建议排期对齐。

## 9. 产物索引

- 批次清单：`.regression_batches/s_00.txt..s_23.txt`
- 每批日志/XML：`.regression_batches/run_s_*.log` / `s_*.xml`
- 重跑日志/XML：`.regression_batches/run_rr*.log` / `rr0_p*.xml` / `rerun_1.xml`
- 汇总中间产物：`.regression_batches/total_agg.txt`、`final.txt`、`fail_by_file.txt`
- RC 日志：`.regression_batches/rc_check.log`
- 辅助脚本（可审计/可复跑）：`regen_batches.py`、`repack.py`、`run_sbatch.sh`、`agg_xml.py`、`make_rerun.py`、`final_totals.py`、`count_progress.py`、`collect_out.txt`
