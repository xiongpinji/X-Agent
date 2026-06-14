import { pandaLogoSrc } from '../data/navigation'
import type { ActivityItem } from '../types'
import { ActivitySummaryRow, PandaEmptyState, RailCard, RuntimeMetaStrip } from './common'
import {
  buildRightRailActivityRowViewModels,
  rightRailActivityCardHeader,
  rightRailActivityEmptyState,
} from './rightRailActivityCardViewModel'

export function AgentActivityCard({ activities }: { activities: readonly ActivityItem[] }) {
  const rows = buildRightRailActivityRowViewModels(activities)

  return (
    <RailCard title={rightRailActivityCardHeader.title} action={rightRailActivityCardHeader.action}>
      {rows.length ? (
        <div className="space-y-3">
          {rows.map((item) => (
            <div key={item.id}>
              <ActivitySummaryRow
                avatarSrc={pandaLogoSrc}
                title={item.title}
                subtitle={item.subtitle}
                tone={item.tone}
              />
              <div className="pl-12">
                <RuntimeMetaStrip runtime={item.runtime} updatedAt={item.updatedAt} risk={item.tone} />
              </div>
            </div>
          ))}
        </div>
      ) : <PandaEmptyState title={rightRailActivityEmptyState.title} description={rightRailActivityEmptyState.description} />}
    </RailCard>
  )
}
