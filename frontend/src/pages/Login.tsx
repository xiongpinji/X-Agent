import React from 'react'
import { Lock, LogIn, Mail } from 'lucide-react'
import { consumeAuthRedirect, storeAuthSession } from '@/services/authHeaders'
import { useAppStore } from '@/store/appStore'

interface LoginResponse {
  access_token: string
  refresh_token?: string
  user?: {
    id?: string
    email?: string
    display_name?: string
    name?: string
  }
}

export default function Login() {
  const setUser = useAppStore((state) => state.setUser)
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload.message || payload.detail || '登录失败')
      }

      const payload = (await response.json()) as LoginResponse
      storeAuthSession(payload.access_token, payload.refresh_token)
      setUser({
        id: payload.user?.id || payload.user?.email || email,
        name: payload.user?.display_name || payload.user?.name || email,
        email: payload.user?.email || email,
      })
      window.location.assign(consumeAuthRedirect('/'))
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="panda-login-page">
      <section className="panda-login-panel" aria-labelledby="login-title">
        <div className="panda-login-brand">
          <div className="panda-login-mark">X</div>
          <div>
            <h1 id="login-title">X-Agent</h1>
            <p>商业控制台登录</p>
          </div>
        </div>

        <form className="panda-login-form" onSubmit={handleSubmit}>
          <label>
            <span>邮箱</span>
            <span className="panda-login-input">
              <Mail size={17} aria-hidden="true" />
              <input
                autoComplete="email"
                inputMode="email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </span>
          </label>

          <label>
            <span>密码</span>
            <span className="panda-login-input">
              <Lock size={17} aria-hidden="true" />
              <input
                autoComplete="current-password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </span>
          </label>

          {error ? <p className="panda-login-error">{error}</p> : null}

          <button className="panda-login-submit" disabled={isSubmitting} type="submit">
            <LogIn size={18} aria-hidden="true" />
            {isSubmitting ? '登录中' : '登录'}
          </button>
        </form>
      </section>
    </main>
  )
}
