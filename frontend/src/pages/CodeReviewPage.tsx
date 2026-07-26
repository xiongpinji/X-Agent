import React, { useState } from 'react'
import { toErrorMessage } from '@/services/errorMessage'
import { apiClient } from '@/services/api'
import { useAppStore } from '@/store/appStore'
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
  const { theme } = useAppStore()
  const { t } = useI18n()
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState<string>('python')
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isDark = theme === 'dark'

  const submitReview = async () => {
    if (!code.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await apiClient.postCodeReview(code, language)
      setResult({
        approved: resp?.approved ?? resp?.status === 'approved',
        score: resp?.score,
        comments: resp?.comments ?? resp?.findings ?? resp?.results ?? [],
      })
    } catch (err: any) {
      setError(toErrorMessage(err, 'Review request failed'))
    } finally {
      setLoading(false)
    }
  }

  const severityColors: Record<string, string> = {
    error: 'text-red-500 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
    warning: 'text-amber-600 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
    info: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
  }

  const severityIcons: Record<string, string> = { error: '🔴', warning: '🟡', info: '🔵' }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">🔍 {t('codeReview.title', 'Code Review')}</h1>
      <p className={clsx('text-sm mb-6', isDark ? 'text-slate-400' : 'text-slate-500')}>
        {t('codeReview.subtitle', 'Submit code or a diff for multi-dimensional AI review (logic, security, style, tests)')}
      </p>

      {/* Input */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-3">
          <label
            htmlFor="review-language"
            className={clsx('text-sm font-medium', isDark ? 'text-slate-300' : 'text-slate-700')}
          >
            {t('codeReview.language', 'Language')}
          </label>
          <select
            id="review-language"
            value={language}
            onChange={e => setLanguage(e.target.value)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-sm border',
              isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
            )}
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
          className={clsx(
            'w-full px-4 py-3 rounded-lg border text-sm font-mono resize-y',
            isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
          )}
        />
        <button
          onClick={submitReview}
          disabled={!code.trim() || loading}
          className="mt-3 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? '⏳ Reviewing...' : '🔍 Submit Review'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className={clsx(
          'mb-4 p-3 rounded-lg border text-sm',
          isDark ? 'bg-red-900/20 border-red-800 text-red-400' : 'bg-red-50 border-red-200 text-red-600'
        )}>
          ⚠️ {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3">
          {/* Approval status */}
          <div className={clsx(
            'flex items-center gap-3 p-4 rounded-xl border',
            result.approved
              ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
              : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
          )}>
            <span className="text-2xl">{result.approved ? '✅' : '⚠️'}</span>
            <div>
              <p className={clsx('font-semibold text-sm', result.approved ? 'text-green-700 dark:text-green-400' : 'text-amber-700 dark:text-amber-400')}>
                {result.approved ? t('codeReview.approved', 'Approved') : t('codeReview.changesRequested', 'Changes Requested')}
              </p>
              {result.score != null && (
                <p className={clsx('text-xs', isDark ? 'text-slate-400' : 'text-slate-500')}>
                  Score: {result.score}/100
                </p>
              )}
            </div>
          </div>

          {/* Comments list */}
          <h2 className="text-lg font-semibold">
            {t('codeReview.comments', 'Comments')} {result.comments.length > 0 && `(${result.comments.length})`}
          </h2>
          {result.comments.length === 0 ? (
            <p className={clsx('text-sm py-6 text-center', isDark ? 'text-slate-500' : 'text-slate-400')}>
              ✓ {t('codeReview.noIssues', 'No issues found. Code looks good!')}
            </p>
          ) : (
            result.comments.map((c, i) => {
              const severity = c.severity ?? 'info'
              return (
                <div key={i} className={clsx('p-4 rounded-lg border', severityColors[severity])}>
                  <div className="flex items-start gap-2">
                    <span>{severityIcons[severity]}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {c.dimension && <span className="text-xs font-semibold uppercase">{c.dimension}</span>}
                        {c.line != null && <span className="text-xs opacity-70">Line {c.line}</span>}
                      </div>
                      <p className="text-sm font-medium">{c.message}</p>
                      {c.suggestion && (
                        <p className="text-xs mt-1 opacity-80">💡 {c.suggestion}</p>
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
  )
}

export default CodeReviewPage
