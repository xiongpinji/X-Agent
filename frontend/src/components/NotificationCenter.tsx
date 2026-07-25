import React, { useEffect, useState, useCallback } from 'react'
import { websocketClient, Notification } from '@/services/websocketClient'
import { useAppStore } from '@/store/appStore'
import clsx from 'clsx'

interface NotificationItem extends Notification {
  id: string
  read: boolean
}

const NotificationCenter: React.FC = () => {
  const { theme } = useAppStore()
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [connected, setConnected] = useState(false)

  const handleNotification = useCallback((notification: Notification) => {
    if (notification.type === 'connected') {
      setConnected(true)
      return
    }
    if (notification.type === 'pong') return

    setNotifications(prev => [{
      ...notification,
      id: `notif-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      read: false,
    }, ...prev].slice(0, 50))
  }, [])

  useEffect(() => {
    websocketClient.connect()
    const unsubscribe = websocketClient.subscribe(handleNotification)
    return () => {
      unsubscribe()
      websocketClient.disconnect()
    }
  }, [handleNotification])

  const unreadCount = notifications.filter(n => !n.read).length

  const markAllRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const clearAll = () => {
    setNotifications([])
  }

  const isDark = theme === 'dark'

  const getIcon = (type: string) => {
    switch (type) {
      case 'agent_complete': return '🤖'
      case 'workflow_status': return '🔀'
      case 'system_alert': return '⚠️'
      case 'memory_update': return '🧠'
      default: return '🔔'
    }
  }

  const timeAgo = (timestamp: number) => {
    const seconds = Math.floor(Date.now() / 1000 - timestamp)
    if (seconds < 60) return 'just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'relative p-2 rounded-lg transition-colors',
          isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'
        )}
        aria-label={`Notifications (${unreadCount} unread)`}
        aria-expanded={isOpen}
      >
        <span className="text-lg">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
        <span className={clsx(
          'absolute bottom-0.5 right-0.5 w-2 h-2 rounded-full',
          connected ? 'bg-green-500' : 'bg-slate-400'
        )} />
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <>
          <div
            role="button"
            tabIndex={0}
            aria-label="Close notifications"
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setIsOpen(false); }}
          />
          <div className={clsx(
            'absolute right-0 top-full mt-2 w-80 max-h-96 rounded-xl shadow-xl border z-50 overflow-hidden flex flex-col',
            isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
          )} role="region" aria-label="Notifications">
            {/* Header */}
            <div className={clsx(
              'flex items-center justify-between px-4 py-3 border-b',
              isDark ? 'border-slate-700' : 'border-slate-200'
            )}>
              <h3 className="text-sm font-semibold">Notifications</h3>
              <div className="flex gap-2">
                <button onClick={markAllRead} className="text-xs text-blue-500 hover:text-blue-600">
                  Mark all read
                </button>
                <button onClick={clearAll} className="text-xs text-slate-400 hover:text-slate-600">
                  Clear
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="py-10 text-center">
                  <p className="text-2xl mb-2">🔕</p>
                  <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                    No notifications yet
                  </p>
                </div>
              ) : (
                notifications.map(item => (
                  <div
                    key={item.id}
                    className={clsx(
                      'px-4 py-3 border-b last:border-0 transition-colors',
                      isDark ? 'border-slate-800' : 'border-slate-100',
                      !item.read && (isDark ? 'bg-blue-900/10' : 'bg-blue-50')
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-base mt-0.5">{getIcon(item.type)}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{item.title}</p>
                        <p className={clsx('text-xs mt-0.5 line-clamp-2', isDark ? 'text-slate-400' : 'text-slate-500')}>
                          {item.body}
                        </p>
                        <p className={clsx('text-[10px] mt-1', isDark ? 'text-slate-600' : 'text-slate-400')}>
                          {timeAgo(item.timestamp)}
                        </p>
                      </div>
                      {!item.read && (
                        <span className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default NotificationCenter
