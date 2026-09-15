/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Enhanced Color Palette
      colors: {
        // ── Accent: "signal" teal-cyan ─────────────────────────────────────
        // Single source of truth for the brand accent. To re-skin the app,
        // change these 11 values only. Chosen over the default blue/violet
        // because: (a) success=green / warning=amber / error=red are already
        // taken, so a warm accent would collide; (b) it stays clear of the
        // generic "AI purple/blue" look the design skill bans.
        primary: {
          50: '#eefcfd',
          100: '#cff7fa',
          200: '#a5eef3',
          300: '#66dee8',
          400: '#29c3d3',
          500: '#199aab',
          600: '#147d90',
          700: '#156476',
          800: '#175362',
          900: '#174553',
          950: '#092c38',
        },
        // Legacy alias: the app historically used `blue-*` as its accent
        // (205 `bg-blue-*` + 78 `text-blue-*` usages). Remapping the scale here
        // re-skins those pages without a ~600-site refactor. Revert = delete
        // this key to fall back to Tailwind's stock blue.
        blue: {
          50: '#eefcfd',
          100: '#cff7fa',
          200: '#a5eef3',
          300: '#66dee8',
          400: '#29c3d3',
          500: '#199aab',
          600: '#147d90',
          700: '#156476',
          800: '#175362',
          900: '#174553',
          950: '#092c38',
        },
        // Secondary Colors
        secondary: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
        // Success Colors
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#145231',
          950: '#052e16',
        },
        // Warning Colors
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          950: '#451a03',
        },
        // Error Colors
        error: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
          950: '#450a0a',
        },
        // Neutral Colors
        slate: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
      },
      // Enhanced Typography
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        mono: [
          '"Fira Code"',
          '"Courier New"',
          'monospace',
        ],
        display: [
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      fontSize: {
        // Heading Sizes
        'h1': ['2.5rem', { lineHeight: '1.2', fontWeight: '700' }],
        'h2': ['2rem', { lineHeight: '1.3', fontWeight: '700' }],
        'h3': ['1.5rem', { lineHeight: '1.4', fontWeight: '600' }],
        'h4': ['1.25rem', { lineHeight: '1.4', fontWeight: '600' }],
        'h5': ['1.125rem', { lineHeight: '1.5', fontWeight: '600' }],
        'h6': ['1rem', { lineHeight: '1.5', fontWeight: '600' }],
        // Body Sizes
        'body-lg': ['1.125rem', { lineHeight: '1.75' }],
        'body-md': ['1rem', { lineHeight: '1.5' }],
        'body-sm': ['0.875rem', { lineHeight: '1.5' }],
        'body-xs': ['0.75rem', { lineHeight: '1.5' }],
      },
      // Enhanced Spacing
      spacing: {
        'xs': '0.25rem',
        'sm': '0.5rem',
        'md': '1rem',
        'lg': '1.5rem',
        'xl': '2rem',
        '2xl': '3rem',
        '3xl': '4rem',
      },
      // Enhanced Animations
      animation: {
        'spin': 'spin 1s linear infinite',
        'pulse': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce': 'bounce 1s infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-in-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
      },
      // Enhanced Shadows — elevation ramp for "bold" depth without neon glows.
      // Layered (ambient + key) shadows read as premium; single big blurs do not.
      boxShadow: {
        'xs': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
        'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
        'inner': 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
        'focus': '0 0 0 3px rgba(25, 154, 171, 0.28)',
        // Elevation ramp (light theme)
        'e1': '0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)',
        'e2': '0 2px 4px rgba(16, 24, 40, 0.04), 0 6px 16px -4px rgba(16, 24, 40, 0.10)',
        'e3': '0 4px 8px rgba(16, 24, 40, 0.05), 0 18px 36px -8px rgba(16, 24, 40, 0.16)',
        // Dark theme: shadows need more opacity to register on dark surfaces
        'e1-dark': '0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.5)',
        'e2-dark': '0 2px 4px rgba(0, 0, 0, 0.4), 0 8px 20px -6px rgba(0, 0, 0, 0.6)',
        'e3-dark': '0 4px 10px rgba(0, 0, 0, 0.45), 0 24px 48px -12px rgba(0, 0, 0, 0.7)',
      },
      // Border Radius
      borderRadius: {
        'xs': '0.25rem',
        'sm': '0.375rem',
        'md': '0.5rem',
        'lg': '0.75rem',
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      // Transitions
      transitionDuration: {
        '75': '75ms',
        '100': '100ms',
        '150': '150ms',
        '200': '200ms',
        '300': '300ms',
        '500': '500ms',
        '700': '700ms',
        '1000': '1000ms',
      },
      // Easings — `spring`/`smooth` approximate motion-library feel in pure CSS.
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'in-smooth': 'cubic-bezier(0.7, 0, 0.84, 0)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      // Z-index Scale
      zIndex: {
        'hide': '-1',
        'auto': 'auto',
        '0': '0',
        '10': '10',
        '20': '20',
        '30': '30',
        '40': '40',
        '50': '50',
        'dropdown': '1000',
        'sticky': '1020',
        'fixed': '1030',
        'modal-backdrop': '1040',
        'modal': '1050',
        'popover': '1060',
        'tooltip': '1070',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}
