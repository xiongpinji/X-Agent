import React, { forwardRef, memo } from 'react'
import clsx from 'clsx'
import { AriaBuilder } from '@/utils/accessibility'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success' | 'warning'
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

const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95'

const variantStyles = {
  primary: 'bg-primary-600 hover:bg-primary-700 text-white focus:ring-primary-500 dark:bg-primary-500 dark:hover:bg-primary-600',
  secondary: 'bg-slate-200 hover:bg-slate-300 text-slate-900 focus:ring-slate-500 dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-white',
  danger: 'bg-error-600 hover:bg-error-700 text-white focus:ring-error-500 dark:bg-error-500 dark:hover:bg-error-600',
  ghost: 'hover:bg-slate-100 text-slate-900 focus:ring-slate-500 dark:hover:bg-slate-800 dark:text-white',
  success: 'bg-success-600 hover:bg-success-700 text-white focus:ring-success-500 dark:bg-success-500 dark:hover:bg-success-600',
  warning: 'bg-warning-600 hover:bg-warning-700 text-white focus:ring-warning-500 dark:bg-warning-500 dark:hover:bg-warning-600',
}

const sizeStyles = {
  xs: 'px-2 py-1 text-xs',
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
  xl: 'px-8 py-4 text-xl',
}

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

      const iconElement = isLoading ? (
        <span className="animate-spin" aria-hidden="true">
          ⏳
        </span>
      ) : icon && !isLoading ? (
        icon
      ) : null

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

