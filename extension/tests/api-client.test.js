/**
 * X-Agent Chrome Extension - Backend API Client Tests
 * Covers settings storage, health check, agent run, SSE streaming and
 * page-context building (chrome.* and fetch fully mocked).
 */

const {
  ApiClientError,
  DEFAULT_BACKEND_SETTINGS,
  BACKEND_SETTINGS_KEY,
  buildPageContext,
  checkHealth,
  extractSSEFrames,
  loadBackendSettings,
  normalizeBaseUrl,
  parseSSEFrame,
  runAgent,
  runAgentStream,
  saveBackendSettings
} = require('../api-client.js');

/* ---------------------------- helpers ---------------------------- */

// jsdom lacks the fetch API globals; polyfill the ones api-client relies on.
const { TextEncoder, TextDecoder } = require('util');
global.TextEncoder = global.TextEncoder || TextEncoder;
global.TextDecoder = global.TextDecoder || TextDecoder;

function useInMemoryStorage() {
  const store = new Map();
  chrome.storage.local.get = jest.fn(async (key) => {
    if (typeof key === 'string') {
      return store.has(key) ? { [key]: store.get(key) } : {};
    }
    if (Array.isArray(key)) {
      const out = {};
      key.forEach((k) => {
        if (store.has(k)) out[k] = store.get(k);
      });
      return out;
    }
    return Object.fromEntries(store.entries());
  });
  chrome.storage.local.set = jest.fn(async (obj) => {
    Object.entries(obj).forEach(([k, v]) => store.set(k, v));
  });
  return store;
}

/** Minimal Response-like object for JSON/text bodies. */
function jsonResponse(body, status = 200, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[String(name).toLowerCase()] || null },
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    body: null
  };
}

/** Minimal SSE Response-like object whose reader yields the given chunks. */
function sseResponse(chunks, headers = { 'content-type': 'text/event-stream' }) {
  const encoder = new TextEncoder();
  const queue = [...chunks];
  return {
    ok: true,
    status: 200,
    headers: { get: (name) => headers[String(name).toLowerCase()] || null },
    body: {
      getReader() {
        return {
          async read() {
            if (queue.length === 0) {
              return { done: true, value: undefined };
            }
            return { done: false, value: encoder.encode(queue.shift()) };
          }
        };
      }
    }
  };
}

const okResponse = (body, headers) => jsonResponse(body, 200, headers);

beforeEach(() => {
  useInMemoryStorage();
  global.fetch = jest.fn();
});

/* ------------------------ normalizeBaseUrl ------------------------ */

describe('normalizeBaseUrl', () => {
  test('keeps a well-formed url and strips trailing slashes', () => {
    expect(normalizeBaseUrl('http://localhost:8000')).toBe('http://localhost:8000');
    expect(normalizeBaseUrl('http://localhost:8000/')).toBe('http://localhost:8000');
    expect(normalizeBaseUrl('https://api.example.com/v1///')).toBe('https://api.example.com/v1');
  });

  test('adds a scheme when missing', () => {
    expect(normalizeBaseUrl('localhost:8000')).toBe('http://localhost:8000');
    expect(normalizeBaseUrl('  192.168.1.5:9000 ')).toBe('http://192.168.1.5:9000');
  });

  test('falls back to the default for empty input', () => {
    expect(normalizeBaseUrl('')).toBe(DEFAULT_BACKEND_SETTINGS.baseUrl);
    expect(normalizeBaseUrl(null)).toBe(DEFAULT_BACKEND_SETTINGS.baseUrl);
  });
});

/* --------------------------- settings ---------------------------- */

describe('backend settings storage', () => {
  test('returns defaults when nothing is stored', async () => {
    const settings = await loadBackendSettings();
    expect(settings).toEqual(DEFAULT_BACKEND_SETTINGS);
    expect(settings.baseUrl).toBe('http://localhost:8000');
  });

  test('loads stored settings merged over defaults', async () => {
    await chrome.storage.local.set({
      [BACKEND_SETTINGS_KEY]: { baseUrl: 'http://10.0.0.2:9000/', apiKey: 'sk-test' }
    });
    const settings = await loadBackendSettings();
    expect(settings.baseUrl).toBe('http://10.0.0.2:9000');
    expect(settings.apiKey).toBe('sk-test');
    expect(settings.attachPageContent).toBe(DEFAULT_BACKEND_SETTINGS.attachPageContent);
  });

  test('saveBackendSettings merges partials and normalizes the url', async () => {
    await chrome.storage.local.set({
      [BACKEND_SETTINGS_KEY]: { apiKey: 'keep-me' }
    });
    const saved = await saveBackendSettings({ baseUrl: 'localhost:8000/' });
    expect(saved.apiKey).toBe('keep-me');
    expect(saved.baseUrl).toBe('http://localhost:8000');
    expect(chrome.storage.local.set).toHaveBeenCalledWith({
      [BACKEND_SETTINGS_KEY]: expect.objectContaining({ baseUrl: 'http://localhost:8000' })
    });

    const reloaded = await loadBackendSettings();
    expect(reloaded.baseUrl).toBe('http://localhost:8000');
  });
});

