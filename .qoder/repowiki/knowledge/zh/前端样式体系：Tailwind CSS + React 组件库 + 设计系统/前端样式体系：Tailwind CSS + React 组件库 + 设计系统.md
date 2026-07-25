---
kind: frontend_style
name: 前端样式体系：Tailwind CSS + React 组件库 + 设计系统
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/tailwind.config.js
    - frontend/src/index.css
    - frontend/app-shell.css
    - frontend/postcss.config.js
    - frontend/.prettierrc
    - frontend/package.json
    - frontend/DESIGN_SYSTEM.md
    - frontend/COMPONENT_LIBRARY.md
---

## 1. 使用的系统与工具链
- **构建与打包**：Vite 6（ESM），PostCSS + Autoprefixer，Lightning CSS 作为 CSS 转换器。
- **样式框架**：Tailwind CSS 3.x，通过 `tailwind.config.js` 集中扩展颜色、字体、间距、动画、阴影、圆角、z-index 等设计令牌；darkMode 使用 `class` 策略。
- **运行时样式入口**：`src/index.css` 中通过 `@tailwind base/components/utilities` 注入 Tailwind，并补充全局滚动条、动画 keyframes、无障碍 focus-visible、响应式排版、代码块/表格/print/skeleton 等基础样式。
- **独立深色主题壳**：`app-shell.css` 定义 `:root` 变量（--bg0/--glass/--accent 等）+ 径向渐变背景 + 网格纹理，配合 `color-scheme: dark` 提供沉浸式暗色外壳。
- **代码风格**：Prettier（`.prettierrc`）统一缩进、引号、分号、行宽等格式规则。
- **UI 组件库**：自研 `components/ui/*`（Button/Card/Alert/Input/Modal/DataTable/CircularProgress/LoadingState/EmptyState 等），并通过 `COMPONENT_LIBRARY.md` / `DESIGN_SYSTEM.md` 文档化 API 与设计规范。
- **图标与可视化**：lucide-react 图标库；recharts 图表库。
- **状态与数据层**：Zustand（store）、TanStack React Query（服务端缓存）、Axios（HTTP）。这些虽非样式相关，但决定了 UI 的渲染与交互模式。

## 2. 关键文件与包
- `frontend/tailwind.config.js` — 设计令牌与主题扩展（primary/secondary/success/warning/error/slate 五套色板、字体族、字号、间距、动画、阴影、圆角、z-index 层级）。
- `frontend/src/index.css` — Tailwind 注入 + 全局基础样式（滚动条、动画、focus-visible、响应式排版、代码/表格/print/skeleton 等）。
- `frontend/app-shell.css` — 深色主题 CSS 变量与背景纹理，供 shell 页面使用。
- `frontend/postcss.config.js` — PostCSS 插件链（tailwindcss + autoprefixer）。
- `frontend/.prettierrc` — 统一代码风格配置。
- `frontend/package.json` — 依赖声明（react 18、vite、tailwind、autoprefixer、postcss、lightningcss、zustand、@tanstack/react-query、recharts、lucide-react 等）。
- `frontend/DESIGN_SYSTEM.md` / `COMPONENT_LIBRARY.md` — 设计系统文档与组件库使用指南。
- `frontend/src/components/ui/*` — 基础 UI 组件实现目录。
- `frontend/src/styles/rtl.css` — RTL 语言支持样式。

## 3. 架构与约定
- **原子化优先**：绝大多数布局与视觉样式通过 Tailwind 原子类在 JSX className 中组合，避免手写 CSS；仅在必要处（滚动条、全局动画、打印样式、skeleton、容器查询等）维护少量 CSS。
- **设计令牌集中管理**：所有颜色、字体、字号、间距、圆角、阴影、动画、z-index 均在 `tailwind.config.js` 的 `theme.extend` 中声明，保证跨项目一致性与可替换性。
- **深色模式按 class 切换**：通过 `dark:` 前缀为组件添加深色变体，由外层 `<html>` 或根节点上的 `.dark` 类控制。
- **组件库分层**：`components/ui/*` 暴露通用原子组件，业务组件（如 `ExecutionPanel`、`WorkflowVisualizer`、`StreamingOutput` 等）基于 ui 组件组合而成。
- **无障碍内建**：`index.css` 提供 `focus-visible` 高亮、`prefers-reduced-motion` 降级、`.sr-only` / `.visually-hidden` 辅助类；RTL 通过 `styles/rtl.css` 支撑。
- **国际化与多语言**：`i18n/` 目录 + `useI18n` hook，结合 `dir={isRTL ? 'rtl' : 'ltr'}` 驱动双向文本布局。

## 4. 开发者应遵循的规则
- **样式来源优先级**：优先使用 Tailwind 原子类；需要自定义时，先在 `tailwind.config.js` 中扩展 token，再复用 `text-*` / `bg-*` / `rounded-*` / `shadow-*` 等语义化类，而非直接写死色值。
- **深色模式**：所有新组件必须同时考虑 `.dark` 变体，使用 `dark:bg-*` / `dark:text-*` 等前缀，确保对比度符合 WCAG AA。
- **组件封装**：新增通用 UI 能力应放入 `components/ui/*`，并在 `COMPONENT_LIBRARY.md` 中补充 Props 与示例；业务组件只负责组合，不重复实现基础样式。
- **动画与过渡**：优先使用 `tailwind.config.js` 中已定义的 `animate-*` / `transition-*`；新增动画需在 config 中注册 keyframes 与 animation 别名。
- **无障碍**：按钮/输入/链接等交互元素必须提供 `aria-label` / `aria-describedby` / `role` 等标签；焦点可见性不得被覆盖；尊重 `prefers-reduced-motion`。
- **代码风格**：所有 TSX/TS/JSON/CSS 提交前经 Prettier 格式化，保持单引号、尾逗号、100 列宽度、无 tab 等统一风格。
- **响应式**：采用移动优先策略，使用 Tailwind 断点前缀（sm/md/lg/xl/2xl）逐步增强布局；必要时利用 `container-type` 容器查询做组件级响应式。
- **RTL 语言**：涉及方向性的布局需兼容 `dir="rtl"`，参考 `styles/rtl.css` 中的镜像规则。