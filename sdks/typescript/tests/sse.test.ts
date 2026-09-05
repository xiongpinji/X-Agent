import { describe, expect, it } from "vitest";
import {
  parseSseFrame,
  parseSseStream,
  toStreamEventEnvelope,
} from "../src/agents.js";
import type { SseMessage } from "../src/agents.js";

async function collect(messages: AsyncGenerator<SseMessage, void, unknown>): Promise<SseMessage[]> {
  const out: SseMessage[] = [];
  for await (const message of messages) out.push(message);
  return out;
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe("parseSseFrame", () => {
  it("parses event + data lines", () => {
    const frame = parseSseFrame('event: tool_call\ndata: {"a":1}');
    expect(frame).toEqual({
      event: "tool_call",
      data: '{"a":1}',
      id: undefined,
      retry: undefined,
    });
  });

  it("joins multi-line data fields with newlines (SSE spec)", () => {
    const frame = parseSseFrame("data: first\ndata: second");
    expect(frame?.data).toBe("first\nsecond");
  });

  it("strips exactly one leading space after the colon", () => {
    const frame = parseSseFrame("data:   padded");
    expect(frame?.data).toBe("  padded");
  });

  it("ignores comments and blank lines", () => {
    expect(parseSseFrame(": keep-alive")).toBeNull();
    expect(parseSseFrame("")).toBeNull();
  });

  it("captures id and retry fields", () => {
    const frame = parseSseFrame("id: 42\nretry: 1500\nevent: x\ndata: y");
    expect(frame?.id).toBe("42");
    expect(frame?.retry).toBe(1500);
  });

  it("ignores unknown fields", () => {
    const frame = parseSseFrame("foo: bar\ndata: x");
    expect(frame?.data).toBe("x");
    expect(frame?.event).toBeUndefined();
  });
});

describe("parseSseStream", () => {
  it("parses a sequence of frames in order", async () => {
    const messages = await collect(
      parseSseStream(streamOf(['event: a\ndata: {"1":1}\n\n', 'event: b\ndata: {"2":2}\n\n'])),
    );
    expect(messages.map((m) => m.event)).toEqual(["a", "b"]);
  });

  it("reassembles frames split across chunk boundaries mid-JSON", async () => {
    const messages = await collect(
      parseSseStream(
        streamOf([
          'event: iteration\nda',
          'ta: {"event_type":"iteration","run_i',
          'd":"r1","sequence":2}\n\n',
        ]),
      ),
    );
    expect(messages).toHaveLength(1);
    expect(messages[0]?.data).toBe('{"event_type":"iteration","run_id":"r1","sequence":2}');
  });

  it("handles CRLF line endings", async () => {
    const messages = await collect(
      parseSseStream(streamOf(["event: heartbeat\r\ndata: {}\r\n\r\n"])),
    );
    expect(messages).toHaveLength(1);
    expect(messages[0]?.event).toBe("heartbeat");
  });

  it("flushes a trailing frame that lacks the final blank line", async () => {
    const messages = await collect(parseSseStream(streamOf(['event: completion\ndata: {"x":1}'])));
    expect(messages).toHaveLength(1);
  });

  it("stops promptly once the abort signal fires", async () => {
    const controller = new AbortController();
    const many = Array.from({ length: 50 }, (_, i) => `event: e${i}\ndata: {"i":${i}}\n\n`).join("");
    const events: unknown[] = [];
    for await (const message of parseSseStream(streamOf([many]), { signal: controller.signal })) {
      events.push(message);
      if (events.length === 1) controller.abort();
    }
    expect(events).toHaveLength(1);
  });
});

describe("toStreamEventEnvelope", () => {
  it("maps the backend envelope data payload", () => {
    const envelope = toStreamEventEnvelope({
      event: "iteration",
      data: JSON.stringify({
        event_type: "iteration",
        timestamp: "2026-09-05T00:00:00",
        run_id: "r1",
        data: { step_kind: "write", instruction: "do it" },
        sequence: 3,
      }),
      id: undefined,
      retry: undefined,
    });
    expect(envelope).toEqual({
      event_type: "iteration",
      timestamp: "2026-09-05T00:00:00",
      run_id: "r1",
      data: { step_kind: "write", instruction: "do it" },
      sequence: 3,
    });
  });

  it("falls back to the event: line when the payload lacks event_type", () => {
    const envelope = toStreamEventEnvelope({ event: "completion", data: "{}", id: undefined, retry: undefined });
    expect(envelope?.event_type).toBe("completion");
  });

  it("returns null for frames without data", () => {
    expect(toStreamEventEnvelope({ event: "ping", data: null, id: undefined, retry: undefined })).toBeNull();
  });

  it("returns null for non-JSON data", () => {
    expect(
      toStreamEventEnvelope({ event: "x", data: "not-json", id: undefined, retry: undefined }),
    ).toBeNull();
  });

  it("defaults data to {} when the payload has no data field (heartbeats)", () => {
    const envelope = toStreamEventEnvelope({
      event: "heartbeat",
      data: JSON.stringify({ event_type: "heartbeat", timestamp: "t", run_id: "r", sequence: 9 }),
      id: undefined,
      retry: undefined,
    });
    expect(envelope?.data).toEqual({});
    expect(envelope?.sequence).toBe(9);
  });
});
