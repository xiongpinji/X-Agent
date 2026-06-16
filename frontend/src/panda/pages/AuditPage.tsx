import { StandardModulePageShell } from '../components/common'
import { AuditReplayWorkspace } from '../components/auditReplay'
import { useAuditPageResources } from '../state/useModulePageResources'

export function AuditPage() {
  const resources = useAuditPageResources()

  return (
    <StandardModulePageShell page="audit" count={resources.count}>
      <AuditReplayWorkspace auditEvents={resources.auditEvents} />
    </StandardModulePageShell>
  )
}
