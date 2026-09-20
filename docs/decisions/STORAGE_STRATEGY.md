# T6 存储策略决策文档

> 日期：2026-09-20 ｜ 基线：develop @ ecc9343 ｜ 状态：**已批准（D1-D7 采纳，2026-09-20）**

## 1. 现状盘点（实测）

X-Agent 当前同时存在 **三层持久化路径**：

| 层 | 实现 | 默认? | 使用方 |
|---|---|---|---|
| A. JSON/JSONL 文件 | `settings.py` 指向 `data/*.jsonl|json`（memory/traces/runs/workflows/approvals/api_keys/audit/tool_executions 共 9 类 store） | ✅ 默认 | 几乎所有 core/api 模块；全部测试 |
| B. SQLite 本地库 | `backend/local/`（database.py 803 行、migration、encryption、sync_client） | ❌ | local-first 部署叙事、云同步（cloud/） |
| C. PostgreSQL | `dependencies.py` 的 `memory_backend="postgres"` → PostgresMemorySystem；`trace_backend="postgres"` → PostgresTraceStore；audit_postgres（僵尸，T5 已判归档） | ❌ 开关式 | docker-compose 提供 postgres/redis/qdrant 服务 |

辅助设施：Qdrant（可选向量检索，`XAGENT_QDRANT_URL` 为空即禁用）、Redis（可选：token 存储/速率限制/Celery broker）。

## 2. 已知问题

1. **JSONL 并发缺陷**：高并发写导致 OOM/PermissionError（历史测试基线 4 err 的根因；
   pytest-xdist 需 per-worker 数据目录隔离才能跑）
2. **无界增长**：历史事故——runs.jsonl 曾达 344MB、workflows.json 211MB 混入仓库（导致 550MB
   git 历史被重置）。文件 store 没有轮转/压缩/TTL 机制
3. **宣传与现实脱节**：README 曾以 PostgreSQL/Qdrant/Neo4j 为主打（T2 已改为分层表述）；
   Neo4j 仅有依赖注入式可选代码路径（driver 不在 requirements，默认静默禁用），从未真实运行
4. **B 层定位模糊**：backend/local SQLite 与 A 层 JSONL 职责重叠，二者无同步机制
5. **C 层覆盖不全**：Postgres 后端只有 memory/trace 两类 store，workflows/approvals/audit/
   api_keys 等仍走文件

## 3. 建议方案（待拍板）

**定位：local-first 单机默认 + Postgres 生产 profile，两层都真实可用；JSONL 逐步换 SQLite。**

| 决策点 | 建议 |
|---|---|
| D1 默认存储 | 保持 A 层（零依赖快速启动是真实卖点），但**新 store 一律不再加 JSONL**，改用 B 层 SQLite（`backend/local` 已有基建） |
| D2 JSONL→SQLite 迁移 | 分两阶段：先给现有 JSONL store 加"启动时自动迁移到 SQLite"逻辑；跑稳一个里程碑后删除 JSONL 路径。优先迁移 audit/runs（增长最快、并发写最痛） |
| D3 Postgres profile | 补全 C 层覆盖（workflows/approvals/api_keys/audit 的 Postgres 后端），用同一 Store 接口抽象；docker-compose 即生产参考部署 |
| D4 backend/local 定位 | 升级为"默认存储引擎"（D1/D2 的落点），不再是孤立子系统 |
| D5 Qdrant/Redis | 维持可选（URL 为空即禁用），文档如实标注"生产建议启用" |
| D6 Neo4j | 实为依赖注入式可选集成（4 个文件，driver 未注入即静默降级；driver 不在 requirements，无真实使用/测试痕迹）。建议：从主文档技术栈清单中移除 Neo4j，代码标注 experimental；记忆图谱默认由 memory_graph（进程内/Postgres）承担 |
| D7 数据目录治理 | `data/` 加 .gitignore 强校验 + 启动时体积告警（>100MB 提示轮转），杜绝 344MB 事故重演 |

## 4. 影响面

- README/CLAUDE.md/docs：按 D1-D6 统一口径（T2 已做第一步）
- 代码改动集中在 `settings.py`、`dependencies.py`、`backend/local/`，属 M2 阶段工作，
  不阻塞 P0 其他任务
- 测试：迁移逻辑需新增测试；现有 4179 测试大多用临时 JSONL 路径，D2 第二阶段才需要改

## 5. 待用户决策

> **2026-09-20 用户批复：D1-D7 按建议整体采纳。** 实施排期：D7（数据目录治理）与文档口径
> 统一可随 P0/P1 落地；D1/D2/D4（SQLite 迁移）属 M2 阶段工作；D3（Postgres profile 补全）
> 属 M2-M3；D5 维持现状；D6 随下次文档修订执行。

- [x] D1-D7 采纳（用户 2026-09-20 拍板）
- [x] D2 迁移优先级：audit/runs 先行（随 D1-D7 一揽子采纳）
- [x] Neo4j 从主文档技术栈清单移除、代码标 experimental（随 D6 采纳）
