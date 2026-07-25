import React from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import { SUPPORTED_LANGUAGES, LanguageCode } from '@/i18n/config'
import { Menu, X, Moon, Sun, LogOut, Globe } from 'lucide-react'
import clsx from 'clsx'
import NotificationCenter from '@/components/NotificationCenter'

interface LayoutProps {
  children: React.ReactNode
}

// Only languages with a bundled translation file are offered; the rest of
// SUPPORTED_LANGUAGES would fall back to English anyway.
const AVAILABLE_LANGUAGES: LanguageCode[] = ['en', 'zh', 'ja', 'ko', 'es', 'ar']

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { sidebarOpen, toggleSidebar, theme, toggleTheme, user, logout } = useAppStore()
  const { t, language, setLanguage } = useI18n()

  return (
    <div className={clsx('flex h-screen', theme === 'dark' ? 'dark bg-slate-950' : 'bg-white')}>
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-white transition-transform duration-300 lg:relative lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between p-6 border-b border-slate-700">
            <h1 className="text-2xl font-bold">{t('common.appName', 'X-Agent')}</h1>
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-2 hover:bg-slate-800 rounded-lg transition-colors"
              aria-label={t('common.closeMenu', 'Close menu')}
            >
              <X size={20} />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-2" aria-label={t('navigation.main', 'Main navigation')}>
            <NavLink href="/" icon="🏠" label={t('navigation.dashboard', 'Dashboard')} />
            <NavLink href="/chat" icon="💬" label={t('navigation.chat', 'Chat')} />
            <NavLink href="/tasks" icon="✓" label={t('navigation.tasks', 'Tasks')} />
            <NavLink href="/workflows" icon="🔀" label={t('navigation.workflows', 'Workflows')} />
            <NavLink href="/tools" icon="🔧" label={t('navigation.tools', 'Tools')} />
            <NavLink href="/memory" icon="🧠" label={t('navigation.memory', 'Memory')} />
            <NavLink href="/agents" icon="🤖" label={t('navigation.agents', 'Agents')} />
            <NavLink href="/goals" icon="🎯" label={t('navigation.goals', 'Goals')} />
            <NavLink href="/evolution" icon="🧬" label={t('navigation.evolution', 'Evolution')} />
            <NavLink href="/review" icon="🔍" label={t('navigation.review', 'Code Review')} />
            <NavLink href="/settings" icon="⚙️" label={t('navigation.settings', 'Settings')} />
          </nav>

          {/* User Profile */}
          <div className="p-4 border-t border-slate-700">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium">{user?.name || 'Guest'}</p>
                <p className="text-xs text-slate-400">{user?.email || t('errors.unauthorized', 'Not logged in')}</p>
              </div>
              <button
                onClick={logout}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
                title={t('common.logout', 'Logout')}
                aria-label={t('common.logout', 'Logout')}
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className={clsx(
          'flex items-center justify-between px-6 py-4 border-b',
          theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        )}>
          <button
            onClick={toggleSidebar}
            className="lg:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            aria-label={t('common.openMenu', 'Open menu')}
          >
            <Menu size={24} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-4">
            {/* Notifications */}
            <NotificationCenter />

            {/* Language Switcher */}
            <div className="flex items-center gap-2">
              <Globe size={18} className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'} aria-hidden="true" />
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as LanguageCode)}
                className={clsx(
                  'px-2 py-1 rounded-lg text-sm',
                  theme === 'dark'
                    ? 'bg-slate-800 text-white border border-slate-700'
                    : 'bg-white text-slate-900 border border-slate-300'
                )}
                aria-label={t('common.language', 'Language')}
              >
                {AVAILABLE_LANGUAGES.map((code) => (
                  <option key={code} value={code}>
                    {SUPPORTED_LANGUAGES[code].nativeName}
                  </option>
                ))}
              </select>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={clsx(
                'p-2 rounded-lg transition-colors',
                theme === 'dark'
                  ? 'bg-slate-800 hover:bg-slate-700'
                  : 'bg-slate-100 hover:bg-slate-200'
              )}
              title={t('common.toggleTheme', 'Toggle theme')}
              aria-label={t('common.toggleTheme', 'Toggle theme')}
            >
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            {/* Connection Status */}
            <ConnectionStatus />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className={clsx(
            'h-full',
            theme === 'dark' ? 'bg-slate-950 text-white' : 'bg-white text-slate-900'
          )}>
            {children}
          </div>
        </main>
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Close sidebar"
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleSidebar(); }}
        />
      )}
    </div>
  )
}

interface NavLinkProps {
  href: string
  icon: string
  label: string
}

const NavLink: React.FC<NavLinkProps> = ({ href, icon, label }) => {
  const isActive = window.location.pathname === href

  return (
    <a
      href={href}
      aria-current={isActive ? 'page' : undefined}
      className={clsx(
        'flex items-center gap-3 px-4 py-2 rounded-lg transition-colors',
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-slate-300 hover:bg-slate-800'
      )}
    >
      <span className="text-xl" aria-hidden="true">{icon}</span>
      <span className="text-sm font-medium">{label}</span>
    </a>
  )
}

const ConnectionStatus: React.FC = () => {
  const { isConnected } = useAppStore()
  const { t } = useI18n()

  return (
    <div className="flex items-center gap-2" role="status" aria-live="polite">
      <div
        className={clsx(
          'w-2 h-2 rounded-full',
          isConnected ? 'bg-green-500' : 'bg-red-500'
        )}
        aria-hidden="true"
      />
      <span className="text-xs text-slate-500">
        {isConnected ? t('common.connected', 'Connected') : t('common.disconnected', 'Disconnected')}
      </span>
    </div>
  )
}

export default Layout
