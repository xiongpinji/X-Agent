/**
 * Mobile-First Responsive Design System
 */

import React, { useEffect, useState } from 'react';

// Breakpoints
export const BREAKPOINTS = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const;

// Touch-friendly sizes
export const TOUCH_SIZES = {
  minTapTarget: 44, // iOS minimum
  minTouchTarget: 48, // Android minimum
  spacing: 8,
  padding: {
    xs: 8,
    sm: 12,
    md: 16,
    lg: 24,
    xl: 32,
  },
} as const;

// Responsive utilities
export const useMediaQuery = (query: string): boolean => {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    if (media.matches !== matches) {
      setMatches(media.matches);
    }

    const listener = () => setMatches(media.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [matches, query]);

  return matches;
};

export const useIsMobile = (): boolean => {
  return useMediaQuery(`(max-width: ${BREAKPOINTS.md - 1}px)`);
};

export const useIsTablet = (): boolean => {
  return useMediaQuery(
    `(min-width: ${BREAKPOINTS.md}px) and (max-width: ${BREAKPOINTS.lg - 1}px)`
  );
};

export const useIsDesktop = (): boolean => {
  return useMediaQuery(`(min-width: ${BREAKPOINTS.lg}px)`);
};

export const useOrientation = (): 'portrait' | 'landscape' => {
  const [orientation, setOrientation] = useState<'portrait' | 'landscape'>('portrait');

  useEffect(() => {
    const handleOrientationChange = () => {
      setOrientation(
        window.innerHeight > window.innerWidth ? 'portrait' : 'landscape'
      );
    };

    handleOrientationChange();
    window.addEventListener('orientationchange', handleOrientationChange);
    window.addEventListener('resize', handleOrientationChange);

    return () => {
      window.removeEventListener('orientationchange', handleOrientationChange);
      window.removeEventListener('resize', handleOrientationChange);
    };
  }, []);

  return orientation;
};

// Viewport utilities
export const useViewport = () => {
  const [viewport, setViewport] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
    isMobile: false,
    isTablet: false,
    isDesktop: false,
  });

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;

      setViewport({
        width,
        height,
        isMobile: width < BREAKPOINTS.md,
        isTablet: width >= BREAKPOINTS.md && width < BREAKPOINTS.lg,
        isDesktop: width >= BREAKPOINTS.lg,
      });
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return viewport;
};

// Safe area insets for notch/dynamic island
export const useSafeAreaInsets = () => {
  const [insets, setInsets] = useState({
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
  });

  useEffect(() => {
    const updateInsets = () => {
      const root = document.documentElement;
      setInsets({
        top: parseInt(getComputedStyle(root).getPropertyValue('--safe-area-inset-top') || '0'),
        right: parseInt(getComputedStyle(root).getPropertyValue('--safe-area-inset-right') || '0'),
        bottom: parseInt(getComputedStyle(root).getPropertyValue('--safe-area-inset-bottom') || '0'),
        left: parseInt(getComputedStyle(root).getPropertyValue('--safe-area-inset-left') || '0'),
      });
    };

    updateInsets();
    window.addEventListener('resize', updateInsets);
    return () => window.removeEventListener('resize', updateInsets);
  }, []);

  return insets;
};

