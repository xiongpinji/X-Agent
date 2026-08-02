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
  const { setUser, theme } = useAppStore()
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
      } catch (err: any) {
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

      // Set user in store
      setUser({
        id: response.user?.id || '',
        name: response.user?.display_name || email.split('@')[0],
        email: response.user?.email || email,
      })

      navigate('/')
    } catch (err: any) {
      setError(toErrorMessage(err, 'Authentication failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={clsx(
      'min-h-screen flex items-center justify-center px-4',
      theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'
    )}>
      <div className={clsx(
        'w-full max-w-md rounded-xl shadow-lg p-8',
        theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
      )}>
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className={clsx(
            'text-3xl font-bold mb-2',
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          )}>
            X-Agent
          </h1>
          <p className={clsx(
            'text-sm',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'apikey' ? (
            <div>
              <label
                htmlFor="apikey"
                className={clsx(
                  'block text-sm font-medium mb-1',
                  theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                )}
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
                className={clsx(
                  'w-full px-4 py-2 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
                  theme === 'dark'
                    ? 'bg-slate-800 text-white border-slate-700 placeholder-slate-500'
                    : 'bg-white text-slate-900 border-slate-300 placeholder-slate-400'
                )}
              />
              <p className={clsx('mt-1 text-xs', theme === 'dark' ? 'text-slate-500' : 'text-slate-400')}>
                开发模式：直接输入后端 X-API-Key 即可进入
              </p>
            </div>
          ) : (
            <>
          <div>
            <label
              htmlFor="email"
              className={clsx(
                'block text-sm font-medium mb-1',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
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
              className={clsx(
                'w-full px-4 py-2 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border-slate-700 placeholder-slate-500'
                  : 'bg-white text-slate-900 border-slate-300 placeholder-slate-400'
              )}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className={clsx(
                'block text-sm font-medium mb-1',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
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
              className={clsx(
                'w-full px-4 py-2 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border-slate-700 placeholder-slate-500'
                  : 'bg-white text-slate-900 border-slate-300 placeholder-slate-400'
              )}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label
                htmlFor="confirm-password"
                className={clsx(
                  'block text-sm font-medium mb-1',
                  theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                )}
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
                className={clsx(
                  'w-full px-4 py-2 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
                  theme === 'dark'
                    ? 'bg-slate-800 text-white border-slate-700 placeholder-slate-500'
                    : 'bg-white text-slate-900 border-slate-300 placeholder-slate-400'
                )}
              />
            </div>
          )}
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors',
              loading
                ? 'opacity-50 cursor-not-allowed bg-blue-600 text-white'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            )}
          >
            {loading ? (
              <Loader size={20} className="animate-spin" />
            ) : mode === 'login' ? (
              <LogIn size={20} />
            ) : (
              <UserPlus size={20} />
            )}
            {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : 'Enter'}
          </button>
        </form>

        {/* Toggle mode */}
        <div className="mt-6 text-center space-y-2">
          <button
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError(null)
            }}
            className="block w-full text-sm text-blue-600 hover:text-blue-700 font-medium"
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
            className="block w-full text-sm text-slate-500 hover:text-slate-700 font-medium"
          >
            {mode === 'apikey' ? '← Email login' : '🔑 API Key login (dev)'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
