import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { securityOps, MFASetupResponse, SessionItem, SSOProvidersResponse, SSOStatusResponse } from '@/services/securityOps'
import { useI18n } from '@/i18n/context'
import {
  ShieldCheck,
  KeyRound,
  MonitorSmartphone,
  RefreshCw,
  Copy,
  Check,
  Trash2,
  Globe,
  Lock,
} from 'lucide-react'
import clsx from 'clsx'

/**
 * SecurityAuthPage (A17) — 安全与认证管理。
 * 数据来源(全部为真实后端端点, 见 services/securityOps.ts 头部注释):
 * - MFA 设置/验证: POST /api/v1/auth/mfa/setup, POST /api/v1/auth/mfa/verify
 * - SSO 提供方: GET /api/v1/sso/providers, GET /api/v1/sso/status
 * - 活跃会话: GET /api/v1/auth/sessions, DELETE /api/v1/auth/sessions/{id},
 *   POST /api/v1/auth/sessions/revoke-all
 * 后端缺失 "MFA 禁用" / "MFA 状态" 端点 — 对应入口置灰 coming soon。
 * 依赖中无 qrcode 库 — otpauth URI 以明文+复制形式展示。
 */
export const SecurityAuthPage: React.FC = () => {
  const { theme, setError } = useAppStore()
  const { t } = useI18n()

  // MFA state
  const [mfaMethod, setMfaMethod] = useState<'totp' | 'sms' | 'email'>('totp')
  const [mfaSetup, setMfaSetup] = useState<MFASetupResponse | null>(null)
  const [mfaLoading, setMfaLoading] = useState(false)
  const [challengeId, setChallengeId] = useState('')
  const [verifyCode, setVerifyCode] = useState('')
  const [verifyResult, setVerifyResult] = useState<boolean | null>(null)
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  // SSO state
  const [providers, setProviders] = useState<SSOProvidersResponse | null>(null)
  const [ssoStatus, setSsoStatus] = useState<SSOStatusResponse | null>(null)

  // Sessions state
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)

  const loadSessions = useCallback(async () => {
    try {
      setSessionsLoading(true)
      setSessions(await securityOps.listSessions())
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load sessions')
    } finally {
      setSessionsLoading(false)
    }
  }, [setError])

  const loadSSO = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([
        securityOps.listSSOProviders(),
        securityOps.getSSOStatus(),
      ])
      setProviders(p)
      setSsoStatus(s)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load SSO configuration')
    }
  }, [setError])

  useEffect(() => {
    loadSSO()
    loadSessions()
  }, [loadSSO, loadSessions])

  const handleSetupMFA = async () => {
    try {
      setMfaLoading(true)
      setVerifyResult(null)
      const result = await securityOps.setupMFA(mfaMethod)
      setMfaSetup(result)
      if (result.challenge_id) setChallengeId(result.challenge_id)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to set up MFA')
    } finally {
      setMfaLoading(false)
    }
  }

  const handleVerifyMFA = async () => {
    try {
      setVerifyLoading(true)
      const result = await securityOps.verifyMFA(challengeId, verifyCode)
      setVerifyResult(result.verified)
    } catch (error) {
      setVerifyResult(false)
      setError(error instanceof Error ? error.message : 'MFA verification failed')
    } finally {
      setVerifyLoading(false)
    }
  }

  const handleCopyURI = async () => {
    if (!mfaSetup?.provisioning_uri) return
    try {
      await navigator.clipboard.writeText(mfaSetup.provisioning_uri)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError(t('security.copyFailed', 'Copy failed — please copy the URI manually'))
    }
  }

  const handleRevokeSession = async (sessionId: string) => {
    if (!confirm(t('security.revokeConfirm', 'Revoke this session?'))) return
    try {
      await securityOps.revokeSession(sessionId)
      setSessions(sessions.filter((s) => s.session_id !== sessionId))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to revoke session')
    }
  }

  const handleRevokeAll = async () => {
    if (!confirm(t('security.revokeAllConfirm', 'Revoke all other sessions?'))) return
    try {
      await securityOps.revokeAllSessions(true)
      await loadSessions()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to revoke sessions')
    }
  }

  const cardCls = clsx(
    'rounded-lg p-6',
    theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
  )
  const headingCls = clsx('text-lg font-semibold mb-4 flex items-center gap-2', theme === 'dark' ? 'text-white' : 'text-slate-900')
  const subTextCls = clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')
  const inputCls = clsx(
    'px-3 py-2 rounded-lg border text-sm w-full',
    theme === 'dark'
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
  )

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
            {t('security.title', 'Security & Authentication')}
          </h1>
          <p className={subTextCls}>
            {t('security.subtitle', 'MFA, SSO providers and active session management')}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ── MFA 设置 ─────────────────────────────────────────── */}
          <div className={cardCls}>
            <h2 className={headingCls}>
              <KeyRound size={20} className="text-blue-500" />
              {t('security.mfaSetup', 'Multi-Factor Authentication')}
            </h2>
            <p className={clsx(subTextCls, 'mb-4')}>
              {t('security.mfaHint', 'Set up TOTP / SMS / Email verification for your account')}
            </p>

            <div className="flex gap-2 mb-4">
              <select
                value={mfaMethod}
                onChange={(e) => setMfaMethod(e.target.value as 'totp' | 'sms' | 'email')}
                className={inputCls}
              >
                <option value="totp">TOTP (Authenticator App)</option>
                <option value="sms">SMS</option>
                <option value="email">Email</option>
              </select>
              <button
                onClick={handleSetupMFA}
                disabled={mfaLoading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium whitespace-nowrap transition-colors"
              >
                {mfaLoading ? t('common.loading', 'Loading...') : t('security.startSetup', 'Start Setup')}
              </button>
            </div>

            {/* TOTP secret + otpauth URI (无 qrcode 依赖 — 明文展示) */}
            {mfaSetup?.provisioning_uri && (
              <div className={clsx('rounded-lg p-4 mb-4 text-sm', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}>
                <p className={clsx('font-medium mb-2', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                  {t('security.secretLabel', 'Secret')}
                </p>
                <code className={clsx('block break-all mb-3 font-mono text-xs', theme === 'dark' ? 'text-green-400' : 'text-green-700')}>
                  {mfaSetup.secret}
                </code>
                <p className={clsx('font-medium mb-2', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                  {t('security.provisioningUri', 'Provisioning URI (paste into your authenticator)')}
                </p>
                <code className={clsx('block break-all font-mono text-xs mb-3', theme === 'dark' ? 'text-slate-300' : 'text-slate-600')}>
                  {mfaSetup.provisioning_uri}
                </code>
                <button
                  onClick={handleCopyURI}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                  {copied ? t('common.copied', 'Copied') : t('common.copy', 'Copy URI')}
                </button>
              </div>
            )}

            {/* MFA 验证 */}
            <div className="space-y-2">
              <input
                value={challengeId}
                onChange={(e) => setChallengeId(e.target.value)}
                placeholder={t('security.challengeId', 'Challenge ID')}
                className={inputCls}
              />
              <div className="flex gap-2">
                <input
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value)}
                  placeholder={t('security.verifyCode', 'Verification code')}
                  className={inputCls}
                />
                <button
                  onClick={handleVerifyMFA}
                  disabled={verifyLoading || !challengeId || !verifyCode}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium whitespace-nowrap transition-colors"
                >
                  {t('security.verify', 'Verify')}
                </button>
              </div>
              {verifyResult !== null && (
                <p className={clsx('text-sm font-medium', verifyResult ? 'text-green-600' : 'text-red-600')}>
                  {verifyResult
                    ? t('security.verifySuccess', 'MFA code verified successfully')
                    : t('security.verifyFailed', 'Verification failed')}
                </p>
              )}
            </div>

            {/* MFA 禁用 — 后端无端点, 置灰 */}
            <button
              disabled
              title={t('security.comingSoon', 'Coming soon — backend endpoint not available')}
              className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
            >
              {t('security.disableMfa', 'Disable MFA')} · {t('common.comingSoon', 'Coming soon')}
            </button>
          </div>

          {/* ── SSO 提供方 ───────────────────────────────────────── */}
          <div className={cardCls}>
            <h2 className={headingCls}>
              <Globe size={20} className="text-purple-500" />
              {t('security.ssoProviders', 'SSO Providers')}
            </h2>

            {/* 能力状态 */}
            {ssoStatus && (
              <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
                {([
                  ['OIDC', ssoStatus.oidc?.status, `${ssoStatus.oidc?.providers_configured ?? 0} configured`],
                  ['SAML 2.0', ssoStatus.saml?.status, ssoStatus.saml?.message],
                  ['LDAP', (ssoStatus.ldap as any)?.configured ? 'configured' : 'not configured', (ssoStatus.ldap as any)?.status],
                  ['WebAuthn', (ssoStatus.webauthn as any)?.status, 'FIDO2'],
                ] as Array<[string, string | undefined, string | undefined]>).map(([name, status, detail]) => (
                  <div
                    key={name}
                    className={clsx('rounded-lg p-3', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}
                  >
                    <p className={clsx('font-medium', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>{name}</p>
                    <p className={clsx('text-xs', status === 'GA' ? 'text-green-600' : 'text-amber-600')}>
                      {status ?? '—'}
                    </p>
                    {detail && <p className="text-xs text-slate-500 truncate">{String(detail)}</p>}
                  </div>
                ))}
              </div>
            )}

            {/* 已配置 OIDC 提供方 */}
            <p className={clsx('text-sm font-medium mb-2', theme === 'dark' ? 'text-slate-300' : 'text-slate-700')}>
              {t('security.configuredOidc', 'Configured OIDC providers')}
            </p>
            {!providers || providers.oidc_providers.length === 0 ? (
              <p className={subTextCls}>
                {t('security.noProviders', 'No OIDC providers configured (set XAGENT_SSO_PROVIDERS)')}
              </p>
            ) : (
              <ul className="space-y-2">
                {providers.oidc_providers.map((p, idx) => (
                  <li
                    key={String(p.provider_name ?? idx)}
                    className={clsx('rounded-lg p-3 text-sm flex items-center justify-between', theme === 'dark' ? 'bg-slate-800' : 'bg-slate-50')}
                  >
                    <div>
                      <p className={clsx('font-medium', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                        {String(p.provider_name ?? `provider-${idx}`)}
                      </p>
                      <p className="text-xs text-slate-500">
                        tenant: {String(p.tenant_id ?? 'default')}
                        {p.discovery_url ? ` · ${String(p.discovery_url)}` : ''}
                      </p>
                    </div>
                    <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      OIDC
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {providers?.saml && (
              <p className={clsx('text-xs mt-3', theme === 'dark' ? 'text-slate-500' : 'text-slate-500')}>
                SAML: {providers.saml.status} — {providers.saml.message ?? ''}
              </p>
            )}
          </div>
        </div>

        {/* ── 活跃会话 ─────────────────────────────────────────── */}
        <div className={clsx(cardCls, 'mt-6')}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={clsx(headingCls, 'mb-0')}>
              <MonitorSmartphone size={20} className="text-amber-500" />
              {t('security.activeSessions', 'Active Sessions')}
            </h2>
            <div className="flex gap-2">
              <button
                onClick={loadSessions}
                disabled={sessionsLoading}
                className="flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50 transition-colors"
              >
                <RefreshCw size={14} className={sessionsLoading ? 'animate-spin' : ''} />
                {t('common.refresh', 'Refresh')}
              </button>
              <button
                onClick={handleRevokeAll}
                className="flex items-center gap-1 px-3 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                <Trash2 size={14} />
                {t('security.revokeAll', 'Revoke All Others')}
              </button>
            </div>
          </div>

          {sessions.length === 0 ? (
            <p className={subTextCls}>{t('security.noSessions', 'No active sessions found')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={clsx('border-b', theme === 'dark' ? 'border-slate-700' : 'border-slate-200')}>
                  <tr>
                    {[t('security.device', 'Device'), t('security.ipAddress', 'IP'), t('security.createdAt', 'Created'), t('security.lastActivity', 'Last Activity'), t('security.mfaVerified', 'MFA'), ''].map((h, i) => (
                      <th key={i} className={clsx('px-4 py-2 text-left text-sm font-semibold', theme === 'dark' ? 'text-slate-300' : 'text-slate-900')}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id} className={clsx('border-b', theme === 'dark' ? 'border-slate-800' : 'border-slate-100')}>
                      <td className={clsx('px-4 py-3 text-sm', theme === 'dark' ? 'text-slate-200' : 'text-slate-700')}>
                        {s.device_name ?? '—'}
                        {s.trusted_device && (
                          <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                            trusted
                          </span>
                        )}
                      </td>
                      <td className={clsx('px-4 py-3 text-sm font-mono', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                        {s.ip_address ?? '—'}
                      </td>
                      <td className={clsx('px-4 py-3 text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                        {new Date(s.created_at).toLocaleString()}
                      </td>
                      <td className={clsx('px-4 py-3 text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
                        {new Date(s.last_activity).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {s.mfa_verified ? (
                          <ShieldCheck size={16} className="text-green-500" />
                        ) : (
                          <Lock size={16} className="text-slate-400" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleRevokeSession(s.session_id)}
                          className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
                        >
                          {t('security.revoke', 'Revoke')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SecurityAuthPage
