# @xagent/sdk — X-Agent 统一 TypeScript SDK

「五端一核」的契约钉子：**CLI、浏览器扩展、Web 前端、桌面（Tauri 壳复用 frontend）、移动（Expo/RN）** 共同依赖的 backend 核心契约客户端。一处定义、处处复用——backend 契约变更时只需升级本 SDK，而不是五端各自改 HTTP 调用。

- 零运行时依赖（只依赖平台 `fetch` / `ReadableStream`，Node >= 18 / 现代浏览器 / React Native 均内置）
- ESM + UMD 双格式产物（`dist/xagent-sdk.js` / `dist/xagent-sdk.umd.cjs`）+ 完整 `.d.ts`
- 契约类型与 backend 模型 **1:1 镜像**（snake_case 字段名即线上契约，勿改）

## 契约总览

以下每个端点都已对照 backend 实现逐字段确认（括号为 source of truth）：

| 能力 | 端点 | backend 源码 |
| --- | --- | --- |
| 认证 | `x-api-key` 头；Bearer token 回退；无凭证时浏览器 cookie 会话 + CSRF | `backend/app/dependencies.py get_current_principal`、`backend/app/main.py CSRFProtectionMiddleware` |
| 一次性运行 | `POST /api/v1/agents/run` → `AgentRunResponse` | `backend/app/api/agents.py`、`core/contracts.py` |
| 流式运行 | `POST /api/v1/agent/run/stream` → `{run_id, stream_url, trace_id}` | `backend/app/api/streaming.py` |
| 事件流 | `GET /api/v1/agent/stream/{run_id}?since_sequence=N`（SSE） | 同上 |
| 事件信封 | `{event_type, timestamp, run_id, data, sequence}`；细粒度类型 `iteration` / `tool_call` / `tool_result` / `plan` / `observation` / `reflection` / `agent` / `approval_required` + 遗留类型 `message` / `progress` / `completion` / `error` / `heartbeat` 等；**`completion` / `error` 为终止事件，服务端随后关流** | `streaming.py StreamEvent`、`TERMINAL_EVENT_TYPES` |
| 审批 | `GET /api/v1/approvals`、`GET /{id}`、`POST /{id}/approve|reject|execute`（`decided_by` 由服务端绑定，客户端不传） | `backend/app/api/approvals.py`、`core/approvals.py` |
| 断点续跑 | `POST /api/v1/checkpoints/{trace_id}/resume`（+ list/get/delete） | `backend/app/api/checkpoints.py` |
| 沙箱任务 | `POST /api/v1/sandbox/tasks`（fire-and-forget）、`GET /tasks/{id}`、`GET /tasks` | `backend/app/api/sandbox_tasks.py` |
| 健康检查 | `GET /health`（liveness）、`GET /ready`（readiness） | `backend/app/main.py` |
| 错误信封 | `{code, message, request_id, trace_id, details}`；FastAPI `{detail}` 亦做归一化 | `backend/app/api/errors.py` |

认证要点：

- `x-api-key`（bootstrap 管理键或签发的 API key）是**程序化客户端的首选**——服务端对携带有效 key 的请求**豁免 CSRF**。
- Bearer token（auth 会话）同样豁免 CSRF。
- 浏览器 cookie 会话（无上述两种凭证）下，SDK 会在首个写请求前自动 `POST /api/v1/csrf-token` 取令牌并附加 `X-CSRF-Token` 头；遇到 CSRF 403 自动刷新一次并重放。

## 快速开始

```bash
npm install @xagent/sdk   # 仓库内暂以源码/workspace 方式引用
```

```ts
import { XAgentClient, XAgentApiError } from "@xagent/sdk";

const client = new XAgentClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: process.env.XAGENT_API_KEY!, // x-api-key 头；CSRF 豁免
});

// 一次性运行
const result = await client.agents.run({ task: "给 utils 加测试", max_iterations: 10 });

// 流式运行（SSE → AsyncIterable）
const stream = await client.agents.runStream({ task: "给 utils 加测试" });
for await (const event of stream.events) {
  switch (event.event_type) {
    case "plan":             console.log("计划", event.data); break;
    case "tool_call":        console.log("工具", event.data.tool_name); break;
    case "approval_required": console.log("待审批", event.data.approval_id); break;
    case "completion":       console.log("完成", event.data.status); break; // 终止事件，之后迭代自然结束
    case "error":            console.error("失败", event.data.error_message); break;
  }
}

// 审批闭环
const pending = await client.approvals.list({ status: "pending" });
await client.approvals.approve(pending[0]!.id, { reason: "允许" });
await client.approvals.execute(pending[0]!.id);

// 断点续跑 / 沙箱任务 / 健康
await client.checkpoints.resume(traceId, { from_iteration: 3 });
const task = await client.tasks.submit({ name: "ci", command: "pytest -q" });
await client.tasks.pollUntilDone(task.task_id, { intervalMs: 2000 });
await client.health(); // { status: "ok", service: "x-agent" }
```

