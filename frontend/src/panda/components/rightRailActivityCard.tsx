import { pandaLogoSrc } from '../data/navigation'
import type { ActivityItem } from '../types'
import { ActivitySummaryRow, PandaEmptyState, RailCard, RuntimeMetaStrip } from './common'

export function AgentActivityCard({ activities }: { activities: readonly ActivityItem[] }) {
  return (
    <RailCard title="智能体活动" action="查看全部">
      {activities.length ? (
        <div className="space-y-3">
          {activities.map((item) => (
            <div key={item.id}>
              <ActivitySummaryRow
                avatarSrc={pandaLogoSrc}
                title={item.title}
                subtitle={item.subtitle}
                tone={item.tone}
              />
              <div className="pl-12">
                <RuntimeMetaStrip runtime={item.runtime} updatedAt={item.time} risk={item.tone} />
              </div>
            </div>
          ))}
        </div>
      ) : <PandaEmptyState title="暂无智能体活动" description="启动任务后会在这里显示智能体运行、等待审批和失败事件。" />}
    </RailCard>
  )
}
