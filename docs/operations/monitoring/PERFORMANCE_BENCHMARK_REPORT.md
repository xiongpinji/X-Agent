# X-Agent 性能基准测试报告 (Wave A 真实测量)

> 本报告于 2026-07-20 由 P1-18 (性能基准工程师) 用**真实测量数据**整体回填。
> 此前版本中所有 `-` 占位符及样例数字均已废弃; 本报告每个数字都来自可复现的基准运行,
> 原始机器可读数据见 `benchmarks/results/` 下的 JSON 文件。

## 1. 测量环境

| 项目 | 值 |
|------|-----|
| 测量日期 | 2026-07-19 21:59–22:05 UTC (负载基准) / 2026-07-20 05:58 UTC+8 (数据库基准) |
| 操作系统 | Windows 11 (10.0.26200), AMD64 |
| CPU | AMD64 Family 26 Model 112 (32 逻辑核) |
| 内存 | 123.65 GB |
| Python | 3.13.13 (项目 venv) |
| 应用模式 | `XAGENT_APP_MODE=development` |
| LLM | **mock** (`settings.llm_backend` 默认值 `"mock"`, 未配置真实 LLM API key) |
| 数据库 | SQLite (应用默认 `sqlite:///./data/xagent.db`); 数据库微基准用独立临时 SQLite 库 (WAL) |
| 服务器 | uvicorn 单 worker, `backend.app.main:app`, 127.0.0.1, 测完即终止 |
| Git 基线 | Phase 1 完成点 7cd9b18 (测量期间 12 个并行子代理在改其他子系统) |

测量方法: 自写异步客户端 (`benchmarks/wave_a_load_benchmark.py`, httpx + 有界并发信号量,
复用单 AsyncClient)。延迟样本**仅统计 HTTP status < 400 的响应**; 429 (限流拒绝) 与
5xx/网络异常单独计数, 不混入服务端点延迟。

## 2. 核心端点负载测量 (Phase A: 配额内真实延迟)

为避开硬编码限流 (`/api/*` 合计 100 req/min/IP, 见 §5) 对延迟样本的污染,
本阶段以低并发、冷配额测量, api 桶总消耗 44 < 100。

| 端点 | n | 并发 | p50 | p95 | p99 | 吞吐 | 错误 |
|------|---|------|-----|-----|-----|------|------|
| POST /api/v1/auth/login | 8 | 2 | 469.54 ms | 477.47 ms | 477.58 ms | 4.22 rps | 0 |
| GET /api/v1/agents | 15 | 5 | 36.35 ms | 450.04 ms | 450.20 ms | 28.7 rps | 0 |
| POST /api/v1/agents/run (mock) | 3 | 2 | **147.45 s** | 147.45 s | 147.45 s | 0.01 rps | 0 |
| POST /api/v1/memory (写入) | 20 | 5 | 34.06 ms | 41.98 ms | 45.50 ms | 127.5 rps | 0 |
| POST /api/v1/memory/search | 20 | 5 | 23.05 ms | 26.51 ms | 27.42 ms | 175.1 rps | 0 |
| GET /api/v1/memory/count | 10 | 5 | 15.47 ms | 15.97 ms | 16.17 ms | 199.0 rps | 0 |

补充单发校准 (顺序单请求, 服务器无其他负载): agent run 50.33 s; login 246 ms;
agents list 230 ms (含首次构建开销); memory 写/搜/计数 5–10 ms。

## 3. /health 洪泛与并发扫描 (Phase B, /health 不限流)

| 场景 | n | 并发 | p50 | p95 | p99 | 吞吐 | 状态码 |
|------|---|------|-----|-----|-----|------|--------|
| health_flood | 2000 | 50 | 143.94 ms | 667.76 ms | 1238.62 ms | 219.19 rps | 2000×200, 0 错误 |
| health_c10 | 1000 | 10 | 23.72 ms | 33.43 ms | 50.17 ms | **353.70 rps** | 1000×200 |
| health_c50 | 1000 | 50 | 169.79 ms | 931.20 ms | 1428.22 ms | 168.49 rps | 1000×200 |
| health_c100 | 1000 | 100 | 690.47 ms | 3002.58 ms | 4851.46 ms | 100.85 rps | 1000×200 |

**吞吐随并发上升反而下降** (354 → 168 → 101 rps), 两次独立运行均可复现, 见 §6 发现 F2。

## 4. 数据库基准 (SQLite 模式, 真实测量)

本地 PostgreSQL 虽在监听 5432, 但无可用凭据 (不猜测), 按任务许可使用 SQLite 模式:
`database_benchmark.py --sqlite` (新增, aiosqlite, WAL + synchronous=NORMAL,
临时库 `benchmarks/results/perf_test_sqlite.db`, 测完自动删除)。

