/**
 * X-Agent Browser Extension - Backend API Client
 * Direct HTTP integration with the X-Agent backend, so the extension is
 * usable without the desktop app (native messaging stays optional).
 *
 * Backend contract (backend/app/api/agents.py):
 *   POST /api/v1/agents/run          -> { trace_id, status, answer, ... }
 *   POST /api/v1/agents/run/stream   -> SSE: `event: trace` / `event: completed`
 *   GET  /health                     -> { status: "ok", service: "x-agent" } (public)
 * Auth: `x-api-key` header (also exempts the request from CSRF middleware).
 */

export const BACKEND_SETTINGS_KEY = 'xagent_backend';

export const DEFAULT_BACKEND_SETTINGS = {
  baseUrl: 'http://localhost:8000',
  apiKey: '',
  useStreaming: false,
  attachPageContent: true,
  maxPageTextChars: 8000
};

/** Error thrown for any backend API failure; carries HTTP status when present. */
export class ApiClientError extends Error {
  constructor(message, status = null, details = null) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.details = details;
  }
}

/** Normalize a user-entered base URL (trims, strips trailing slash, adds scheme). */
export function normalizeBaseUrl(raw) {
  let url = String(raw || '').trim();
  if (!url) {
    return DEFAULT_BACKEND_SETTINGS.baseUrl;
  }
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(url)) {
    url = `http://${url}`;
  }
  return url.replace(/\/+$/, '');
}

function buildHeaders(settings) {
  const headers = { 'Content-Type': 'application/json' };
  const key = (settings && settings.apiKey || '').trim();
  if (key) {
    headers['x-api-key'] = key;
  }
  return headers;
}

function friendlyHttpError(status, body) {
  const detail = body && (body.detail || body.message || body.error);
  if (status === 401) {
    return new ApiClientError('认证失败：请检查 API Key（401）', status, body);
  }
  if (status === 403) {
    return new ApiClientError(
      '被后端拒绝（403）：POST 需要 API Key 或 CSRF token，请在设置中填写 API Key',
      status,
      body
    );
  }
  if (status === 422) {
    const errors = body && body.details && body.details.errors;
    const field = Array.isArray(errors) && errors[0] && errors[0].field;
    return new ApiClientError(
      `请求校验失败${field ? `（字段: ${field}）` : ''}${detail ? `: ${detail}` : ''}`,
      status,
      body
    );
  }
  if (status >= 500) {
    return new ApiClientError(`后端内部错误（${status}）`, status, body);
  }
  return new ApiClientError(detail ? String(detail) : `请求失败（${status}）`, status, body);
}

async function parseResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/* ------------------------------------------------------------------ */
/* Settings storage (chrome.storage.local)                             */
/* ------------------------------------------------------------------ */

/** Load backend settings merged over defaults. */
export async function loadBackendSettings() {
  try {
    const result = await chrome.storage.local.get(BACKEND_SETTINGS_KEY);
    const stored = result && result[BACKEND_SETTINGS_KEY];
    const settings = { ...DEFAULT_BACKEND_SETTINGS, ...(stored || {}) };
    settings.baseUrl = normalizeBaseUrl(settings.baseUrl);
    settings.apiKey = String(settings.apiKey || '');
    return settings;
  } catch (error) {
    console.error('[X-Agent API] Error loading backend settings:', error);
    return { ...DEFAULT_BACKEND_SETTINGS };
  }
}

/** Merge-persist partial settings; returns the saved settings. */
export async function saveBackendSettings(partial) {
  const current = await loadBackendSettings();
  const merged = { ...current, ...partial };
  merged.baseUrl = normalizeBaseUrl(merged.baseUrl);
  merged.apiKey = String(merged.apiKey || '');
  await chrome.storage.local.set({ [BACKEND_SETTINGS_KEY]: merged });
  return merged;
}

/* ------------------------------------------------------------------ */
/* Health check                                                        */
/* ------------------------------------------------------------------ */

/**
 * GET {base}/health (public endpoint, no auth needed).
 * @returns {Promise<{ok: boolean, status?: string, service?: string, httpStatus?: number, latencyMs?: number, error?: string}>}
 */
