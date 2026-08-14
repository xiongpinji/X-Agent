import React from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import { SUPPORTED_LANGUAGES, LanguageCode } from '@/i18n/config'
import { Menu, X, Moon, Sun, LogOut } from 'lucide-react'
import clsx from 'clsx'

interface LayoutProps {
  children: React.ReactNode
}

// Only languages with a bundled translation file are offered; the rest of
// SUPPORTED_LANGUAGES would fall back to English anyway.
const AVAILABLE_LANGUAGES: LanguageCode[] = ['en', 'zh', 'ja', 'ko', 'es', 'ar']

const DIVIDER = 'var(--divider)'

interface NavItem {
  href: string
  labelKey: string
  fallback: string
}

interface NavGroup {
  labelKey: string
  fallback: string
  items: NavItem[]
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { sidebarOpen, toggleSidebar, theme, toggleTheme, user, logout } = useAppStore()
  const { t, language, setLanguage } = useI18n()

  const navGroups: NavGroup[] = [
    {
      labelKey: 'navigation.groupWorkspace',
      fallback: 'Workspace',
      items: [
        { href: '/', labelKey: 'navigation.dashboard', fallback: 'Dashboard' },
        { href: '/chat', labelKey: 'navigation.chat', fallback: 'Chat' },
        { href: '/tasks', labelKey: 'navigation.tasks', fallback: 'Tasks' },
        { href: '/work-sessions', labelKey: 'navigation.workSessions', fallback: 'Work Sessions' },
        { href: '/forum', labelKey: 'navigation.forum', fallback: 'Forum' },
        { href: '/console', labelKey: 'navigation.console', fallback: 'Console' },
      ],
    },
    {
      labelKey: 'navigation.groupManage',
      fallback: 'Manage',
      items: [
        { href: '/workflows', labelKey: 'navigation.workflows', fallback: 'Workflows' },
        { href: '/workflows/schedules', labelKey: 'navigation.workflowSchedules', fallback: 'Schedules' },
        { href: '/workflows/runs', labelKey: 'navigation.workflowRuns', fallback: 'Runs' },
        { href: '/checkpoints', labelKey: 'navigation.checkpoints', fallback: 'Checkpoints' },
        { href: '/tools', labelKey: 'navigation.tools', fallback: 'Tools' },
        { href: '/memory', labelKey: 'navigation.memory', fallback: 'Memory' },
        { href: '/agents', labelKey: 'navigation.agents', fallback: 'Agents' },
        { href: '/goals', labelKey: 'navigation.goals', fallback: 'Goals' },
        { href: '/mcp', labelKey: 'navigation.mcp', fallback: 'MCP' },
        { href: '/sandbox-tasks', labelKey: 'navigation.sandboxTasks', fallback: 'Sandbox' },
        { href: '/approvals', labelKey: 'navigation.approvals', fallback: 'Approvals' },
        { href: '/automation', labelKey: 'navigation.automation', fallback: 'Automation' },
        { href: '/sync', labelKey: 'navigation.sync', fallback: 'Sync' },
      ],
    },
    {
      labelKey: 'navigation.groupSystem',
      fallback: 'System',
      items: [
        { href: '/audit-logs', labelKey: 'navigation.auditLogs', fallback: 'Audit Logs' },
        { href: '/backup', labelKey: 'navigation.backup', fallback: 'Backup' },
        { href: '/observability', labelKey: 'navigation.observability', fallback: 'Observability' },
        { href: '/analytics', labelKey: 'navigation.analytics', fallback: 'Analytics' },
        { href: '/compliance', labelKey: 'navigation.compliance', fallback: 'Compliance' },
        { href: '/admin/tenants', labelKey: 'navigation.tenants', fallback: 'Tenants' },
        { href: '/admin/users', labelKey: 'navigation.usersAdmin', fallback: 'Users' },
        { href: '/security', labelKey: 'navigation.security', fallback: 'Security' },
        { href: '/evolution', labelKey: 'navigation.evolution', fallback: 'Evolution' },
        { href: '/review', labelKey: 'navigation.review', fallback: 'Code Review' },
        { href: '/settings', labelKey: 'navigation.settings', fallback: 'Settings' },
      ],
    },
  ]

