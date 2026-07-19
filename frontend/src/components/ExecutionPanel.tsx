import React from 'react'
import clsx from 'clsx'
import { Card, CardBody } from './ui'
import { Timeline } from './ui/Timeline'

export interface ExecutionStep {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'error'
  startTime?: string
  endTime?: string
  error?: string
  output?: string
}

export interface ExecutionPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  steps: ExecutionStep[]
  isRunning?: boolean
}

export const ExecutionPanel = React.forwardRef<HTMLDivElement, ExecutionPanelProps>(
  ({ steps, isRunning = false, className, ...props }, ref) => {
    const timelineItems = steps.map((step) => ({
      id: step.id,
      title: step.name,
      description: step.error || step.output,
      timestamp: step.endTime ? new Date(step.endTime).toLocaleTimeString() : undefined,
      status: step.status,
    }))

    return (
      <div ref={ref} className={clsx('space-y-4', className)} {...props}>
        <Card>
          <CardBody>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Execution Progress</h3>
              {isRunning && (
                <span className="inline-flex items-center gap-2 px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-sm font-medium">
                  <span className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                  Running
                </span>
              )}
            </div>

            <div className="mb-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-slate-600 dark:text-slate-400">Progress</span>
                <span className="font-semibold">
                  {steps.filter((s) => s.status === 'completed').length} / {steps.length}
                </span>
              </div>
              <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all"
                  style={{
                    width: `${(steps.filter((s) => s.status === 'completed').length / steps.length) * 100}%`,
                  }}
                />
              </div>
            </div>

            <Timeline items={timelineItems} />
          </CardBody>
        </Card>
      </div>
    )
  }
)

ExecutionPanel.displayName = 'ExecutionPanel'