// Touch gesture detection
export const useTouchGestures = (ref: React.RefObject<HTMLElement>) => {
  const [gesture, setGesture] = useState<{
    type: 'swipe' | 'pinch' | 'long-press' | null;
    direction?: 'left' | 'right' | 'up' | 'down';
    scale?: number;
  }>({ type: null });

  useEffect(() => {
    if (!ref.current) return;

    let touchStartX = 0;
    let touchStartY = 0;
    let touchStartTime = 0;
    let touchStartDistance = 0;

    const handleTouchStart = (e: TouchEvent) => {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = Date.now();

      if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        touchStartDistance = Math.sqrt(dx * dx + dy * dy);
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const scale = distance / touchStartDistance;

        if (Math.abs(scale - 1) > 0.1) {
          setGesture({ type: 'pinch', scale });
        }
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      const touchEndX = e.changedTouches[0].clientX;
      const touchEndY = e.changedTouches[0].clientY;
      const touchEndTime = Date.now();

      const deltaX = touchEndX - touchStartX;
      const deltaY = touchEndY - touchStartY;
      const deltaTime = touchEndTime - touchStartTime;

      // Detect swipe
      if (Math.abs(deltaX) > 50 && deltaTime < 300) {
        setGesture({
          type: 'swipe',
          direction: deltaX > 0 ? 'right' : 'left',
        });
      } else if (Math.abs(deltaY) > 50 && deltaTime < 300) {
        setGesture({
          type: 'swipe',
          direction: deltaY > 0 ? 'down' : 'up',
        });
      }

      // Detect long press
      if (deltaX < 10 && deltaY < 10 && deltaTime > 500) {
        setGesture({ type: 'long-press' });
      }
    };

    const element = ref.current;
    element.addEventListener('touchstart', handleTouchStart);
    element.addEventListener('touchmove', handleTouchMove);
    element.addEventListener('touchend', handleTouchEnd);

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
    };
  }, [ref]);

  return gesture;
};

// Haptic feedback
export const useHapticFeedback = () => {
  const light = () => {
    if ('vibrate' in navigator) {
      navigator.vibrate(10);
    }
  };

  const medium = () => {
    if ('vibrate' in navigator) {
      navigator.vibrate(20);
    }
  };

  const heavy = () => {
    if ('vibrate' in navigator) {
      navigator.vibrate(30);
    }
  };

  const pattern = (pattern: number[]) => {
    if ('vibrate' in navigator) {
      navigator.vibrate(pattern);
    }
  };

  return { light, medium, heavy, pattern };
};

// Screen lock
export const useScreenLock = () => {
  const [isLocked, setIsLocked] = useState(false);

  const lock = async () => {
    try {
      if ('wakeLock' in navigator) {
        await (navigator as any).wakeLock.request('screen');
        setIsLocked(true);
      }
    } catch (error) {
      console.warn('Screen lock failed:', error);
    }
  };

  const unlock = () => {
    setIsLocked(false);
  };

  return { isLocked, lock, unlock };
};

// Fullscreen API
export const useFullscreen = (ref: React.RefObject<HTMLElement>) => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const enter = async () => {
    try {
      if (ref.current?.requestFullscreen) {
        await ref.current.requestFullscreen();
        setIsFullscreen(true);
      }
    } catch (error) {
      console.warn('Fullscreen request failed:', error);
    }
  };

  const exit = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (error) {
      console.warn('Fullscreen exit failed:', error);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  return { isFullscreen, enter, exit };
};

// Responsive image loading
export const useResponsiveImage = (src: string) => {
  const [imageSrc, setImageSrc] = useState(src);
  const viewport = useViewport();

  useEffect(() => {
    // Adjust image based on viewport
    if (viewport.isMobile) {
      setImageSrc(src.replace(/\.(jpg|png)$/, '-sm.$1'));
    } else if (viewport.isTablet) {
      setImageSrc(src.replace(/\.(jpg|png)$/, '-md.$1'));
    } else {
      setImageSrc(src);
    }
  }, [src, viewport]);

  return imageSrc;
};

// Lazy loading intersection observer
export const useLazyLoad = (ref: React.RefObject<HTMLElement>) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (!ref.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);

  return isVisible;
};

export default {
  BREAKPOINTS,
  TOUCH_SIZES,
  useMediaQuery,
  useIsMobile,
  useIsTablet,
  useIsDesktop,
  useOrientation,
  useViewport,
  useSafeAreaInsets,
  useTouchGestures,
  useHapticFeedback,
  useScreenLock,
  useFullscreen,
  useResponsiveImage,
  useLazyLoad,
};
