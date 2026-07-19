import React from 'react'
import clsx from 'clsx'

export interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  max?: number
  variant?: 'default' | 'success' | 'warning' | 'danger'
  showLabel?: boolean
  animated?: boolean
}

export const ProgressBar = React.forwardRef<HTMLDivElement, ProgressBarProps>(
  (
    {
      value,
      max = 100,
      variant = 'default',
      showLabel = false,
      animated = true,
      className,
      ...props
    },
    ref
  ) => {
    const percentage = Math.min((value / max) * 100, 100)

    const variantStyles = {
      default: 'bg-blue-600',
      success: 'bg-green-600',
      warning: 'bg-yellow-600',
      danger: 'bg-red-600',
    }

    return (
      <div ref={ref} className={clsx('w-full', className)} {...props}>
        <div
          className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden"
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        >
          <div
            className={clsx(
              'h-full transition-all',
              variantStyles[variant],
              animated && 'animate-pulse'
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
        {showLabel && (
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            {Math.round(percentage)}%
          </p>
        )}
      </div>
    )
  }
)

ProgressBar.displayName = 'ProgressBar'
