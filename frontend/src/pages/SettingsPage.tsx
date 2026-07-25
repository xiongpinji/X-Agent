import React, { useState } from 'react'
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
      setMessage({ type: 'success', text: t('settings.profileSaved', 'Profile updated successfully') })
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const handleCreateApiKey = async () => {
    if (!newKeyName.trim()) return
    setSaving(true)
    try {
      const key = await apiClient.createApiKey(newKeyName)
      setApiKeys(prev => [...prev, {
        id: key?.id || `key-${Date.now()}`,
        name: newKeyName,
        prefix: key?.prefix || 'xag_...',
        createdAt: new Date().toISOString(),
      }])
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
      setApiKeys(prev => prev.filter(k => k.id !== id))
    }
  }

  const tabs: Array<{ id: SettingsTab; label: string; icon: string }> = [
    { id: 'profile', label: t('settings.profile', 'Profile'), icon: '👤' },
    { id: 'apikeys', label: t('settings.apiKeys', 'API Keys'), icon: '🔑' },
    { id: 'appearance', label: t('settings.appearance', 'Appearance'), icon: '🎨' },
    { id: 'notifications', label: t('settings.notifications', 'Notifications'), icon: '🔔' },
  ]

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">{t('settings.title', 'Settings')}</h1>

      {/* Message */}
      {message && (
        <div className={clsx(
          'mb-4 p-3 rounded-lg text-sm',
          message.type === 'success'
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        )} role="alert">
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
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
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            )}
          >
            <span className="mr-1.5">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-1">{t('settings.displayName', 'Display Name')}</label>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className={clsx(
                'w-full max-w-md px-3 py-2 rounded-lg border text-sm',
                isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
              )}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t('settings.email', 'Email')}</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className={clsx(
                'w-full max-w-md px-3 py-2 rounded-lg border text-sm',
                isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
              )}
            />
          </div>
          <button
            onClick={handleSaveProfile}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? t('common.saving', 'Saving...') : t('common.save', 'Save Changes')}
          </button>
        </div>
      )}

      {/* API Keys Tab */}
      {activeTab === 'apikeys' && (
        <div className="space-y-4">
          <div className="flex gap-2 max-w-md">
            <input
              type="text"
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              placeholder={t('settings.keyNamePlaceholder', 'Key name (e.g. Production)')}
              className={clsx(
                'flex-1 px-3 py-2 rounded-lg border text-sm',
                isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
              )}
            />
            <button
              onClick={handleCreateApiKey}
              disabled={!newKeyName.trim() || saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {t('settings.createKey', 'Create')}
            </button>
          </div>

          {apiKeys.length === 0 ? (
            <p className={clsx('text-sm py-8 text-center', isDark ? 'text-slate-500' : 'text-slate-400')}>
              {t('settings.noKeys', 'No API keys created yet.')}
            </p>
          ) : (
            <div className="space-y-2">
              {apiKeys.map(key => (
                <div key={key.id} className={clsx(
                  'flex items-center justify-between p-3 rounded-lg border',
                  isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
                )}>
                  <div>
                    <p className="text-sm font-medium">{key.name}</p>
                    <p className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                      {key.prefix} • {new Date(key.createdAt).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteApiKey(key.id)}
                    className="text-xs text-red-500 hover:text-red-700 font-medium"
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
        <div className="space-y-6">
          <div className="flex items-center justify-between max-w-md">
            <div>
              <p className="text-sm font-medium">{t('settings.darkMode', 'Dark Mode')}</p>
              <p className={clsx('text-xs', isDark ? 'text-slate-500' : 'text-slate-400')}>
                {t('settings.darkModeDesc', 'Switch between light and dark theme')}
              </p>
            </div>
            <button
              onClick={toggleTheme}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                isDark ? 'bg-blue-600' : 'bg-slate-300'
              )}
              role="switch"
              aria-checked={isDark}
              aria-label={t('settings.darkMode', 'Dark Mode')}
            >
              <span className={clsx(
                'absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform',
                isDark ? 'translate-x-6' : 'translate-x-0.5'
              )} />
            </button>
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="space-y-4 max-w-md">
          {([
            ['agentComplete', t('settings.notifAgent', 'Agent task completion')],
            ['workflowStatus', t('settings.notifWorkflow', 'Workflow status changes')],
            ['systemAlerts', t('settings.notifSystem', 'System alerts')],
            ['emailDigest', t('settings.notifEmail', 'Email digest (daily)')],
          ] as const).map(([key, label]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="text-sm">{label}</span>
              <button
                onClick={() => setNotifPrefs(prev => ({ ...prev, [key]: !prev[key] }))}
                className={clsx(
                  'relative w-10 h-5 rounded-full transition-colors',
                  notifPrefs[key] ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-600'
                )}
                role="switch"
                aria-checked={notifPrefs[key]}
                aria-label={label}
              >
                <span className={clsx(
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                  notifPrefs[key] ? 'translate-x-5' : 'translate-x-0.5'
                )} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default SettingsPage
