import React, { useCallback, useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { securityOps, MFASetupResponse, SessionItem, SSOProvidersResponse, SSOStatusResponse } from '@/services/securityOps'
import { useI18n } from '@/i18n/context'
import {
  RefreshCw,
  Copy,
  Check,
  Trash2,
} from 'lucide-react'
import clsx from 'clsx'

const DIVIDER = 'var(--divider)'

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

  const inputCls = clsx(
    'px-3 py-2 rounded-lg border text-sm w-full',
    theme === 'dark'
      ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500'
      : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400'
  )
  const ghostBtnCls = clsx(
    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
    theme === 'dark' ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
  )

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx(
              'w-12 border-t-2 mb-5',
              theme === 'dark' ? 'border-slate-200' : 'border-[#333333]'
            )}
            aria-hidden="true"
          />
          <h1 className="page-title">{t('security.title', 'Security & Authentication')}</h1>
          <p className="page-subtitle">
            {t('security.subtitle', 'MFA, SSO providers and active session management')}
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* ── MFA 设置 ─────────────────────────────────────────── */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('security.mfaSetup', 'Multi-Factor Authentication')}
            </h2>
            <p className="text-[13px] opacity-60 mb-4">
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
              <div className="row-line text-sm" style={{ padding: '16px 0' }}>
                <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2">
                  {t('security.secretLabel', 'Secret')}
                </p>
                <code className="block break-all mb-3 cell-data text-[#16a34a]">
                  {mfaSetup.secret}
                </code>
                <p className="text-[11px] uppercase tracking-[0.06em] opacity-50 mb-2">
                  {t('security.provisioningUri', 'Provisioning URI (paste into your authenticator)')}
                </p>
                <code className="block break-all cell-data opacity-70 mb-3">
                  {mfaSetup.provisioning_uri}
                </code>
                <button
                  onClick={handleCopyURI}
                  className={clsx(ghostBtnCls, 'py-1.5 text-xs')}
                >
                  {copied ? <Check size={14} className="text-[#16a34a]" /> : <Copy size={14} />}
                  {copied ? t('common.copied', 'Copied') : t('common.copy', 'Copy URI')}
                </button>
              </div>
            )}

            {/* MFA 验证 */}
            <div className="space-y-2 mt-4">
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
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium whitespace-nowrap transition-colors"
                >
                  {t('security.verify', 'Verify')}
                </button>
              </div>
              {verifyResult !== null && (
                <p className={clsx('text-sm font-medium', verifyResult ? 'text-[#16a34a]' : 'text-[#dc2626]')}>
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
              className={clsx(ghostBtnCls, 'mt-4 opacity-50 cursor-not-allowed')}
            >
              {t('security.disableMfa', 'Disable MFA')} · {t('common.comingSoon', 'Coming soon')}
            </button>
          </section>

          {/* ── SSO 提供方 ───────────────────────────────────────── */}
          <section>
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
              {t('security.ssoProviders', 'SSO Providers')}
            </h2>

            {/* 能力状态 — divider rows */}
            {ssoStatus && (
              <div className="mb-4">
                {([
                  ['OIDC', ssoStatus.oidc?.status, `${ssoStatus.oidc?.providers_configured ?? 0} configured`],
                  ['SAML 2.0', ssoStatus.saml?.status, ssoStatus.saml?.message],
                  ['LDAP', ssoStatus.ldap.configured ? 'configured' : 'not configured', ssoStatus.ldap.status],
                  ['WebAuthn', ssoStatus.webauthn.status, 'FIDO2'],
                ] as Array<[string, string | undefined, string | undefined]>).map(([name, status, detail]) => (
                  <div
                    key={name}
                    className="flex items-baseline justify-between gap-4 py-2 border-b"
                    style={{ borderColor: DIVIDER }}
                  >
                    <span className="text-sm font-medium">{name}</span>
                    <span className="flex items-center gap-2">
                      {detail && <span className="cell-data opacity-50 truncate">{String(detail)}</span>}
                      <span className={clsx('badge-status', status === 'GA' ? 'badge-success' : 'badge-warning')}>
                        {status ?? '—'}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* 已配置 OIDC 提供方 */}
            <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2 mt-6">
              {t('security.configuredOidc', 'Configured OIDC providers')}
            </h3>
            {!providers || providers.oidc_providers.length === 0 ? (
              <p className="empty-state">
                {t('security.noProviders', 'No OIDC providers configured (set XAGENT_SSO_PROVIDERS)')}
              </p>
            ) : (
              <div>
                {providers.oidc_providers.map((p, idx) => (
                  <div
                    key={String(p.provider_name ?? idx)}
                    className="row-line flex items-center justify-between gap-4"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {String(p.provider_name ?? `provider-${idx}`)}
                      </p>
                      <p className="cell-data opacity-50 truncate">
                        tenant: {String(p.tenant_id ?? 'default')}
                        {p.discovery_url ? ` · ${String(p.discovery_url)}` : ''}
                      </p>
                    </div>
                    <span className="badge-status badge-success">OIDC</span>
                  </div>
                ))}
              </div>
            )}
            {providers?.saml && (
              <p className="cell-data opacity-50 mt-3">
                SAML: {providers.saml.status} — {providers.saml.message ?? ''}
              </p>
            )}
          </section>
        </div>

        {/* ── 活跃会话 ─────────────────────────────────────────── */}
        <section className="mt-10">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
              {t('security.activeSessions', 'Active Sessions')}
            </h2>
            <div className="flex gap-2">
              <button
                onClick={loadSessions}
                disabled={sessionsLoading}
                className={ghostBtnCls}
                aria-label={t('common.refresh', 'Refresh')}
              >
                <RefreshCw size={14} className={sessionsLoading ? 'animate-spin' : ''} />
                {t('common.refresh', 'Refresh')}
              </button>
              <button
                onClick={handleRevokeAll}
                className={ghostBtnCls}
              >
                <Trash2 size={14} />
                {t('security.revokeAll', 'Revoke All Others')}
              </button>
            </div>
          </div>

          {sessions.length === 0 ? (
            <p className="empty-state">{t('security.noSessions', 'No active sessions found')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-dense">
                <thead>
                  <tr>
                    <th>{t('security.device', 'Device')}</th>
                    <th>{t('security.ipAddress', 'IP')}</th>
                    <th>{t('security.createdAt', 'Created')}</th>
                    <th>{t('security.lastActivity', 'Last Activity')}</th>
                    <th>{t('security.mfaVerified', 'MFA')}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id}>
                      <td>
                        {s.device_name ?? '—'}
                        {s.trusted_device && (
                          <span className="ml-2 badge-status badge-muted">trusted</span>
                        )}
                      </td>
                      <td className="cell-data opacity-70">
                        {s.ip_address ?? '—'}
                      </td>
                      <td className="cell-data opacity-70">
                        {new Date(s.created_at).toLocaleString()}
                      </td>
                      <td className="cell-data opacity-70">
                        {new Date(s.last_activity).toLocaleString()}
                      </td>
                      <td>
                        <span className={clsx('badge-status', s.mfa_verified ? 'badge-success' : 'badge-muted')}>
                          {s.mfa_verified ? t('security.mfaVerified', 'MFA') : '—'}
                        </span>
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => handleRevokeSession(s.session_id)}
                          className="text-sm text-[#dc2626] opacity-60 hover:opacity-100 transition-opacity font-medium"
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
        </section>
      </div>
    </div>
  )
}

export default SecurityAuthPage