/* --------------------------- health ------------------------------ */

describe('checkHealth', () => {
  test('reports ok for a healthy backend', async () => {
    global.fetch.mockResolvedValue(okResponse({ status: 'ok', service: 'x-agent' }));
    const result = await checkHealth('http://localhost:8000');
    expect(result.ok).toBe(true);
    expect(result.service).toBe('x-agent');
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({ method: 'GET' })
    );
  });

  test('sends the api key header when provided', async () => {
    global.fetch.mockResolvedValue(okResponse({ status: 'ok' }));
    await checkHealth('http://localhost:8000', 'sk-123');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ headers: { 'x-api-key': 'sk-123' } })
    );
  });

  test('reports failure for non-200 responses', async () => {
    global.fetch.mockResolvedValue(jsonResponse("unavailable", 503));
    const result = await checkHealth('http://localhost:8000');
    expect(result.ok).toBe(false);
    expect(result.httpStatus).toBe(503);
    expect(result.error).toContain('503');
  });

  test('reports failure when the backend is unreachable', async () => {
    global.fetch.mockRejectedValue(new TypeError('fetch failed'));
    const result = await checkHealth('http://localhost:9999');
    expect(result.ok).toBe(false);
    expect(result.error).toContain('无法连接');
  });
});

/* --------------------------- runAgent ---------------------------- */

describe('runAgent', () => {
  test('posts the API contract body and returns the result', async () => {
    const body = { trace_id: 't1', status: 'completed', answer: '你好' };
    global.fetch.mockResolvedValue(okResponse(body));

    const result = await runAgent(
      { task: '总结页面', extraContext: { page: { title: 'x' } } },
      { baseUrl: 'http://localhost:8000', apiKey: 'sk-1' }
    );

    expect(result.answer).toBe('你好');
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/agents/run');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.headers['x-api-key']).toBe('sk-1');
    expect(JSON.parse(init.body)).toEqual({
      task: '总结页面',
      extra_context: { page: { title: 'x' } }
    });
  });

  test('omits extra_context and api key when empty', async () => {
    global.fetch.mockResolvedValue(okResponse({ trace_id: 't2', answer: 'ok' }));
    await runAgent({ task: 'hi' }, { baseUrl: 'http://localhost:8000', apiKey: '' });
    const init = global.fetch.mock.calls[0][1];
    expect(init.headers['x-api-key']).toBeUndefined();
    expect(JSON.parse(init.body)).toEqual({ task: 'hi' });
  });

  test('throws a friendly ApiClientError on 403 (CSRF / api key)', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: 'forbidden' }, 403));
    await expect(
      runAgent({ task: 'x' }, { baseUrl: 'http://localhost:8000', apiKey: '' })
    ).rejects.toMatchObject({
      name: 'ApiClientError',
      status: 403,
      message: expect.stringContaining('API Key')
    });
  });

  test('throws an auth error on 401', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: "bad key" }, 401));
    await expect(
      runAgent({ task: 'x' }, { baseUrl: 'http://localhost:8000', apiKey: 'wrong' })
    ).rejects.toMatchObject({ status: 401, message: expect.stringContaining('API Key') });
  });

  test('throws when the backend cannot be reached', async () => {
    global.fetch.mockRejectedValue(new TypeError('network down'));
    await expect(
      runAgent({ task: 'x' }, { baseUrl: 'http://localhost:8000' })
    ).rejects.toThrow('无法连接到后端');
  });
});

/* --------------------------- SSE parsing -------------------------- */

describe('SSE helpers', () => {
  test('parseSSEFrame parses event and JSON data', () => {
    const frame = 'event: completed\ndata: {"_final": true, "result": {"answer": "done"}}';
    expect(parseSSEFrame(frame)).toEqual({
      event: 'completed',
      data: { _final: true, result: { answer: 'done' } }
    });
  });

  test('parseSSEFrame handles multi-line data and defaults the event', () => {
    const frame = 'data: line1\ndata: line2';
    expect(parseSSEFrame(frame)).toEqual({ event: 'message', data: 'line1\nline2' });
  });

  test('parseSSEFrame ignores frames without data', () => {
    expect(parseSSEFrame('event: trace')).toBeNull();
    expect(parseSSEFrame(': keepalive')).toBeNull();
  });

  test('extractSSEFrames keeps the trailing partial frame in rest', () => {
    const { frames, rest } = extractSSEFrames('event: a\ndata: 1\n\nevent: b\ndata: 2\n\nevent: c\nda');
    expect(frames).toEqual(['event: a\ndata: 1', 'event: b\ndata: 2']);
    expect(rest).toBe('event: c\nda');
  });
});

/* ------------------------- runAgentStream ------------------------- */

