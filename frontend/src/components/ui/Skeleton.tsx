import React from 'react'
import clsx from 'clsx'

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  count?: number
  height?: string
  width?: string
  circle?: boolean
}

export const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ count = 1, height = 'h-4', width = 'w-full', circle = false, className, ...props }, ref) => {
    return (
      <div ref={ref} className="space-y-2" {...props}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className={clsx(
              'bg-slate-200 dark:bg-slate-700 animate-pulse',
              circle ? 'rounded-full' : 'rounded-lg',
              height,
              width,
              className
            )}
          />
        ))}
      </div>
    )
  }
)

Skeleton.displayName = 'Skeleton'
