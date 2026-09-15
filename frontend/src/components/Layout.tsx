import React, { useEffect, useRef } from 'react'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import { SUPPORTED_LANGUAGES, LanguageCode } from '@/i18n/config'
import { Menu, X, Moon, Sun, LogOut } from 'lucide-react'
import { NavLink as RouterNavLink, useLocation } from 'react-router-dom'
import clsx from 'clsx'

interface LayoutProps {
  children: React.ReactNode
}

// Only languages with a bundled translation file are offered; the rest of
// SUPPORTED_LANGUAGES would fall back to English anyway.
const AVAILABLE_LANGUAGES: LanguageCode[] = ['en', 'zh', 'ja', 'ko', 'es', 'ar']

/**
 * Shell chrome uses `--surface` while the page body uses `--bg`, which is what
 * actually separates navigation from content here. `.glass` is intentionally
 * NOT used: nothing scrolls underneath these surfaces (the header sits outside
 * the scroll container), so a backdrop-filter would blur nothing and just cost
 * a compositing layer. `.glass` stays reserved for real overlays.
 */
const SURFACE = 'bg-[var(--surface)]'
const HAIRLINE = 'border-[var(--divider)]'

/** Shared hit-target for the chrome's icon-only buttons. */
const ICON_BUTTON =
  'focus-ring inline-flex items-center justify-center h-8 w-8 rounded-lg ' +
  'opacity-60 hover:opacity-100 hover:bg-[var(--hover)] ' +
  'transition-[opacity,background-color] duration-150'

interface NavItem {
  href: string
  labelKey: string
  fallback: string
  /** 可见角色白名单；缺省 = 所有登录用户可见（后端仍做 scope 鉴权） */
  roles?: string[]
  /**
   * Force exact-path matching. Needed when another nav entry lives *under* this
   * one: react-router's NavLink prefix-matches, so `/workflows` stays active on
   * `/workflows/schedules`, highlighting two rows at once.
   */
  end?: boolean
}

interface NavGroup {
  labelKey: string
  fallback: string
  items: NavItem[]
}

/** 当前用户角色：登录/注册响应写入（默认 user 最小权限） */
function currentUserRole(): string {
  try {
    return localStorage.getItem('user_role') || 'user'
  } catch {
    return 'user'
  }
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { sidebarOpen, toggleSidebar, theme, toggleTheme, user, logout } = useAppStore()
  const { t, language, setLanguage } = useI18n()
  const location = useLocation()
  const contentRef = useRef<HTMLDivElement>(null)

  /*
   * Route-enter animation without remounting the page.
   *
   * The wrapper is keyed by nothing; instead the animation class is removed,
   * a reflow is forced (so the browser registers the class change), then the
   * class is re-added. Using `key={location.pathname}` would be fewer lines but
   * would tear down and rebuild the whole page subtree on every navigation,
   * discarding form input and scroll position.
   */
  useEffect(() => {
    const el = contentRef.current
    if (!el) return
    el.classList.remove('route-enter')
    void el.offsetWidth
    el.classList.add('route-enter')
  }, [location.pathname])

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
        { href: '/workflows', labelKey: 'navigation.workflows', fallback: 'Workflows', end: true },
        { href: '/workflows/schedules', labelKey: 'navigation.workflowSchedules', fallback: 'Schedules' },
        { href: '/workflows/runs', labelKey: 'navigation.workflowRuns', fallback: 'Runs' },
        { href: '/checkpoints', labelKey: 'navigation.checkpoints', fallback: 'Checkpoints' },
        { href: '/tools', labelKey: 'navigation.tools', fallback: 'Tools' },
        { href: '/memory', labelKey: 'navigation.memory', fallback: 'Memory' },
        { href: '/agents', labelKey: 'navigation.agents', fallback: 'Agents' },
        { href: '/goals', labelKey: 'navigation.goals', fallback: 'Goals' },
        { href: '/mcp', labelKey: 'navigation.mcp', fallback: 'MCP' },
        { href: '/sandbox-tasks', labelKey: 'navigation.sandboxTasks', fallback: 'Sandbox' },
        { href: '/approvals', roles: ["admin"], labelKey: 'navigation.approvals', fallback: 'Approvals' }, // workflow:control 仅 admin 具备
        { href: '/automation', labelKey: 'navigation.automation', fallback: 'Automation' },
        { href: '/sync', roles: ["admin", "developer"], labelKey: 'navigation.sync', fallback: 'Sync' },
      ],
    },
    {
      labelKey: 'navigation.groupSystem',
      fallback: 'System',
      items: [
        { href: '/audit-logs', roles: ["admin", "developer"], labelKey: 'navigation.auditLogs', fallback: 'Audit Logs' },
        { href: '/backup', roles: ["admin"], labelKey: 'navigation.backup', fallback: 'Backup' },
        { href: '/observability', roles: ["admin"], labelKey: 'navigation.observability', fallback: 'Observability' },
        { href: '/analytics', roles: ["admin", "developer"], labelKey: 'navigation.analytics', fallback: 'Analytics' },
        { href: '/feedback', roles: ["admin", "developer"], labelKey: 'navigation.feedback', fallback: 'Feedback' },
        { href: '/compliance', roles: ["admin"], labelKey: 'navigation.compliance', fallback: 'Compliance' },
        { href: '/admin/tenants', roles: ["admin"], labelKey: 'navigation.tenants', fallback: 'Tenants' },
        { href: '/admin/users', roles: ["admin"], labelKey: 'navigation.usersAdmin', fallback: 'Users' },
        { href: '/security', roles: ["admin"], labelKey: 'navigation.security', fallback: 'Security' },
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
          'fixed inset-y-0 left-0 z-50 w-60 border-r transition-transform duration-300 lg:relative lg:translate-x-0',
          SURFACE,
          HAIRLINE,
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Brand */}
          <div className={clsx('flex items-center justify-between px-5 py-4 border-b', HAIRLINE)}>
            <div className="flex items-center gap-2.5 min-w-0">
              <span
                className="inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--elev-1)]"
                aria-hidden="true"
              >
                {/* Monogram mark — drawn, not a glyph or emoji. */}
                <svg width="14" height="14" viewBox="0 0 16 16">
                  <path
                    d="M3.5 2.5 L8 8 L3.5 13.5 M12.5 2.5 L8 8 L12.5 13.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <h1 className="text-[15px] font-semibold tracking-tight truncate">
                {t('common.appName', 'X-Agent')}
              </h1>
            </div>
            <button
              onClick={toggleSidebar}
              className={clsx(ICON_BUTTON, 'lg:hidden')}
              aria-label={t('common.closeMenu', 'Close menu')}
            >
              <X size={18} />
            </button>
          </div>

          {/* Navigation — text-only rows, accent bar + tint on the active one */}
          <nav
            className="flex-1 overflow-y-auto py-2"
            aria-label={t('navigation.main', 'Main navigation')}
          >
            {navGroups.map((group, groupIndex) => {
              // 按角色过滤导航入口（后端 scope 鉴权仍是权威；这里只隐藏无权限入口，
              // 修复普通用户点进管理页只能看到裸 403 的体验问题）
              const role = currentUserRole()
              const visible = group.items.filter(
                (item) => !item.roles || item.roles.includes(role)
              )
              if (!visible.length) return null
              return (
              <div key={group.labelKey} className="mb-1">
                {groupIndex > 0 && (
                  <div className={clsx('mx-5 mb-1 border-t', HAIRLINE)} aria-hidden="true" />
                )}
                <div
                  className="px-5 pt-3 pb-1.5 text-[11px] uppercase tracking-[0.08em] opacity-50 select-none"
                  aria-hidden="true"
                >
                  {t(group.labelKey, group.fallback)}
                </div>
                {visible.map((item) => (
                  <SidebarLink
                    key={item.href}
                    to={item.href}
                    label={t(item.labelKey, item.fallback)}
                    end={item.end}
                  />
                ))}
              </div>
              )
            })}
          </nav>

          {/* User Profile */}
          <div className={clsx('px-4 py-3 border-t', HAIRLINE)}>
            <div className="flex items-center gap-2.5">
              <span
                className={clsx(
                  'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                  'bg-[var(--surface-raised)] border text-[12px] font-medium',
                  HAIRLINE
                )}
                aria-hidden="true"
              >
                {(user?.name || 'G').trim().charAt(0).toUpperCase()}
              </span>
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
                className={ICON_BUTTON}
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
          className={clsx(
            'flex items-center justify-between px-6 py-2.5 border-b',
            SURFACE,
            HAIRLINE
          )}
        >
          <button
            onClick={toggleSidebar}
            className={clsx(ICON_BUTTON, 'lg:hidden')}
            aria-label={t('common.openMenu', 'Open menu')}
          >
            <Menu size={20} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <ConnectionStatus />

            {/* Language Switcher */}
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as LanguageCode)}
              className="focus-ring bg-transparent text-[12px] opacity-70 hover:opacity-100 transition-opacity cursor-pointer border-0 rounded-md"
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
              className={ICON_BUTTON}
              title={t('common.toggleTheme', 'Toggle theme')}
              aria-label={t('common.toggleTheme', 'Toggle theme')}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="h-full" ref={contentRef}>
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

