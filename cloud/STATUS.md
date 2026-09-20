# 状态：冻结的纯文档目录（Frozen docs-only — no code）

**评估日期：** 2026-09-20（T11 外围冻结，见 `docs/decisions/CONVERGENCE_DECISIONS.md`）

## 这是什么
云端服务的**设计文档**（架构 / 数据库 Schema / 部署指南 / OpenAPI 说明），共 11 个 .md，无任何可执行代码。

## 当前定位
- 文档描述的多租户云服务**未实现**；本轮治理确认的存储决策是
  local-first + SQLite（见 `docs/decisions/CONVERGENCE_DECISIONS.md` D1–D7），
  与本目录的云端 Schema 设计**并不一致**，两者并存时以决策文档为准。
- 不参与 CI，不在 v0.2.0-beta 范围内。

## 恢复条件（何时解冻）
多租户/云端部署进入路线图（当前 ROADMAP 无此里程碑）时，先对照实际
backend 实现重写本目录文档，再谈部署。