describe('runAgentStream', () => {
  test('consumes SSE events split across chunks and resolves the final result', async () => {
    global.fetch.mockResolvedValue(
      sseResponse([
        'event: trace\ndata: {"event": "iteration_start", "iteration": 1}\n\n',
        'event: trace\ndata: {"event": "tool_call", "tool": "read_file"}\n\n',
        'event: completed\ndata: {"_final": true, "result": {"trace_id": "t9", "status": "completed", "answer": "分析完成"}}\n\n'
      ])
    );

    const traceEvents = [];
    let completedPayload = null;
    const result = await runAgentStream(
      { task: '分析页面', extraContext: { page: { url: 'https://x' } } },
      { baseUrl: 'http://localhost:8000', apiKey: 'sk-1' },
      {
        onTraceEvent: (data) => traceEvents.push(data),
        onCompleted: (data) => {
          completedPayload = data;
        }
      }
    );

    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/agents/run/stream');
    expect(init.headers['x-api-key']).toBe('sk-1');
    expect(JSON.parse(init.body).extra_context).toEqual({ page: { url: 'https://x' } });

    expect(traceEvents).toHaveLength(2);
    expect(traceEvents[0].iteration).toBe(1);
    expect(completedPayload.answer).toBe('分析完成');
    expect(result).toMatchObject({ trace_id: 't9', answer: '分析完成' });
  });

  test('rejects a completed event carrying an error payload', async () => {
    global.fetch.mockResolvedValue(
      sseResponse(['event: completed\ndata: {"_final": true, "error": "boom"}\n\n'])
    );
    await expect(
      runAgentStream({ task: 'x' }, { baseUrl: 'http://localhost:8000' })
    ).rejects.toThrow('boom');
  });

  test('supports frames split in the middle of a data line', async () => {
    global.fetch.mockResolvedValue(
      sseResponse([
        'event: trac',
        'e\ndata: {"event": "plan"',
        '}\n\nevent: completed\ndata: {"_final": true, "result": {"status": "completed", "answer": "ok"}}\n\n'
      ])
    );
    const traceEvents = [];
    const result = await runAgentStream(
      { task: 'x' },
      { baseUrl: 'http://localhost:8000' },
      { onTraceEvent: (d) => traceEvents.push(d) }
    );
    expect(traceEvents).toEqual([{ event: 'plan' }]);
    expect(result.answer).toBe('ok');
  });

  test('falls back to a plain JSON response (non-SSE deployments)', async () => {
    global.fetch.mockResolvedValue(
      okResponse({ trace_id: 't3', status: 'completed', answer: 'json-mode' })
    );
    let completedPayload = null;
    const result = await runAgentStream({ task: 'x' }, { baseUrl: 'http://localhost:8000' }, {
      onCompleted: (d) => {
        completedPayload = d;
      }
    });
    expect(result.answer).toBe('json-mode');
    expect(completedPayload.answer).toBe('json-mode');
  });

  test('rejects with an ApiClientError when the stream ends without completion', async () => {
    global.fetch.mockResolvedValue(sseResponse(['event: trace\ndata: {"a": 1}\n\n']));
    await expect(
      runAgentStream({ task: 'x' }, { baseUrl: 'http://localhost:8000' })
    ).rejects.toThrow('流式响应意外结束');
  });
});

/* ------------------------ buildPageContext ------------------------ */

describe('buildPageContext', () => {
  const extract = {
    success: true,
    content: {
      url: 'https://example.com/article',
      title: '示例文章',
      text: 'a'.repeat(100),
      links: Array.from({ length: 30 }, (_, i) => ({ text: `L${i}`, href: `https://e.com/${i}` })),
      images: [{ src: '1.png' }, { src: '2.png' }],
      forms: [{ id: 'f', name: 'n', method: 'post', action: '/x', fields: [{ name: 'q' }, { name: '' }] }],
      metadata: { description: 'demo' }
    }
  };

  test('maps extraction output into a compact context', () => {
    const ctx = buildPageContext(extract, { maxChars: 1000 });
    expect(ctx.source).toBe('xagent-browser-extension');
    expect(ctx.page.url).toBe('https://example.com/article');
    expect(ctx.page.title).toBe('示例文章');
    expect(ctx.page.links).toHaveLength(25);
    expect(ctx.page.linkCount).toBe(30);
    expect(ctx.page.imageCount).toBe(2);
    expect(ctx.page.formCount).toBe(1);
    expect(ctx.page.forms[0].fieldNames).toEqual(['q']);
    expect(ctx.page.metadata).toEqual({ description: 'demo' });
    expect(ctx.page.truncated).toBe(false);
  });

  test('truncates long page text', () => {
    const long = { ...extract, content: { ...extract.content, text: 'x'.repeat(500) } };
    const ctx = buildPageContext(long, { maxChars: 100 });
    expect(ctx.page.truncated).toBe(true);
    expect(ctx.page.text.length).toBeLessThan(150);
    expect(ctx.page.text).toContain('截断');
  });

  test('reports extraction failures without throwing', () => {
    const ctx = buildPageContext({ success: false, error: 'no receiver' });
    expect(ctx.page.error).toBe('no receiver');
    expect(buildPageContext(null).page.error).toBeDefined();
  });
});
