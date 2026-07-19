import React from 'react'
import clsx from 'clsx'

export interface CircularProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  max?: number
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'danger'
  showLabel?: boolean
}

export const CircularProgress = React.forwardRef<HTMLDivElement, CircularProgressProps>(
  (
    {
      value,
      max = 100,
      size = 'md',
      variant = 'default',
      showLabel = true,
      className,
      ...props
    },
    ref
  ) => {
    const percentage = Math.min((value / max) * 100, 100)
    const circumference = 2 * Math.PI * 45

    const sizeStyles = {
      sm: 'w-16 h-16',
      md: 'w-24 h-24',
      lg: 'w-32 h-32',
    }

    const colorMap = {
      default: '#3b82f6',
      success: '#10b981',
      warning: '#f59e0b',
      danger: '#ef4444',
    }

    return (
      <div
        ref={ref}
        className={clsx('flex items-center justify-center', sizeStyles[size], className)}
        {...props}
      >
        <svg className="transform -rotate-90" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-slate-200 dark:text-slate-700"
          />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke={colorMap[variant]}
            strokeWidth="2"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - (percentage / 100) * circumference}
            strokeLinecap="round"
            className="transition-all duration-300"
          />
        </svg>
        {showLabel && (
          <div className="absolute text-center">
            <p className="text-sm font-semibold text-slate-900 dark:text-white">
              {Math.round(percentage)}%
            </p>
          </div>
        )}
      </div>
    )
  }
)

CircularProgress.displayName = 'CircularProgress'
