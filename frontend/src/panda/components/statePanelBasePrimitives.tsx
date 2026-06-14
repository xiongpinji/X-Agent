import React from 'react'

export function PandaStatePanel({
  icon,
  title,
  description,
  action,
  warning = false,
}: {
  icon: React.ReactNode
  title: string
  description: string
  action?: React.ReactNode
  warning?: boolean
}) {
  return (
    <div className={warning ? 'panda-state-panel panda-state-warning' : 'panda-state-panel'}>
      {icon}
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
    </div>
  )
}
