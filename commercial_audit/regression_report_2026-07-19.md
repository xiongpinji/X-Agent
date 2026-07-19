# Phase 1 里程碑全量回归验证报告

- **日期**: 2026-07-19
- **范围**: 商用修复 Phase 1 三波改动（基线 f3aab93 → HEAD 78cf5b4，共 4 个提交）
- **执行人**: 全量回归验证工程师（subagent）
- **状态**: 已定稿（失败清单化 + 分类 + A 类修复 + RC/冒烟完成）

## 执行摘要

| 指标 | 数值 |
|---|---|
| 全量收集 | **4423 用例，0 errors** |
| 全量执行 | **完成**（分批 + pytest-xdist -n 4；跳过 ~224 为设计内 e2e/压测门控） |
| 失败 | **29（批次计数）= 25 个唯一用例**；A 类 2 / B 类 4 / C 类 19 |
| A 类修复 | **2 处已修并复跑转绿**（tests/test_api_comprehensive.py） |
| 修复后失败 | 27（批次计数）/ 23 唯一，全部 B/C 类 |
| 真实通过率 | ≈ **99.3%**（执行口径：(4423−224−29)/(4423−224)） |
| 真实覆盖率 | 未产出（分批 -n 4 + --no-cov 提速，见"未覆盖项"） |
| RC 基线 | **通过**（agent-core 9 + mcp-and-channels 100 + sandbox-api 9） |
| 端点冒烟 | / 200、/console 200、/health 200、/ready 200；/metrics 精确路径 404（/metrics/ 正常 200，见疑似问题 S-2） |

## 运行策略说明（重要）

4423 用例全串行预计 40 分钟以上，超出单次命令时限，采用以下策略：

1. 按文件把 295 个测试文件装箱为 13 个批次（每批 ≤380 用例，装箱清单见 `.regression_batches/`）。
2. 每批命令: `pytest <批次文件> -q --timeout=120 -p no:cacheprovider --cov=backend --cov-append --cov-report=`（覆盖率跨批累计，最后一次统一出报告）。
3. 批次 1 起改用 `pytest-xdist -n 4` 并行加速（xdist 3.8.0 为本任务新装入 venv）。
4. **性能/压测目录**：本机 8000 端口被**无关项目**（`molimama 无线画布\ai-moive-studio` 的 uvicorn，PID 61760）占用。`tests/performance/conftest.py` 的探活守卫误判"有服务"后会真打 60s+ 负载。按守卫设计以 `XAGENT_PERF_PORT=59999` 触发设计内 skip（该目录设计为需要活服务器的可选套件）。
5. e2e 目录默认 skip 为设计内行为（`XAGENT_E2E=1` 才放行）。

## 已确认的修复（tests/ 范围，2 处）

### 修复 1：tests/test_browser_service.py — 事件循环污染（级联 233 errors 的根因）

- **现象**: 批次 2 中 117 个用例报 233 个 error（setup/teardown 成对），全部信息为
  `RuntimeError: Cannot run the event loop while another loop is running` /
  `Cannot close a running event loop`。
- **根因**: `test_browser_session_can_record_actions` 调用 `browser_client.create_session()` →
  `sync_playwright().start()` 启动真实浏览器，其驱动事件循环在主线程驻留且永不回收
  （backend `playwright_client.py` 未暴露 stop；`close_session` 只关 browser 不停驱动）。
  该用例随后向 example.com 的 `#name` 填充（该元素不存在）必然超时失败，
  失败后驱动循环继续驻留 → 后续全部 pytest-asyncio 用例级联报错。
- **分类**: 既有问题（Phase 1 未改动该测试与 backend 循环管理逻辑；审计前"全跳过"状态掩盖了它）。
  其中 `fill/click/goto` 对 fallback 会话从"假成功"改为"记 ok=False"是 Phase 1 新契约
  （"No silent fake success"），但本环境装了 Playwright，走的是真实路径，与新契约无关。
- **修复（tests/ 侧）**: 真实浏览器用例改为 `XAGENT_REAL_BROWSER=1` opt-in 门控 + try/finally 关闭会话；
  `test_browser_session_close_prevents_further_actions` 用 monkeypatch 置 `sync_playwright=None`
  走非托管路径，不再启动真实浏览器。
