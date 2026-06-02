import React from 'react'
import { useAppStore } from '@/store/appStore'
import { Menu, X, Moon, Sun, LogOut } from 'lucide-react'
import clsx from 'clsx'

interface LayoutProps {
  children: React.ReactNode
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { sidebarOpen, toggleSidebar, theme, toggleTheme, user, logout } = useAppStore()

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
            <h1 className="text-2xl font-bold">X-Agent</h1>
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-2 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-2">
            <NavLink href="/" icon="🏠" label="Dashboard" />
            <NavLink href="/chat" icon="💬" label="Chat" />
            <NavLink href="/tasks" icon="✓" label="Tasks" />
            <NavLink href="/tools" icon="🔧" label="Tools" />
            <NavLink href="/memory" icon="🧠" label="Memory" />
            <NavLink href="/agents" icon="🤖" label="Agents" />
            <NavLink href="/settings" icon="⚙️" label="Settings" />
          </nav>

          {/* User Profile */}
          <div className="p-4 border-t border-slate-700">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm font-medium">{user?.name || 'Guest'}</p>
                <p className="text-xs text-slate-400">{user?.email || 'Not logged in'}</p>
              </div>
              <button
                onClick={logout}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
                title="Logout"
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
          >
            <Menu size={24} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-4">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={clsx(
                'p-2 rounded-lg transition-colors',
                theme === 'dark'
                  ? 'bg-slate-800 hover:bg-slate-700'
                  : 'bg-slate-100 hover:bg-slate-200'
              )}
              title="Toggle theme"
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
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
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
      className={clsx(
        'flex items-center gap-3 px-4 py-2 rounded-lg transition-colors',
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-slate-300 hover:bg-slate-800'
      )}
    >
      <span className="text-xl">{icon}</span>
      <span className="text-sm font-medium">{label}</span>
    </a>
  )
}

const ConnectionStatus: React.FC = () => {
  const { isConnected } = useAppStore()

  return (
    <div className="flex items-center gap-2">
      <div className={clsx(
        'w-2 h-2 rounded-full',
        isConnected ? 'bg-green-500' : 'bg-red-500'
      )} />
      <span className="text-xs text-slate-500">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  )
}

export default Layout
