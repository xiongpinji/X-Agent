import React, { useState } from 'react'
import clsx from 'clsx'

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  tabs: Array<{
    id: string
    label: string
    content: React.ReactNode
  }>
  defaultTab?: string
}

export const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ tabs, defaultTab, className, ...props }, ref) => {
    const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id)

    return (
      <div ref={ref} className={clsx('w-full', className)} {...props}>
        {/* Tab List */}
        <div
          className="flex border-b border-slate-200 dark:border-slate-700"
          role="tablist"
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'px-4 py-2 font-medium text-sm transition-colors border-b-2 -mb-px',
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300'
              )}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`panel-${tab.id}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {tabs.map((tab) => (
          <div
            key={tab.id}
            id={`panel-${tab.id}`}
            className={clsx('pt-4', activeTab !== tab.id && 'hidden')}
            role="tabpanel"
            aria-labelledby={tab.id}
          >
            {tab.content}
          </div>
        ))}
      </div>
    )
  }
)

Tabs.displayName = 'Tabs'
