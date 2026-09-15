import React from 'react'
import clsx from 'clsx'

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'primary' | 'success'
}

const sizeStyles = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
}

/**
 * `border-2` (down from `border-4`) keeps the ring crisp at the 16px size;
 * a 4px ring on a 16px circle is mostly border. Colours are tokens, so the
 * track and the head both adapt to the theme without `dark:` overrides.
 */
const variantStyles = {
  default: 'border-[var(--divider)] border-t-[var(--fg)]',
  primary: 'border-[var(--accent-soft)] border-t-[var(--accent)]',
  success: 'border-[var(--success-soft)] border-t-[var(--success)]',
}

export const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ size = 'md', variant = 'default', className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx(
        'border-2 rounded-full animate-spin',
        sizeStyles[size],
        variantStyles[variant],
        className
      )}
      role="status"
      aria-label="Loading"
      {...props}
    />
  )
)

Spinner.displayName = 'Spinner'
