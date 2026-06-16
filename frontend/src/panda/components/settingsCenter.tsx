import { Settings } from 'lucide-react'
import type { SettingsSection } from '../types'
import { ResourceCardGrid, ResourceInfoCard } from './common'
import { buildSettingsSectionCardViewModel } from './settingsCenterViewModel'

export function SettingsSectionGrid({ settingsSections }: { settingsSections: readonly SettingsSection[] }) {
  return (
    <ResourceCardGrid
      items={settingsSections}
      className="panda-list-grid"
      renderItem={(section) => <SettingsSectionCard key={section.id} section={section} />}
    />
  )
}

export function SettingsSectionCard({ section }: { section: SettingsSection }) {
  const card = buildSettingsSectionCardViewModel(section)

  return (
    <ResourceInfoCard
      icon={<Settings className="text-rose-300" size={19} />}
      title={card.title}
      tone={section.tone}
      description={card.description}
      items={card.items}
    />
  )
}
