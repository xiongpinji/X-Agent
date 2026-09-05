/**
 * X-Agent Chrome Extension - Background Worker Tests
 * Covers the backend-direct features: settings messages, health/status,
 * chat run (plain + SSE) and the context-menu "analyze page" flow.
 */

const { BackgroundWorker } = require('../background.js');

/* ---------------------------- helpers ---------------------------- */

function useInMemoryStorage() {
  const store = new Map();
  chrome.storage.local.get = jest.fn(async (key) => {
    if (typeof key === 'string') {
      return store.has(key) ? { [key]: store.get(key) } : {};
    }
    return Object.fromEntries(store.entries());
  });
  chrome.storage.local.set = jest.fn(async (obj) => {
    Object.entries(obj).forEach(([k, v]) => store.set(k, v));
  });
  return store;
}

const PAGE_EXTRACT = {
  success: true,
  content: {
    url: 'https://example.com/page',
    title: 'Demo',
    text: 'page body text',
    links: [{ text: 'a', href: 'https://example.com/a' }],
    images: [],
    forms: [],
    metadata: {}
  }
};

function jsonFetch(body, status = 200) {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    text: async () => text,
    body: null
  };
}

function sseFetch(frames) {
  const { TextEncoder } = require('util');
  const encoder = new TextEncoder();
  const queue = [...frames];
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'text/event-stream' },
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

let worker;

/** Dispatch a message through the worker and capture the response. */
async function dispatch(type, payload = {}, sender = { tab: { id: 7 } }) {
  const responses = [];
  await worker.handleMessage({ type, payload }, sender, (r) => responses.push(r));
  return responses[0];
}

beforeEach(() => {
  jest.clearAllMocks();
  useInMemoryStorage();
  global.fetch = jest.fn();
  chrome.tabs.sendMessage.mockReset();
  chrome.notifications.create.mockReset();
  chrome.notifications.create.mockImplementation(() => 'notif-id');
  chrome.tabs.sendMessage.mockResolvedValue(PAGE_EXTRACT);

  worker = new BackgroundWorker();
  worker.setupEventListeners();
});

/* ------------------------- settings messages ------------------------ */

describe('background settings messages', () => {
  test('GET_BACKEND_SETTINGS returns defaults', async () => {
    const response = await dispatch('GET_BACKEND_SETTINGS');
    expect(response.success).toBe(true);
    expect(response.settings.baseUrl).toBe('http://localhost:8000');
  });

  test('SAVE_BACKEND_SETTINGS persists normalized settings', async () => {
    const response = await dispatch('SAVE_BACKEND_SETTINGS', {
      baseUrl: 'localhost:9000/',
      apiKey: 'sk-abc'
    });
    expect(response.success).toBe(true);
    expect(response.settings.baseUrl).toBe('http://localhost:9000');
    expect(response.settings.apiKey).toBe('sk-abc');

    const reloaded = await dispatch('GET_BACKEND_SETTINGS');
    expect(reloaded.settings.baseUrl).toBe('http://localhost:9000');
  });

  test('TEST_BACKEND_CONNECTION reports backend health', async () => {
    global.fetch.mockResolvedValue(jsonFetch({ status: 'ok', service: 'x-agent' }));
    const response = await dispatch('TEST_BACKEND_CONNECTION');
    expect(response.success).toBe(true);
    expect(response.health.ok).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({ method: 'GET' })
    );
  });

  test('GET_STATUS reports backend connectivity (direct mode)', async () => {
    global.fetch.mockResolvedValue(jsonFetch({ status: 'ok', service: 'x-agent' }));
    const response = await dispatch('GET_STATUS');
    expect(response.success).toBe(true);
    expect(response.backend.ok).toBe(true);
    expect(response.backend.baseUrl).toBe('http://localhost:8000');
    expect(response.nativeMcp.optional).toBe(true);
    expect(response.connected).toBe(false); // desktop app not installed in tests
  });
});

/* --------------------------- session messages ----------------------- */

describe('background session messages', () => {
  test('GET_SESSION returns the stored session', async () => {
    await chrome.storage.local.set({
      xagent_session: { id: 'session_1', name: 'S1', actions: [{ type: 'click' }] }
    });
    const response = await dispatch('GET_SESSION');
    expect(response.success).toBe(true);
    expect(response.session.name).toBe('S1');
  });

  test('GET_ACTION_HISTORY returns session actions', async () => {
    worker.activeSession = { actions: [{ type: 'navigate' }, { type: 'click' }] };
    const response = await dispatch('GET_ACTION_HISTORY');
    expect(response.success).toBe(true);
    expect(response.history).toHaveLength(2);
  });

  test('SAVE_SETTING persists through StorageManager', async () => {
    const response = await dispatch('SAVE_SETTING', { debugMode: true });
    expect(response.success).toBe(true);
    expect(chrome.storage.local.set).toHaveBeenCalled();
  });
});

