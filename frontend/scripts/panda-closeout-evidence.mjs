import { buildRouteApiResourcesEvidence } from './panda-script-utils.mjs'

export const PANDA_CLOSEOUT_EVIDENCE_SOURCE = 'frontend/scripts/panda-closeout-evidence.mjs'

export function buildPandaBackendAlignmentHandoff({ manifest, routeRollover }) {
  return {
    frontendOwnedCommands: manifest.frontendHandoffGates.frontendOwnedCommands,
    backendOwnedCommands: manifest.frontendHandoffGates.backendOwnedCommands,
    handoffRule: manifest.frontendHandoffGates.handoffRule,
    resourcesBffFlag: manifest.bff.resourcesFlag,
    resourcesBffEndpoint: manifest.bff.resourcesEndpoint,
    pendingRouteCount: routeRollover.pendingRoutes.length,
    pendingRouteIds: routeRollover.pendingRoutes.map((route) => route.route),
  }
}

export function buildPandaCloseoutEvidence({ manifest, routeRollover, resourceKeyBoundary }) {
  const frontendTasks = manifest.nextFrontendTasks.filter((task) => task.owner === 'frontend')
  const backendPendingTasks = manifest.nextFrontendTasks.filter((task) => task.status === 'pending-backend')
  const routeApiResourcesEvidence = resourceKeyBoundary
    ? buildRouteApiResourcesEvidence({ routeRollover, resourceKeyBoundary })
    : {
        status: 'missing',
        routePlan: routeRollover.sourceScript,
        keyMap: 'src/panda/api/resourceKeys.ts',
        routeApiResources: [],
        boundaryApiResources: [],
        unknownRouteApiResources: [],
        missingRouteApiResources: [],
        diff: {
          unknownRouteApiResources: [],
          missingRouteApiResources: [],
        },
        expectedAlignment:
          'Every routes[].apiResources entry in the alignment report must be resolved from src/panda/api/resourceKeys.ts, stay inside the backend API resource boundary, and expose unknown/missing key diffs for backend handoff.',
      }
  const frontendEvidence = [
    {
      id: 'delivery-readiness',
      status: Object.values(manifest.deliveryReadiness).every((value) => value === 'ready' || value === 'pending-backend' || String(value).startsWith('http'))
        ? 'passed'
        : 'review',
      detail: 'Shell, page contracts, mock fallback, API adapters, and visible contract strips are recorded in deliveryReadiness.',
    },
    {
      id: 'visual-review',
      status: manifest.visualReviewEvidence?.status ?? 'missing',
      detail: manifest.visualReviewEvidence?.interaction ?? 'Visual review evidence is missing.',
    },
    {
      id: 'accessibility-pass',
      status: manifest.accessibilityEvidence?.status ?? 'missing',
      detail: manifest.accessibilityEvidence?.staticProof ?? 'Accessibility evidence is missing.',
    },
    {
      id: 'scripted-qa-smoke',
      status: manifest.scriptedQaEvidence?.status ?? 'missing',
      detail: manifest.scriptedQaEvidence?.fallback ?? 'Scripted QA evidence is missing.',
    },
    {
      id: 'resources-bff-validation',
      status: manifest.resourceBoundary?.validation && manifest.resourceBoundary?.invalidApiFallback === 'mock-with-error' ? 'passed' : 'missing',
      detail: manifest.resourceBoundary?.validation
        ? `${manifest.resourceBoundary.validation} validates resources BFF snapshots and falls back with ${manifest.resourceBoundary.invalidApiFallback}.`
        : 'Resources BFF validation boundary is missing.',
    },
    {
      id: 'resources-validation-executable',
      status: manifest.resourceBoundary?.validationProbe ? 'passed' : 'missing',
      detail: manifest.resourceBoundary?.validationProbe
        ? `${manifest.resourceBoundary.validationProbe} runs positive and negative resources BFF validation checks.`
        : 'Executable resources validation probe is missing.',
    },
    {
      id: 'resources-contract-consistency',
      status: manifest.resourceBoundary?.contractProbe ? 'passed' : 'missing',
      detail: manifest.resourceBoundary?.contractProbe
        ? `${manifest.resourceBoundary.contractProbe} verifies resource keys, mock-ready contract fields, closeout pending route handoff fields, standard module page content keys/page fields, and page -> hook -> PageResources type bindings across the manifest, shared resource key pairs, validation, adapters, fallback snapshots, page contracts, and module page structure.`
        : 'Executable resources contract consistency probe is missing.',
    },
    {
      id: 'route-api-resources-evidence',
      status: routeApiResourcesEvidence.status,
      detail:
        routeApiResourcesEvidence.status === 'passed'
          ? `${routeApiResourcesEvidence.routePlan} maps route apiResources through ${routeApiResourcesEvidence.keyMap}; unknownRouteApiResources and missingRouteApiResources are empty.`
          : `${routeApiResourcesEvidence.routePlan} has route apiResources drift; unknownRouteApiResources=${routeApiResourcesEvidence.unknownRouteApiResources.join(', ') || '(none)'}; missingRouteApiResources=${routeApiResourcesEvidence.missingRouteApiResources.join(', ') || '(none)'}.`,
    },
    {
      id: 'resources-dry-run-fixture',
      status: manifest.resourceBoundary?.dryRunProbe ? 'passed' : 'missing',
      detail: manifest.resourceBoundary?.dryRunProbe
        ? `${manifest.resourceBoundary.dryRunProbe} reuses the shared API fixture layer to validate representative aggregate cross-resource runtime metadata, shared pandaCoreRuntimeFields core runtime API field coverage, runtime shape stability, home activity runtime metadata, default import safety, default-disabled BFF config, explicit opt-in config, bootstrap loader behavior, and loadPandaResources mock/api/error fallback behavior without enabling the real BFF flag by default.`
        : 'Executable resources dry-run fixture probe is missing.',
    },
    {
      id: 'adapter-behavior-executable',
      status: manifest.resourceBoundary?.adapterProbe ? 'passed' : 'missing',
      detail: manifest.resourceBoundary?.adapterProbe
        ? `${manifest.resourceBoundary.adapterProbe} verifies tone fallback, progress clamping, runtime metadata mapping, evidence refs and agent permissions copy semantics, agent role preset mapping, and aggregate resource snapshot mapping.`
        : 'Executable adapter behavior probe is missing.',
    },
    {
      id: 'agent-role-card-contract',
      status:
        manifest.resourceBoundary?.agentRoleApiContract === 'ApiAgentRolePreset' &&
        manifest.resourceBoundary?.agentRoleTypes &&
        manifest.resourceBoundary?.agentRolePresets &&
        manifest.resourceBoundary?.agentRolePortraits &&
        manifest.resourceBoundary?.agentRoleAdapters
          ? 'passed'
          : 'missing',
      detail:
        manifest.resourceBoundary?.agentRoleApiContract === 'ApiAgentRolePreset'
          ? `${manifest.resourceBoundary.agentRoleApiContract} maps through ${manifest.resourceBoundary.agentRoleAdapters} into AgentRolePreset with portrait_key resolved by ${manifest.resourceBoundary.agentRolePortraits}.`
          : 'Agent role card API/view/portrait/adapter boundary is missing.',
    },
  ]

  return {
    sourceScript: PANDA_CLOSEOUT_EVIDENCE_SOURCE,
    frontendTasks,
    backendPendingTasks,
    backendAlignmentHandoff: buildPandaBackendAlignmentHandoff({ manifest, routeRollover }),
    routeApiResourcesEvidence,
    frontendBoundary: {
      shell: manifest.deliveryReadiness.frontendShell,
      pageContracts: manifest.deliveryReadiness.pageContracts,
      mockFallback: manifest.deliveryReadiness.mockFallback,
      apiAdapters: manifest.deliveryReadiness.apiAdapters,
      visibleContractStrip: manifest.deliveryReadiness.visibleContractStrip,
      strictBackendGate: manifest.deliveryReadiness.strictBackendGate,
    },
    frontendCompletion: {
      status: frontendEvidence.every((item) => item.status === 'passed') ? 'passed' : 'review',
      owner: 'frontend',
      evidence: frontendEvidence,
      passedTasks: frontendTasks.filter((task) => task.status === 'passed').map((task) => task.id),
      safeScope: manifest.frontendCloseout.safeScope,
    },
    backendAlignmentBlockers: {
      status: backendPendingTasks.length === 0 && routeRollover.pendingRoutes.length === 0 ? 'passed' : 'pending-backend',
      owner: 'frontend-backend',
      pendingTasks: backendPendingTasks.map((task) => ({
        id: task.id,
        description: task.description,
      })),
      pendingRoutes: routeRollover.pendingRoutes.map((route) => ({
        route: route.route,
        endpoint: route.endpoint,
        resources: route.viewResources.join(', '),
        apiResources: route.apiResources.join(', '),
        runtimeFields: route.runtimeFields.join(', '),
        apiNeeds: route.apiNeeds.join('; '),
      })),
      pendingItems: manifest.backendAlignmentPending,
    },
  }
}
