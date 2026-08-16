// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConsoleApp } from "../ConsoleApp";
import {
  ConsoleApiError,
  fetchConsoleBootstrap,
  getConsoleAuthHeaders,
  readConsoleEventStream,
  type ConsoleSseEvent,
} from "../services/consoleApi";

function chunkedResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "Content-Type": status === 200 ? "text/event-stream" : "application/json" },
  });
}

const emptyBootstrap = {
  console: {
    mode: "unified_console",
    tenant_id: "tenant-a",
    org_id: "",
    agent_id: "agent-a",
    session_id: "session-a",
    user_id: "user-a",
  },
  dispatch: { availability: "unavailable", status: "unavailable", actions: [], pending: [], queue_size: 0 },
  collaboration: { availability: "available", rooms: [] },
  workflow: { availability: "unavailable", templates: [], active: [] },
  execution: { availability: "available", count: 0, runs: [], active_runs: [] },
  role_catalog: { templates: [], workflows: [], role_groups: {}, role_index: {}, avatar_map: {} },
  organization_graph: { availability: "available" },
  meeting_rooms: { availability: "available", rooms: [] },
  realtime: { availability: "available", messages: [], conversations: [], presence: {}, online_agents: [], unread_count: 0 },
  ui: { availability: "unavailable", panels: [], routes: [] },
  avatars: [],
  tools: { availability: "available", count: 0, items: [] },
  entries: [],
  workflows: { availability: "unavailable", templates: [] },
  memory: { availability: "available", count: 0, items: [], memory_refs: [], layer_totals: {} },
  permissions: { scope: [] },
};

describe("consoleApi authentication and SSE", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("prefers the Login bearer key and falls back to the Login API key", () => {
    localStorage.setItem("api_key", "api-secret");
    localStorage.setItem("auth_token", "bearer-secret");

    expect(getConsoleAuthHeaders()).toEqual({ Authorization: "Bearer bearer-secret" });

    localStorage.removeItem("auth_token");
    expect(getConsoleAuthHeaders()).toEqual({ "X-API-Key": "api-secret" });
  });

  it("authenticates bootstrap and reports 401 explicitly", async () => {
    localStorage.setItem("auth_token", "bearer-secret");
    const okFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(emptyBootstrap), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchConsoleBootstrap({ fetcher: okFetch })).resolves.toMatchObject({
      console: { tenant_id: "tenant-a" },
    });
    expect(okFetch).toHaveBeenCalledWith(
      "/api/v1/workbench",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer bearer-secret" }) }),
    );

    const unauthorizedFetch = vi.fn().mockResolvedValue(chunkedResponse([], 401));
    await expect(fetchConsoleBootstrap({ fetcher: unauthorizedFetch })).rejects.toEqual(
      expect.objectContaining<Partial<ConsoleApiError>>({
        name: "ConsoleApiError",
        status: 401,
        message: "Console authentication required.",
      }),
    );
  });

  it("parses CRLF, chunk boundaries, multi-data, named events, and first terminal", async () => {
    localStorage.setItem("api_key", "api-secret");
    const events: ConsoleSseEvent[] = [];
    const fetcher = vi.fn().mockResolvedValue(
      chunkedResponse([
        "event: message.created\r\nid: evt-",
        '1\r\ndata: {"event_type":"message.created",\r\n',
        'data: "payload":{"content":"hello"}}\r\n\r\n',
        'event: stream.closed\ndata: {"event_type":"stream.closed"}\n\n',
        'event: message.created\ndata: {"event_type":"message.created","payload":{"content":"ignored"}}\n\n',
      ]),
    );

    const result = await readConsoleEventStream({
      url: "/api/v1/messages/stream?replay_only=true",
      lastEventId: "evt-0",
      fetcher,
      onEvent: (event) => events.push(event),
    });

    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ name: "message.created", id: "evt-1" });
    expect(JSON.parse(events[0].data)).toEqual({
      event_type: "message.created",
      payload: { content: "hello" },
    });
    expect(result).toEqual({ terminal: true, lastEventId: "evt-1" });
    const [requestUrl, requestInit] = fetcher.mock.calls[0];
    expect(requestUrl).not.toContain("api-secret");
    expect(requestUrl).not.toContain("token");
    expect(requestInit.headers).toEqual(
      expect.objectContaining({ "X-API-Key": "api-secret", "Last-Event-ID": "evt-0" }),
    );
  });

  it("reports stream authentication failure explicitly", async () => {
    const fetcher = vi.fn().mockResolvedValue(chunkedResponse([], 401));

    await expect(readConsoleEventStream({ fetcher, onEvent: vi.fn() })).rejects.toEqual(
      expect.objectContaining<Partial<ConsoleApiError>>({
        name: "ConsoleApiError",
        status: 401,
        message: "Console authentication required.",
      }),
    );
  });

  it("aborts an ongoing stream without treating cancellation as a terminal event", async () => {
    const controller = new AbortController();
    const reader = {
      read: vi.fn().mockImplementation(() => new Promise((_, reject) => {
        if (controller.signal.aborted) {
          reject(new DOMException("Aborted", "AbortError"));
          return;
        }
        controller.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      })),
      cancel: vi.fn(),
      releaseLock: vi.fn(),
    };
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    } as unknown as Response);
    const promise = readConsoleEventStream({
      signal: controller.signal,
      fetcher,
      onEvent: vi.fn(),
    });

    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });

  it("mounts using only workbench and the authenticated messages fetch-stream", async () => {
    localStorage.setItem("auth_token", "bearer-secret");
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/workbench")) {
        return new Response(JSON.stringify(emptyBootstrap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.startsWith("/api/v1/messages/stream")) {
        return chunkedResponse([
          'event: stream.closed\ndata: {"event_type":"stream.closed"}\n\n',
        ]);
      }
      throw new Error(`Unexpected Console URL: ${url}`);
    });

    render(React.createElement(ConsoleApp));

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const urls = fetcher.mock.calls.map(([input]) => String(input));
    expect(urls).toEqual([
      "/api/v1/workbench",
      expect.stringMatching(/^\/api\/v1\/messages\/stream/),
    ]);
    expect(urls.join(" ")).not.toMatch(/(?:execution|tools|memory|organization|marketplace|navigation)-control/);
    expect(screen.getByText("运行记录")).toBeTruthy();
    expect(screen.getByText("当前不可用：dispatch、workflow、ui、workflows")).toBeTruthy();
    expect(screen.queryByText("能力市场")).toBeNull();
    for (const [, init] of fetcher.mock.calls) {
      expect(init?.headers).toEqual(expect.objectContaining({ Authorization: "Bearer bearer-secret" }));
    }
  });
});
