import React from 'react'
import clsx from 'clsx'

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  count?: number
  height?: string
  width?: string
  circle?: boolean
}

/**
 * `.shimmer` (src/design/language.css) is a directional sweep with an easing
 * curve, rather than Tailwind's `animate-pulse` opacity blink — a sweep reads
 * as "content loading", a blink reads as "element disabled".
 *
 * `height`/`width` are Tailwind class strings (e.g. "h-4", "w-1/2"), which is
 * the existing contract; it is kept as-is so callers do not break.
 */
export const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ count = 1, height = 'h-4', width = 'w-full', circle = false, className, ...props }, ref) => {
    return (
      <div ref={ref} className="space-y-2" {...props}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className={clsx(
              'shimmer',
              circle ? 'rounded-full' : 'rounded-md',
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
