# Qdrant 恢复演练记录 (P1-17)

**首次演练日期**: 2026-07-26
**执行方式**: mock HTTP 服务演练(本机无真实 Qdrant 实例, localhost:6333 无响应)

## 诚实声明

本次演练**未**针对真实 Qdrant 集群执行。本机 readiness 历史上虽显示 qdrant ok,
但 2026-07-26 当日 `localhost:6333` 无服务监听, 故按预案采用 mock 路径:
用实现官方快照 API 语义的 mock HTTP 服务
(`disaster-recovery/scripts/mock-qdrant-server.py`) 真实走通
`deployment/backup/backup.sh` 的快照备份流程与
`disaster-recovery/scripts/restore-qdrant.sh`(本次新增) 的恢复流程。
pg_dump / redis-cli 本机不存在, 以 stub 替代(仅用于不阻断 backup.sh 的前序步骤,
Qdrant 快照链路本身是与 mock 服务的真实 HTTP 交互)。**真实集群演练仍为待办**,
RTO/RPO 实测值仅在 mock 环境下有效, 不代表生产量级数据下的表现。

## 演练流程与结果 (2026-07-26)

| 步骤 | 操作 | 结果 | 证据 |
|------|------|------|------|
| 1 | mock Qdrant 启动, 预置集合 `xagent_memory` = 42 points | ✅ | `evidence/qdrant-drill-2026-07-26/mock1.log` |
| 2 | `backup.sh` 自动发现集合并走官方快照 API(POST /collections/{name}/snapshots → GET 下载) | ✅ 快照 51 bytes, `backup exit=0` | `evidence/qdrant-drill-2026-07-26/backup.log`, `backups/20260726_164754/` |
| 3 | manifest 校验: qdrant 段 method=snapshot-api 且快照文件登记 | ✅ python json 断言通过 | `backups/20260726_164754/manifest.json` |
| 4 | 灾难模拟: 杀进程 + 清空数据目录, 重启空实例 → `xagent_memory` 返回 404 | ✅ | 演练日志 |
| 5 | `restore-qdrant.sh` 经官方 upload API(POST /collections/{name}/snapshots/upload) 恢复快照 | ✅ | 演练日志 |
| 6 | 校验: `GET /collections/xagent_memory` → points_count=42, 与备份前一致 | ✅ VERIFY PASS | 演练日志 |

**实测耗时 (mock 环境)**: 备份(含 stub pg_dump/redis-cli 全链路) ≈1s; 恢复+校验 ≈1s。

## RTO/RPO 标注

DISASTER_RECOVERY_PLAN.md 中的 RTO(<1h)/RPO(向量库 <10min) 为**目标值**。
本次演练新增实测值字段如下(仅 mock 环境, 生产量级待真实集群演练回填):

| 指标 | 目标值 | 演练实测值 | 实测环境 | 实测日期 |
|------|--------|-----------|---------|---------|
| Qdrant 单集合恢复耗时 (RTO 分量) | —(隶属整体 RTO <1h) | ≈1s + 校验 | mock (51B 快照) | 2026-07-26 |
| Qdrant 备份耗时 (影响 RPO 可达性) | 快照频率支撑 RPO <10min | ≈1s | mock | 2026-07-26 |
| 真实集群 RTO/RPO 实测 | <1h / <10min | **待实测** | 需真实 Qdrant + 生产量级数据 | — |

---

## 演练记录模板 (后续每次演练复制填写)

**演练编号**: DR-QDRANT-YYYY-NNN
**演练日期**:
**执行人**:
**环境**: 真实集群 / mock (注明地址与数据量级)
**备份产物路径**:

| 步骤 | 操作 | 预期 | 实际 | 通过? |
|------|------|------|------|-------|
| 备份 | backup.sh 快照 API 全链路 | 快照文件 + manifest 登记 | | |
| 灾难 | 删除集合/清空数据 | 集合 404 | | |
| 恢复 | restore-qdrant.sh 上传快照 | exit 0 | | |
| 校验 | points_count/抽样向量一致 | 与备份前一致 | | |

**实测值回填**: 备份耗时 ___s; 恢复耗时 ___s; 校验耗时 ___s; 数据量级 ___
**偏差与改进**:
