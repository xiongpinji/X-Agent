import React from 'react'
import clsx from 'clsx'
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react'

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'info' | 'success' | 'warning' | 'error'
  title?: string
  onClose?: () => void
  children: React.ReactNode
}

export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ variant = 'info', title, onClose, children, className, ...props }, ref) => {
    const variantStyles = {
      info: 'bg-blue-50 border border-blue-200 text-blue-800 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-200',
      success: 'bg-green-50 border border-green-200 text-green-800 dark:bg-green-900/20 dark:border-green-800 dark:text-green-200',
      warning: 'bg-yellow-50 border border-yellow-200 text-yellow-800 dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-200',
      error: 'bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-200',
    }

    const iconMap = {
      info: <Info size={20} />,
      success: <CheckCircle size={20} />,
      warning: <AlertTriangle size={20} />,
      error: <AlertCircle size={20} />,
    }

    return (
      <div
        ref={ref}
        className={clsx('rounded-lg p-4 flex gap-3', variantStyles[variant], className)}
        role="alert"
        {...props}
      >
        <div className="flex-shrink-0">{iconMap[variant]}</div>
        <div className="flex-1">
          {title && <h3 className="font-semibold mb-1">{title}</h3>}
          <div className="text-sm">{children}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="flex-shrink-0 hover:opacity-70 transition-opacity"
            aria-label="Close alert"
          >
            <X size={20} />
          </button>
        )}
      </div>
    )
  }
)

Alert.displayName = 'Alert'
