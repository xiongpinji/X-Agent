import { describe, expect, it } from "vitest";
import { XAgentApiError, XAgentClient } from "../src/client.js";
import type { StreamEventEnvelope } from "../src/types.js";
import {
  errorResponse,
  headersOf,
  jsonResponse,
  mockFetch,
  sseFrame,
  sseResponse,
} from "./helpers.js";

const BASE = "http://api.test.local";

function makeClient(): { client: XAgentClient; mock: ReturnType<typeof mockFetch> } {
  const mock = mockFetch();
  const client = new XAgentClient({ baseUrl: BASE, apiKey: "key", fetch: mock.fetch });
  return { client, mock };
}

function envelope(eventType: string, sequence: number, data: Record<string, unknown> = {}): string {
  return sseFrame(eventType, {
    event_type: eventType,
    timestamp: `2026-09-05T00:00:0${sequence}`,
    run_id: "run-1",
    data,
    sequence,
  });
}

describe("agents.run", () => {
  it("POSTs /api/v1/agents/run and returns the full result", async () => {
    const { client, mock } = makeClient();
    const result = {
      trace_id: "t1",
      agent_id: "a1",
      status: "completed",
      answer: "done",
      iterations: 2,
      memory_hits: 0,
      tool_calls: [],
      events: [],
      plan: [],
      execution_summary: {},
      error: null,
      snapshot: {},
    };
    mock.push(jsonResponse(result));

    const response = await client.agents.run({
      task: "write tests",
      max_iterations: 5,
      sandbox_mode: "subprocess",
      extra_context: { repo: "x-agent" },
    });

    expect(response).toEqual(result);
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/agents/run`);
    expect(mock.calls[0].init.method).toBe("POST");
    expect(headersOf(mock.calls[0])["x-api-key"]).toBe("key");
    expect(JSON.parse(mock.calls[0].init.body as string)).toEqual({
      task: "write tests",
      max_iterations: 5,
      sandbox_mode: "subprocess",
      extra_context: { repo: "x-agent" },
    });
  });

  it("surfaces 422 validation errors with field details", async () => {
    const { client, mock } = makeClient();
    mock.push(
      errorResponse(422, {
        code: "validation_error",
        message: "task is required.",
        details: { errors: [{ field: "task", message: "task is required." }] },
      }),
    );
    const error = (await client.agents.run({ task: "" }).catch((e: unknown) => e)) as XAgentApiError;
    expect(error.code).toBe("validation_error");
    expect(error.status).toBe(422);
  });
});

describe("agents.runStream", () => {
  it("starts the run then consumes the SSE stream in order", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({
        run_id: "run-1",
        stream_url: "/api/v1/agent/stream/run-1",
        trace_id: "trace-1",
        status: "started",
      }),
      sseResponse([
        envelope("message", 1, { content: "Starting execution", role: "system" }),
        envelope("plan", 2, { goal: "ship sdk", step_count: 3 }),
        envelope("iteration", 3, { step_kind: "write", instruction: "implement" }),
        envelope("tool_call", 4, { tool_name: "fs.write", success: true, latency_ms: 12 }),
        envelope("tool_result", 5, { tool_name: "fs.write", success: true }),
        envelope("heartbeat", 6),
      ]),
    );

    const stream = await client.agents.runStream({ task: "build the sdk" });
    expect(stream.run_id).toBe("run-1");
    expect(stream.trace_id).toBe("trace-1");

    const types: string[] = [];
    for await (const event of stream.events) types.push(event.event_type);
    expect(types).toEqual(["message", "plan", "iteration", "tool_call", "tool_result", "heartbeat"]);

    // Two hops: start + subscribe.
    expect(mock.calls).toHaveLength(2);
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/agent/run/stream`);
    expect(mock.calls[0].init.method).toBe("POST");
    expect(JSON.parse(mock.calls[0].init.body as string)).toEqual({
      task: "build the sdk",
      extra_context: {},
    });
    expect(mock.calls[1].url).toBe(`${BASE}/api/v1/agent/stream/run-1`);
    expect(headersOf(mock.calls[1])["accept"]).toBe("text/event-stream");
    expect(headersOf(mock.calls[1])["x-api-key"]).toBe("key");
  });

  it("terminates iteration after the completion event (server closes there)", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ run_id: "run-2", stream_url: "/f", trace_id: "t", status: "started" }),
      sseResponse([
        envelope("iteration", 1),
        envelope("completion", 2, { status: "completed", result: "ok" }),
        // Server guarantees nothing after terminal; a buffering proxy could
        // still deliver stale frames — the SDK must stop at completion.
        envelope("heartbeat", 3),
      ]),
    );

    const stream = await client.agents.runStream({ task: "x" });
    const events: StreamEventEnvelope[] = [];
    for await (const event of stream.events) events.push(event);
    expect(events.map((e) => e.event_type)).toEqual(["iteration", "completion"]);
    const completion = events[1];
    expect(completion?.data).toEqual({ status: "completed", result: "ok" });
  });

  it("yields the error terminal event and then stops", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ run_id: "run-3", stream_url: "/f", trace_id: "t", status: "started" }),
      sseResponse([
        envelope("error", 1, {
          error_code: "EXECUTION_ERROR",
          error_message: "boom",
          recoverable: false,
        }),
        envelope("heartbeat", 2),
      ]),
    );

    const stream = await client.agents.runStream({ task: "x" });
    const events: StreamEventEnvelope[] = [];
    for await (const event of stream.events) events.push(event);
    expect(events.map((e) => e.event_type)).toEqual(["error"]);
    expect((events[0]?.data as Record<string, unknown>)["error_code"]).toBe("EXECUTION_ERROR");
  });

  it("normalizes HTTP errors from the stream endpoint", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ run_id: "run-4", stream_url: "/f", trace_id: "t", status: "started" }),
      errorResponse(401, { code: "authentication_failed", message: "Invalid API key." }),
    );

    const stream = await client.agents.runStream({ task: "x" });
    const error = (await stream.events.next().catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.code).toBe("authentication_failed");
  });

  it("re-attaches with since_sequence on subscribeStream", async () => {
    const { client, mock } = makeClient();
    mock.push(sseResponse([envelope("completion", 42)]));

    const events: StreamEventEnvelope[] = [];
    for await (const event of client.agents.subscribeStream("run-9", { sinceSequence: 41 })) {
      events.push(event);
    }
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/agent/stream/run-9?since_sequence=41`);
    expect(events).toHaveLength(1);
  });

  it("stops consuming when the abort signal fires", async () => {
    const { client, mock } = makeClient();
    const frames = Array.from({ length: 20 }, (_, i) => envelope("iteration", i + 1)).join("");
    mock.push(sseResponse([frames]));

    const controller = new AbortController();
    const events: StreamEventEnvelope[] = [];
    for await (const event of client.agents.subscribeStream("run-a", { signal: controller.signal })) {
      events.push(event);
      if (events.length === 2) controller.abort();
    }
    expect(events).toHaveLength(2);
  });
});

describe("agents.streamEvents (polling fallback)", () => {
  it("fetches buffered events with pagination params", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({
        run_id: "run-1",
        events: [],
        total: 0,
        limited: false,
      }),
    );
    const result = await client.agents.streamEvents("run-1", { sinceSequence: 5, limit: 50 });
    expect(mock.calls[0].url).toBe(
      `${BASE}/api/v1/agent/stream/run-1/events?since_sequence=5&limit=50`,
    );
    expect(result.run_id).toBe("run-1");
    expect(result.limited).toBe(false);
  });
});