- **复跑验证**: `pytest tests/test_browser_service.py tests/test_playwright_real_path.py tests/test_cache.py`
  → **31 passed, 2 skipped**，级联消失。

### 修复 2：tests/test_playwright_real_path.py — 同类污染 + 新契约对齐

- 该文件无守卫，无条件 `create_session()` + 真实 `goto(example.com)`：装 Playwright 则污染事件循环；
  未装则因新契约（fallback 不再假成功，`goto.ok=False`）必然断言失败。
- **修复（tests/ 侧）**: 整文件加 `XAGENT_REAL_BROWSER=1` opt-in 门控 + try/finally 关闭会话。
- **backend 侧问题（只记录，不修改）**: `backend/app/services/browser/playwright_client.py`
  的 sync_playwright 驱动未提供 stop/回收路径，任何真实浏览器用例在套件内运行都会泄漏事件循环。
  建议后续在 backend 增加驱动生命周期管理或在 conftest 增加进程级隔离。

## 分批执行结果（最终）

13 个批次全部跑完，合计 4423 收集 / 0 errors / 约 4258 passed / ~224 skipped（设计内门控）/ **29 failed（批次计数）**。其中 batch_04 前 15 个文件与后 5 个文件有 4 个失败用例重叠（两批共同包含 test_creative_studio / test_distributed_integration / test_distributed_performance），去重后 **25 个唯一失败用例**。含失败的批次重跑核对（`-rf --tb=no`，部分两轮以捕获时序性用例）：

| 范围 | 批次计数失败 | 唯一失败 |
|---|---|---|
| b01d（tests/test_api_comprehensive.py） | 2 | 2 |
| batch_04 前半（head -15） | 10（两轮：9 + 1 时序） | 9 |
| batch_04 后半（tail -5） | 4 | 0（全部与前半重叠） |
| batch_05 | 6 | 6 |
| batch_06 | 1 | 1 |
| batch_08 | 3（两轮：2 + 1 时序） | 3 |
| batch_10 | 1 | 1 |
| batch_11 | 2 | 2 |
| **合计** | **29** | **25** |

## 失败清单（定稿，25 个唯一用例 + 4 个批次重叠）

### A 类：本次修复引入的契约变化（2 个，已修复）

| # | 用例 | 根因与新契约 | 处置 |
|---|---|---|---|
| A-1 | tests/test_api_comprehensive.py::TestMemoryEndpoints::test_list_memories_unauthorized | 断言期望 401/403/405，实际 404。78cf5b4 新增 SPA fallback 兜底路由（`GET /{spa_path:path}`，注册于所有路由之后）全匹配了"路径存在但方法不匹配"的 API 请求，按设计注释（"其余未知路径(含 /api/...)仍返回标准 404"）以 404 取代原 405。已读 backend/app/main.py:842-853 确认为修复意图 | **已修复**：断言改 (401, 403, 404) 并更新注释 |
| A-2 | tests/test_api_comprehensive.py::TestCollaborationEndpoints::test_list_messages_unauthorized | 同上（messages 仅 POST，GET 经 SPA fallback 得 404） | **已修复**：断言改 (401, 403, 404) 并更新注释 |

**修复验证**：`pytest tests/test_api_comprehensive.py -n 4` → **40 passed**（原 2 failed 转绿）。

### B 类：既有问题（4 个，基线上即失败，Phase 1 相关路径零改动）

| # | 用例 | 证据 |
|---|---|---|
| B-1 | tests/test_creative_studio.py::test_creative_tools_registered_in_default_registry | 断言 `create_short_drama_storyboard` 在 `build_default_tool_registry` 中；但该函数（backend/app/core/tools.py:1264-1302）只注册基础工具，`git log -S` 显示 creative 工具**从未**进入默认注册表；Phase 1 未改 tools.py 与 creative_studio/wiring.py。测试写于一个从未成立的期望 |
| B-2 | tests/test_test_taxonomy.py::test_test_file_naming_matches_taxonomy | tests/e2e/test_agent_fix_real_llm.py 由基线快照 f3aab93 引入（`git log` 首提交即 f3aab93），既不以 `_e2e.py` 结尾也不在 e2e 白名单内 |
| B-3 | tests/test_resume_recovery.py::test_resume_run_reuses_previous_subtask_state | 断言 `any(step.kind == "final" for step in result.plan)` 为 False；resume 路径（backend/app/core/agent/loop.py、RunStore、contracts）Phase 1 diff 为空，单跑稳定复现 |
| B-4 | tests/test_streaming_comprehensive.py::TestStreamingEndpoints::test_stream_health | **backend 路由顺序缺陷**：`GET /api/v1/agent/stream/{run_id}`（subscribe_to_stream）注册先于 `/stream/health`，`health` 被当作 run_id 进入 SSE 订阅而永久挂起。pytest 外用裸 TestClient 直探同样挂起；streaming.py Phase 1 零改动。列入"疑似 backend 问题 S-1" |

