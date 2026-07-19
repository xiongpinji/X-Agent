import React from 'react'
import clsx from 'clsx'

export interface TimelineProps extends React.HTMLAttributes<HTMLDivElement> {
  items: Array<{
    id: string
    title: string
    description?: string
    timestamp?: string
    status?: 'pending' | 'active' | 'completed' | 'error'
  }>
}

export const Timeline = React.forwardRef<HTMLDivElement, TimelineProps>(
  ({ items, className, ...props }, ref) => {
    const getStatusColor = (status?: string) => {
      switch (status) {
        case 'completed':
          return 'bg-green-600'
        case 'active':
          return 'bg-blue-600'
        case 'error':
          return 'bg-red-600'
        default:
          return 'bg-slate-300 dark:bg-slate-600'
      }
    }

    return (
      <div ref={ref} className={clsx('space-y-6', className)} {...props}>
        {items.map((item, index) => (
          <div key={item.id} className="flex gap-4">
            {/* Timeline Dot */}
            <div className="flex flex-col items-center">
              <div
                className={clsx(
                  'w-4 h-4 rounded-full transition-colors',
                  getStatusColor(item.status)
                )}
              />
              {index < items.length - 1 && (
                <div className="w-1 h-12 bg-slate-300 dark:bg-slate-600 mt-2" />
              )}
            </div>

            {/* Timeline Content */}
            <div className="flex-1 pt-1">
              <h4 className="font-semibold text-slate-900 dark:text-white">{item.title}</h4>
              {item.description && (
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{item.description}</p>
              )}
              {item.timestamp && (
                <p className="text-xs text-slate-500 dark:text-slate-500 mt-2">{item.timestamp}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }
)

Timeline.displayName = 'Timeline'
