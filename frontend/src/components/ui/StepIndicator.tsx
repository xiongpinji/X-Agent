import React from 'react'
import clsx from 'clsx'

export interface StepIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  steps: Array<{
    id: string
    label: string
    status?: 'pending' | 'active' | 'completed' | 'error'
  }>
  currentStep?: string
}

export const StepIndicator = React.forwardRef<HTMLDivElement, StepIndicatorProps>(
  ({ steps, currentStep: _currentStep, className, ...props }, ref) => {
    const getStatusColor = (status?: string) => {
      switch (status) {
        case 'completed':
          return 'bg-green-600'
        case 'active':
          return 'bg-blue-600'
        case 'error':
          return 'bg-red-600'
        default:
          return 'bg-slate-300 dark:bg-slate-600'
      }
    }

    return (
      <div ref={ref} className={clsx('flex items-center gap-2', className)} {...props}>
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            {/* Step Circle */}
            <div
              className={clsx(
                'flex items-center justify-center w-8 h-8 rounded-full font-semibold text-sm transition-colors',
                getStatusColor(step.status),
                step.status === 'completed' || step.status === 'active' || step.status === 'error'
                  ? 'text-white'
                  : 'text-slate-600 dark:text-slate-300'
              )}
              role="status"
              aria-label={`Step ${index + 1}: ${step.label}`}
            >
              {step.status === 'completed' ? '✓' : index + 1}
            </div>

            {/* Connector */}
            {index < steps.length - 1 && (
              <div
                className={clsx(
                  'flex-1 h-1 transition-colors',
                  steps[index].status === 'completed' ? 'bg-green-600' : 'bg-slate-300 dark:bg-slate-600'
                )}
              />
            )}
          </React.Fragment>
        ))}
      </div>
    )
  }
)

StepIndicator.displayName = 'StepIndicator'