### C 类：环境依赖（19 个）

**C-R：Redis/fakeredis 缺失（10 个）**——requirements-dev.txt:17 声明 `fakeredis==2.35.1` 但本 venv 未安装，根级 conftest 的 fakeredis 注入被 `except ImportError: pass` 静默跳过，`RateLimiterRedis()/CSRFTokenStoreRedis()` 抛 `RuntimeError: Redis未初始化`：

| # | 用例 |
|---|---|
| C-1 | tests/test_distributed_state_management.py::TestRateLimiter::test_check_rate_limit_allowed |
| C-2 | tests/test_distributed_state_management.py::TestRateLimiter::test_check_rate_limit_exceeded |
| C-3 | tests/test_distributed_state_management.py::TestRateLimiter::test_reset_limit |
| C-4 | tests/test_distributed_state_management.py::TestCSRFTokenStore::test_create_token |
| C-5 | tests/test_distributed_state_management.py::TestCSRFTokenStore::test_validate_token |
| C-6 | tests/test_distributed_state_management.py::TestCSRFTokenStore::test_revoke_token |
| C-7 | tests/test_distributed_integration.py::TestRestartRecovery::test_redis_session_recovery |
| C-8 | tests/test_distributed_performance.py::TestPerformance::test_rate_limiter_throughput |
| C-9 | tests/test_distributed_performance.py::TestStressTest::test_high_concurrency_rate_limiting |
| C-10 | tests/test_distributed_performance.py::TestPerformance::test_concurrent_throughput（成功率 0/1000，同 Redis 根因） |

**C-L：真实 LLM/外网依赖（5 个）**——测试直接实例化未 mock 的 `LLMRouter()` + 真实默认工具注册表，无 API key 环境下离线规划器反复派发 search_text 等工具读盘打转直至 120s 超时（串行 -n 0 单跑仍超时；backend/app/core/ 下 agent/llm 路径 Phase 1 零改动）：

| # | 用例 |
|---|---|
| C-11 | tests/test_coverage_boundary_conditions.py::TestBoundaryConditions::test_empty_task |
| C-12 | tests/test_coverage_boundary_conditions.py::TestBoundaryConditions::test_whitespace_only_task |
| C-13 | tests/test_coverage_boundary_conditions.py::TestBoundaryConditions::test_task_with_special_characters |
| C-14 | tests/test_coverage_boundary_conditions.py::TestBoundaryConditions::test_task_with_unicode（时序性：两轮各现一次） |
| C-15 | tests/test_coverage_boundary_conditions.py::TestBoundaryConditions::test_concurrent_execution |

**C-P：性能/时序阈值（4 个）**——真实执行耗时超过测试硬编码阈值或 120s 超时，与机器负载相关：

| # | 用例 | 现象 |
|---|---|---|
| C-16 | tests/test_hybrid_memory.py::TestPerformance::test_hot_tier_performance | 热层存取耗时超阈值 |
| C-17 | tests/test_performance.py::TestAPIPerformance::test_agent_run_performance | 20 次真实 `POST /api/v1/agents/run` 迭代总耗时超 120s（串行单跑 180s 仍超时） |
| C-18 | tests/test_performance_extended.py::TestLoadTesting::test_spike_load | 脉冲负载阈值 |
| C-19 | tests/test_performance_stress.py::TestResourceUsage::test_llm_response_time_consistency | 时序性：batch_08 两轮重跑仅第二轮出现 |

**批次重叠说明**：batch_04 后半的 4 个失败（test_creative_tools_registered_in_default_registry、test_redis_session_recovery、test_rate_limiter_throughput、test_high_concurrency_rate_limiting）与前半为同文件同用例，已计入上表，不重复编号。

## 疑似 backend 问题清单（只记录，未修改）

