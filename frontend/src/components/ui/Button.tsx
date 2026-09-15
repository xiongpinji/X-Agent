import React, { forwardRef, memo } from 'react'
import clsx from 'clsx'
import { AriaBuilder } from '@/utils/accessibility'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'success' | 'warning'
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  isLoading?: boolean
  isDisabled?: boolean
  icon?: React.ReactNode
  iconPosition?: 'left' | 'right'
  fullWidth?: boolean
  children: React.ReactNode
  ariaLabel?: string
  ariaDescribedBy?: string
}

/**
 * Focus is handled by the `.focus-ring` class (outline-based, themed via
 * --accent) rather than a ring utility, so it survives on both themes and on
 * any surface without per-variant `ring-offset` colours.
 *
 * Colour comes from the design tokens in src/design/language.css; only the
 * semantic status variants (success/warning/danger) keep their own scale,
 * because re-pointing those at the brand accent would destroy their meaning.
 */
const baseStyles =
  'focus-ring inline-flex items-center justify-center gap-2 font-medium rounded-lg ' +
  'transition-[background-color,border-color,color,transform,opacity] duration-150 ease-smooth ' +
  'disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]'

const variantStyles: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary:
    'sheen bg-[var(--accent)] text-[var(--accent-fg)] hover:bg-[var(--accent-strong)]',
  secondary:
    'bg-[var(--surface-raised)] text-[var(--fg)] border border-[var(--divider)] ' +
    'hover:bg-[var(--surface-raised-hover)] hover:border-[var(--accent-line)]',
  outline:
    'bg-transparent text-[var(--fg)] border border-[var(--divider)] ' +
    'hover:border-[var(--accent-line)] hover:text-[var(--accent)]',
  ghost: 'bg-transparent text-[var(--fg)] hover:bg-[var(--hover)]',
  danger: 'bg-error-600 text-white hover:bg-error-700',
  success: 'bg-success-600 text-white hover:bg-success-700',
  warning: 'bg-warning-600 text-white hover:bg-warning-700',
}

/**
 * Sizes set an explicit height instead of padding-derived height, so buttons on
 * one row align even when their font sizes differ.
 */
const sizeStyles: Record<NonNullable<ButtonProps['size']>, string> = {
  xs: 'h-7 px-2.5 text-xs',
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-10 px-4 text-sm',
  lg: 'h-11 px-5 text-[15px]',
  xl: 'h-12 px-6 text-base',
}

/**
 * CSS ring spinner. Sized in `em` and coloured with `currentColor` so it
 * inherits the variant's text colour and font size — no per-variant overrides,
 * and no emoji (the previous implementation rendered a literal "⏳").
 */
const SpinnerGlyph: React.FC = () => (
  <span
    className="inline-block shrink-0 rounded-full border-2 border-current border-t-transparent animate-spin"
    style={{ width: '1em', height: '1em' }}
    aria-hidden="true"
  />
)

export const Button = memo(
  forwardRef<HTMLButtonElement, ButtonProps>(
    (
      {
        variant = 'primary',
        size = 'md',
        isLoading = false,
        isDisabled = false,
        icon,
        iconPosition = 'left',
        fullWidth = false,
        children,
        className,
        disabled,
        ariaLabel,
        ariaDescribedBy,
        ...props
      },
      ref
    ) => {
      const isButtonDisabled = disabled || isDisabled || isLoading

      // Build ARIA attributes
      const ariaAttrs = new AriaBuilder()
        .disabled(isButtonDisabled)
        .busy(isLoading)

      if (ariaLabel) {
        ariaAttrs.label(ariaLabel)
      }

      if (ariaDescribedBy) {
        ariaAttrs.describedBy(ariaDescribedBy)
      }

      const iconElement = isLoading ? <SpinnerGlyph /> : icon ?? null

      return (
        <button
          ref={ref}
          className={clsx(
            baseStyles,
            variantStyles[variant],
            sizeStyles[size],
            fullWidth && 'w-full',
            className
          )}
          disabled={isButtonDisabled}
          {...ariaAttrs.build()}
          {...props}
        >
          {iconPosition === 'left' && iconElement}
          <span>{children}</span>
          {iconPosition === 'right' && iconElement}
        </button>
      )
    }
  )
)

Button.displayName = 'Button'
