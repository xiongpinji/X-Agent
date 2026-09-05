import { describe, expect, it } from "vitest";
import { XAgentApiError, XAgentClient } from "../src/client.js";
import { headersOf, jsonResponse, mockFetch } from "./helpers.js";

const BASE = "http://api.test.local";

function makeClient(): { client: XAgentClient; mock: ReturnType<typeof mockFetch> } {
  const mock = mockFetch();
  const client = new XAgentClient({ baseUrl: BASE, apiKey: "key", fetch: mock.fetch });
  return { client, mock };
}

const approvalRecord = {
  id: "ap-1",
  tenant_id: "default",
  actor_id: "user-1",
  trace_id: "t-1",
  resource_type: "tool",
  resource_id: "fs.write",
  action: "tool.execute",
  risk_level: "high",
  status: "pending",
  reason: "writes outside workspace",
  arguments_preview: { path: "/etc/hosts" },
  arguments: {},
  decided_by: null,
  decided_at: null,
  decision_reason: null,
  executed_by: null,
  executed_at: null,
  execution_trace_id: null,
  linked_policy_trace_id: null,
  created_at: "2026-09-05T00:00:00Z",
};

describe("approvals", () => {
  it("lists approvals with limit/status filters", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse([approvalRecord]));
    const approvals = await client.approvals.list({ limit: 10, status: "pending" });
    expect(approvals).toEqual([approvalRecord]);
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/approvals?limit=10&status=pending`);
  });

  it("fetches a single approval", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse(approvalRecord));
    const record = await client.approvals.get("ap-1");
    expect(record.id).toBe("ap-1");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/approvals/ap-1`);
  });

  it("approves with a reason body (decided_by is server-bound, never sent)", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ ...approvalRecord, status: "approved" }));
    const record = await client.approvals.approve("ap-1", { reason: "safe change" });
    expect(record.status).toBe("approved");
    const body = JSON.parse(mock.calls[0].init.body as string);
    expect(body).toEqual({ reason: "safe change" });
    expect("decided_by" in body).toBe(false);
  });

  it("rejects with a reason body", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ ...approvalRecord, status: "rejected" }));
    const record = await client.approvals.reject("ap-1");
    expect(record.status).toBe("rejected");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/approvals/ap-1/reject`);
  });

  it("executes an approved tool call and returns the ToolCallRecord", async () => {
    const { client, mock } = makeClient();
    const toolCall = { tool_name: "fs.write", success: true, output: null, error: null };
    mock.push(jsonResponse(toolCall));
    const result = await client.approvals.execute("ap-1");
    expect(result.tool_name).toBe("fs.write");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/approvals/ap-1/execute`);
    expect(mock.calls[0].init.method).toBe("POST");
  });
});

describe("checkpoints", () => {
  it("lists resumable checkpoints", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ items: [], total: 0 }));
    const result = await client.checkpoints.list(20);
    expect(result.total).toBe(0);
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/checkpoints?limit=20`);
  });

  it("resumes with extra_context and from_iteration", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({
        trace_id: "t-1",
        new_trace_id: "resume-abc",
        resumed_from_iteration: 3,
        status: "completed",
        message: "ok",
      }),
    );
    const result = await client.checkpoints.resume("t-1", {
      extra_context: { hint: "skip tests" },
      from_iteration: 3,
    });
    expect(result.new_trace_id).toBe("resume-abc");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/checkpoints/t-1/resume`);
    expect(JSON.parse(mock.calls[0].init.body as string)).toEqual({
      extra_context: { hint: "skip tests" },
      from_iteration: 3,
    });
  });

  it("resumes from the latest checkpoint by default (from_iteration: null)", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ trace_id: "t-2", new_trace_id: "n", resumed_from_iteration: 1, status: "completed", message: "" }));
    await client.checkpoints.resume("t-2");
    expect(JSON.parse(mock.calls[0].init.body as string)).toEqual({
      extra_context: {},
      from_iteration: null,
    });
  });

  it("deletes checkpoints", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ trace_id: "t-3", deleted_count: 2 }));
    const result = await client.checkpoints.delete("t-3");
    expect(result.deleted_count).toBe(2);
    expect(mock.calls[0].init.method).toBe("DELETE");
  });
});

describe("sandbox tasks", () => {
  it("submits a task (fire-and-forget)", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ task_id: "task-1", status: "queued" }));
    const result = await client.tasks.submit({
      name: "run checks",
      command: "pytest -q",
      timeout_seconds: 120,
      enable_network: false,
    });
    expect(result.task_id).toBe("task-1");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/sandbox/tasks`);
    expect(JSON.parse(mock.calls[0].init.body as string)).toEqual({
      name: "run checks",
      command: "pytest -q",
      timeout_seconds: 120,
      enable_network: false,
    });
  });

  it("polls a task status", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ task_id: "task-1", status: "completed", backend: "docker", steps: [], error: null }),
    );
    const status = await client.tasks.get("task-1");
    expect(status.status).toBe("completed");
    expect(mock.calls[0].url).toBe(`${BASE}/api/v1/sandbox/tasks/task-1`);
  });

  it("lists known tasks", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse({ tasks: [{ task_id: "task-1", status: "queued" }] }));
    const result = await client.tasks.list();
    expect(result.tasks).toHaveLength(1);
  });

  it("pollUntilDone returns once the task reaches a terminal status", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ task_id: "task-9", status: "running", backend: "docker", steps: [], error: null }),
      jsonResponse({ task_id: "task-9", status: "running", backend: "docker", steps: [], error: null }),
      jsonResponse({ task_id: "task-9", status: "failed", backend: "docker", steps: [], error: "exit 1" }),
    );
    const final = await client.tasks.pollUntilDone("task-9", { intervalMs: 1, timeoutMs: 5_000 });
    expect(final.status).toBe("failed");
    expect(final.error).toBe("exit 1");
    expect(mock.calls).toHaveLength(3);
  });

  it("pollUntilDone throws timeout_error past the deadline", async () => {
    const { client, mock } = makeClient();
    mock.push(
      jsonResponse({ task_id: "task-s", status: "running", backend: null, steps: [], error: null }),
    );
    const error = (await client.tasks
      .pollUntilDone("task-s", { intervalMs: 1, timeoutMs: 0 })
      .catch((e: unknown) => e)) as XAgentApiError;
    expect(error).toBeInstanceOf(XAgentApiError);
    expect(error.isTimeout).toBe(true);
  });
});

describe("auth applies to every resource call", () => {
  it("carries x-api-key on resource requests", async () => {
    const { client, mock } = makeClient();
    mock.push(jsonResponse([]), jsonResponse({ items: [], total: 0 }), jsonResponse({ tasks: [] }));
    await client.approvals.list();
    await client.checkpoints.list();
    await client.tasks.list();
    for (const call of mock.calls) {
      expect(headersOf(call)["x-api-key"]).toBe("key");
    }
  });
});
