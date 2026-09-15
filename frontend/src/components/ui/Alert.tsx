import React from 'react'
import clsx from 'clsx'
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react'

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'info' | 'success' | 'warning' | 'error'
  title?: string
  onClose?: () => void
  children: React.ReactNode
}

/**
 * Status hues come from the design tokens (--accent/--success/--warning/
 * --danger and their -soft fills), so the icon, the rail and the wash stay in
 * step automatically across themes.
 *
 * The 4px left rail carries the severity even when the icon is missed at a
 * glance — the previous version relied on a full 1px border in the same hue,
 * which read as decoration rather than signal.
 */
const variantStyles = {
  info: 'bg-[var(--accent-soft)] border-l-[var(--accent)]',
  success: 'bg-[var(--success-soft)] border-l-[var(--success)]',
  warning: 'bg-[var(--warning-soft)] border-l-[var(--warning)]',
  error: 'bg-[var(--danger-soft)] border-l-[var(--danger)]',
}

const iconColorStyles = {
  info: 'text-[var(--accent)]',
  success: 'text-[var(--success)]',
  warning: 'text-[var(--warning)]',
  error: 'text-[var(--danger)]',
}

export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ variant = 'info', title, onClose, children, className, ...props }, ref) => {
    const iconMap = {
      info: <Info size={18} />,
      success: <CheckCircle size={18} />,
      warning: <AlertTriangle size={18} />,
      error: <AlertCircle size={18} />,
    }

    return (
      <div
        ref={ref}
        className={clsx(
          'flex gap-3 rounded-lg border border-l-4 border-[var(--divider)] p-4 text-[var(--fg)]',
          variantStyles[variant],
          className
        )}
        role="alert"
        {...props}
      >
        <div className={clsx('flex-shrink-0 mt-0.5', iconColorStyles[variant])} aria-hidden="true">
          {iconMap[variant]}
        </div>
        <div className="flex-1 min-w-0">
          {title && <h3 className="font-semibold mb-1 text-[15px] leading-snug">{title}</h3>}
          <div className="text-sm opacity-80">{children}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="focus-ring flex-shrink-0 h-6 w-6 -mr-1 -mt-1 inline-flex items-center justify-center rounded opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Close alert"
          >
            <X size={16} />
          </button>
        )}
      </div>
    )
  }
)

Alert.displayName = 'Alert'
