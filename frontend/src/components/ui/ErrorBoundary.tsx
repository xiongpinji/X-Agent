import React, { ReactNode } from 'react'
import { Button } from './Button'
import { AriaBuilder, announceToScreenReader } from '@/utils/accessibility'

export interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: (error: Error, reset: () => void) => ReactNode
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
  level?: 'page' | 'section' | 'component'
  showDetails?: boolean
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
  errorCount: number
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private resetTimeout: NodeJS.Timeout | null = null

  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const errorCount = this.state.errorCount + 1

    this.setState(() => ({
      errorInfo,
      errorCount,
    }))

    // Log error
    console.error('Error caught by boundary:', error, errorInfo)

    // Call custom error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // Announce to screen readers
    announceToScreenReader(
      `An error occurred: ${error.message}. Please try again or contact support.`,
      'assertive'
    )

    // Auto-reset after multiple errors (prevent infinite loops)
    if (errorCount > 3) {
      console.warn('Too many errors, auto-resetting')
      this.resetTimeout = setTimeout(() => {
        this.reset()
      }, 5000)
    }
  }

  componentWillUnmount() {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout)
    }
  }

  reset = () => {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout)
      this.resetTimeout = null
    }

    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })

    announceToScreenReader('Error cleared, please try again', 'polite')
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset)
      }

      const { level = 'component', showDetails = false } = this.props
      const { error, errorInfo, errorCount } = this.state

      const ariaAttrs = new AriaBuilder()
        .role('alert')
        .live('assertive')
        .atomic(true)
        .build()

      return (
        <div
          className={`p-6 rounded-lg border-2 border-error-200 bg-error-50 dark:bg-error-950 dark:border-error-800 ${
            level === 'page' ? 'min-h-screen flex items-center justify-center' : ''
          }`}
          {...ariaAttrs}
        >
          <div className="max-w-2xl">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <svg
                  className="h-6 w-6 text-error-600 dark:text-error-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>

              <div className="flex-1">
                <h2 className="text-lg font-semibold text-error-900 dark:text-error-100 mb-2">
                  {level === 'page' ? 'Something went wrong' : 'An error occurred'}
                </h2>

                <p className="text-error-800 dark:text-error-200 mb-4">
                  {error.message || 'An unexpected error occurred. Please try again.'}
                </p>

                {showDetails && errorInfo && (
                  <details className="mb-4 text-sm">
                    <summary className="cursor-pointer font-medium text-error-700 dark:text-error-300 hover:underline">
                      Error details
                    </summary>
                    <pre className="mt-2 p-3 bg-error-100 dark:bg-error-900 rounded text-xs overflow-auto max-h-48 text-error-900 dark:text-error-100">
                      {errorInfo.componentStack}
                    </pre>
                  </details>
                )}

                {errorCount > 1 && (
                  <p className="text-sm text-error-700 dark:text-error-300 mb-4">
                    Error occurred {errorCount} times. If this persists, please contact support.
                  </p>
                )}

                <div className="flex gap-3">
                  <Button
                    variant="danger"
                    size="md"
                    onClick={this.reset}
                    ariaLabel="Try again"
                  >
                    Try again
                  </Button>

                  {level === 'page' && (
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => window.location.href = '/'}
                      ariaLabel="Go to home page"
                    >
                      Go home
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
