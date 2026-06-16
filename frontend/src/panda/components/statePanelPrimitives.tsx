import React from 'react'
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import { PandaStatePanel } from './statePanelBasePrimitives'

export { PandaStatePanel } from './statePanelBasePrimitives'

export function PandaLoadingState({
  title = '正在加载工作台',
  description = '正在读取 Panda Agent 工作区状态。',
}: {
  title?: string
  description?: string
}) {
  return (
    <PandaStatePanel
      icon={<Loader2 className="panda-state-icon is-spinning" size={22} />}
      title={title}
      description={description}
    />
  )
}

export function PandaEmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <PandaStatePanel
      icon={<Inbox className="panda-state-icon" size={22} />}
      title={title}
      description={description}
      action={action}
    />
  )
}

export function PandaErrorState({
  title = '数据已降级',
  description,
  action,
}: {
  title?: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <PandaStatePanel
      icon={<AlertTriangle className="panda-state-icon" size={22} />}
      title={title}
      description={description}
      action={action}
      warning
    />
  )
}
