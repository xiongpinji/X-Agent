import React from 'react'
import clsx from 'clsx'

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: Array<{ value: string | number; label: string }>
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, className, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            {label}
          </label>
        )}
        <select
          ref={ref}
          className={clsx(
            'w-full px-4 py-2 rounded-lg border transition-colors',
            error
              ? 'border-red-500 focus:border-red-600 focus:ring-red-500'
              : 'border-slate-300 dark:border-slate-600 focus:border-blue-500 focus:ring-blue-500',
            'bg-white dark:bg-slate-800 text-slate-900 dark:text-white',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'appearance-none cursor-pointer',
            className
          )}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>}
      </div>
    )
  }
)

Select.displayName = 'Select'
