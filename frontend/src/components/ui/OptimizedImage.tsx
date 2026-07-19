/**
 * Optimized Image Component
 *
 * Features:
 * - Lazy loading
 * - WebP support with fallback
 * - Responsive images
 * - Placeholder/skeleton
 * - Error handling
 */

import React, { useState, useEffect, useRef, memo } from 'react'
import clsx from 'clsx'

export interface OptimizedImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string
  alt: string
  width?: number
  height?: number
  placeholder?: 'blur' | 'empty' | 'skeleton'
  priority?: boolean
  sizes?: string
  srcSet?: string
  onLoad?: () => void
  onError?: () => void
  className?: string
}

export const OptimizedImage = memo(
  React.forwardRef<HTMLImageElement, OptimizedImageProps>(
    (
      {
        src,
        alt,
        width,
        height,
        placeholder = 'blur',
        priority = false,
        sizes,
        srcSet,
        onLoad,
        onError,
        className,
        ...props
      },
      ref
    ) => {
      const [isLoaded, setIsLoaded] = useState(false)
      const [hasError, setHasError] = useState(false)
      const [imageSrc, setImageSrc] = useState<string | null>(null)
      const imgRef = useRef<HTMLImageElement>(null)

      // Combine refs
      React.useImperativeHandle(ref, () => imgRef.current as HTMLImageElement)

      useEffect(() => {
        if (!priority) {
          // Use Intersection Observer for lazy loading
          if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver(
              ([entry]) => {
                if (entry.isIntersecting) {
                  setImageSrc(src)
                  observer.unobserve(entry.target)
                }
              },
              { rootMargin: '50px' }
            )

            if (imgRef.current) {
              observer.observe(imgRef.current)
            }

            return () => {
              if (imgRef.current) {
                observer.unobserve(imgRef.current)
              }
            }
          } else {
            // Fallback for browsers without IntersectionObserver
            setImageSrc(src)
          }
        } else {
          setImageSrc(src)
        }
      }, [src, priority])

      const handleLoad = () => {
        setIsLoaded(true)
        onLoad?.()
      }

      const handleError = () => {
        setHasError(true)
        onError?.()
      }

      // Generate WebP srcset
      const generateWebPSrcSet = (originalSrc: string): string => {
        if (!srcSet) return ''
        return srcSet
          .split(',')
          .map((item) => {
            const [url, descriptor] = item.trim().split(/\s+/)
            const webpUrl = url.replace(/\.(jpg|jpeg|png)$/i, '.webp')
            return `${webpUrl} ${descriptor}`
          })
          .join(',')
      }

      if (hasError) {
        return (
          <div
            className={clsx(
              'bg-slate-200 dark:bg-slate-700 flex items-center justify-center',
              className
            )}
            style={{ width, height }}
            role="img"
            aria-label={alt}
          >
            <span className="text-slate-500 dark:text-slate-400 text-sm">
              Failed to load image
            </span>
          </div>
        )
      }

      return (
        <picture>
          {/* WebP format */}
          {imageSrc && (
            <source
              srcSet={generateWebPSrcSet(imageSrc)}
              type="image/webp"
            />
          )}

          {/* Fallback image */}
          <img
            ref={imgRef}
            src={imageSrc || undefined}
            alt={alt}
            width={width}
            height={height}
            sizes={sizes}
            srcSet={srcSet}
            loading={priority ? 'eager' : 'lazy'}
            decoding="async"
            className={clsx(
              'transition-opacity duration-300',
              isLoaded ? 'opacity-100' : 'opacity-0',
              placeholder === 'blur' && !isLoaded && 'blur-sm',
              className
            )}
            onLoad={handleLoad}
            onError={handleError}
            {...props}
          />

          {/* Placeholder */}
          {!isLoaded && placeholder !== 'empty' && (
            <div
              className={clsx(
                'absolute inset-0 bg-slate-200 dark:bg-slate-700',
                placeholder === 'skeleton' && 'animate-shimmer'
              )}
              style={{ width, height }}
              aria-hidden="true"
            />
          )}
        </picture>
      )
    }
  )
)

OptimizedImage.displayName = 'OptimizedImage'

/**
 * Image with responsive srcset
 */
export interface ResponsiveImageProps extends OptimizedImageProps {
  srcSmall?: string
  srcMedium?: string
  srcLarge?: string
}

export const ResponsiveImage = memo(
  React.forwardRef<HTMLImageElement, ResponsiveImageProps>(
    (
      {
        src,
        srcSmall,
        srcMedium,
        srcLarge,
        sizes = '(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw',
        ...props
      },
      ref
    ) => {
      const srcSet = [
        srcSmall && `${srcSmall} 640w`,
        srcMedium && `${srcMedium} 1024w`,
        srcLarge && `${srcLarge} 1920w`,
      ]
        .filter(Boolean)
        .join(',')

      return (
        <OptimizedImage
          ref={ref}
          src={src}
          srcSet={srcSet || undefined}
          sizes={sizes}
          {...props}
        />
      )
    }
  )
)

ResponsiveImage.displayName = 'ResponsiveImage'
