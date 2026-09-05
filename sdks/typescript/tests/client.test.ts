import { describe, expect, it } from "vitest";
import { XAgentApiError, XAgentClient } from "../src/client.js";
import {
  errorResponse,
  headersOf,
  jsonResponse,
  mockFetch,
  textResponse,
} from "./helpers.js";

const BASE = "http://api.test.local";

function makeClient(
  overrides: Partial<ConstructorParameters<typeof XAgentClient>[0]> = {},
  fetchImpl?: typeof fetch,
): { client: XAgentClient; mock: ReturnType<typeof mockFetch> } {
  const mock = mockFetch();
  const client = new XAgentClient({
    baseUrl: BASE,
    apiKey: "test-key-123",
    ...(fetchImpl ? { fetch: fetchImpl } : { fetch: mock.fetch }),
    ...overrides,
  });
  return { client, mock };
}

describe("authentication headers", () => {
  it("sends the x-api-key header on every request", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ data: [] }));
    await client.request("GET", "/api/v1/agents");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/agents`);
    expect(headersOf(mock.calls[0])["x-api-key"]).toBe("test-key-123");
  });

  it("sends Authorization Bearer when a bearer token is configured", async () => {
    const { client, mock } = makeClient({ apiKey: undefined, bearerToken: "tok-1" });
    mock.push(jsonResponse({ ok: true }));
    await client.request("GET", "/api/v1/approvals");
    const headers = headersOf(mock.calls[0]);
    expect(headers["authorization"]).toBe("Bearer tok-1");
    expect(headers["x-api-key"]).toBeUndefined();
  });

  it("merges defaultHeaders and lets them override built-ins", async () => {
    const { client, mock } = makeClient({
      defaultHeaders: { "x-client": "extension", Accept: "application/json;v=2" },
    });
    mock.push(jsonResponse({}));
    await client.request("GET", "/health");
    const headers = headersOf(mock.calls[0]);
    expect(headers["x-client"]).toBe("extension");
    expect(headers["accept"]).toBe("application/json;v=2");
    expect(headers["x-api-key"]).toBe("test-key-123");
  });

  it("serializes query params and skips null/undefined values", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse([]));
    await client.request("GET", "/api/v1/approvals", {
      query: { limit: 10, status: "pending", tenant_id: undefined, other: null },
    });
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/approvals?limit=10&status=pending`);
  });

  it("json-encodes the request body with a content-type header", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({}));
    await client.request("POST", "/api/v1/agents/run", { body: { task: "hi" } });
    const headers = headersOf(mock.calls[0]);
    expect(headers["content-type"]).toBe("application/json");
    expect(mock.calls[0].init.body).toBe(JSON.stringify({ task: "hi" }));
  });
});

describe("error normalization", () => {
  it("maps the backend error envelope onto XAgentApiError", async () => {
    const { client, mock } = makeClient();
    mock.push(
      errorResponse(401, {
        code: "authentication_failed",
        message: "Invalid API key.",
        request_id: "req-1",
        trace_id: "trace-1",
        details: { hint: "rotate key" },
      }),
    );
    const error = await client.request("GET", "/api/v1/agents").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(XAgentApiError);
    const apiError = error as XAgentApiError;
    expect(apiError.status).toBe(401);
    expect(apiError.code).toBe("authentication_failed");
    expect(apiError.message).toBe("Invalid API key.");
    expect(apiError.requestId).toBe("req-1");
    expect(apiError.traceId).toBe("trace-1");
    expect(apiError.details).toEqual({ hint: "rotate key" });
    expect(apiError.isAuthError).toBe(true);
    expect(apiError.isRetryable).toBe(false);
    expect(apiError.name).toBe("XAgentApiError");
  });

  it("normalizes FastAPI {detail} bodies (checkpoints 404)", async () => {
    const { client, mock } = makeClient();
    mock.push(errorResponse(404, { detail: "No checkpoints found for trace_id=abc" }));
    const error = (await client.checkpoints
      .get("abc")
      .catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.status).toBe(404);
    expect(error.message).toBe("No checkpoints found for trace_id=abc");
    expect(error.code).toBe("http_error");
  });

  it("normalizes non-JSON error bodies", async () => {
    const { client, mock } = makeClient();
    mock.push(textResponse(502, "Bad Gateway (proxy)"));
    const error = (await client.request("GET", "/health").catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.status).toBe(502);
    expect(error.message).toContain("Bad Gateway");
    expect(error.isRetryable).toBe(true);
  });

  it("converts network failures into XAgentApiError with status 0", async () => {
    const { client, mock } = makeClient();
    mock.push(new TypeError("fetch failed"));
    const error = (await client.request("GET", "/health").catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.status).toBe(0);
    expect(error.code).toBe("network_error");
    expect(error.isNetworkError).toBe(true);
    expect(error.isRetryable).toBe(true);
  });

  it("converts timeouts into timeout_error", async () => {
    const { client, mock } = makeClient({ timeoutMs: 20 });
    // A handler that never settles; only the abort can finish it.
    mock.push(() => new Promise<Response>(() => undefined));
    const error = (await client.request("GET", "/api/v1/agents").catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.isTimeout).toBe(true);
    expect(error.code).toBe("timeout_error");
    expect(error.status).toBe(0);
  });

  it("propagates consumer-initiated aborts as raw AbortError", async () => {
    const { client, mock } = makeClient({ timeoutMs: 0 });
    const controller = new AbortController();
    mock.push(() => {
      controller.abort();
      return new Promise<Response>(() => undefined);
    });
    const error = await client
      .request("GET", "/api/v1/agents", { signal: controller.signal })
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).name).toBe("AbortError");
    expect(error).not.toBeInstanceOf(XAgentApiError);
  });
});

