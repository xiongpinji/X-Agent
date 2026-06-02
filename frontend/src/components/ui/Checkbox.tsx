import React from 'react'
import clsx from 'clsx'

export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, className, ...props }, ref) => {
    return (
      <div className="flex items-center gap-2">
        <input
          ref={ref}
          type="checkbox"
          className={clsx(
            'w-4 h-4 rounded border-slate-300 dark:border-slate-600',
            'text-blue-600 focus:ring-blue-500 cursor-pointer',
            'bg-white dark:bg-slate-800',
            className
          )}
          {...props}
        />
        {label && (
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer">
            {label}
          </label>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox'
