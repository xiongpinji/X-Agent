import React, { useCallback, useEffect, useState } from 'react'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import {
  adminOps,
  isForbidden,
  errorMessage,
  AdminUserRecord,
  UserActivityResponse,
} from '@/services/adminOps'
import clsx from 'clsx'

type PageTab = 'users' | 'activity'

const ROLE_OPTIONS = ['admin', 'developer', 'viewer'] as const

const ROLE_BADGE: Record<string, string> = {
  admin: 'badge-danger',
  developer: 'badge-muted',
  viewer: 'badge-muted',
}

const UsersAdminPage: React.FC = () => {
  const { t } = useI18n()
  const { theme, user: currentUser } = useAppStore()
  const isDark = theme === 'dark'

  const [activeTab, setActiveTab] = useState<PageTab>('users')
  const [forbidden, setForbidden] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Users tab
  const [users, setUsers] = useState<AdminUserRecord[]>([])
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserName, setNewUserName] = useState('')
  const [newUserRole, setNewUserRole] = useState<string>('developer')
  const [newUserTenant, setNewUserTenant] = useState('default')
  const [creating, setCreating] = useState(false)
  const [roleEdits, setRoleEdits] = useState<Record<string, string>>({})
  const [savingRoleFor, setSavingRoleFor] = useState<string | null>(null)

  // Activity tab
  const [activityUserId, setActivityUserId] = useState<string | null>(null)
  const [activity, setActivity] = useState<UserActivityResponse | null>(null)
  const [loadingActivity, setLoadingActivity] = useState(false)

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 4000)
  }

  const handleError = (error: unknown, fallback: string) => {
    if (isForbidden(error)) {
      setForbidden(true)
      return
    }
    showMessage('error', errorMessage(error, fallback))
  }

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      setUsers(await adminOps.listUsers())
    } catch (error) {
      handleError(error, t('admin.users.loadFailed', 'Failed to load users'))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const loadActivity = useCallback(async (userId: string) => {
    setLoadingActivity(true)
    try {
      setActivity(await adminOps.getUserActivity(userId, 50, 0))
    } catch (error) {
      handleError(error, t('admin.activity.loadFailed', 'Failed to load activity'))
      setActivity(null)
    } finally {
      setLoadingActivity(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openActivity = (userId: string) => {
    setActivityUserId(userId)
    setActiveTab('activity')
    loadActivity(userId)
  }

  const handleCreateUser = async () => {
    if (!newUserEmail.trim()) return
    setCreating(true)
    try {
      const created = await adminOps.createUser({
        email: newUserEmail.trim(),
        display_name: newUserName.trim() || undefined,
        role: newUserRole,
        tenant_id: newUserTenant.trim() || 'default',
      })
      setUsers(prev => [...prev, created])
      setNewUserEmail('')
      setNewUserName('')
      showMessage('success', t('admin.users.created', 'User created'))
    } catch (error) {
      handleError(error, t('admin.users.createFailed', 'Failed to create user'))
    } finally {
      setCreating(false)
    }
  }

  const handleSaveRole = async (userId: string) => {
    const role = roleEdits[userId]
    if (!role) return
    setSavingRoleFor(userId)
    try {
      const updated = await adminOps.updateUserRole(userId, role)
      setUsers(prev => prev.map(u => (u.id === userId ? { ...u, role: updated.role ?? role } : u)))
      showMessage('success', t('admin.users.roleSaved', 'Role updated'))
    } catch (error) {
      handleError(error, t('admin.users.roleFailed', 'Failed to update role'))
    } finally {
      setSavingRoleFor(null)
    }
  }

  const handleDeleteUser = async (userId: string) => {
    try {
      await adminOps.deleteUser(userId)
      setUsers(prev => prev.filter(u => u.id !== userId))
      showMessage('success', t('admin.users.deleted', 'User deleted'))
    } catch (error) {
      handleError(error, t('admin.users.deleteFailed', 'Failed to delete user'))
    }
  }

  const inputCls = clsx(
    'px-3 py-2 rounded-lg border text-sm',
    isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
  )

  // 403 — graceful permission notice instead of a crash
  if (forbidden) {
    return (
      <div className={clsx(
        'min-h-full px-8 py-10',
        isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
      )}>
        <div className="max-w-3xl">
          <header className="mb-8">
            <div
              className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
              aria-hidden="true"
            />
            <h1 className="page-title">{t('admin.forbidden.title', 'Admin access required')}</h1>
            <p className="page-subtitle">
              {t('admin.forbidden.usersDesc', 'User management requires the security:manage scope. Contact an administrator to request access.')}
            </p>
          </header>
        </div>
      </div>
    )
  }

  const tabs: Array<{ id: PageTab; label: string }> = [
    { id: 'users', label: t('admin.tabs.users', 'Users') },
    { id: 'activity', label: t('admin.tabs.activity', 'Activity') },
  ]

  const activityUser = users.find(u => u.id === activityUserId) || null

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      isDark ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-5xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className={clsx('w-12 border-t-2 mb-5', isDark ? 'border-slate-200' : 'border-[#333333]')}
            aria-hidden="true"
          />
          <h1 className="page-title">{t('admin.usersAdmin.title', 'User Administration')}</h1>
          <p className="page-subtitle">{t('admin.usersAdmin.subtitle', 'Manage users, roles and activity')}</p>
        </header>

        {message && (
          <div className={clsx(
            'mb-4 px-3 py-2 rounded-lg text-sm border',
            message.type === 'success'
              ? 'border-[#16a34a]/30 text-[#16a34a]'
              : 'border-[#dc2626]/30 text-[#dc2626]'
          )} role="alert">
            {message.text}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-8 border-b" style={{ borderColor: 'var(--divider)' }} role="tablist">
          {tabs.map(tab => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent opacity-50 hover:opacity-100'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Users Tab */}
        {activeTab === 'users' && (
          <div>
            {/* Create user */}
            <section className="mb-10">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3">
                {t('admin.users.create', 'Create User')}
              </h2>
              <div className="flex flex-wrap gap-2">
                <input
                  type="email"
                  value={newUserEmail}
                  onChange={e => setNewUserEmail(e.target.value)}
                  placeholder={t('admin.users.emailPlaceholder', 'Email')}
                  className={clsx(inputCls, 'flex-1 min-w-[180px]')}
                />
                <input
                  type="text"
                  value={newUserName}
                  onChange={e => setNewUserName(e.target.value)}
                  placeholder={t('admin.users.namePlaceholder', 'Display name')}
                  className={clsx(inputCls, 'flex-1 min-w-[140px]')}
                />
                <select
                  value={newUserRole}
                  onChange={e => setNewUserRole(e.target.value)}
                  className={inputCls}
                  aria-label={t('admin.users.role', 'Role')}
                >
                  {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                <input
                  type="text"
                  value={newUserTenant}
                  onChange={e => setNewUserTenant(e.target.value)}
                  placeholder={t('admin.users.tenantPlaceholder', 'Tenant ID')}
                  className={clsx(inputCls, 'w-32')}
                />
                <button
                  onClick={handleCreateUser}
                  disabled={!newUserEmail.trim() || creating}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {creating ? t('common.saving', 'Saving...') : t('common.create', 'Create')}
                </button>
              </div>
            </section>

            {/* User list — divider rows, no cards */}
            <section>
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">
                {t('admin.users.list', 'Users')}
              </h2>
              {loading ? (
                <p className="empty-state">{t('common.loading', 'Loading...')}</p>
              ) : users.length === 0 ? (
                <p className="empty-state">{t('admin.users.empty', 'No users found.')}</p>
              ) : (
                <div>
                  {users.map(u => {
                    const locked = u.locked_until && new Date(u.locked_until) > new Date()
                    return (
                      <div key={u.id} className="row-line" style={{ padding: '14px 0' }}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {u.display_name}
                              {currentUser?.email === u.email && (
                                <span className="ml-2 text-xs font-normal opacity-50">
                                  ({t('admin.users.you', 'you')})
                                </span>
                              )}
                            </p>
                            <p className="cell-data opacity-50 truncate">
                              {u.email} • {u.tenant_id}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={clsx('badge-status', ROLE_BADGE[u.role] ?? 'badge-muted')}>{u.role}</span>
                            <span className={clsx('badge-status', locked ? 'badge-danger' : 'badge-success')}>
                              {locked ? t('admin.users.locked', 'locked') : t('admin.users.active', 'active')}
                            </span>
                            {/* Role edit (admin scope) */}
                            <select
                              value={roleEdits[u.id] ?? u.role}
                              onChange={e => setRoleEdits(prev => ({ ...prev, [u.id]: e.target.value }))}
                              className={clsx(inputCls, 'py-1 text-xs')}
                              aria-label={t('admin.users.editRole', 'Edit role')}
                            >
                              {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                            </select>
                            <button
                              onClick={() => handleSaveRole(u.id)}
                              disabled={savingRoleFor === u.id || (roleEdits[u.id] ?? u.role) === u.role}
                              className="px-2 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 disabled:opacity-40"
                            >
                              {savingRoleFor === u.id ? t('common.saving', 'Saving...') : t('common.save', 'Save Changes')}
                            </button>
                            <button
                              onClick={() => openActivity(u.id)}
                              className="px-2 py-1 text-xs font-medium opacity-50 hover:opacity-100 transition-opacity"
                            >
                              {t('admin.users.viewActivity', 'Activity')}
                            </button>
                            <button
                              onClick={() => handleDeleteUser(u.id)}
                              className="px-2 py-1 text-xs font-medium text-[#dc2626] opacity-60 hover:opacity-100 transition-opacity"
                            >
                              {t('common.delete', 'Delete')}
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        {/* Activity Tab */}
        {activeTab === 'activity' && (
          <section>
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                {t('admin.activity.title', 'User Activity')}
              </h2>
              <select
                value={activityUserId ?? ''}
                onChange={e => { setActivityUserId(e.target.value); if (e.target.value) loadActivity(e.target.value) }}
                className={clsx(inputCls, 'max-w-xs')}
                aria-label={t('admin.activity.selectUser', 'Select user')}
              >
                <option value="">{t('admin.activity.selectUser', 'Select user')}</option>
                {users.map(u => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}
              </select>
            </div>
            {loadingActivity ? (
              <p className="empty-state">{t('common.loading', 'Loading...')}</p>
            ) : !activityUserId ? (
              <p className="empty-state">{t('admin.activity.selectFirst', 'Select a user to view activity.')}</p>
            ) : !activity || activity.items.length === 0 ? (
              <p className="empty-state">
                {t('admin.activity.empty', 'No activity recorded')}
                {activityUser ? ` — ${activityUser.display_name}` : ''}
              </p>
            ) : (
              <div>
                {activity.items.map((item, i) => (
                  <div key={String(item.id ?? i)} className="row-line">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{String(item.action ?? item.event ?? item.type ?? 'event')}</p>
                      <p className="cell-data opacity-50">
                        {item.created_at || item.timestamp ? new Date(String(item.created_at ?? item.timestamp)).toLocaleString() : '—'}
                      </p>
                    </div>
                    {((item.resource_type || item.resource_id || item.details) as React.ReactNode) && (
                      <p className="cell-data opacity-50 mt-1 break-all">
                        {[item.resource_type, item.resource_id].filter(Boolean).join(' / ')}
                        {item.details ? ` — ${typeof item.details === 'string' ? item.details : JSON.stringify(item.details)}` : ''}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  )
}

export default UsersAdminPage
