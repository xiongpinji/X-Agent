import React from 'react'
import clsx from 'clsx'

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'primary' | 'success'
}

export const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ size = 'md', variant = 'default', className, ...props }, ref) => {
    const sizeStyles = {
      sm: 'w-4 h-4',
      md: 'w-8 h-8',
      lg: 'w-12 h-12',
    }

    const variantStyles = {
      default: 'border-slate-300 dark:border-slate-600 border-t-slate-900 dark:border-t-white',
      primary: 'border-blue-200 border-t-blue-600',
      success: 'border-green-200 border-t-green-600',
    }

    return (
      <div
        ref={ref}
        className={clsx(
          'border-4 rounded-full animate-spin',
          sizeStyles[size],
          variantStyles[variant],
          className
        )}
        role="status"
        aria-label="Loading"
        {...props}
      />
    )
  }
)

Spinner.displayName = 'Spinner'
