# T12 前端构建与类型检查报告

**日期：** 2026-09-20 · **结果：** `npm run build`（tsc && vite build）**绿色** ✅（1445 模块，React bundle 正常产出）

## 重大发现：一个目录，两个互不接线的前端

1. **生产 UI = `frontend/index.html`**：314 行 vanilla JS 单文件中文控制台。
   后端 `settings.static_dir = frontend/`，`GET /` 直接返回它（startup.html 优先，
   chat.html 亦被引用，均存在）。这是当前真实交付的用户界面。
2. **React 应用 = `frontend/src/`**：约 150 文件的 TypeScript React 工程，
   **从未接线**——原 index.html 没有 `<script type="module" src="/src/main.tsx">`，
   vite 构建只会拷贝 vanilla 控制台（"3 modules transformed"），React 树根本
   不参与构建，也从未被任何部署路径服务过。

**处置（不静默翻转产品形态）**：新增独立入口 `app.html`，vite 多页构建
（`input: {main: index.html, app: app.html}`）→ dist 同时含 vanilla 控制台与
React bundle（dist/app.html）。是否把 React 应用切换为生产 UI（后端静态服务
指向 frontend/dist）是**产品决策，留给用户/M2**，见 §5。

## 修复清单（构建从完全不可用 → 绿色）

### 依赖与配置
- `package.json`：移除幻觉依赖 `zustand-persist@^1.0.0`（npm 上该包只有 0.4.0，
  `npm install` 直接 ETARGET 失败；代码实际用 zustand 内置 persist 中间件，从未 import 它）
- `vite.config.ts`：**重写**。原文件引用 5 个未安装插件/工具（vite-plugin-compression、
  rollup-plugin-visualizer、@babel/plugin-proposal-decorators、terser、lightningcss），
  `rollupOptions` 键重复出现两次（后者静默覆盖前者），terser 选项嵌错在 react() 插件里——
  该构建从第一天起就不可能运行。压缩交给生产反代层。
- `tsconfig.node.json`：补齐（被 tsconfig.json 引用但文件缺失，标准 Vite 模板件）

### 代码修复（挂载树）
- `AnalyticsDashboard.tsx` 第 1 行是 **Python 三引号 docstring**（生成痕迹）→ JS 注释
- `ToolsPage.tsx`：lucide-react 0.294 无 `Toggle2` → `ToggleLeft`
- `main.tsx`：`window.__ANALYTICS__` 无类型 → 新增 `src/globals.d.ts` 全局声明
- `hooks/index.ts`：React UMD 全局引用 → 显式 import
- `performanceMonitor.ts`：LCP 条目 renderTime/loadTime 类型断言
- `services/api.ts`：**memory 客户端与后端现实对齐**（详见下节）

### api.ts ↔ 后端 memory API 错配（已知债务清偿）
后端（backend/app/api/memory.py，append-only 设计，修订走 revision+rollback）：
- `GET /memory/search?q=` → 后端是 **POST** /memory/search {query, top_k} → 已改为 POST
- `GET /memory`（分页列表）→ 后端无此路由 → 改为 GET /memory/export 取 bundle 客户端分页
- `PUT /memory/{id}`、`DELETE /memory/{id}` → **后端不存在**（append-only 设计使然）
  → 客户端方法改为抛出明确错误（原先运行时静默 405），UI 调用侧已有错误展示
- 字段映射：后端 snake_case MemoryItem（含 layer）→ 前端 camelCase Memory（type=`L{layer}`）

### 冻结排除（tsconfig exclude，不删除）
- `src/console/`（52 文件）：**未挂载孤岛**——App.tsx/main.tsx 无任何 import 指向它，
  引用大量不存在的类型（RealtimeSnapshot、RoleAvatar、DispatchResult…），从未编译通过。
  它是 `*_control` 系列 API 的预期消费者；若未来删除，API_INVENTORY 中 6 个 control
  路由去留需一并复议。见 `frontend/src/console/STATUS.md`
- `src/**/__tests__/`：无测试运行器（vitest/jest 均不在 package.json），文件不可执行
- 16 个未挂载 aspirational 孤岛（无挂载树 import，部分从未编译）：components/streaming、
  components/feedback、Forum、AnalyticsDashboard*、ExecutionPanel、AgentWorkspace、
  FeedbackDashboard、OptimizedDashboard、OptimizedTasksPage、agentStore、sseClient、
  serviceWorker、pwaManager、pushNotificationManager、performanceOptimizer
  （*AnalyticsDashboard 语法错误已修，但仍无人挂载）

类型检查棘轮：`noUnusedLocals/noUnusedParameters` 关闭（48 处历史违例，属 ESLint 管辖，
不应阻断构建）。`strict: true` 保留。

## 构建产物（dist/）
vanilla 控制台 index.html（32KB）+ React：app.html、vendor-react 160KB(gzip 52KB)、
5 个懒加载页面 chunk、app CSS 50KB。挂载树 5 路由（Dashboard/Chat/Tasks/Tools/Memory）。

## 遗留决策（需用户）
1. React 应用是否升级为生产 UI（后端 static 服务 → frontend/dist，路由回退到 app.html）？
2. src/console 与 16 个孤岛：删除（同后端僵尸岛处置）还是补全挂载？
3. memory PUT/DELETE：接受 append-only 现状（前端已改为明确报错），还是为后端增补
   基于 revision 的"逻辑删除/更新"端点？