interface SidebarLinkProps {
  to: string
  label: string
  /** Exact-path matching; see NavItem.end. */
  end?: boolean
}

/**
 * Sidebar nav row.
 *
 * Uses react-router's NavLink so navigation stays client-side. The previous
 * implementation was a bare `<a href>` with `window.location.pathname` for the
 * active check — that made every sidebar click a full document reload: all
 * lazy chunks were re-fetched, in-flight requests and local component state
 * were dropped, and the active state only updated after the reload.
 *
 * The root route is matched exactly. That is partly belt-and-braces — in
 * react-router 7 `to="/"` already cannot prefix-match (the match probe reads
 * `pathname.charAt(1)`, which is only "/" for a "//" path) — but depending on
 * that implementation detail to keep the Dashboard row un-highlighted is
 * fragile.
 */
const SidebarLink: React.FC<SidebarLinkProps> = ({ to, label, end }) => (
  <RouterNavLink
    to={to}
    end={end ?? to === '/'}
    className={({ isActive }) =>
      clsx(
        'link-plain group relative flex items-center pl-5 pr-3 py-[7px] text-[13px] leading-5',
        'transition-[color,background-color,opacity] duration-150',
        isActive
          ? 'opacity-100 font-medium bg-[var(--accent-soft)]'
          : 'opacity-50 hover:opacity-90 hover:bg-[var(--hover)]'
      )
    }
  >
    {({ isActive }) => (
      <>
        <span
          className={clsx(
            'absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-full',
            'bg-[var(--accent)] transition-[transform,opacity] duration-200 ease-smooth',
            isActive ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-50'
          )}
          aria-hidden="true"
        />
        {label}
      </>
    )}
  </RouterNavLink>
)

const ConnectionStatus: React.FC = () => {
  const { isConnected } = useAppStore()
  const { t } = useI18n()

  return (
    <div className="flex items-center gap-2" role="status" aria-live="polite">
      <div
        className={clsx(
          'w-1.5 h-1.5 rounded-full',
          isConnected ? 'bg-[var(--success)] breathe' : 'bg-[var(--danger)]'
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
