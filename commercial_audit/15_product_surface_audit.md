# 产品形态完成度审计报告（面向终端用户）

- **角色标签**：产品形态审计员
- **任务范围**：审计 X-Agent 面向终端用户的产品形态完成度，覆盖 `frontend/`（React/Vite 应用）、`desktop/`（打包与启动脚本）、`mobile/`、`extension/`（浏览器扩展）、`locales/`（i18n）、可访问性与移动端支持文档的落实情况；回答核心问题：**付费客户拿到手能否开箱即用？**
- **审计日期**：2026-07-19
- **审计方法**：逐文件阅读源码、配置与文档，所有结论附路径:行号证据；严格区分"文档宣称"与"代码实际实现"。

---

## 一、竞品产品形态基准（调研类，含来源）

作为"完整商用交付"的参照系，先看竞品在 2026 年的产品形态覆盖：

**OpenAI Codex（截至 2026 年中）**：同一 Agent 覆盖至少 7 个可用形态——macOS/Windows 桌面应用、云端 Web（chatgpt.com/codex）、IDE 扩展（VS Code/Cursor/Windsurf/JetBrains）、开源 CLI（Apache-2.0，Rust 实现，可经 Homebrew/npm 安装）、Chrome 扩展（2026-05-07 发布）、iOS 应用、ChatGPT for Excel 集成，外加 `codex mcp-server` 模式可被其他 Agent 调用。所有形态均已发布且真实可用。
来源：[OpenAI Codex Review (May 2026), future-stack-reviews.com, 2026-07-14](https://future-stack-reviews.com/codex-review/)；[Morph AI: OpenCode vs Codex CLI, 2026-07-06](https://www.morphllm.com/comparisons/opencode-vs-codex)；[techjacksolutions.com Codex Guides, 2026-06-16](https://techjacksolutions.com/ai-tools/openai-codex/)

**Hermes Agent（Nous Research）**：公开定位为"持久化自主 Agent，具备记忆进化能力"，但业界评价其"部署复杂、生产稳定性验证中"。公开渠道未检索到其官方商用桌面/移动/扩展形态的确切发布信息，本报告标注为**待验证/不确定**。
来源：[CSDN: 2025-2026 AI Agent 开发岗面试真题（含框架对比）, 2026-05-09](https://blog.csdn.net/weixin_43726381/article/details/160897821)（二手来源，可信度有限）

**基准结论**：商用水准的"多形态"意味着每个形态都**可安装、可启动、核心流程可用**。下文以此为标尺衡量 X-Agent。

---

## 二、总体判断（先说结论）

**付费客户无法开箱即用。** X-Agent 宣称的四大终端形态（Web/桌面/移动/浏览器扩展）中，没有任何一个达到"可安装、可启动、核心流程走通"的商用标准：

| 形态 | 宣称 | 实际状态 | 完成度估计 |
|---|---|---|---|
| Web 前端 | React 18 + Vite 现代化 UI（frontend/README.md:38-57） | React 应用无 HTML 入口、从未构建；实际服役的是两个静态原生 JS 页面，且其中多个 API 调用与后端路由不匹配 | 可用面 ~30%，React 代码 0% 可达 |
| 桌面端 | Tauri + Vue3 跨平台桌面应用（desktop/README.md:1-3） | 图标缺失 + Tauri 配置 v1/v2 混用 → 无法构建；启动脚本实际只是"启动后端 + 打开浏览器" | ~15% |
| 移动端 | Expo/React Native，iOS + Android（mobile/README.md） | 依赖名错误、缺依赖、无入口文件、原生工程各只有 1 个文件、密钥全为占位符 → 完全不可构建 | ~10%（仅有 UI 源码草稿） |
| 浏览器扩展 | Chrome MV3 扩展，含 Web Store 上架文档 | 图标文件缺失（Chrome 拒绝加载）、原生消息宿主配置为模板占位符、构建脚本引用的 webpack 配置不存在 | ~35%（JS 逻辑较完整但不可安装） |
| i18n | 10+ 语言、RTL 支持（frontend/src/i18n/config.ts:4） | 前端翻译仅 6 语言且只接在"孤儿" React 应用上；实际服役的静态 UI 为硬编码中文 | ~20% |
| 可访问性 | WCAG 2.1 AA（frontend/ACCESSIBILITY.md:5） | aria 属性仅存在于未被使用的 React 组件；实际服役页面 aria 为 0~1 处 | ~10% |

---

## 三、Web 前端（frontend/）详细发现

### 3.1 核心问题：React 应用是"孤儿代码"，没有任何入口

1. `frontend/package.json:6-13` 定义了标准 Vite 脚本（`dev`/`build`），`frontend/src/main.tsx:70` 要求页面存在 `id="root"` 的挂载点。
2. **但 `frontend/index.html`（全 316 行）不含 `<div id="root">`，也不含 `<script type="module" src="/src/main.tsx">`**——它是 2026-06 后改为的一个纯原生 JS 静态控制台（内联 `<script>`，index.html:183-314）。对 `frontend/*.html` 全局检索 `main.tsx|id="root"` 的结果为 **0 匹配**。
3. `frontend/dist/` 目录不存在 → 该 React 应用从未被构建过。
4. 后果：`frontend/src/` 下的全部 React 代码——5 个页面（`src/pages/`：Dashboard/ChatPage/TasksPage/ToolsPage/MemoryPage）、20+ 组件、zustand store、websocket 服务、i18n 体系——**无法通过 `npm run dev` 或 `npm run build` 到达用户浏览器**。Vite 以 index.html 为入口，入口不引用 src，src 即为死代码。
5. 更严重的是 `frontend/src/console/ConsoleShell.tsx`（570 行）——一个含 28 个子页面（agents/audit/chat/execution/graph/marketplace/meetings/memory/navigation/organization/overview/roles/templates/tools/workflow，见 `src/console/pages/` 目录列表）的完整控制台应用，**全仓库无任何文件 import 它**（`grep -rn "ConsoleShell" frontend/src` 仅命中其自身定义文件）。

### 3.2 实际服役的 UI：两个静态原生 JS 页面

后端直接以静态文件方式提供页面（`backend/app/main.py:335-338` 挂载 frontend 目录；`main.py:658-662` 根路径返回 `startup.html`→刷新至 `index.html`；`main.py:653-654` `/chat` 返回 `chat.html`）：

- **`frontend/index.html`（316 行）**：原生 JS 控制台，含记忆/组织架构/自我进化/Agent 工作台四个页签。存在多处**前端调用与后端路由不匹配**：
  - 调用 `GET /api/v1/memory/count`（index.html:192）——后端 `backend/app/api/memory_enhanced.py:24` 路由前缀为 `/api/v1/memory`，其端点只有 `/store /recall /search /relate /related /merge /stats /sync`（memory_enhanced.py:151-373），**无 `/count`** → 首屏记忆总览必失败。
  - 调用的 `/api/v1/org/organizations`（index.html:201 ↔ backend/app/api/org.py:81）、`/api/v1/evolution/summary`（index.html:211 ↔ backend/app/api/evolution.py:12）、`/api/v1/agent/runs`（index.html:225 ↔ backend/app/api/agent.py:150-151）匹配，这部分可用。
  - index.html:158 默认 `agentBaseUrl` 为 `http://127.0.0.1:8003`，而 index.html:185 的 `api()` 默认 `http://127.0.0.1:8000`，两个默认值并存，容易混淆。
- **`frontend/chat.html`（1107 行）**：功能更全的聊天/运行/API Key/审计页面，但同样存在路由漂移：
  - 调用 `/api/v1/security/api-keys`（chat.html:869）——后端实际路由是 `/api/v1/api-keys`（backend/app/api/api_keys.py:31），**全后端无 `security/api-keys`** → API Key 管理功能整体失效。
  - 调用 `/api/v1/memory/layers`（chat.html:813）与 `/api/v1/memory/consolidate`（chat.html:842）——后端均无此端点（检索 0 匹配）→ 对应功能失效。
  - 可用的：`/api/v1/agents/run`（chat.html:703 ↔ backend/app/api/agents.py:128）、`/api/v1/agents/runs`（chat.html:768 ↔ agents.py:171）、`/api/v1/tools`（chat.html:848 ↔ backend/app/api/tools.py:10）、`/api/v1/audit-logs`（chat.html:916 ↔ backend/app/api/audit.py:12）。
- 鉴权注意：上述 agent 接口要求 `Principal`（backend/app/api/agent.py:16, 96）；无凭证时仅开发模式回落匿名主体（backend/app/dependencies.py:232-237），**生产模式（app_mode=production）下匿名访问会被 401 拒绝**（dependencies.py:232-235），而两个静态页面均无任何登录/Token 输入 UI（chat.html 全文无 login/token 字段，仅有 API Key 管理面板——恰好该面板调用的路由是错的）。即生产部署下静态控制台的核心按钮会全部 401。

### 3.3 工程化与文档宣称的落差

- `frontend/README.md:38-47` 宣称 Dashboard/Chat/Tasks/Tools/Memory 五大功能 + 主题 + 响应式 + WebSocket 实时——这些只存在于不可达的 React 代码中（`src/App.tsx:62-67` 路由定义）。**文档宣称 ≠ 用户可用**。
- `frontend/jest.config.js` 存在且 `src/__tests__/` 有测试文件，但 `package.json:6-13` 的 scripts 中**没有 `test` 脚本** → 测试无法通过 npm 运行。
- `frontend/public/` 有 PWA 的 `manifest.json` 与 `sw.js`，但 `index.html`/`chat.html` **均未引用 manifest、未注册 ServiceWorker**（grep 0 匹配）；注册逻辑只在 React 的 `src/serviceWorker.ts`/`main.tsx` 中（不可达）。PWA 宣称不成立。
- 亮点（如实记录）：`vite.config.ts:34-48` 配置了 API/WS 代理、`src/services/api.ts:107-292` 的 ApiClient 封装完整、React 代码本身质量尚可——它们是"半成品资产"，不是"可用产品"。

## 四、桌面端（desktop/）详细发现

1. **技术栈分裂**：`desktop/README.md:1-3` 宣称"Tauri + Vue 3"；`desktop/frontend/package.json` 依赖确为 vue 3 + element-plus；而主前端是 React。**一个仓库两套前端框架**，且 `desktop/frontend/src/App.vue` 与主前端无任何代码共享。
2. **Tauri 配置不可构建**：
   - `desktop/tauri.conf.json:8-32` 使用 Tauri v2 的 `app.windows`/`app.systemTray` 键，而 `:37-115` 又使用 Tauri v1 的 `tauri.allowlist`；`Cargo.toml:10` 依赖 `tauri = "1.5"`（v1）。v1 配置 schema 不识别 `app` 节 → 配置校验失败。
   - `tauri.conf.json:121-126` 引用 `icons/32x32.png` 等 5 个图标文件，但 **`desktop/icons/` 目录不存在** → 打包必然失败。
3. **启动脚本名不副实**：根目录 `start_xagent_desktop.bat` 调用 `scripts/one_click_desktop.py`，其实际行为（one_click_desktop.py:41-58）是 `pip install -e .[dev]` 后用 uvicorn 在 8003 端口起后端，然后 **`webbrowser.open("http://127.0.0.1:8003/")`**——即"桌面模式"= 浏览器打开静态控制台，根本没有 Tauri 应用参与。
4. **打包脚本无产出**：`scripts/package_desktop.py:20-28` 找到 `packaging/xagent-desktop.spec` 时仅打印"请用你的打包器构建"，找不到时打印"应用已可被 PyInstaller/Briefcase 打包"——**不产出任何安装包**。
5. Rust 侧代码（desktop/src/main.rs、ipc.rs、tray.rs、db.rs 等）存在且结构完整，属于无法编译通过的资产。

## 五、移动端（mobile/）详细发现

1. **依赖声明错误，无法安装**：`mobile/package.json:36-38` 声明 `react-navigation`、`react-navigation-bottom-tabs`、`react-navigation-native-stack`——React Navigation v6 的正确包名是 `@react-navigation/native`、`@react-navigation/bottom-tabs`、`@react-navigation/native-stack`；前三个包名在 npm 上或为陈旧 v4 legacy 包，按此声明安装后 `import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'`（mobile/src/navigation/RootNavigator.tsx 用法）必然解析失败。
2. **缺失依赖**：`mobile/src/screens/HomeScreen.tsx:15` 引用 `@expo/vector-icons`，package.json 依赖列表中**没有该包**。
3. **无入口文件**：`package.json:8` 声明 `"main": "index.js"`，但 `mobile/` 下**不存在 index.js**；Expo 亦未配置 `App.tsx` 默认入口（mobile/ 根无 App.tsx/App.js）。
4. **原生工程为空壳**：`mobile/android/` 全目录仅 1 个文件（`app/src/main/java/com/xagent/BiometricAuthModule.kt`）——无 build.gradle、无 AndroidManifest.xml、无 settings.gradle；`mobile/ios/` 仅 1 个 `BiometricAuthModule.swift`——无 Xcode 工程、无 Podfile、无 Info.plist。**这不是"未完成的工程"，是"没有工程"**。
5. **发布配置全占位**：`mobile/app.json:73-77` EAS projectId 为 `"your-project-id"`；`mobile/eas.json:36-42` 的 appleId/ascAppId/appleTeamId/serviceAccount 均为 `"your-..."`/`"path/to/..."` 占位符。
6. `mobile/node_modules` 不存在（从未安装）；`mobile/RELEASE_CHECKLIST.md` 中 Apple Developer 注册等全部为未勾选状态（:11-15）。
7. 如实记录的优点：`mobile/src/` 下 5 个 Screen（Home/Login/Settings/TaskList/WorkflowMonitor）+ navigation + services（apiClient/database/pushNotificationManager/syncManager）+ store 的 TypeScript 源码结构完整，约等于"UI 草稿完成、工程化未开始"。

## 六、浏览器扩展（extension/）详细发现

1. **图标缺失 → Chrome 直接拒绝加载**：`extension/manifest.json:22-26,45-49` 引用 `images/icon-16.png`、`icon-48.png`、`icon-128.png`，但 **`extension/images/` 目录不存在**。Chrome MV3 加载时会对缺失图标报错。
2. **原生消息宿主是模板**：扩展通过 `chrome.runtime.connectNative('com.xagent.extension')` 连接桌面端（extension/mcp-client.js:23），但 `extension/native-messaging-host.json:3-7` 的 `path` 为占位符 `"/path/to/x-agent-native-host"`、`allowed_origins` 为 `"chrome-extension://YOUR_EXTENSION_ID/"`——且仓库内不存在该 native host 的实现程序与安装器 → **扩展 ↔ 桌面端的通道完全未打通**。
3. **构建不可用**：`extension/package.json:14-16` 的 build 脚本调用 `webpack`，但 `extension/` 下**不存在 webpack.config.js**（`ls webpack*` 无结果）→ `npm run build:prod` 无法执行；`package` 脚本（:22）因此也无法产出上架 zip。
4. **占位链接**：`extension/popup.js:405,415-416` 的帮助/官网/文档链接均为 `https://x-agent.example.com` 占位域名。
5. **文档与资产脱节**：extension/ 下有 CHROME_WEBSTORE_CHECKLIST.md、CHROME_WEBSTORE_SUBMISSION_GUIDE.md、PRIVACY_POLICY.md、TERMS_OF_SERVICE.md 等一整套上架文档，但 ASSET_PREPARATION_GUIDE.md 所述截图/图标资产未实际制备（图标目录缺失即证）。
6. 优点：background.js(406 行)/content.js/popup.js(428 行)/storage-manager.js/tab-group-manager.js 等核心逻辑代码量真实存在，manifest 权限声明（manifest.json:6-18）完整，tests/ 有 unit/integration/security 测试文件——属于"逻辑较完整、工程闭环缺失"的状态。

## 七、i18n（locales/ 与 frontend/src/i18n/）

1. **两套翻译并存、互不相通**：
   - 根级 `locales/`：en/es/ja/ko/zh 五个 JSON，各仅 72 行（`wc -l locales/*.json`），内容仅覆盖 common 等浅层键（locales/zh.json:1-30）。其消费方是后端 `backend/app/api/translation_management.py` 与 `backend/app/core/translation_quality.py`，**与前端的 i18n 体系无任何集成证据**。
   - 前端 `frontend/src/i18n/`：translations/ 下 6 个语言文件（ar/en/es/ja/ko/zh），zh.json 含 common/navigation/dashboard/chat/tasks/tools/memory/agents/workflows/settings 等命名空间——但整套体系只被孤儿 React 应用引用（`src/i18n/I18nContext.tsx`、`src/components/LanguageSwitcher.tsx`），**实际服役的 index.html/chat.html 为硬编码中文界面**（index.html:71 "X-Agent 控制台"、:76-79 页签均为写死中文）。
2. **宣称与清单不符**：`frontend/src/i18n/config.ts:4-10` 注释与类型宣称支持 10 种语言（en/zh/ja/ko/fr/de/es/pt/ru/ar）且支持 RTL，但 translations/ 目录仅 6 个文件，fr/de/pt/ru 缺失。
3. 结论：对付费用户而言，**产品界面目前只有中文一种语言**，多语言能力停留在未接线的代码资产层面。

## 八、可访问性与移动端适配文档的落实

1. **可访问性**：`frontend/ACCESSIBILITY.md:5` 宣称"确保符合 WCAG 2.1 AA"，并有 ACCESSIBILITY_GUIDE.md。实际证据：
   - aria 属性仅出现在孤儿 React 的 UI 组件中（`grep aria-|role=`：仅 10 个 .tsx 文件共 27 处，集中在 `src/components/ui/` 的 Modal/Tabs/ProgressBar 等）。
   - **实际服役页面：index.html 0 处 aria，chat.html 仅 1 处**；无 skip-link、无焦点管理、表单控件无 label 关联（index.html:112-126 的组织创建表单全为裸 input+placeholder）。
   - `frontend/package.json:28-43` 无 `eslint-plugin-jsx-a11y`、无 axe-core 等任何 a11y  tooling。
2. **移动端适配**：`frontend/MOBILE_SUPPORT_GUIDE.md:1-4` 自称"v2.0、生产就绪"，内容覆盖 PWA/离线/推送/响应式。实际：
   - `src/hooks/useResponsive.ts:7-30` 的断点/触控尺寸体系存在于孤儿 React 中；
   - 服役的 index.html 仅有一条 `@media (max-width: 980px)` 断点（index.html:66），按钮/输入框未达指南自己宣称的 44px 触控目标；
   - PWA manifest/ServiceWorker 未接线（见 3.3）。
3. 结论：**两份文档描述的能力均未落实到用户实际接触的页面上**，属于"文档先行、实现未跟随"。

## 九、开箱即用判断（付费客户视角）

模拟付费客户的标准动线：

1. 按 README 安装后端 → 启动 → 浏览器打开控制台：**能打开**（index.html），但首屏"记忆总览"因 `/api/v1/memory/count` 404 而空白；Agent 运行在生产模式下 401（无登录 UI）；API Key 管理面板路由错误失效。**核心闭环（发任务→看结果）在开发模式下可部分走通，生产模式下走不通。**
2. 想装桌面客户端：`start_xagent_desktop.bat` 只是再起一次后端并打开浏览器；Tauri 构建因配置与图标缺失直接失败。**无桌面产品。**
3. 想装手机 App：无入口、依赖错误、原生工程空壳、凭证占位。**无移动产品。**
4. 想装浏览器扩展：Chrome 加载即报图标缺失；即便补齐图标，native host 配置是模板、webpack 配置缺失。**无扩展产品。**
5. 非中文用户：界面仅中文。**无国际化产品。**

**总评：当前产品形态完成度约 20%（四大形态仅 Web 的一个静态控制台部分可用，且该控制台自身也有路由漂移与鉴权缺口）。距离 Codex 式"同一 Agent、多形态皆可装可用"的商用水准差距极大；唯一可交付的形态是"后端 + 静态控制台"的开发模式本地体验。**

---

## 十、要点摘要（供整合报告引用）

1. **React 前端整体是不可达的孤儿代码**：frontend/index.html 不含 `id="root"` 与 main.tsx 引用（0 匹配），dist 从未构建；含 28 页的 ConsoleShell（570 行）无任何 import 方——仓库中最重的 UI 资产用户完全看不到。
2. **实际服役 UI 是两个静态原生 JS 页面**（backend/app/main.py:653-662 直出 index.html/chat.html），且存在 4 处前端-后端路由不匹配：`/api/v1/memory/count`（index.html:192）、`/api/v1/memory/layers`、`/api/v1/memory/consolidate`、`/api/v1/security/api-keys`（chat.html:813/842/869）在后端均不存在。
3. **生产模式下静态控制台必然 401**：agent 接口要求 Principal（backend/app/dependencies.py:232-237），而两个页面没有任何登录/凭证输入界面——"开发模式能点、生产模式全挂"。
4. **桌面端 = 假桌面**：Tauri 配置 v1/v2 键混用 + icons 目录缺失导致无法构建；start_xagent_desktop.bat 实为"起后端 + webbrowser.open"（scripts/one_click_desktop.py:41-58）；package_desktop.py 不产出安装包。
5. **移动端完全不可构建**：react-navigation 依赖名错误、缺 @expo/vector-icons、无 index.js 入口、android/ios 原生工程各仅 1 个文件、eas.json 全占位符——仅有约 5 个 Screen 的 UI 源码草稿。
6. **浏览器扩展不可安装**：manifest 引用的 images/ 图标目录缺失（Chrome 拒绝加载）、native-messaging-host.json 为模板占位符、webpack.config.js 缺失导致无法打包；上架文档齐全而资产未备。
7. **i18n 与可访问性文档均未落实**：界面实际仅中文（宣称 10 语言）；WCAG 2.1 AA 宣称 vs 服役页面 0~1 处 aria，无 a11y 工具链；MOBILE_SUPPORT_GUIDE 自称"生产就绪"但 PWA 未接线、仅 1 条媒体查询。
8. **修复杠杆建议（优先级排序）**：① 把 index.html 换回 React 入口或将 React 应用正式接线（一处改动激活全部 UI 资产）；② 统一前端-后端路由契约并补登录/凭证 UI；③ 四形态各做一次"可安装冒烟"（Tauri 修配置补图标、扩展补图标与 webpack 配置、移动端修依赖补入口）后再谈功能完整度。
