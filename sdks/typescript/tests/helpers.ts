/** Shared test helpers: fetch mocking without hitting the network. */

export interface FetchCall {
  url: string;
  init: RequestInit;
}

export type MockHandler =
  | Response
  | Error
  | ((call: FetchCall, index: number) => Response | Promise<Response>);

export interface MockFetch {
  fetch: typeof fetch;
  calls: FetchCall[];
  /** Queue the next response(s); a function handler receives the call. */
  push: (...handlers: MockHandler[]) => void;
}

/** A fetch double that records calls, respects abort signals, and replays queued handlers. */
export function mockFetch(): MockFetch {
  const calls: FetchCall[] = [];
  const queue: MockHandler[] = [];

  const fetchImpl: typeof fetch = (async (
    input: Parameters<typeof globalThis.fetch>[0],
    init?: RequestInit,
  ): Promise<Response> => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const call: FetchCall = { url, init: init ?? {} };
    calls.push(call);

    const handler = queue.shift();
    if (handler === undefined) {
      throw new Error(`test: unexpected fetch call #${calls.length} -> ${url}`);
    }

    const signal = init?.signal;
    return await new Promise<Response>((resolve, reject) => {
      const settle = (outcome: Promise<Response>) => {
        outcome.then(resolve, reject);
      };
      if (signal) {
        if (signal.aborted) {
          reject(signal.reason instanceof Error ? signal.reason : abortError());
          return;
        }
        signal.addEventListener(
          "abort",
          () => {
            reject(signal.reason instanceof Error ? signal.reason : abortError());
          },
          { once: true },
        );
      }
      if (handler instanceof Error) {
        reject(handler);
        return;
      }
      settle(
        typeof handler === "function"
          ? Promise.resolve(handler(call, calls.length - 1))
          : Promise.resolve(handler),
      );
    });
  }) as typeof fetch;

  return {
    fetch: fetchImpl,
    calls,
    push: (...handlers) => {
      queue.push(...handlers);
    },
  };
}

function abortError(): Error {
  const error = new Error("Aborted");
  error.name = "AbortError";
  return error;
}

/** JSON Response helper. */
export function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    ...init,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

/** Error Response helper with a JSON body. */
export function errorResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** Plain-text error response (non-JSON path). */
export function textResponse(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { "content-type": "text/plain" },
  });
}

/** Build an SSE Response whose body emits the given encoded chunks in order. */
export function sseResponse(chunks: string[], init: ResponseInit = {}): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    ...init,
    headers: { "content-type": "text/event-stream", ...(init.headers ?? {}) },
  });
}

/** Encode an SSE frame exactly the way the backend emits it. */
export function sseFrame(eventType: string, payload: unknown): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`;
}

/** Readable headers off a recorded call, normalized to lowercase keys. */
export function headersOf(call: FetchCall): Record<string, string> {
  const raw = (call.init.headers ?? {}) as Record<string, string>;
  const normalized: Record<string, string> = {};
  for (const [key, value] of Object.entries(raw)) {
    normalized[key.toLowerCase()] = value;
  }
  return normalized;
}