  return (
    <div
      className={clsx(
        'flex h-screen bg-[var(--bg)] text-[var(--fg)]',
        theme === 'dark' && 'dark'
      )}
    >
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-60 transition-transform duration-300 lg:relative lg:translate-x-0 border-r',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        style={{ borderColor: DIVIDER }}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div
            className="flex items-center justify-between px-5 py-5 border-b"
            style={{ borderColor: DIVIDER }}
          >
            <h1 className="text-[15px] font-semibold tracking-tight">
              {t('common.appName', 'X-Agent')}
            </h1>
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-1.5 opacity-50 hover:opacity-100 transition-opacity"
              aria-label={t('common.closeMenu', 'Close menu')}
            >
              <X size={18} />
            </button>
          </div>

          {/* Navigation — text-only, 50% → 100% opacity, 2px accent bar */}
          <nav
            className="flex-1 overflow-y-auto py-3"
            aria-label={t('navigation.main', 'Main navigation')}
          >
            {navGroups.map((group) => (
              <div key={group.labelKey} className="mb-1">
                <div
                  className="px-5 pt-4 pb-1.5 text-[11px] uppercase tracking-[0.08em] opacity-50 select-none"
                  aria-hidden="true"
                >
                  {t(group.labelKey, group.fallback)}
                </div>
                {group.items.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    label={t(item.labelKey, item.fallback)}
                  />
                ))}
              </div>
            ))}
          </nav>

          {/* User Profile */}
          <div className="px-5 py-4 border-t" style={{ borderColor: DIVIDER }}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium truncate">
                  {user?.name || 'Guest'}
                </p>
                <p className="text-[11px] opacity-50 truncate">
                  {user?.email || t('errors.unauthorized', 'Not logged in')}
                </p>
              </div>
              <button
                onClick={logout}
                className="p-1.5 opacity-50 hover:opacity-100 transition-opacity"
                title={t('common.logout', 'Logout')}
                aria-label={t('common.logout', 'Logout')}
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header — connection dot + language + theme only */}
        <header
          className="flex items-center justify-between px-6 py-3 border-b"
          style={{ borderColor: DIVIDER }}
        >
          <button
            onClick={toggleSidebar}
            className="lg:hidden p-1.5 opacity-50 hover:opacity-100 transition-opacity"
            aria-label={t('common.openMenu', 'Open menu')}
          >
            <Menu size={20} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-5">
            {/* Connection Status */}
            <ConnectionStatus />

            {/* Language Switcher */}
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as LanguageCode)}
              className="bg-transparent text-[12px] opacity-70 hover:opacity-100 transition-opacity cursor-pointer border-0 outline-none"
              aria-label={t('common.language', 'Language')}
            >
              {AVAILABLE_LANGUAGES.map((code) => (
                <option key={code} value={code}>
                  {SUPPORTED_LANGUAGES[code].nativeName}
                </option>
              ))}
            </select>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-1.5 opacity-50 hover:opacity-100 transition-opacity"
              title={t('common.toggleTheme', 'Toggle theme')}
              aria-label={t('common.toggleTheme', 'Toggle theme')}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="h-full">
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
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') toggleSidebar()
          }}
        />
      )}
    </div>
  )
}

interface NavLinkProps {
  href: string
  label: string
}

const NavLink: React.FC<NavLinkProps> = ({ href, label }) => {
  const isActive = window.location.pathname === href

  return (
    <a
      href={href}
      aria-current={isActive ? 'page' : undefined}
      className={clsx(
        'link-plain relative flex items-center pl-5 pr-3 py-[7px] text-[13px] leading-5 transition-opacity duration-150',
        isActive ? 'opacity-100 font-medium' : 'opacity-50 hover:opacity-90'
      )}
    >
      <span
        className={clsx(
          'absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-blue-600 transition-opacity duration-150',
          isActive ? 'opacity-100' : 'opacity-0'
        )}
        aria-hidden="true"
      />
      {label}
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
          'w-1.5 h-1.5 rounded-full',
          isConnected ? 'bg-green-500' : 'bg-red-500'
        )}
        aria-hidden="true"
      />
      <span className="text-[11px] opacity-50">
        {isConnected
          ? t('common.connected', 'Connected')
          : t('common.disconnected', 'Disconnected')}
      </span>
    </div>
  )
}

export default Layout
