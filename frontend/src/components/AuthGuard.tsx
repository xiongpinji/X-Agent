import React from 'react'
import { getStoredAuthToken, redirectToLogin } from '@/services/authHeaders'
import { useAppStore } from '@/store/appStore'

interface AuthGuardProps {
  children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
  const isAuthenticated = useAppStore((state) => state.isAuthenticated)
  const hasToken = !!getStoredAuthToken()

  React.useEffect(() => {
    if (!isAuthenticated && !hasToken) {
      redirectToLogin()
    }
  }, [hasToken, isAuthenticated])

  if (!isAuthenticated && !hasToken) {
    return (
      <div className="panda-auth-loading" role="status" aria-live="polite">
        正在进入登录...
      </div>
    )
  }

  return <>{children}</>
}

export default AuthGuard
