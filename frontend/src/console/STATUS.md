# 状态：冻结的未挂载前端子系统（Frozen — never compiled, not mounted）

**评估日期：** 2026-09-20（T12，见 `docs/reports/T12_FRONTEND.md`）

52 个文件（ConsoleShell + console/pages/**、hooks、state）。App.tsx / main.tsx
及 src/ 其余部分**没有任何 import** 指向本目录；代码引用了仓库中不存在的类型
（RealtimeSnapshot、RoleAvatar、DispatchResult 等），`tsc` 从未通过。

已从 tsconfig `exclude`，不参与构建。待用户决策：**删除**（同 backend 僵尸岛
处置）或**补全类型并挂载**。它是 `*_control` 系列 API 的预期消费者——若删除，
docs/API_INVENTORY.md 中 6 个 control 路由的去留需一并复议。
