import React, { useState } from 'react'
import { toErrorMessage } from '@/services/errorMessage'
import { apiClient } from '@/services/api'
import { useI18n } from '@/i18n/context'
import clsx from 'clsx'

interface ReviewComment {
  dimension?: string
  severity?: 'info' | 'warning' | 'error'
  line?: number
  message: string
  suggestion?: string
}

interface ReviewResult {
  approved: boolean
  score?: number
  comments: ReviewComment[]
}

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'java', label: 'Java' },
] as const

const CodeReviewPage: React.FC = () => {
  const { t } = useI18n()
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState<string>('python')
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submitReview = async () => {
    if (!code.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = (await apiClient.postCodeReview(code, language)) as {
        approved?: boolean
        status?: string
        score?: number
        comments?: ReviewComment[]
        findings?: ReviewComment[]
        results?: ReviewComment[]
      } | null
      setResult({
        approved: resp?.approved ?? resp?.status === 'approved',
        score: resp?.score,
        comments: resp?.comments ?? resp?.findings ?? resp?.results ?? [],
      })
    } catch (err) {
      setError(toErrorMessage(err, 'Review request failed'))
    } finally {
      setLoading(false)
    }
  }

  const severityBadge: Record<string, string> = {
    error: 'badge-danger',
    warning: 'badge-warning',
    info: 'badge-muted',
  }

  const inputCls =
    'w-full px-3 py-2 border border-[var(--divider)] bg-transparent text-sm outline-none transition-colors focus:border-[var(--fg)] placeholder:opacity-40'

  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-4xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div className="w-12 border-t-2 mb-5" style={{ borderColor: 'var(--fg)' }} aria-hidden="true" />
          <h1 className="page-title">{t('codeReview.title', 'Code Review')}</h1>
          <p className="page-subtitle">
            {t('codeReview.subtitle', 'Submit code or a diff for multi-dimensional AI review (logic, security, style, tests)')}
          </p>
        </header>

        {/* Input */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-3">
            <label
              htmlFor="review-language"
              className="text-[11px] uppercase tracking-[0.06em] opacity-50"
            >
              {t('codeReview.language', 'Language')}
            </label>
            <select
              id="review-language"
              value={language}
              onChange={e => setLanguage(e.target.value)}
              className="px-3 py-1.5 border border-[var(--divider)] bg-transparent text-sm outline-none"
            >
              {LANGUAGES.map(lang => (
                <option key={lang.value} value={lang.value}>{lang.label}</option>
              ))}
            </select>
          </div>
          <textarea
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder={t('codeReview.placeholder', 'Paste your code or git diff here...')}
            rows={10}
            className={clsx(inputCls, 'px-4 py-3 font-mono resize-y')}
          />
          <button
            onClick={submitReview}
            disabled={!code.trim() || loading}
            className="mt-3 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '⏳ Reviewing...' : '🔍 Submit Review'}
          </button>
        </div>

        {/* Error — thin border, transparent background */}
        {error && (
          <div className="mb-6 p-3 border border-[#dc2626]/30 text-sm text-[#dc2626]" role="alert">
            ⚠️ {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div>
            {/* Approval status — inline badge row, no colored panel */}
            <div className="mb-8 flex items-center gap-4 flex-wrap">
              <span className={clsx('badge-status', result.approved ? 'badge-success' : 'badge-warning')}>
                {result.approved ? '✓ ' : '! '}
                {result.approved ? t('codeReview.approved', 'Approved') : t('codeReview.changesRequested', 'Changes Requested')}
              </span>
              {result.score != null && (
                <span className="text-[13px] opacity-60">
                  Score: <span className="font-data">{result.score}/100</span>
                </span>
              )}
            </div>

            {/* Comments list — hairline divider rows */}
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('codeReview.comments', 'Comments')} {result.comments.length > 0 && `(${result.comments.length})`}
            </h2>
            {result.comments.length === 0 ? (
              <p className="empty-state">
                ✓ {t('codeReview.noIssues', 'No issues found. Code looks good!')}
              </p>
            ) : (
              result.comments.map((c, i) => {
                const severity = c.severity ?? 'info'
                return (
                  <div key={i} className="row-line">
                    <div className="flex items-start gap-3">
                      <span className={clsx('badge-status shrink-0 mt-0.5', severityBadge[severity])}>
                        {severity}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          {c.dimension && <span className="text-xs font-semibold uppercase tracking-wide">{c.dimension}</span>}
                          {c.line != null && <span className="text-xs opacity-50 font-data">Line {c.line}</span>}
                        </div>
                        <p className="text-sm font-medium break-words">{c.message}</p>
                        {c.suggestion && (
                          <p className="text-xs mt-1 opacity-60">💡 {c.suggestion}</p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default CodeReviewPage
