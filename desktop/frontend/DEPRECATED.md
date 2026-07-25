# DEPRECATED — 技术债标注 (P1-22c, 2026-07-20)

本目录 (`desktop/frontend/`) 是一套独立的 **Vue 3** 前端，与项目主前端
(`frontend/`，React 18 + Vite) 长期分裂、重复建设。

**已做决策（Wave B）：** Tauri 桌面端不再使用本目录，改为直接复用主前端产物：

- `desktop/tauri.conf.json` 的 `build.distDir` 指向 `../frontend/dist`（主 React 前端的构建产物）；
- `build.beforeDevCommand` / `build.beforeBuildCommand` 改为 `npm --prefix ../frontend run dev|build`；
- `build.devPath` 对齐主前端 Vite 端口 `http://localhost:3000`。

**本目录当前状态：** 保留作历史参考（含 e2e 测试资产），**不再参与 Tauri 构建**，
后续应整体移除或迁移其中有价值的测试用例到主前端。移除前请勿在其中新增功能。