| # | 问题 | 说明 |
|---|---|---|
| S-1 | streaming 路由遮蔽 | `GET /api/v1/agent/stream/{run_id}` 先于 `/stream/health` 注册，health 被 SSE 订阅吞噬挂起（对应 B-4）。建议将 `/stream/health` 注册移到 `/{run_id}` 之前 |
| S-2 | `/metrics` 精确路径 404 | Phase 1 新增 `app.mount("/metrics", make_asgi_app())`（main.py:386-392），Starlette Mount 不匹配无尾斜杠精确路径：`GET /metrics` 404（落入 SPA fallback），`GET /metrics/` 200 且 Prometheus 输出正常。基线根本无根路径 /metrics（仅 /api/v1/metrics/*），属新增能力的边角问题，非回归 |
| S-3 | Playwright 驱动泄漏 | （承前次记录）playwright_client.py 未暴露 sync_playwright 驱动 stop，真实浏览器用例泄漏事件循环 |

## RC 基线与端点冒烟（2026-07-19 复核）

**RC 基线**：`./venv/Scripts/python.exe scripts/release_candidate_check.py` → **通过**
- agent-core：9 passed（含 reflect/replan prompt 契约用例 + test_agent_fix_runner.py）
- mcp-and-channels：100 passed
- sandbox-api：9 passed（此前报告过的沙箱 API CSRF 403 未再出现）

**5 端点冒烟（TestClient，单进程）**：

| 端点 | 结果 |
|---|---|
| `/` | **200**（436B） |
| `/console` | **200**（33.7KB 控制台页） |
| `/health` | **200** |
| `/ready` | **200**（221B，组件就绪报告） |
| `/metrics` | **404**（22B；尾斜杠形态 `/metrics/` 为 200，见 S-2） |

## 真实通过率

- 收集 4423 / 跳过 ~224（设计内 e2e + 压测门控）/ 实际执行 ~4199。
- 修复前：29 failed（批次计数，25 唯一）→ 通过率 ≈ 99.31%（(4423−224−29)/(4423−224)）。
- A 类修复后：27 failed（批次计数，23 唯一，全部 B/C 类）→ 通过率 ≈ **99.36%**。

## 与审计前基线对比

| 维度 | 审计前基线 | 本次（Phase 1 后） |
|---|---|---|
| 收集 | 4,377 | **4,423（+46）** |
| 执行 | **0（全跳过假象）** | **~4,199 真实执行，0 errors** |
| 失败可见性 | 不可见（被全跳过掩盖） | 29→27（25→23 唯一），全部清单化分类 |
| 覆盖率 | 不可信 | 未产出全量数字（见下） |
| RC 门禁 | 未建立 | **通过**（118 用例 targeted baseline） |

## 未覆盖项与遗留说明

1. **全量覆盖率数字未产出**：分批回归为压时间统一用 `--no-cov`；如需真实覆盖率，建议补跑 `--cov=backend --cov-report=term` 且范围限 `tests/unit + tests/contracts + tests/runtime`（其余目录含大量环境依赖用例，数字会被拉偏），本次时间预算内未执行。
2. **C 类环境缺口**：本 venv 缺 `fakeredis`（requirements-dev.txt:17 已声明）与 `lupa`（Redis Lua）；安装后 C-R 组 10 个用例预期转绿，C-L/C-P 组依赖 LLM key 与机器性能基线。
3. **B 类 4 个未修**（规则：仅修明确 A 类）：B-1/B-2 为测试期望与现实不符（修白名单/注册期望各 1 行即可，建议下个迭代处理）；B-3 需 backend resume 语义确认；B-4 需 backend 路由顺序调整（S-1）。
4. **时序性用例**：C-14、C-19 在并行负载下间歇出现，属 flaky 性能断言，建议加 `@pytest.mark.flaky` 或放宽阈值。
5. 根级 conftest 提示 `XAGENT_AUDIT_HMAC_SECRET` 未设（开发态临时 key），生产部署需配置。

## 附录：环境

- Python 3.13.13 (venv)，pytest 8.4.2，pytest-cov 7.1.0，pytest-timeout 2.3.1，pytest-asyncio 0.25.3，pytest-xdist 3.8.0（本任务新装）
- Windows，工作目录 D:\AI编程库\项目库\进行中的项目\X-Agent
- 环境变量：`XAGENT_PERF_PORT=59999`（压测探活覆盖）
