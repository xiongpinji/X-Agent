# 业务连续性与灾备策略 (BCP/DR Policy)

| 字段 | 值 |
|---|---|
| 文档编号 | XA-POL-006 |
| 版本 | 1.0 |
| 生效日期 | 2026-07-21 |
| TSC 映射 | CC7.1 - CC7.2 |

## 1. 目标

| 指标 | 目标值 |
|---|---|
| RPO (恢复点目标) | ≤ 1 小时 |
| RTO (恢复时间目标) | ≤ 4 小时 |
| 可用性 SLA | ≥ 99.9% |

## 2. 备份策略

- PostgreSQL: 每日 pg_dump + WAL 归档
- Qdrant: 官方快照 API 每日备份
- 配置: Git 版本化
- 备份验证: 月度恢复演练

## 3. 高可用架构

- 多副本部署 (≥ 3 replicas)
- 健康检查: /health + /ready
- 自动故障转移: K8s liveness/readiness probes
- 金丝雀发布: 异常自动回滚

## 4. 灾备演练

- 频率: 半年度
- 范围: 全栈恢复 (数据库 + 向量库 + 应用)
- 记录: 演练报告 + 改进项跟踪

---
*技术实现: deployment/backup/, disaster-recovery/*