取消流：给 `runStream`/`subscribeStream` 传 `signal`（`AbortController`），迭代立即结束并释放连接。断线重连：用 `subscribeStream(runId, { sinceSequence: lastSeq })` 续订，不重放已消费事件。

错误处理：所有失败（HTTP 4xx/5xx、网络断开、超时）统一抛 `XAgentApiError`——`status`（网络层失败为 0）、`code`（backend ErrorCode 或 `network_error`/`timeout_error`）、`details`、`requestId`/`traceId`，以及 `isNetworkError` / `isTimeout` / `isAuthError` / `isRetryable` 谓词。

## 各端接入指引

### 浏览器扩展（extension/，background service worker）

```ts
// background.ts — service worker 可能有冷启动，保持 client 轻量（零依赖本身就是为此）
import { XAgentClient } from "@xagent/sdk";

const client = new XAgentClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: (await chrome.storage.local.get("apiKey")).apiKey,
  defaultHeaders: { "x-client": "xagent-extension" },
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "agent.run") {
    client.agents
      .runStream({ task: msg.task })
      .then(async (stream) => {
        for await (const event of stream.events) {
          chrome.runtime.sendMessage({ type: "agent.event", runId: stream.run_id, event });
        }
        sendResponse({ ok: true });
      })
      .catch((error) => sendResponse({ ok: false, message: String(error) }));
    return true; // async sendResponse
  }
});
```

要点：扩展里**始终用 `apiKey`**（header 凭证 CSRF 豁免，不依赖 cookie）；跨源时在 manifest `host_permissions` 里声明 backend 源；SSE 用 `fetch` 流式读取，无需 `EventSource`（无法带自定义头）。

### Web 前端 / 桌面（frontend/，Tauri 壳复用）

```ts
// src/api/xagent.ts — 替换散落的 fetch 调用
import { XAgentClient } from "@xagent/sdk";

export const xagent = new XAgentClient({
  baseUrl: import.meta.env.VITE_API_BASE ?? "",
  // 已登录的浏览器会话（cookie）可不带 apiKey：SDK 自动处理 CSRF token
  credentials: "same-origin",
});

// React 组件里消费事件流
function useAgentStream(task: string) {
  const [events, setEvents] = useState<StreamEventEnvelope[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    xagent.agents
      .runStream({ task }, { signal: controller.signal })
      .then(async (stream) => {
        for await (const event of stream.events) {
          setEvents((prev) => [...prev, event]); // iteration/tool_call/completion...
        }
      })
      .catch(() => undefined);
    return () => controller.abort(); // 组件卸载即断流
  }, [task]);
  return events;
}
```

要点：同源部署（backend 伺服 frontend/dist）下 cookie 会话可用；跨源部署传 `credentials: "include"` 并配好 CORS。桌面端同一份代码（Tauri webview 内 fetch 可用）。

### 移动端（mobile，Expo / React Native）

```ts
import { XAgentClient } from "@xagent/sdk";

const client = new XAgentClient({
  baseUrl: "https://api.x-agent.dev",       // 手机上必须是公网可达的 backend
  apiKey: await secureStore.get("apiKey"),  // expo-secure-storage
  timeoutMs: 60_000,                        // 移动网络更慢，放宽默认 30s
});

// 发任务 + 后台轮询沙箱结果（App 切后台时 SSE 可能被系统掐断）
const stream = await client.agents.runStream({ task });
let lastSequence = 0;
try {
  for await (const event of stream.events) lastSequence = event.sequence;
} catch {
  // 网络切换/回前台：从断点续订，不丢事件
  for await (const event of client.agents.subscribeStream(stream.run_id, {
    sinceSequence: lastSequence,
  })) lastSequence = event.sequence;
}
```

要点：RN 的 `fetch` 原生支持流式响应（Expo SDK 49+ / RN 0.72+）；弱网下结合 `subscribeStream({ sinceSequence })` 做断线续订，配合 `checkpoints.resume` 恢复中断的运行。

## 开发

```bash
cd sdks/typescript
npm install
npm test        # vitest run（58 个用例：认证头/错误归一化/SSE 解析/流终止/CSRF/资源层）
npm run check   # tsc --noEmit
npm run build   # vite build（ESM + UMD）+ tsc --emitDeclarationOnly（.d.ts）
```

测试全部基于 mock fetch / ReadableStream，不依赖运行中的 backend。

### 修改契约时

1. 先改 backend（`backend/app/api/*`、`core/contracts.py` 等）。
2. 同步 `src/types.ts`（字段名保持 snake_case 镜像）与对应资源方法。
3. 补/改测试，`npm test && npm run check && npm run build` 全绿。
4. 升版本、各端升级依赖。
