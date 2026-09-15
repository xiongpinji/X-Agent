import React from 'react'
import clsx from 'clsx'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  variant?: 'default' | 'elevated' | 'outlined'
  /** Frosted panel (backdrop blur). Intended for sticky bars / overlays. */
  glass?: boolean
  /** Adds a hover lift. Opt in only for genuinely clickable cards. */
  interactive?: boolean
}

/**
 * Surfaces come from the design tokens (src/design/language.css), so one
 * component tree renders correctly in both themes with no `dark:` prefixes.
 *
 * `default` deliberately carries a hairline border and NO box-shadow: the
 * console sub-app (`.console-root` in index.css) mandates flat, borderless-
 * chrome surfaces, and a hard-coded shadow here would leak past that spec.
 * `elevated` is the explicit opt-in for depth.
 */
const variantStyles = {
  default: 'bg-[var(--surface)] border border-[var(--divider)]',
  elevated:
    'bg-[var(--surface)] border border-[var(--divider)] shadow-[var(--elev-2)]',
  outlined: 'bg-[var(--surface)] border-2 border-[var(--divider)]',
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ children, variant = 'default', glass = false, interactive = false, className, ...props }, ref) => {
    const baseStyles =
      'rounded-xl transition-[box-shadow,transform,border-color] duration-200 ease-smooth'

    return (
      <div
        ref={ref}
        className={clsx(
          baseStyles,
          glass ? 'glass border border-[var(--divider)]' : variantStyles[variant],
          interactive && 'lift',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const CardHeader = React.forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ children, className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx('px-6 py-4 border-b border-[var(--divider)]', className)}
      {...props}
    >
      {children}
    </div>
  )
)

CardHeader.displayName = 'CardHeader'

export interface CardBodyProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const CardBody = React.forwardRef<HTMLDivElement, CardBodyProps>(
  ({ children, className, ...props }, ref) => (
    <div ref={ref} className={clsx('px-6 py-4', className)} {...props}>
      {children}
    </div>
  )
)

CardBody.displayName = 'CardBody'

export interface CardFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const CardFooter = React.forwardRef<HTMLDivElement, CardFooterProps>(
  ({ children, className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx('px-6 py-4 border-t border-[var(--divider)]', className)}
      {...props}
    >
      {children}
    </div>
  )
)

CardFooter.displayName = 'CardFooter'
