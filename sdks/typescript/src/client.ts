/**
 * HTTP base for the X-Agent SDK.
 *
 * Responsibilities (the "contract nails" every consumer relies on):
 *   - baseUrl + path joining + query serialization
 *   - authentication: `x-api-key` header (bootstrap or issued key),
 *     Bearer token fallback (backend/app/dependencies.py get_current_principal)
 *   - CSRF handling for browser session-cookie flows: lazily fetch a token
 *     from POST /api/v1/csrf-token and attach `X-CSRF-Token` on mutating
 *     requests, refreshing once on a CSRF 403 (backend/app/main.py
 *     CSRFProtectionMiddleware). API-key / Bearer requests are CSRF-exempt.
 *   - per-request timeout via AbortController (default 30s, 0 disables)
 *   - error normalization: every failure surfaces as XAgentApiError
 */

import { AgentsResource } from "./agents.js";
import { ApprovalsResource } from "./approvals.js";
import { CheckpointsResource } from "./checkpoints.js";
import { SandboxTasksResource } from "./tasks.js";
import type { HealthStatus, ReadinessStatus } from "./types.js";

/** Subset of RequestCredentials without requiring DOM lib types. */
export type FetchCredentials = "omit" | "same-origin" | "include";

/** Options accepted by {@link XAgentClient}. */
export interface XAgentClientOptions {
  /** Backend origin, e.g. "http://127.0.0.1:8000". Trailing slash tolerated. */
  baseUrl: string;
  /** Value for the `x-api-key` header. CSRF-exempt server-side. */
  apiKey?: string;
  /** Value for the `Authorization: Bearer <token>` header. CSRF-exempt. */
  bearerToken?: string;
  /** Fetch implementation to use. Defaults to global fetch. */
  fetch?: typeof fetch;
  /** Default request timeout in ms. Default 30000; 0 disables. */
  timeoutMs?: number;
  /** Headers attached to every request (can override defaults). */
  defaultHeaders?: Record<string, string>;
  /** Pre-provisioned CSRF token (from POST /api/v1/csrf-token). */
  csrfToken?: string;
  /** RequestCredentials passed to fetch (use "include" for cross-origin cookie sessions). */
  credentials?: FetchCredentials;
}

/** Per-request options. */
export interface RequestOptions {
  /** Query params; undefined/null values are skipped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** JSON-serialized request body. */
  body?: unknown;
  /** Extra headers for this request. */
  headers?: Record<string, string>;
  /** Overrides Accept header. Default "application/json". */
  accept?: string;
  /** Abort signal (cooperates with the timeout controller). */
  signal?: AbortSignal;
  /** Per-request timeout in ms; overrides client default; 0 disables. */
  timeoutMs?: number;
  /** Advanced: skip the automatic CSRF token attach/refresh (used by the token fetch itself). */
  skipCsrf?: boolean;
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Normalized error for every failure mode (HTTP error, malformed body,
 * network failure, timeout). Field names mirror the backend error envelope
 * `{code, message, request_id, trace_id, details}` from
 * backend/app/api/errors.py; FastAPI `{detail}` bodies are also normalized.
 */
export class XAgentApiError extends Error {
  /** HTTP status code. 0 for transport-level failures (network/timeout). */
  readonly status: number;
  /** Backend ErrorCode value, or "network_error" / "timeout_error" from the SDK. */
  readonly code: string;
  /** Backend `details` payload (e.g. validation errors), when present. */
  readonly details: unknown;
  readonly requestId: string | null;
  readonly traceId: string | null;
  readonly method: string;
  readonly url: string;

  constructor(init: {
    message: string;
    status: number;
    code: string;
    details?: unknown;
    requestId?: string | null;
    traceId?: string | null;
    method: string;
    url: string;
    cause?: unknown;
  }) {
    super(init.message);
    this.name = "XAgentApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? null;
    this.requestId = init.requestId ?? null;
    this.traceId = init.traceId ?? null;
    this.method = init.method;
    this.url = init.url;
    if (init.cause !== undefined) {
      (this as { cause?: unknown }).cause = init.cause;
    }
  }

  /** Transport-level failure (server unreachable, DNS, socket reset...). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** SDK-level timeout (per-request or client default). */
  get isTimeout(): boolean {
    return this.code === "timeout_error";
  }

  /** 401/403 from the backend. */
  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  /** Safe to retry (idempotent transport failures and 429/5xx). */
  get isRetryable(): boolean {
    if (this.status === 0) return true;
    return this.status === 429 || this.status >= 500;
  }
}

/** Error body shapes the backend can produce. */
interface BackendErrorBody {
  code?: unknown;
  message?: unknown;
  request_id?: unknown;
  trace_id?: unknown;
  details?: unknown;
  detail?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function toApiError(response: Response, method: string, url: string): Promise<XAgentApiError> {
  const raw = await response.text().catch(() => "");
  let parsed: unknown = undefined;
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = undefined;
    }
  }

