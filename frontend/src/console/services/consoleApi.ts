export type ConsoleSseEvent = {
  name: string;
  id: string | null;
  data: string;
};

export type ConsoleStreamResult = {
  terminal: boolean;
  lastEventId: string | null;
};

type Fetcher = typeof fetch;
const MAX_SSE_BUFFER_BYTES = 1024 * 1024;
const MAX_SSE_EVENT_BYTES = 512 * 1024;
const MAX_SSE_DATA_BYTES = 256 * 1024;
const textEncoder = new TextEncoder();

export class ConsoleApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ConsoleApiError";
    this.status = status;
  }
}

export function getConsoleAuthHeaders(storage: Pick<Storage, "getItem"> = window.localStorage): Record<string, string> {
  const bearer = storage.getItem("auth_token")?.trim();
  if (bearer) return { Authorization: `Bearer ${bearer}` };

  const apiKey = storage.getItem("api_key")?.trim();
  return apiKey ? { "X-API-Key": apiKey } : {};
}

function assertConsoleResponse(response: Response): void {
  if (response.status === 401) {
    throw new ConsoleApiError("Console authentication required.", 401);
  }
  if (!response.ok) {
    throw new ConsoleApiError(`Console request failed (${response.status}).`, response.status);
  }
}

export async function fetchConsoleBootstrap<T = unknown>(options: {
  url?: string;
  fetcher?: Fetcher;
  signal?: AbortSignal;
} = {}): Promise<T> {
  const {
    url = "/api/v1/workbench",
    fetcher = fetch,
    signal,
  } = options;
  const response = await fetcher(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...getConsoleAuthHeaders(),
    },
    signal,
  });
  assertConsoleResponse(response);
  return response.json() as Promise<T>;
}

function parseEventBlock(block: string): ConsoleSseEvent | null {
  if (textEncoder.encode(block).byteLength > MAX_SSE_EVENT_BYTES) {
    throw new ConsoleApiError("Console event stream exceeded the safe size limit.", 413);
  }
  let name = "message";
  let id: string | null = null;
  const data: string[] = [];

  for (const line of block.split(/\r\n|\r|\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event" && value) name = value;
    if (field === "id" && !value.includes("\0")) id = value;
    if (field === "data") data.push(value);
  }

  if (data.length === 0) return null;
  const joinedData = data.join("\n");
  if (textEncoder.encode(joinedData).byteLength > MAX_SSE_DATA_BYTES) {
    throw new ConsoleApiError("Console event stream exceeded the safe size limit.", 413);
  }
  return { name, id, data: joinedData };
}

function takeNextBlock(buffer: string): { block: string; rest: string } | null {
  const separator = /\r\n\r\n|\n\n|\r\r/.exec(buffer);
  if (!separator || separator.index === undefined) return null;
  return {
    block: buffer.slice(0, separator.index),
    rest: buffer.slice(separator.index + separator[0].length),
  };
}

const TERMINAL_EVENT_NAMES = new Set(["stream.closed", "stream.completed"]);

export async function readConsoleEventStream(options: {
  url?: string;
  lastEventId?: string | null;
  signal?: AbortSignal;
  fetcher?: Fetcher;
  onOpen?: () => void;
  onEvent: (event: ConsoleSseEvent) => void;
}): Promise<ConsoleStreamResult> {
  const {
    url = "/api/v1/messages/stream",
    lastEventId = null,
    signal,
    fetcher = fetch,
    onOpen,
    onEvent,
  } = options;
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    ...getConsoleAuthHeaders(),
  };
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;

  const response = await fetcher(url, { method: "GET", headers, signal });
  assertConsoleResponse(response);
  if (!response.body) {
    throw new ConsoleApiError("Console event stream is unavailable.", response.status);
  }
  onOpen?.();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let latestEventId = lastEventId;
  let streamDone = false;
  try {
    while (!streamDone) {
      const { done, value } = await reader.read();
      streamDone = done;
      buffer += decoder.decode(value, { stream: !done });
      if (textEncoder.encode(buffer).byteLength > MAX_SSE_BUFFER_BYTES) {
        throw new ConsoleApiError("Console event stream exceeded the safe size limit.", 413);
      }

      let next = takeNextBlock(buffer);
      while (next) {
        buffer = next.rest;
        const event = parseEventBlock(next.block);
        if (event) {
          if (event.id) latestEventId = event.id;
          onEvent(event);
          if (TERMINAL_EVENT_NAMES.has(event.name)) {
            await reader.cancel();
            return { terminal: true, lastEventId: latestEventId };
          }
        }
        next = takeNextBlock(buffer);
      }

    }
    return { terminal: false, lastEventId: latestEventId };
  } catch (error) {
    if (error instanceof ConsoleApiError && error.status === 413) {
      try {
        await reader.cancel();
      } catch {
        // The stable size-limit error remains authoritative if cancellation fails.
      }
    }
    throw error;
  } finally {
    reader.releaseLock();
  }
}
