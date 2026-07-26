# 前端孤儿组件归档 — 2026-07-26

审计 B11/B12/B14 处置记录。所有文件保留原始相对路径（frontend/src/... 前缀）。

## 归档清单与处置原因

| 文件 | 原路径 | 处置原因 |
|---|---|---|
| StreamingDashboard.tsx | frontend/src/components/streaming/ | 无任何 import 方；且自身 import 路径损坏（`./StreamingOutput`、`./streaming/TaskProgressBar` 均指向不存在的位置）。后端 streaming_router 虽已挂载，但组件无消费方、不可用，归档待后续需要时重建。 |
| TaskTimeline.tsx | frontend/src/components/streaming/ | 仅被孤儿子 StreamingDashboard 引用，连带归档。 |
| LiveMetrics.tsx | frontend/src/components/streaming/ | 同上，仅被 StreamingDashboard 引用。 |
| TaskProgressBar.tsx | frontend/src/components/streaming/ | 同上，仅被 StreamingDashboard 引用。 |
| RealtimeVisualization.tsx | frontend/src/components/streaming/ | 无任何 import 方，纯孤儿。 |
| apiClient.ts | frontend/src/services/ | 旧版 API 客户端，与现行 `frontend/src/services/api.ts`（App.tsx 及各页面统一使用）重复，仅被自身测试引用。归档以避免双客户端并存。 |
| apiClient.test.ts | frontend/src/__tests__/services/ | 旧 apiClient 的配套测试，随主文件一并归档（否则 tsc 报缺失模块）。 |

注意：`frontend/src/store/apiClient.ts`（APIClient，被 store/agentStore.ts 使用）**不是**孤儿，已核查保留。

## 未归档、交编排者接入的组件

- **AnalyticsDashboard.tsx**（保留在 frontend/src/components/）：调用 `/api/v1/analytics/realtime|costs|performance`，与后端 `backend/app/api/analytics.py` 路由完全匹配；但 main.py 未挂载该 router。
  - 挂载说明：在 `backend/app/main.py` 中 `from backend.app.api.analytics import router as analytics_router`，并在路由注册区追加 `app.include_router(analytics_router)`。
- **Forum.tsx**（保留在 frontend/src/components/）：调用 `/api/v1/forum/posts|comments|users/*`，与 `backend/app/api/forum.py` 路由完全匹配（另 `forum_search.py` 提供 `/api/v1/forum/search`）；main.py 均未挂载。
  - 挂载说明：`from backend.app.api.forum import router as forum_router`、`from backend.app.api.forum_search import router as forum_search_router`，追加两行 `app.include_router(...)`。
- 两组件还需在 App.tsx / Layout.tsx 增加路由入口（编排者职责，本工程师禁改）。
