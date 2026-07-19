import React, { useCallback } from 'react'
import clsx from 'clsx'
import { Card, CardBody, EmptyState } from './ui'

export interface WorkflowNode {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'error'
  dependencies?: string[]
}

export interface WorkflowVisualizerProps extends React.HTMLAttributes<HTMLDivElement> {
  nodes: WorkflowNode[]
  onNodeClick?: (nodeId: string) => void
}

export const WorkflowVisualizer = React.forwardRef<HTMLDivElement, WorkflowVisualizerProps>(
  ({ nodes, onNodeClick, className, ...props }, ref) => {
    const getStatusColor = useCallback((status: string) => {
      switch (status) {
        case 'completed':
          return 'bg-green-500'
        case 'running':
          return 'bg-blue-500'
        case 'error':
          return 'bg-red-500'
        default:
          return 'bg-slate-300 dark:bg-slate-600'
      }
    }, [])

    if (nodes.length === 0) {
      return (
        <Card>
          <CardBody>
            <EmptyState title="No workflow nodes" description="Add nodes to visualize your workflow" />
          </CardBody>
        </Card>
      )
    }

    return (
      <div ref={ref} className={clsx('', className)} {...props}>
        <Card>
          <CardBody>
            <div className="overflow-x-auto">
              <div className="flex gap-4 pb-4 min-w-max">
                {nodes.map((node, index) => (
                  <div key={node.id} className="flex items-center gap-4">
                    {/* Node */}
                    <button
                      onClick={() => onNodeClick?.(node.id)}
                      className={clsx(
                        'flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all',
                        'hover:shadow-lg cursor-pointer',
                        node.status === 'completed'
                          ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                          : node.status === 'running'
                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                            : node.status === 'error'
                              ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                              : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800'
                      )}
                    >
                      <div
                        className={clsx(
                          'w-3 h-3 rounded-full',
                          getStatusColor(node.status)
                        )}
                      />
                      <span className="text-sm font-medium text-center max-w-xs truncate">
                        {node.name}
                      </span>
                    </button>

                    {/* Arrow */}
                    {index < nodes.length - 1 && (
                      <div className="text-slate-400 dark:text-slate-600">→</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    )
  }
)

WorkflowVisualizer.displayName = 'WorkflowVisualizer'
