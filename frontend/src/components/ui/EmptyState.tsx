import React from 'react'
import clsx from 'clsx'

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon, title, description, action, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx('flex flex-col items-center justify-center py-12 text-center', className)}
        {...props}
      >
        {icon && <div className="mb-4 text-slate-400">{icon}</div>}
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">{title}</h3>
        {description && (
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 max-w-sm">{description}</p>
        )}
        {action && <div>{action}</div>}
      </div>
    )
  }
)

EmptyState.displayName = 'EmptyState'
