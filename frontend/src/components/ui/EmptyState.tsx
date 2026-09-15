import React from 'react'
import clsx from 'clsx'

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

/**
 * The icon sits in a token-surfaced tile with a hairline edge instead of
 * floating loose in grey — it gives the empty state a focal point without
 * needing illustration assets. `.breathe` is a slow opacity/scale ambient
 * (GPU-only properties) and is disabled under `prefers-reduced-motion`.
 */
export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon, title, description, action, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx('flex flex-col items-center justify-center py-12 text-center', className)}
        {...props}
      >
        {icon && (
          <div
            className={clsx(
              'mb-4 flex items-center justify-center h-14 w-14 rounded-md',
              'bg-[var(--surface-raised)] border border-[var(--divider)] shadow-[var(--elev-1)]',
              'text-[var(--accent)] breathe'
            )}
            aria-hidden="true"
          >
            {icon}
          </div>
        )}
        <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">{title}</h3>
        {description && (
          <p className="text-sm opacity-60 mb-4 max-w-sm">{description}</p>
        )}
        {action && <div>{action}</div>}
      </div>
    )
  }
)

EmptyState.displayName = 'EmptyState'
