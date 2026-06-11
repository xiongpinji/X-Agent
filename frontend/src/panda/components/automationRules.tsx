import { Timer } from 'lucide-react'
import type { AutomationRule } from '../types'
import { ManagementRow, SectionHeader, WorkspacePanel } from './common'

export function AutomationRulesPanel({ automationRules }: { automationRules: readonly AutomationRule[] }) {
  return (
    <WorkspacePanel>
      <SectionHeader icon={<Timer className="text-rose-300" size={22} />} title="自动化规则" />
      <div className="space-y-3">
        {automationRules.map((rule) => (
          <AutomationRuleRow key={rule.id} rule={rule} />
        ))}
      </div>
    </WorkspacePanel>
  )
}

export function AutomationRuleRow({ rule }: { rule: AutomationRule }) {
  return (
    <ManagementRow
      tone={rule.tone}
      title={rule.name}
      description={`${rule.trigger} · ${rule.destination}`}
      runtime={rule.runtime}
    >
      <div className="text-right text-sm">
        <div className="font-medium text-slate-100">{rule.status}</div>
        <div className="mt-1 text-xs text-slate-400">{rule.lastRun}</div>
      </div>
    </ManagementRow>
  )
}
