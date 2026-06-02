import React from 'react'
import clsx from 'clsx'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
  icon?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, icon, className, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{icon}</div>}
          <input
            ref={ref}
            className={clsx(
              'w-full px-4 py-2 rounded-lg border transition-colors',
              icon && 'pl-10',
              error
                ? 'border-red-500 focus:border-red-600 focus:ring-red-500'
                : 'border-slate-300 dark:border-slate-600 focus:border-blue-500 focus:ring-blue-500',
              'bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500',
              'focus:outline-none focus:ring-2 focus:ring-offset-0',
              className
            )}
            {...props}
          />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>}
        {helperText && !error && (
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{helperText}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
