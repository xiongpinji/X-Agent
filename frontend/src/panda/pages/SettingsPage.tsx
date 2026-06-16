import { StandardModulePageShell } from '../components/common'
import { SettingsSectionGrid } from '../components/settingsCenter'
import { useSettingsPageResources } from '../state/useModulePageResources'

export function SettingsPage() {
  const resources = useSettingsPageResources()

  return (
    <StandardModulePageShell page="settings" count={resources.count}>
      <SettingsSectionGrid settingsSections={resources.settingsSections} />
    </StandardModulePageShell>
  )
}
