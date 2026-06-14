import type { AutomationRule, RuntimeMetadata, StatusTone } from '../types'

export type AutomationRulesHeaderViewModel = {
  readonly title: string
}

export type AutomationRuleRowViewModel = {
  readonly title: string
  readonly tone: StatusTone
  readonly description: string
  readonly runtime?: RuntimeMetadata
  readonly status: string
  readonly lastRun: string
}

export const automationRulesHeader: AutomationRulesHeaderViewModel = {
  title: '自动化规则',
}

export function buildAutomationRuleRowViewModel(rule: AutomationRule): AutomationRuleRowViewModel {
  return {
    title: rule.name,
    tone: rule.tone,
    description: [rule.trigger, rule.destination].filter(Boolean).join(' · '),
    runtime: rule.runtime,
    status: rule.status,
    lastRun: rule.lastRun,
  }
}