  if (isRecord(parsed)) {
    const body = parsed as BackendErrorBody;
    // Structured envelope: backend/app/api/errors.py ErrorResponse
    if (typeof body.code === "string" || typeof body.message === "string") {
      return new XAgentApiError({
        message: typeof body.message === "string" ? body.message : response.statusText || "Request failed",
        status: response.status,
        code: typeof body.code === "string" ? body.code : "http_error",
        details: body.details,
        requestId: typeof body.request_id === "string" ? body.request_id : null,
        traceId: typeof body.trace_id === "string" ? body.trace_id : null,
        method,
        url,
      });
    }
    // FastAPI HTTPException / CSRF middleware: {"detail": "..."}
    if (typeof body.detail === "string") {
      return new XAgentApiError({
        message: body.detail,
        status: response.status,
        code: response.status === 403 && /csrf/i.test(body.detail) ? "csrf_error" : "http_error",
        details: parsed,
        method,
        url,
      });
    }
  }

  return new XAgentApiError({
    message: raw ? raw.slice(0, 500) : response.statusText || `HTTP ${response.status}`,
    status: response.status,
    code: "http_error",
    details: parsed,
    method,
    url,
  });
}

/** Combine signals without AbortSignal.any (needs Node >= 20). */
function combineSignals(signals: AbortSignal[]): { signal: AbortSignal; cleanup(): void } {
  const controller = new AbortController();
  const cleanups: Array<() => void> = [];
  for (const source of signals) {
    const forward = () => controller.abort(source.reason);
    if (source.aborted) {
      forward();
    } else {
      source.addEventListener("abort", forward, { once: true });
      cleanups.push(() => source.removeEventListener("abort", forward));
    }
  }
  return { signal: controller.signal, cleanup: () => cleanups.forEach((fn) => fn()) };
}

/**
 * Core HTTP client. Instantiate one per backend origin + credential pair and
 * reuse it; resources (`agents`, `approvals`, ...) hang off it.
 */
export class XAgentClient {
  private readonly baseUrl: string;
  private apiKey: string | undefined;
  private bearerToken: string | undefined;
  private csrfToken: string | undefined;
  private readonly fetchFn: typeof fetch;
  private readonly timeoutMs: number;
  private readonly defaultHeaders: Record<string, string>;
  private readonly credentials: FetchCredentials | undefined;

  readonly agents: import("./agents.js").AgentsResource;
  readonly approvals: import("./approvals.js").ApprovalsResource;
  readonly checkpoints: import("./checkpoints.js").CheckpointsResource;
  readonly tasks: import("./tasks.js").SandboxTasksResource;

  constructor(options: XAgentClientOptions) {
    if (!options || !options.baseUrl) {
      throw new TypeError("XAgentClient requires a baseUrl option.");
    }
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.bearerToken = options.bearerToken;
    this.csrfToken = options.csrfToken;
    this.fetchFn = options.fetch ?? globalThis.fetch?.bind(globalThis);
    if (typeof this.fetchFn !== "function") {
      throw new TypeError("No fetch implementation available; pass `fetch` explicitly.");
    }
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.defaultHeaders = { ...(options.defaultHeaders ?? {}) };
    this.credentials = options.credentials;

    this.agents = new AgentsResource(this);
    this.approvals = new ApprovalsResource(this);
    this.checkpoints = new CheckpointsResource(this);
    this.tasks = new SandboxTasksResource(this);
  }

  /** Backend origin this client points at. */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /** Swap the API key (e.g. after rotation). */
  setApiKey(apiKey: string | undefined): void {
    this.apiKey = apiKey;
  }

  /** Swap the bearer token (e.g. after refresh). */
  setBearerToken(token: string | undefined): void {
    this.bearerToken = token;
  }

  /** Set / clear a pre-provisioned CSRF token. */
  setCsrfToken(token: string | undefined): void {
    this.csrfToken = token;
  }

  /**
   * Fetch and cache a CSRF token from POST /api/v1/csrf-token.
   * Only needed for browser session-cookie flows — x-api-key / Bearer
   * requests are CSRF-exempt server-side. Exported for advanced use;
   * mutating requests without credentials fetch one automatically.
   */
  async ensureCsrfToken(forceRefresh = false): Promise<string> {
    if (this.csrfToken && !forceRefresh) return this.csrfToken;
    const body = await this.request<{ csrf_token?: string }>("POST", "/api/v1/csrf-token", {
      skipCsrf: true,
    });
    if (!body || typeof body.csrf_token !== "string") {
      throw new XAgentApiError({
        message: "CSRF token endpoint returned an unexpected payload.",
        status: 0,
        code: "network_error",
        method: "POST",
        url: `${this.baseUrl}/api/v1/csrf-token`,
      });
    }
    this.csrfToken = body.csrf_token;
    return this.csrfToken;
  }

  /** GET /health — liveness probe ({status: "ok"|"draining", service}). */
  async health(signal?: AbortSignal): Promise<HealthStatus> {
    return this.request("GET", "/health", { signal, timeoutMs: 10_000 });
  }