describe("health endpoints", () => {
  it("GET /health returns the parsed liveness payload", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ status: "ok", service: "x-agent" }));
    const health = await client.health();
    expect(health).toEqual({ status: "ok", service: "x-agent" });
    expect(mock.calls[0].url).toBe(`${BASE}/health`);
  });

  it("GET /health during draining throws with the backend body attached", async () => {
    const { client, mock } = makeClient();
    mock.push(errorResponse(503, { status: "draining", service: "x-agent" }));
    const error = (await client.health().catch((e: unknown) => e)) as XAgentApiError;
    expect(error.status).toBe(503);
    expect(error.details).toEqual({ status: "draining", service: "x-agent" });
  });

  it("GET /ready returns component status", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({
        status: "ready",
        components: { memory: "ok", qdrant: "degraded" },
        integrations: { qdrant: false },
      }),
    );
    const ready = await client.ready();
    expect(ready.status).toBe("ready");
    expect(ready.components.qdrant).toBe("degraded");
  });
});

describe("CSRF handling (browser session-cookie flows)", () => {
  it("lazily fetches a CSRF token before mutating requests and caches it", async () => {
    const { client, mock } = makeClient({ apiKey: undefined });
    const approval = { id: "ap-1", status: "approved" };
    mock.push(
      jsonResponse({ csrf_token: "tok-1" }),
      jsonResponse(approval),
      jsonResponse({ id: "ap-2", status: "rejected" }),
    );

    await client.approvals.approve("ap-1", { reason: "ok" });
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/csrf-token`);
    expect(mock.calls[0].init.method).toBe("POST");
    expect(headersOf(mock.calls[1])["x-csrf-token"]).toBe("tok-1");

    // Second call reuses the cached token: no extra csrf-token fetch.
    await client.approvals.reject("ap-2");
    expect(mock.calls).toHaveLength(3);
    expect(mock.calls[2].url).toBe(`${BASE}/api/v1/approvals/ap-2/reject`);
    expect(headersOf(mock.calls[2])["x-csrf-token"]).toBe("tok-1");
  });

  it("never fetches CSRF tokens when an API key is present (CSRF-exempt)", async () => {
    const { client, mock } = makeClient(); // apiKey set
    mock.push(jsonResponse({ id: "ap-1", status: "approved" }));
    await client.approvals.approve("ap-1");
    expect(mock.calls).toHaveLength(1);
    expect(headersOf(mock.calls[0])["x-csrf-token"]).toBeUndefined();
  });

  it("refreshes the token once and replays on a CSRF 403", async () => {
    const { client, mock } = makeClient({ apiKey: undefined });
    mock.push(
      jsonResponse({ csrf_token: "stale" }),
      errorResponse(403, { detail: "Invalid CSRF token" }),
      jsonResponse({ csrf_token: "fresh" }),
      jsonResponse({ id: "ap-9", status: "approved" }),
    );
    const record = await client.approvals.approve("ap-9");
    expect(record.id).toBe("ap-9");
    expect(mock.calls).toHaveLength(4);
    expect(headersOf(mock.calls[1])["x-csrf-token"]).toBe("stale");
    expect(headersOf(mock.calls[3])["x-csrf-token"]).toBe("fresh");
  });

  it("does not retry non-CSRF 403s", async () => {
    const { client, mock } = makeClient({ apiKey: undefined });
    mock.push(
      jsonResponse({ csrf_token: "tok" }),
      errorResponse(403, { detail: "Approval tenant mismatch." }),
    );
    const error = (await client.approvals.approve("ap-1").catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.message).toBe("Approval tenant mismatch.");
    expect(mock.calls).toHaveLength(2);
  });
});
