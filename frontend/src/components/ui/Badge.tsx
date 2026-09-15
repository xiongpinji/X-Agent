import React from 'react'
import clsx from 'clsx'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
  size?: 'sm' | 'md' | 'lg'
  /** Renders a leading status dot in the badge's own colour. */
  dot?: boolean
  children: React.ReactNode
}

/**
 * The fill/border come from `.badge-tint` (src/design/language.css), which
 * mixes them from `currentColor`. Each variant therefore only declares a text
 * colour, and light/dark both resolve from the same tokens — no `dark:` pairs.
 */
const variantStyles = {
  default: 'badge-tint badge-neutral',
  info: 'badge-tint text-[var(--accent)]',
  success: 'badge-tint text-[var(--success)]',
  warning: 'badge-tint text-[var(--warning)]',
  danger: 'badge-tint text-[var(--danger)]',
}

const sizeStyles = {
  sm: 'px-2 py-0.5 text-[11px] gap-1',
  md: 'px-2.5 py-1 text-xs gap-1.5',
  lg: 'px-3 py-1 text-[13px] gap-1.5',
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', size = 'md', dot = false, children, className, ...props }, ref) => (
    <span
      ref={ref}
      className={clsx(
        'inline-flex items-center justify-center font-medium rounded-full border whitespace-nowrap',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" aria-hidden="true" />
      )}
      {children}
    </span>
  )
)

Badge.displayName = 'Badge'
