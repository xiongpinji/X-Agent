import React, { useState } from 'react'
import { toErrorMessage } from '@/services/errorMessage'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { Loader, LogIn, UserPlus, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

type AuthMode = 'login' | 'register' | 'apikey'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const { setUser } = useAppStore()
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // API Key quick login
    if (mode === 'apikey') {
      if (!apiKey.trim()) {
        setError('API Key is required')
        return
      }
      try {
        setLoading(true)
        localStorage.setItem('api_key', apiKey.trim())
        setUser({ id: 'api-key-user', name: 'Developer', email: 'dev@local' })
        navigate('/')
      } catch (err) {
        setError(toErrorMessage(err, 'API Key login failed'))
      } finally {
        setLoading(false)
      }
      return
    }

    if (!email.trim() || !password.trim()) {
      setError('Email and password are required')
      return
    }

    if (mode === 'register') {
      if (password !== confirmPassword) {
        setError('Passwords do not match')
        return
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters')
        return
      }
      if (!/[A-Z]/.test(password) || !/[a-z]/.test(password)) {
        setError('Password must contain both uppercase and lowercase letters')
        return
      }
      if (!/\d/.test(password)) {
        setError('Password must contain at least one digit')
        return
      }
    }

    try {
      setLoading(true)
      const response = mode === 'login'
        ? await apiClient.login(email, password)
        : await apiClient.register(email, password)

      // Store tokens
      localStorage.setItem('auth_token', response.access_token)
      if (response.refresh_token) {
        localStorage.setItem('refresh_token', response.refresh_token)
      }
      // 角色供侧栏导航过滤（Layout.currentRoleFilter；后端 scope 鉴权仍是权威）
      const role = (response.user as { role?: string } | undefined)?.role
      localStorage.setItem('user_role', role || 'user')

      // Set user in store
      setUser({
        id: response.user?.id || '',
        name: response.user?.display_name || email.split('@')[0],
        email: response.user?.email || email,
      })

      navigate('/')
    } catch (err) {
      setError(toErrorMessage(err, 'Authentication failed'))
    } finally {
      setLoading(false)
    }
  }

  // Square thin-border inputs — Codex terminal feel, theme via CSS vars.
  const inputCls =
    'w-full px-3 py-2 border bg-transparent text-sm outline-none transition-colors placeholder:opacity-40 focus:border-[var(--fg)]'

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--bg)', color: 'var(--fg)' }}
    >
      {/* Hairline container — no radius, no shadow */}
      <div
        className="w-full max-w-md border p-8"
        style={{ borderColor: 'var(--divider)' }}
      >
        {/* Header */}
        <div className="mb-8">
          <div
            className="w-10 border-t-2 mb-4"
            style={{ borderColor: 'var(--fg)' }}
            aria-hidden="true"
          />
          <h1 className="text-[22px] font-medium tracking-tight">X-Agent</h1>
          <p className="text-[13px] opacity-50 mt-1">
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        {/* Error — thin border, transparent background */}
        {error && (
          <div
            role="alert"
            className="mb-4 flex items-center gap-2 border px-3 py-2 text-sm text-[#dc2626]"
            style={{ borderColor: 'rgba(220,38,38,.35)' }}
          >
            <AlertTriangle size={15} />
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'apikey' ? (
            <div>
              <label
                htmlFor="apikey"
                className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1"
              >
                API Key
              </label>
              <input
                id="apikey"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="xagent-dev-key-2024"
                autoComplete="off"
                className={inputCls}
                style={{ borderColor: 'var(--divider)' }}
              />
              <p className="mt-1 text-xs opacity-50">
                开发模式：直接输入后端 X-API-Key 即可进入
              </p>
            </div>
          ) : (
            <>
          <div>
            <label
              htmlFor="email"
              className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              className={inputCls}
              style={{ borderColor: 'var(--divider)' }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className={inputCls}
              style={{ borderColor: 'var(--divider)' }}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label
                htmlFor="confirm-password"
                className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1"
              >
                Confirm Password
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
                className={inputCls}
                style={{ borderColor: 'var(--divider)' }}
              />
            </div>
          )}
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-4 py-2.5 font-medium text-sm text-white transition-opacity',
              loading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90'
            )}
            style={{ backgroundColor: 'var(--accent)' }}
          >
            {loading ? (
              <Loader size={18} className="animate-spin" />
            ) : mode === 'login' ? (
              <LogIn size={18} />
            ) : (
              <UserPlus size={18} />
            )}
            {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : 'Enter'}
          </button>
        </form>

        {/* Toggle mode */}
        <div
          className="mt-6 pt-4 text-center space-y-2 border-t"
          style={{ borderColor: 'var(--divider)' }}
        >
          <button
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError(null)
            }}
            className="block w-full text-sm font-medium hover:opacity-80 transition-opacity"
            style={{ color: 'var(--accent)' }}
          >
            {mode === 'login'
              ? "Don't have an account? Sign up"
              : mode === 'register'
              ? 'Already have an account? Sign in'
              : 'Back to email login'}
          </button>
          <button
            onClick={() => {
              setMode(mode === 'apikey' ? 'login' : 'apikey')
              setError(null)
            }}
            className="block w-full text-sm font-medium opacity-50 hover:opacity-100 transition-opacity"
          >
            {mode === 'apikey' ? '← Email login' : '🔑 API Key login (dev)'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
