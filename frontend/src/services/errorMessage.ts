/**
 * Normalize any backend/axios error into a render-safe string.
 *
 * Backend error shapes seen in the wild:
 * - FastAPI 422: { detail: [{ loc, msg, type }, ...] }  (detail is an ARRAY)
 * - api_error:   { code, message, details: {...} }
 * - HTTPException: { detail: "..." } or { detail: {...} }
 * Rendering any of the non-string variants crashes React with
 * "Objects are not valid as a React child".
 */
export function toErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (!err) return fallback
  if (typeof err === 'string') return err || fallback

  const anyErr = err as {
    response?: { data?: unknown }
    message?: unknown
    detail?: unknown
  }

  const candidates: unknown[] = [
    (anyErr.response?.data as { detail?: unknown })?.detail,
    (anyErr.response?.data as { message?: unknown })?.message,
    anyErr.detail,
    anyErr.message,
  ]

  for (const candidate of candidates) {
    const text = stringifyCandidate(candidate)
    if (text) return text
  }
  return fallback
}

function stringifyCandidate(value: unknown): string | null {
  if (value == null) return null
  if (typeof value === 'string') return value.trim() || null
  if (Array.isArray(value)) {
    // FastAPI 422 shape: join the per-field messages.
    const parts = value
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const rec = item as { loc?: unknown[]; msg?: unknown }
          const where = Array.isArray(rec.loc) ? rec.loc.join('.') : ''
          const msg = typeof rec.msg === 'string' ? rec.msg : JSON.stringify(item)
          return where ? `${where}: ${msg}` : msg
        }
        return String(item)
      })
      .filter(Boolean)
    return parts.length ? parts.join('; ') : null
  }
  if (typeof value === 'object') {
    const rec = value as { message?: unknown; detail?: unknown }
    if (typeof rec.message === 'string' && rec.message.trim()) return rec.message
    if (typeof rec.detail === 'string' && rec.detail.trim()) return rec.detail
    try {
      return JSON.stringify(value)
    } catch {
      return null
    }
  }
  return String(value)
}
