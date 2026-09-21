import React, { useState } from 'react'
import { apiClient } from '@/services/api'

/**
 * Minimal login/register page (added in the 2026-09-21 live audit).
 *
 * Why: every state-changing backend endpoint requires a JWT principal, and
 * the api client attaches it from localStorage.auth_token — but nothing in
 * the app ever set that token, so the whole UI was read-only-at-best and
 * 401 on every mutation. This page closes that loop.
 */
export default function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      let res
      if (mode === 'login') {
        res = await apiClient.login(email, password)
      } else {
        await apiClient.register(email, password)
        // NOTE: the token returned by /auth/register is rejected as invalid
        // by the backend (live-audit finding 2026-09-21, backend bug to fix);
        // log in again to obtain a working token.
        res = await apiClient.login(email, password)
      }
      localStorage.setItem('auth_token', res.access_token)
      if (res.refresh_token) {
        localStorage.setItem('refresh_token', res.refresh_token)
      }
      window.location.href = '/'
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string; message?: string } } })
        ?.response?.data
      setError(detail?.detail || detail?.message || (err instanceof Error ? err.message : 'Failed'))
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <form onSubmit={submit} className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div>
          <h1 className="text-xl font-semibold text-white">X-Agent</h1>
          <p className="text-sm text-slate-400">
            {mode === 'login' ? 'Sign in to continue' : 'Create your account'}
          </p>
        </div>
        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded-md px-3 py-2">
            {error}
          </div>
        )}
        <label className="block">
          <span className="text-xs text-slate-400">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
            className="mt-1 w-full rounded-md bg-slate-800 border border-slate-700 text-white px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            placeholder="you@example.com"
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">Password</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
            className="mt-1 w-full rounded-md bg-slate-800 border border-slate-700 text-white px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            placeholder="••••••••"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium py-2"
        >
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Register'}
        </button>
        <button
          type="button"
          onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
          className="w-full text-xs text-slate-400 hover:text-slate-200"
        >
          {mode === 'login' ? 'No account? Register' : 'Have an account? Sign in'}
        </button>
      </form>
    </div>
  )
}