| 操作 | n | Mean | P95 | P99 | 吞吐 | 错误 |
|------|---|------|-----|-----|------|------|
| INSERT (含逐行 commit) | 5000 | 0.81 ms | 0.63 ms | 1.24 ms | 1239 ops/s | 0 |
| SELECT (主键点查) | 5000 | 0.39 ms | 0.61 ms | 0.91 ms | 2557 ops/s | 0 |
| UPDATE (含 commit) | 2000 | 0.37 ms | 0.51 ms | 0.88 ms | 2708 ops/s | 0 |
| COMPLEX_QUERY (窗口函数+排序) | 500 | 4.27 ms | 5.74 ms | 6.95 ms | 234 ops/s | 0 |
| TRANSACTION (2 写 + commit) | 500 | 0.69 ms | 1.00 ms | 2.64 ms | 1446 ops/s | 0 |
| DELETE (含 commit) | 500 | 0.33 ms | 0.61 ms | 1.33 ms | 3031 ops/s | 0 |

原始数据: `benchmarks/results/database_benchmark_sqlite_report.json`。

## 5. 限流行为验证 (Phase C)

代码事实 (`backend/app/main.py::rate_limit_middleware`, **硬编码, 无环境变量开关**):
login 10 req/min/IP; register 5 req/min/IP; 其余 `/api/*` 合计 100 req/min/IP; `/health` 不限流。

实测: 滑窗等待 61s 后以 150 请求 (c=10) 冲击 `GET /api/v1/agents` →
**恰好 100×200 + 50×429**, 与代码声明完全一致。429 响应本身 p50 ≈ 5–30 ms。

推论: 任何"API 端点高吞吐"数字在此限流下物理上不可能超过 100 req/min/IP;
压测 API 端点必须按 §2 的配额内方式测量, 否则测到的只是限流器拒绝延迟。

## 6. 关键发现 (性能问题, 仅记录, 不在本范围修复)

- **F1 (严重)**: `POST /api/v1/agents/run` 即使 mock LLM 也极慢 —— 单发 50.3 s,
  并发 2 时每个请求约 147.5 s (近似完全串行且劣化)。`dependencies.get_agent()`
  每个请求都新建 AgentLoop 并 `build_default_tool_registry()`, 疑似每次运行重建
  工具注册表/索引, 且存在某种全局串行点。商用前必须专项排查。
- **F2 (高)**: `/health` 吞吐随并发反 scale (354→168→101 rps @ c10/50/100),
  p99 从 50 ms 劣化到 4.85 s。Windows 单 worker uvicorn + 中间件栈
  (请求日志/CSRF/限流/Prometheus) 在高并发下疑似存在锁竞争或事件循环阻塞。
- **F3 (中)**: 限流阈值硬编码且无配置项, 压测/生产调优都无法不改代码调整。
- **F4 (低, 符合预期)**: login p50 ≈ 246–470 ms, 为 bcrypt 常量时间设计, 属安全取舍。
- **F5 (正面)**: memory 写/搜/计数端点 p99 ≤ 45.5 ms; SQLite 默认引擎点查/写入
  亚毫秒级, 无错误。

## 7. 复现命令

```bat
REM 负载基准 (分段执行以适配单段时长; 脚本自动起停 uvicorn, 不留后台进程)
.\venv\Scripts\python.exe benchmarks\wave_a_load_benchmark.py --port 8126 --phases ab
.\venv\Scripts\python.exe benchmarks\wave_a_load_benchmark.py --port 8127 --phases c
.\venv\Scripts\python.exe benchmarks\wave_a_load_benchmark.py --merge ^
  benchmarks\results\wave_a_benchmark_ab_latest.json ^
  benchmarks\results\wave_a_benchmark_c_latest.json ^
  --out benchmarks\results\wave_a_benchmark_merged.json

REM 数据库基准 (SQLite 模式)
.\venv\Scripts\python.exe database_benchmark.py --sqlite ^
  --output benchmarks\results\database_benchmark_sqlite_report.json
```

原始数据文件:
- `benchmarks/results/wave_a_benchmark_merged.json` (及 `*_ab_*` / `*_c_*` 分段文件)
- `benchmarks/results/database_benchmark_sqlite_report.json`
- `benchmarks/results/uvicorn_benchmark_server.log` (被测服务器日志)

## 8. 本次未覆盖 (如实声明)

- Locust 运行: 未安装 locust 包, 时间有限, 采用自写异步客户端完成; `locustfile.py`
  保留可用, 未在本次执行。
- agent_v2 vs v1 架构对比基准 (`benchmarks/agent_v2_benchmark.py` 等): 未执行,
  `benchmarks/PERFORMANCE_BENCHMARK_REPORT.md` 中的旧对比数字为不可复现样例,
  已标注作废, 需专项重测。
- PostgreSQL 数据库基准: 无可用凭据, 未执行 (SQLite 已覆盖默认部署形态)。
- 生产模式 + 真实 LLM 的端到端延迟: mock LLM 不产生网络/推理延迟, 真实 provider
  数字需凭生产凭据另行测量。
- 长时间稳定性/soak 测试、内存泄漏曲线: 未覆盖。
