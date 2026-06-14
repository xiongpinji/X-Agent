import type { SettingsSection } from '../types'
import type { KeyValueItem } from './common'

export type SettingsSectionCardViewModel = {
  readonly title: string
  readonly description: string
  readonly items: readonly KeyValueItem[]
}

export const xAgentCorePolicyLabel = 'X-Agent Core'

export function buildSettingsSectionCardViewModel(section: SettingsSection): SettingsSectionCardViewModel {
  return {
    title: section.title,
    description: section.description,
    items: [
      { label: '状态', value: section.status },
      { label: '策略', value: xAgentCorePolicyLabel },
    ],
  }
}
