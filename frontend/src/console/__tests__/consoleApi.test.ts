// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function readerBackedResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  const reader = {
    read: vi.fn().mockImplementation(async () => (
      index < chunks.length
        ? { done: false, value: encoder.encode(chunks[index++]) }
        : { done: true, value: undefined }
    )),
    cancel: vi.fn().mockResolvedValue(undefined),
    releaseLock: vi.fn(),
  };
  return {
    response: {
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    } as unknown as Response,
    reader,
  };
}

function hangingReaderResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  const reader = {
    read: vi.fn().mockImplementation(() => (
      index < chunks.length
        ? Promise.resolve({ done: false, value: encoder.encode(chunks[index++]) })
        : new Promise(() => undefined)
    )),
    cancel: vi.fn().mockResolvedValue(undefined),
    releaseLock: vi.fn(),
  };
  return {
    response: {
      ok: true,
      status: 200,
      body: { getReader: () => reader },
    } as unknown as Response,
    reader,
  };
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

  it("cancels oversized SSE buffers and data with a sanitized error", async () => {
    for (const oversized of [
      `event: message.created\ndata: ${"buffer-secret".repeat(90000)}`,
      `event: message.created\ndata: ${"data-secret".repeat(30000)}\n\n`,
    ]) {
      const { response, reader } = readerBackedResponse([oversized]);
      const fetcher = vi.fn().mockResolvedValue(response);

      const result = readConsoleEventStream({ fetcher, onEvent: vi.fn() });

      await expect(result).rejects.toEqual(
        expect.objectContaining<Partial<ConsoleApiError>>({
          name: "ConsoleApiError",
          status: 413,
          message: "Console event stream exceeded the safe size limit.",
        }),
      );
      await expect(result.catch((error: Error) => error.message)).resolves.not.toMatch(/secret/);
      expect(reader.cancel).toHaveBeenCalledTimes(1);
      expect(reader.releaseLock).toHaveBeenCalledTimes(1);
    }
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

  it("renders real collaboration room and message payloads without accepting malformed events", async () => {
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
          'event: room.created\ndata: {"event_type":"room.created","payload":{"room":{"room_id":"room-real","topic":"Launch Room","status":"active","members":["agent-a"],"message_count":0}}}\n\n',
          'event: message.created\ndata: {"event_type":"message.created","payload":{"message":{"content":"malformed-secret"}}}\n\n',
          'event: room.member_added\ndata: {"event_type":"room.member_added","payload":{"member_id":"agent-b","room":{"room_id":"room-real","topic":"Launch Room","status":"active","members":["agent-a","agent-b"],"message_count":1}}}\n\n',
          'event: message.created\ndata: {"event_type":"message.created","room_id":"room-real","payload":{"message":{"message_id":"message-real","room_id":"room-real","sender_id":"agent-a","sender_type":"agent","content":"real collaboration message","created_at":"2026-08-16T00:00:00Z","metadata":{"message_type":"text"}}}}\n\n',
          'event: room.closed\ndata: {"event_type":"room.closed","payload":{"room":{"room_id":"room-real","topic":"Launch Room","status":"closed","members":["agent-a","agent-b"],"message_count":1}}}\n\n',
          'event: stream.closed\ndata: {"event_type":"stream.closed"}\n\n',
        ]);
      }
      throw new Error(`Unexpected Console URL: ${url}`);
    });

    render(React.createElement(ConsoleApp));

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    fireEvent.click(await screen.findByRole("button", { name: "会议室" }));
    await waitFor(() => expect(screen.getAllByText("Launch Room").length).toBeGreaterThan(0));
    expect(screen.getByText("2 成员")).toBeTruthy();
    expect(screen.getByText("closed")).toBeTruthy();
    expect(screen.getByText("real collaboration message")).toBeTruthy();
    expect(screen.queryByText("malformed-secret")).toBeNull();
  });

  it("reconnects from the last processed event after a stream gap and recovers without duplicates", async () => {
    localStorage.setItem("auth_token", "bearer-secret");
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const bootstrap = {
      ...emptyBootstrap,
      meeting_rooms: {
        availability: "available",
        rooms: [{
          room_id: "room-gap",
          name: "Gap Recovery",
          topic: "Gap Recovery",
          status: "active",
          member_count: 1,
          member_agent_ids: ["agent-a"],
        }],
      },
    };
    const firstStream = hangingReaderResponse([
      'event: message.created\nid: evt-gap-1\ndata: {"event_id":"evt-gap-1","event_type":"message.created","room_id":"room-gap","payload":{"message":{"message_id":"message-gap-1","room_id":"room-gap","sender_id":"agent-a","content":"before gap","created_at":"2026-08-16T00:00:00Z"}}}\n\n'
      + 'event: stream.gap\ndata: {"event_type":"stream.gap","payload":{"reason":"subscriber_overflow"}}\n\n',
    ]);
    let streamCalls = 0;
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/workbench")) {
        return new Response(JSON.stringify(bootstrap), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.startsWith("/api/v1/messages/stream")) {
        streamCalls += 1;
        if (streamCalls === 1) return firstStream.response;
        return chunkedResponse([
          'event: message.created\nid: evt-gap-2\ndata: {"event_id":"evt-gap-2","event_type":"message.created","room_id":"room-gap","payload":{"message":{"message_id":"message-gap-2","room_id":"room-gap","sender_id":"agent-b","content":"after gap","created_at":"2026-08-16T00:00:01Z"}}}\n\n',
          'event: stream.closed\ndata: {"event_type":"stream.closed"}\n\n',
        ]);
      }
      throw new Error(`Unexpected Console URL: ${url}`);
    });

    render(React.createElement(ConsoleApp));

    await waitFor(() => expect(firstStream.reader.cancel).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("正在使用轮询兜底同步")).toBeTruthy());
    expect(screen.queryByText("SSE 实时连接正常")).toBeNull();
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3), { timeout: 3000 });
    const [, recoveryInit] = fetcher.mock.calls[2];
    expect(recoveryInit?.headers).toEqual(
      expect.objectContaining({ "Last-Event-ID": "evt-gap-1" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "会议室" }));
    await waitFor(() => expect(screen.getByText("after gap")).toBeTruthy());
    expect(screen.getAllByText("before gap")).toHaveLength(1);
    expect(screen.getAllByText("after gap")).toHaveLength(1);
  });
});
