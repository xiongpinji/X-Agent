import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import clsx from 'clsx'

type SettingsTab = 'profile' | 'apikeys' | 'appearance' | 'notifications'

const SettingsPage: React.FC = () => {
  const { t } = useI18n()
  const { theme, toggleTheme, user } = useAppStore()
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Profile form
  const [displayName, setDisplayName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')

  // API Keys
  const [apiKeys, setApiKeys] = useState<Array<{ id: string; name: string; prefix: string; createdAt: string }>>([])
  const [newKeyName, setNewKeyName] = useState('')
  // The raw secret is returned exactly once by POST /security/api-keys.
  const [lastCreatedKey, setLastCreatedKey] = useState<string | null>(null)

  // Load existing API keys from the backend on mount.
  useEffect(() => {
    apiClient.listApiKeys()
      .then(records => setApiKeys(records
        .filter(r => !r.revoked)
        .map(r => ({
          id: r.id,
          name: r.name,
          prefix: r.key_prefix,
          createdAt: r.created_at || new Date().toISOString(),
        }))))
      .catch(() => { /* list may be forbidden for non-privileged users */ })
  }, [])

  // Notification prefs
  const [notifPrefs, setNotifPrefs] = useState({
    agentComplete: true,
    workflowStatus: true,
    systemAlerts: true,
    emailDigest: false,
  })

  const isDark = theme === 'dark'

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      await apiClient.updateProfile({ display_name: displayName, email })
      setMessage({ type: 'success', text: t('settings.profileSaved', 'Profile updated successfully') })
    } catch {
      setMessage({ type: 'error', text: t('settings.profileFailed', 'Failed to update profile') })
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const handleCreateApiKey = async () => {
    if (!newKeyName.trim()) return
    setSaving(true)
    try {
      const created = await apiClient.createApiKey(newKeyName)
      const record = created?.record
      setApiKeys(prev => [...prev, {
        id: record?.id || `key-${Date.now()}`,
        name: record?.name || newKeyName,
        prefix: record?.key_prefix || 'xag_...',
        createdAt: record?.created_at || new Date().toISOString(),
      }])
      setLastCreatedKey(created?.key || null)
      setNewKeyName('')
      setMessage({ type: 'success', text: t('settings.keyCreated', 'API key created') })
    } catch {
      setMessage({ type: 'error', text: t('settings.keyFailed', 'Failed to create API key') })
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const handleDeleteApiKey = async (id: string) => {
    try {
      await apiClient.deleteApiKey(id)
      setApiKeys(prev => prev.filter(k => k.id !== id))
    } catch {
      setMessage({ type: 'error', text: t('settings.keyDeleteFailed', 'Failed to revoke API key') })
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const tabs: Array<{ id: SettingsTab; label: string; icon: string }> = [
    { id: 'profile', label: t('settings.profile', 'Profile'), icon: '👤' },
    { id: 'apikeys', label: t('settings.apiKeys', 'API Keys'), icon: '🔑' },
    { id: 'appearance', label: t('settings.appearance', 'Appearance'), icon: '🎨' },
    { id: 'notifications', label: t('settings.notifications', 'Notifications'), icon: '🔔' },
  ]

  const inputCls =
    'w-full px-3 py-2 border bg-transparent text-sm outline-none transition-colors focus:border-[var(--fg)]'

  const renderToggle = (checked: boolean, onClick: () => void, label: string) => (
    <button
      onClick={onClick}
      className={clsx(
        'font-data text-sm transition-opacity',
        checked ? 'opacity-100' : 'opacity-40 hover:opacity-80'
      )}
      role="switch"
      aria-checked={checked}
      aria-label={label}
    >
      {checked ? '✓ on' : '✗ off'}
    </button>
  )

  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-3xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div
            className="w-12 border-t-2 mb-5"
            style={{ borderColor: 'var(--fg)' }}
            aria-hidden="true"
          />
          <h1 className="page-title">{t('settings.title', 'Settings')}</h1>
        </header>

        {/* Message — thin border, transparent background */}
        {message && (
          <div
            className={clsx(
              'mb-4 px-3 py-2 border text-sm',
              message.type === 'success' ? 'text-[#16a34a]' : 'text-[#dc2626]'
            )}
            style={{ borderColor: message.type === 'success' ? 'rgba(22,163,74,.35)' : 'rgba(220,38,38,.35)' }}
            role="alert"
          >
            {message.text}
          </div>
        )}

        {/* Tabs — underline style */}
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

        {/* Profile Tab */}
        {activeTab === 'profile' && (
          <div className="space-y-5 max-w-md">
            <div>
              <label className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">{t('settings.displayName', 'Display Name')}</label>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                className={inputCls}
                style={{ borderColor: 'var(--divider)' }}
              />
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1">{t('settings.email', 'Email')}</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className={inputCls}
                style={{ borderColor: 'var(--divider)' }}
              />
            </div>
            <button
              onClick={handleSaveProfile}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? t('common.saving', 'Saving...') : t('common.save', 'Save Changes')}
            </button>
          </div>
        )}

        {/* API Keys Tab */}
        {activeTab === 'apikeys' && (
          <div className="space-y-4">
            {lastCreatedKey && (
              <div
                className="p-3 border text-sm text-[#16a34a]"
                style={{ borderColor: 'rgba(22,163,74,.35)' }}
                role="alert"
              >
                <p className="font-medium mb-1">{t('settings.keyCreatedOnce', 'Copy your API key now — it is shown only once:')}</p>
                <code className="block break-all text-xs select-all cell-data">{lastCreatedKey}</code>
              </div>
            )}
            <div className="flex gap-2 max-w-md">
              <input
                type="text"
                value={newKeyName}
                onChange={e => setNewKeyName(e.target.value)}
                placeholder={t('settings.keyNamePlaceholder', 'Key name (e.g. Production)')}
                className={clsx(inputCls, 'flex-1')}
                style={{ borderColor: 'var(--divider)' }}
              />
              <button
                onClick={handleCreateApiKey}
                disabled={!newKeyName.trim() || saving}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {t('settings.createKey', 'Create')}
              </button>
            </div>

            {apiKeys.length === 0 ? (
              <p className="empty-state">{t('settings.noKeys', 'No API keys created yet.')}</p>
            ) : (
              <div>
                {apiKeys.map(key => (
                  <div key={key.id} className="row-line flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{key.name}</p>
                      <p className="cell-data opacity-50 truncate">
                        {key.prefix} • {new Date(key.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDeleteApiKey(key.id)}
                      className="text-xs text-[#dc2626] opacity-60 hover:opacity-100 font-medium transition-opacity"
                    >
                      {t('common.delete', 'Delete')}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Appearance Tab */}
        {activeTab === 'appearance' && (
          <div className="max-w-md">
            <div className="row-line flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{t('settings.darkMode', 'Dark Mode')}</p>
                <p className="text-xs opacity-50">
                  {t('settings.darkModeDesc', 'Switch between light and dark theme')}
                </p>
              </div>
              {renderToggle(isDark, toggleTheme, t('settings.darkMode', 'Dark Mode'))}
            </div>
          </div>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <div className="max-w-md">
            {([
              ['agentComplete', t('settings.notifAgent', 'Agent task completion')],
              ['workflowStatus', t('settings.notifWorkflow', 'Workflow status changes')],
              ['systemAlerts', t('settings.notifSystem', 'System alerts')],
              ['emailDigest', t('settings.notifEmail', 'Email digest (daily)')],
            ] as const).map(([key, label]) => (
              <div key={key} className="row-line flex items-center justify-between">
                <span className="text-sm">{label}</span>
                {renderToggle(
                  notifPrefs[key],
                  () => setNotifPrefs(prev => ({ ...prev, [key]: !prev[key] })),
                  label
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SettingsPage
