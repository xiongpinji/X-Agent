import { StandardModulePageShell } from '../components/common'
import { AutomationRulesPanel } from '../components/automationRules'
import { useAutomationPageResources } from '../state/useModulePageResources'

export function AutomationPage() {
  const resources = useAutomationPageResources()

  return (
    <StandardModulePageShell page="automation" count={resources.count}>
      <AutomationRulesPanel automationRules={resources.automationRules} />
    </StandardModulePageShell>
  )
}