  /** GET /ready — readiness probe with per-component status. */
  async ready(signal?: AbortSignal): Promise<ReadinessStatus> {
    return this.request("GET", "/ready", { signal, timeoutMs: 15_000 });
  }

  /**
   * Perform a JSON request and return the parsed body.
   * Throws {@link XAgentApiError} on any failure. Advanced: prefer the
   * resource methods (agents/approvals/...) over calling this directly.
   */
  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const { response, url } = await this.execute(method, path, options);
    if (!response.ok) {
      throw await toApiError(response, method, url);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch (error) {
      throw new XAgentApiError({
        message: "Response body was not valid JSON.",
        status: response.status,
        code: "http_error",
        details: text.slice(0, 500),
        method,
        url,
        cause: error,
      });
    }
  }

  /**
   * Perform a request meant for streaming (SSE). Returns the raw Response
   * after verifying it is ok; errors are normalized to {@link XAgentApiError}.
   * No overall timeout is applied by default (streams are long-lived).
   */
  async requestStream(method: string, path: string, options: RequestOptions = {}): Promise<Response> {
    const { response, url } = await this.execute(method, path, {
      accept: "text/event-stream",
      timeoutMs: 0,
      ...options,
    });
    if (!response.ok) {
      throw await toApiError(response, method, url);
    }
    return response;
  }

  private buildUrl(path: string, query: RequestOptions["query"]): string {
    let url = this.baseUrl + (path.startsWith("/") ? path : `/${path}`);
    if (query) {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      }
      const qs = params.toString();
      if (qs) url += `?${qs}`;
    }
    return url;
  }

  private async execute(
    method: string,
    path: string,
    options: RequestOptions,
    allowCsrfRetry = true,
  ): Promise<{ response: Response; url: string }> {
    const url = this.buildUrl(path, options.query);
    const headers: Record<string, string> = {
      Accept: options.accept ?? "application/json",
      ...this.defaultHeaders,
      ...(options.headers ?? {}),
    };

    const hasBody = options.body !== undefined;
    if (hasBody) {
      headers["Content-Type"] ??= "application/json";
    }
    if (this.apiKey) {
      headers["x-api-key"] = this.apiKey;
    }
    if (this.bearerToken) {
      headers["Authorization"] = `Bearer ${this.bearerToken}`;
    }

    // CSRF: only browser session-cookie flows (no header credential) need it.
    const needsCsrf =
      !options.skipCsrf &&
      MUTATING_METHODS.has(method.toUpperCase()) &&
      !this.apiKey &&
      !this.bearerToken;
    if (needsCsrf) {
      if (!this.csrfToken) {
        await this.ensureCsrfToken();
      }
      if (this.csrfToken) {
        headers["X-CSRF-Token"] = this.csrfToken;
      }
    }

    const timeoutMs = options.timeoutMs !== undefined ? options.timeoutMs : this.timeoutMs;
    const signals: AbortSignal[] = [];
    if (options.signal) signals.push(options.signal);
    let timedOut = false;
    let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
    let timeoutSignal: AbortSignal | undefined;
    if (timeoutMs > 0) {
      const controller = new AbortController();
      timeoutSignal = controller.signal;
      signals.push(timeoutSignal);
      timeoutHandle = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
    }
    const combined = signals.length
      ? combineSignals(signals)
      : { signal: undefined as AbortSignal | undefined, cleanup: () => undefined };

    try {
      const response = await this.fetchFn(url, {
        method: method.toUpperCase(),
        headers,
        body: hasBody ? JSON.stringify(options.body) : undefined,
        signal: combined.signal,
        credentials: this.credentials,
      });

      // CSRF 403 (expired token / server restart): refresh once and replay.
      if (
        response.status === 403 &&
        needsCsrf &&
        allowCsrfRetry &&
        this.csrfToken
      ) {
        const peek = response.clone();
        const text = await peek.text().catch(() => "");
        if (/csrf/i.test(text)) {
          await this.ensureCsrfToken(true);
          return this.execute(method, path, options, false);
        }
      }

      return { response, url };
    } catch (error) {
      if (error instanceof XAgentApiError) throw error;
      if (error instanceof Error && error.name === "AbortError") {
        if (timedOut) {
          throw new XAgentApiError({
            message: `Request timed out after ${timeoutMs}ms (${method} ${path}).`,
            status: 0,
            code: "timeout_error",
            method,
            url,
            cause: error,
          });
        }
        // Consumer-initiated abort: propagate the raw AbortError so callers
        // can distinguish deliberate cancellation from failures.
        throw error;
      }
      throw new XAgentApiError({
        message: error instanceof Error ? error.message : String(error),
        status: 0,
        code: "network_error",
        method,
        url,
        cause: error,
      });
    } finally {
      if (timeoutHandle !== undefined) clearTimeout(timeoutHandle);
      combined.cleanup();
    }
  }
}