export async function checkHealth(baseUrl, apiKey = '', timeoutMs = 5000) {
  const base = normalizeBaseUrl(baseUrl);
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  const startedAt = Date.now();
  try {
    const headers = {};
    const key = String(apiKey || '').trim();
    if (key) {
      headers['x-api-key'] = key;
    }
    const response = await fetch(`${base}/health`, {
      method: 'GET',
      headers,
      signal: controller ? controller.signal : undefined
    });
    const body = await parseResponseBody(response);
    if (!response.ok) {
      return {
        ok: false,
        httpStatus: response.status,
        latencyMs: Date.now() - startedAt,
        error: `HTTP ${response.status}`
      };
    }
    const payload = body && typeof body === 'object' ? body : {};
    if (payload.status && payload.status !== 'ok' && payload.status !== 'healthy') {
      return {
        ok: false,
        status: payload.status,
        service: payload.service,
        latencyMs: Date.now() - startedAt,
        error: `服务状态: ${payload.status}`
      };
    }
    return {
      ok: true,
      status: payload.status || 'ok',
      service: payload.service,
      httpStatus: response.status,
      latencyMs: Date.now() - startedAt
    };
  } catch (error) {
    const aborted = error && (error.name === 'AbortError' || /aborted/i.test(String(error.message)));
    return {
      ok: false,
      error: aborted
        ? `连接超时（${timeoutMs}ms）`
        : `无法连接到 ${base}，请确认后端已启动`
    };
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

/* ------------------------------------------------------------------ */
/* Agent run (non-streaming)                                           */
/* ------------------------------------------------------------------ */

/**
 * POST /api/v1/agents/run.
 * @param {object} options
 * @param {string} options.task
 * @param {object} [options.extraContext]
 * @param {string} [options.sessionId]
 * @param {number} [options.maxIterations]
 * @param {object} settings backend settings (baseUrl / apiKey)
 * @returns {Promise<object>} AgentRunResponse-shaped body (answer, trace_id, status, ...)
 */
export async function runAgent({ task, extraContext, sessionId, maxIterations }, settings) {
  const base = normalizeBaseUrl(settings && settings.baseUrl);
  const body = {
    task: String(task || '')
  };
  if (extraContext && typeof extraContext === 'object' && Object.keys(extraContext).length > 0) {
    body.extra_context = extraContext;
  }
  if (sessionId) {
    body.session_id = String(sessionId);
  }
  if (Number.isInteger(maxIterations) && maxIterations >= 1 && maxIterations <= 100) {
    body.max_iterations = maxIterations;
  }

  let response;
  try {
    response = await fetch(`${base}/api/v1/agents/run`, {
      method: 'POST',
      headers: buildHeaders(settings),
      body: JSON.stringify(body)
    });
  } catch (error) {
    throw new ApiClientError(`无法连接到后端 ${base}：${error.message}`, null, error);
  }

  const responseBody = await parseResponseBody(response);
  if (!response.ok) {
    throw friendlyHttpError(response.status, responseBody);
  }
  return responseBody;
}

/* ------------------------------------------------------------------ */
/* Agent run (SSE streaming)                                           */
/* ------------------------------------------------------------------ */

/**
 * Parse one SSE frame string ("event: x\ndata: {...}") into {event, data}.
 * Data lines are joined with "\n" per the SSE spec.
 */
export function parseSSEFrame(frame) {
  const lines = frame.split('\n');
  let event = 'message';
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''));
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  const raw = dataLines.join('\n');
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: raw };
  }
}

/**
 * Split a stream buffer into complete SSE frames.
 * @returns {{frames: string[], rest: string}}
 */
export function extractSSEFrames(buffer) {
  const parts = String(buffer).split('\n\n');
  const rest = parts.pop();
  return { frames: parts, rest };
}

/**
 * POST /api/v1/agents/run/stream and consume the SSE response with a
 * ReadableStream reader (works in MV3 service workers and popup pages).
 *
 * Emitted events (backend/app/api/agents.py::run_agent_stream):
 *   event: trace     data: <TraceEvent dict>
 *   event: completed data: {"_final": true, "result": {...}} | {"_final": true, "error": "..."}
 *
 * @returns {Promise<object>} the final run result
 */
