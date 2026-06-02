import React from 'react'
import clsx from 'clsx'

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  label: string
  value: string | number
  change?: {
    value: number
    direction: 'up' | 'down'
  }
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red'
}

export const StatCard = React.forwardRef<HTMLDivElement, StatCardProps>(
  ({ icon, label, value, change, color = 'blue', className, ...props }, ref) => {
    const colorClasses = {
      blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
      green: 'bg-green-500/10 text-green-600 dark:text-green-400',
      purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
      orange: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
      red: 'bg-red-500/10 text-red-600 dark:text-red-400',
    }

    return (
      <div
        ref={ref}
        className={clsx(
          'rounded-lg p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700',
          className
        )}
        {...props}
      >
        {icon && (
          <div className={clsx('p-3 rounded-lg w-fit mb-4', colorClasses[color])}>
            {icon}
          </div>
        )}
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
          {label}
        </p>
        <div className="flex items-end justify-between">
          <p className="text-3xl font-bold text-slate-900 dark:text-white">{value}</p>
          {change && (
            <p
              className={clsx(
                'text-sm font-medium',
                change.direction === 'up' ? 'text-green-600' : 'text-red-600'
              )}
            >
              {change.direction === 'up' ? '↑' : '↓'} {Math.abs(change.value)}%
            </p>
          )}
        </div>
      </div>
    )
  }
)

StatCard.displayName = 'StatCard'
