# 状态：冻结的外围原型（Frozen peripheral — NOT covered by CI or release gates）

**评估日期：** 2026-09-20（T11 外围冻结，见 `docs/decisions/CONVERGENCE_DECISIONS.md`）

## 这是什么
Rust（`src/*.rs`，Cargo）+ Vue 前端（`frontend/`）的桌面客户端原型。

## 当前定位
- **不参与** CI 门禁（`.github/workflows/ci.yml` 只覆盖 backend/cli/tests）。
- **不包含**在 v0.2.0-beta 发布范围内；核心交付物是 `backend/` FastAPI 服务 + `frontend/` Web 控制台。
- 未验证可构建：本仓库治理阶段（2026-09）没有在 CI 中执行 `cargo build` 或前端打包。
- 它对接的后端 API 面在 W3 收敛中删除了 ~55 个未挂载模块，桌面端如引用这些接口需自行核对 `docs/API_INVENTORY.md`。

## 恢复条件（何时解冻）
1. 后端 API 契约稳定（v0.2.x 之后无破坏性变更一个版本周期）；
2. 增加 desktop 专属 CI job（cargo check + 前端 typecheck）并连续绿色；
3. 有明确维护者认领。

在此之前，此目录按"只读归档"对待：不修 bug、不加功能、不为其调整核心 API。