/* ------------------------------ chat run ---------------------------- */

describe('background CHAT_RUN', () => {
  test('extracts the page, posts the task with extra_context and returns the answer', async () => {
    global.fetch.mockResolvedValue(
      jsonFetch({ trace_id: 'tr1', status: 'completed', answer: '页面主题是演示' })
    );

    const response = await dispatch('CHAT_RUN', { task: '总结此页', attachPage: true });

    expect(response.success).toBe(true);
    expect(response.result.answer).toBe('页面主题是演示');

    expect(chrome.tabs.sendMessage).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ type: 'EXTRACT_CONTENT', includeText: true })
    );

    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/agents/run');
    const body = JSON.parse(init.body);
    expect(body.task).toBe('总结此页');
    expect(body.extra_context.page.url).toBe('https://example.com/page');
    expect(body.extra_context.page.title).toBe('Demo');
  });

  test('supports streaming (SSE) responses', async () => {
    global.fetch.mockResolvedValue(
      sseFetch([
        'event: trace\ndata: {"event": "iteration_start"}\n\n',
        'event: completed\ndata: {"_final": true, "result": {"trace_id": "tr2", "status": "completed", "answer": "流式答案"}}\n\n'
      ])
    );

    const response = await dispatch('CHAT_RUN', { task: '流式任务', attachPage: false, stream: true });

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/agents/run/stream',
      expect.anything()
    );
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.extra_context).toBeUndefined();
    expect(response.success).toBe(true);
    expect(response.result.answer).toBe('流式答案');
  });

  test('returns a friendly error for empty tasks', async () => {
    const response = await dispatch('CHAT_RUN', { task: '   ' });
    expect(response.success).toBe(false);
    expect(response.error).toBe('任务内容为空');
  });

  test('surfaces API errors (403) to the caller', async () => {
    global.fetch.mockResolvedValue(jsonFetch({ detail: 'forbidden' }, 403));
    const response = await dispatch('CHAT_RUN', { task: 'x', attachPage: false });
    expect(response.success).toBe(false);
    expect(response.error).toContain('API Key');
  });
});

/* -------------------------- analyze page ---------------------------- */

describe('analyzePageInBackground (context menu action)', () => {
  test('extracts, runs the analysis and notifies with the answer', async () => {
    global.fetch.mockResolvedValue(
      jsonFetch({ trace_id: 'tr9', status: 'completed', answer: '这是分析结果' })
    );

    const result = await worker.analyzePageInBackground(7, '');

    expect(result.success).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/agents/run',
      expect.anything()
    );
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.extra_context.page.url).toBe('https://example.com/page');

    const notificationCalls = chrome.notifications.create.mock.calls;
    expect(notificationCalls.length).toBeGreaterThanOrEqual(2);
    expect(notificationCalls[0][0].message).toContain('已开始分析');
    expect(notificationCalls[notificationCalls.length - 1][0].message).toContain('这是分析结果');
  });

  test('notifies on backend failure without throwing', async () => {
    global.fetch.mockRejectedValue(new TypeError('fetch failed'));

    const result = await worker.analyzePageInBackground(7, 'selected text');

    expect(result.success).toBe(false);
    expect(chrome.notifications.create).toHaveBeenCalled();
    const lastCall = chrome.notifications.create.mock.calls.pop()[0];
    expect(lastCall.title).toContain('失败');
  });

  test('ANALYZE_PAGE message delegates to the same flow', async () => {
    global.fetch.mockResolvedValue(
      jsonFetch({ trace_id: 'tr10', status: 'completed', answer: 'ok' })
    );
    const response = await dispatch('ANALYZE_PAGE', { tabId: 7, selectionText: '' });
    expect(response.success).toBe(true);
  });
});

/* ------------------------- createSession robustness ------------------ */

describe('createSession without desktop app', () => {
  test('succeeds even when native messaging is unavailable', async () => {
    const response = await worker.createSession({ sessionName: '直连模式' });
    expect(response.success).toBe(true);
    expect(response.session.name).toBe('直连模式');
    expect(worker.mcpClient.isConnected()).toBe(false);
  });
});