export async function runAgentStream(
  { task, extraContext, sessionId, maxIterations },
  settings,
  { onTraceEvent, onCompleted, signal } = {}
) {
  const base = normalizeBaseUrl(settings && settings.baseUrl);
  const body = { task: String(task || '') };
  if (extraContext && typeof extraContext === 'object' && Object.keys(extraContext).length > 0) {
    body.extra_context = extraContext;
  }
  if (sessionId) {
    body.session_id = String(sessionId);
  }
  if (Number.isInteger(maxIterations) && maxIterations >= 1 && maxIterations <= 100) {
    body.max_iterations = maxIterations;
  }

  let response;
  try {
    response = await fetch(`${base}/api/v1/agents/run/stream`, {
      method: 'POST',
      headers: buildHeaders(settings),
      body: JSON.stringify(body),
      signal
    });
  } catch (error) {
    if (error && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiClientError(`无法连接到后端 ${base}：${error.message}`, null, error);
  }

  const contentType = response.headers ? response.headers.get('content-type') || '' : '';
  if (!response.ok) {
    const responseBody = await parseResponseBody(response);
    throw friendlyHttpError(response.status, responseBody);
  }
  if (!contentType.includes('text/event-stream') || !response.body) {
    // Backend answered JSON instead of SSE (older deployments / proxies).
    const payload = await parseResponseBody(response);
    if (payload && typeof payload === 'object' && payload.error) {
      throw new ApiClientError(String(payload.error));
    }
    if (onCompleted && payload && typeof payload === 'object') {
      onCompleted(payload);
    }
    return payload;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  const handleFrame = (frame) => {
    const parsed = parseSSEFrame(frame);
    if (!parsed) {
      return;
    }
    if (parsed.event === 'trace') {
      if (onTraceEvent) {
        onTraceEvent(parsed.data);
      }
      return;
    }
    // "completed" and any other terminal event carry the final payload.
    const data = parsed.data;
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      if (data._final) {
        if (data.error) {
          finalResult = { status: 'failed', error: String(data.error) };
        } else {
          finalResult = data.result || data;
        }
      } else {
        finalResult = data.result || data;
      }
    } else {
      finalResult = { status: 'failed', error: String(data) };
    }
    if (onCompleted) {
      onCompleted(finalResult);
    }
  };

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = extractSSEFrames(buffer);
      buffer = rest;
      frames.forEach(handleFrame);
    }
    if (done) {
      buffer += decoder.decode();
      const { frames } = extractSSEFrames(`${buffer}\n\n`);
      frames.forEach(handleFrame);
      break;
    }
  }

  if (!finalResult) {
    throw new ApiClientError('流式响应意外结束（未收到 completed 事件）');
  }
  if (finalResult.status && ['failed', 'error'].includes(finalResult.status)) {
    const message = finalResult.error || finalResult.answer || '任务执行失败';
    throw new ApiClientError(String(message), null, finalResult);
  }
  return finalResult;
}

/* ------------------------------------------------------------------ */
/* Page content -> extra_context                                       */
/* ------------------------------------------------------------------ */

/**
 * Convert a content-script extraction result (content.js EXTRACT_CONTENT)
 * into a compact `extra_context` payload for the backend agent.
 */
export function buildPageContext(extractResult, { maxChars = DEFAULT_BACKEND_SETTINGS.maxPageTextChars } = {}) {
  const context = {
    source: 'xagent-browser-extension'
  };

  if (!extractResult || !extractResult.success || !extractResult.content) {
    context.page = {
      error: (extractResult && extractResult.error) || '页面内容提取失败'
    };
    return context;
  }

  const content = extractResult.content;
  const rawText = typeof content.text === 'string' ? content.text : '';
  const limit = Number.isInteger(maxChars) && maxChars > 0 ? maxChars : 8000;
  const truncated = rawText.length > limit;
  const links = Array.isArray(content.links) ? content.links : [];
  const images = Array.isArray(content.images) ? content.images : [];
  const forms = Array.isArray(content.forms) ? content.forms : [];

  context.page = {
    url: content.url || '',
    title: content.title || '',
    text: truncated ? `${rawText.slice(0, limit)}…[截断，共 ${rawText.length} 字符]` : rawText,
    truncated,
    linkCount: links.length,
    links: links.slice(0, 25).map((l) => ({ text: l.text || '', href: l.href || '' })),
    imageCount: images.length,
    formCount: forms.length,
    forms: forms.slice(0, 10).map((f) => ({
      id: f.id || '',
      name: f.name || '',
      method: f.method || '',
      action: f.action || '',
      fieldNames: (f.fields || []).map((field) => field.name).filter(Boolean)
    })),
    metadata: content.metadata && typeof content.metadata === 'object' ? content.metadata : {}
  };
  return context;
}

/**
 * Convenience wrapper: run a task with optional streaming, resolving the
 * final AgentRunResponse either way.
 */
export async function runTask(options, settings, handlers = {}) {
  if (settings && settings.useStreaming) {
    return runAgentStream(options, settings, handlers);
  }
  return runAgent(options, settings);
}
