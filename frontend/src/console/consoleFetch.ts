/**
 * console 子应用的统一请求入口（凭证注入）。
 *
 * 为什么需要它
 * ============
 * console 各页面此前一律使用**裸 `fetch`**，只设 `Content-Type`，不带任何凭证。
 * 实测（`.workbuddy/tmp/probe_browser_write_path.py`，TestClient 四探针）：
 *
 * | 场景                                    | 结果                                   |
 * |-----------------------------------------|----------------------------------------|
 * | 裸 POST /api/v1/organization/organizations | 403 {"detail":"CSRF token required"} |
 * | 同请求带 x-api-key                       | 201                                    |
 * | 裸 GET  /api/v1/organization/organizations | 401 authentication_failed            |
 * | 裸 GET  /api/v1/workbench                | 200（唯一有 dev 匿名放行的读端点）      |
 *
 * 原因见 `backend/app/main.py` 的 `CSRFProtectionMiddleware.dispatch`：非安全方法
 * 依次尝试 x-api-key / Bearer，都没有才要 `X-CSRF-Token` + `session_id` cookie。
 * 于是浏览器里 console 的**所有写操作都是 403**，而 `/api/v1/organization/*`
 * 的读操作是 401（它走 `get_current_principal`，没有匿名放行）。
 *
 * 凭证来源与仓库既有惯例一致（`PerformanceMonitorPage.tsx`、`GitStatusPanel.tsx`、
 * `RunHistoryPanel.tsx` 都从 localStorage 取 `api_key`）。带 x-api-key 的请求在
 * CSRF 中间件里是**显式豁免**的（自定义头无法被跨站页面伪造），因此不需要再走
 * CSRF token 流程。
 *
 * 后端凭证解析优先级见 `dependencies.get_current_principal`：x-api-key 优先，
 * 其次 Bearer。
 */

/** 本地开发兜底 key（与 `.env` 的 XAGENT_BOOTSTRAP_API_KEY 一致）。 */
const DEV_FALLBACK_API_KEY = "xagent-dev-key-2024";

/**
 * 组装 console 请求的凭证头。
 *
 * - 有 `api_key` ⇒ 带 x-api-key（CSRF 豁免 + 认证）
 * - 有 `auth_token` ⇒ 另外带 Bearer（x-api-key 优先，两者都会被 CSRF 中间件豁免）
 * - 两者都没有 ⇒ 带上本地开发 key。**必须有这个兜底**：不带凭证的写请求是 403、
 *   读请求是 401，console 首屏会整个走不动。
 */
export function consoleAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const apiKey = localStorage.getItem("api_key");
  const token = localStorage.getItem("auth_token");
  if (apiKey) headers["x-api-key"] = apiKey;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!apiKey && !token) headers["x-api-key"] = DEV_FALLBACK_API_KEY;
  return headers;
}

/** 带凭证的 fetch —— console 内所有 `/api/` 调用都应走这里。 */
export function consoleFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...consoleAuthHeaders(),
      ...((init.headers as Record<string, string> | undefined) ?? {}),
    },
  });
}
