import { Settings } from 'lucide-react'
import type { SettingsSection } from '../types'
import { ResourceCardGrid, ResourceInfoCard } from './common'

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
  return (
    <ResourceInfoCard
      icon={<Settings className="text-rose-300" size={19} />}
      title={section.title}
      tone={section.tone}
      description={section.description}
      items={[
        { label: '状态', value: section.status },
        { label: '策略', value: 'X-Agent Core' },
      ]}
    />
  )
}
