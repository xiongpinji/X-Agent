import { Timer } from 'lucide-react'
import type { AutomationRule } from '../types'
import { ManagementRow, SectionHeader, WorkspacePanel } from './common'
import { automationRulesHeader, buildAutomationRuleRowViewModel } from './automationRulesViewModel'

export function AutomationRulesPanel({ automationRules }: { automationRules: readonly AutomationRule[] }) {
  return (
    <WorkspacePanel>
      <SectionHeader icon={<Timer className="text-rose-300" size={22} />} title={automationRulesHeader.title} />
      <div className="space-y-3">
        {automationRules.map((rule) => (
          <AutomationRuleRow key={rule.id} rule={rule} />
        ))}
      </div>
    </WorkspacePanel>
  )
}
export function AutomationRuleRow({ rule }: { rule: AutomationRule }) {
  const row = buildAutomationRuleRowViewModel(rule)

  return (
    <ManagementRow
      tone={row.tone}
      title={row.title}
      description={row.description}
      runtime={row.runtime}
    >
      <div className="text-right text-sm">
        <div className="font-medium text-slate-100">{row.status}</div>
        <div className="mt-1 text-xs text-slate-400">{row.lastRun}</div>
      </div>
    </ManagementRow>
  )
}
