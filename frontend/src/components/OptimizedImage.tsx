/**
 * Optimized Image Component
 *
 * Supports lazy loading, responsive images, and multiple formats
 */

import React, { useState, useEffect, useRef } from 'react';

interface OptimizedImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  className?: string;
  priority?: boolean;
  sizes?: string;
  onLoad?: () => void;
  onError?: () => void;
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  alt,
  width,
  height,
  className,
  priority = false,
  sizes,
  onLoad,
  onError,
}) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!imgRef.current) return;

    // Use Intersection Observer for lazy loading
    if (!priority && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && imgRef.current) {
              imgRef.current.src = src;
              observer.unobserve(imgRef.current);
            }
          });
        },
        { rootMargin: '50px' }
      );

      observer.observe(imgRef.current);

      return () => {
        if (imgRef.current) {
          observer.unobserve(imgRef.current);
        }
      };
    } else if (priority) {
      imgRef.current.src = src;
    }
  }, [src, priority]);

  const handleLoad = () => {
    setIsLoaded(true);
    onLoad?.();
  };

  const handleError = () => {
    setIsError(true);
    onError?.();
  };

  // Generate srcSet for responsive images
  const generateSrcSet = () => {
    if (!src.includes('.')) return '';

    const ext = src.split('.').pop();
    const baseSrc = src.substring(0, src.lastIndexOf('.'));

    return `
      ${baseSrc}-300w.${ext} 300w,
      ${baseSrc}-600w.${ext} 600w,
      ${baseSrc}-1200w.${ext} 1200w
    `;
  };

  return (
    <picture>
      {/* WebP format */}
      <source
        srcSet={generateSrcSet().replace(new RegExp(`\\.${src.split('.').pop()}`, 'g'), '.webp')}
        type="image/webp"
        sizes={sizes}
      />

      {/* AVIF format */}
      <source
        srcSet={generateSrcSet().replace(new RegExp(`\\.${src.split('.').pop()}`, 'g'), '.avif')}
        type="image/avif"
        sizes={sizes}
      />

      {/* Fallback */}
      <img
        ref={imgRef}
        alt={alt}
        width={width}
        height={height}
        className={`${className} ${isLoaded ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}
        onLoad={handleLoad}
        onError={handleError}
        loading={priority ? 'eager' : 'lazy'}
        decoding="async"
        data-src={src}
      />

      {/* Loading placeholder */}
      {!isLoaded && !isError && (
        <div
          className="absolute inset-0 bg-gray-200 animate-pulse"
          style={{ width, height }}
        />
      )}

      {/* Error state */}
      {isError && (
        <div
          className="absolute inset-0 bg-gray-100 flex items-center justify-center text-gray-500"
          style={{ width, height }}
        >
          Failed to load image
        </div>
      )}
    </picture>
  );
};

export default OptimizedImage;
