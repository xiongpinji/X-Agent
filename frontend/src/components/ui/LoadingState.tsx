import React from 'react'
import clsx from 'clsx'
import { Spinner } from './Spinner'

export interface LoadingStateProps extends React.HTMLAttributes<HTMLDivElement> {
  message?: string
  size?: 'sm' | 'md' | 'lg'
}

export const LoadingState = React.forwardRef<HTMLDivElement, LoadingStateProps>(
  ({ message = 'Loading...', size = 'md', className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx('flex flex-col items-center justify-center py-12 gap-4', className)}
        {...props}
      >
        <Spinner size={size} />
        <p className="text-slate-600 dark:text-slate-400">{message}</p>
      </div>
    )
  }
)

LoadingState.displayName = 'LoadingState'
