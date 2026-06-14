export const pandaWorkbenchRequiredFiles = [
  'src/panda/PandaAgentApp.tsx',
  'src/panda/PandaAgentApp.css',
  'src/panda/types.ts',
  'src/panda/types/routeTypes.ts',
  'src/panda/types/runtimeTypes.ts',
  'src/panda/types/agentRoleTypes.ts',
  'src/panda/types/resourceTypes.ts',
  'src/panda/types/executionResourceTypes.ts',
  'src/panda/types/organizationResourceTypes.ts',
  'src/panda/types/knowledgeResourceTypes.ts',
  'src/panda/types/governanceResourceTypes.ts',
  'src/panda/types/workbenchTypes.ts',
  'src/panda/data/navigation.ts',
  'src/panda/data/homeActionContent.ts',
  'src/panda/data/moduleFallbackContent.ts',
  'src/panda/data/threadExecutionContent.ts',
  'src/panda/data/modulePageTypes.ts',
  'src/panda/data/modulePageActions.tsx',
  'src/panda/data/modulePageContentCatalog.tsx',
  'src/panda/data/modulePageContent.tsx',
  'src/panda/data/homeContent.ts',
  'src/panda/data/agentRolePortraits.ts',
  'src/panda/data/agentRolePresetFixtures.ts',
  'src/panda/data/agentRolePresets.ts',
  'src/panda/assets/roles/ceo.png',
  'src/panda/assets/roles/designer.png',
  'src/panda/assets/roles/engineer.png',
  'src/panda/assets/roles/finance.png',
  'src/panda/assets/roles/director.png',
  'src/panda/assets/roles/screenwriter.png',
  'src/panda/assets/roles/procurement.png',
  'src/panda/assets/roles/legal.png',
  'src/panda/assets/roles/media-operator.png',
  'src/panda/assets/roles/support.png',
  'src/panda/assets/roles/direct-reference-ceo.png',
  'src/panda/assets/roles/direct-reference-designer.png',
  'src/panda/assets/roles/direct-reference-engineer.png',
  'src/panda/assets/roles/direct-reference-finance.png',
  'src/panda/assets/roles/direct-reference-director.png',
  'src/panda/assets/roles/direct-reference-screenwriter.png',
  'src/panda/assets/roles/direct-reference-procurement.png',
  'src/panda/assets/roles/direct-reference-legal.png',
  'src/panda/assets/roles/direct-reference-media-operator.png',
  'src/panda/assets/roles/direct-reference-support.png',
  'src/panda/data/mockHome.ts',
  'src/panda/data/mockExecutionResources.ts',
  'src/panda/data/mockKnowledgeResources.ts',
  'src/panda/data/mockOrganizationResources.ts',
  'src/panda/data/mockResources.ts',
  'src/panda/data/mockWorkspace.ts',
  'src/panda/api/apiContracts.ts',
  'src/panda/api/agentRoleAdapters.ts',
  'src/panda/api/homeApiContracts.ts',
  'src/panda/api/executionApiContracts.ts',
  'src/panda/api/organizationApiContracts.ts',
  'src/panda/api/knowledgeApiContracts.ts',
  'src/panda/api/governanceApiContracts.ts',
  'src/panda/api/resourceApiContracts.ts',
  'src/panda/api/snapshotApiContracts.ts',
  'src/panda/api/adapters.ts',
  'src/panda/api/homeAdapters.ts',
  'src/panda/api/executionResourceAdapters.ts',
  'src/panda/api/organizationResourceAdapters.ts',
  'src/panda/api/knowledgeResourceAdapters.ts',
  'src/panda/api/governanceResourceAdapters.ts',
  'src/panda/api/resourceItemAdapters.ts',
  'src/panda/api/resourceSnapshotAdapter.ts',
  'src/panda/api/adapterFixtures.ts',
  'src/panda/api/adapterOutputFixtures.ts',
  'src/panda/api/resourceSnapshotFixtures.ts',
  'src/panda/api/resourceRuntimeFixtures.ts',
  'src/panda/api/resourceAdapterFixtures.ts',
  'src/panda/api/resourceDryRunFixtures.ts',
  'src/panda/api/homeActivityFixtures.ts',
  'src/panda/api/resourceClientFixtures.ts',
  'src/panda/api/bootstrapResources.ts',
  'src/panda/api/resourcesBffConfig.ts',
  'src/panda/api/resourcesHttpClient.ts',
  'src/panda/api/resourceSnapshotTypes.ts',
  'src/panda/api/resourceFallbackSnapshot.ts',
  'src/panda/api/resourcesApiLoader.ts',
  'src/panda/api/resourcesClient.ts',
  'src/panda/api/resourcesLoadResult.ts',
  'src/panda/api/workbenchHomeLoadResult.ts',
  'src/panda/api/resourceKeys.ts',
  'src/panda/api/runtimeMapping.ts',
  'src/panda/api/resourcesValidation.ts',
  'src/panda/api/resourceReadiness.ts',
  'src/panda/api/workbenchClient.ts',
  'src/panda/pageRegistry.tsx',
  'src/panda/pandaFrontendManifest.json',
  'src/panda/resourceContractTypes.ts',
  'src/panda/resourceRuntimeFields.ts',
  'src/panda/pageResourceContractCatalog.ts',
  'src/panda/pageResourceContracts.ts',
  'src/panda/resourceContracts.ts',
  'src/panda/state/PandaWorkspaceContext.tsx',
  'src/panda/state/workspaceTypes.ts',
  'src/panda/state/workspaceProvider.tsx',
  'src/panda/state/workspaceLifecycleViewModel.ts',
  'src/panda/state/workspaceHooks.ts',
  'src/panda/state/usePandaHashRoute.ts',
  'src/panda/state/usePandaHomeWorkbench.ts',
  'src/panda/state/homeWorkbenchViewModel.ts',
  'src/panda/state/modulePageResourceTypes.ts',
  'src/panda/state/useCountedModulePageResource.ts',
  'src/panda/state/modulePageResourceHooks.ts',
  'src/panda/state/useModulePageResources.ts',
  'src/panda/components/Shell.tsx',
  'src/panda/components/shellChrome.tsx',
  'src/panda/components/shellBranding.tsx',
  'src/panda/components/shellControls.tsx',
  'src/panda/components/shellActionControls.tsx',
  'src/panda/components/shellTopbar.tsx',
  'src/panda/components/shellConnectionViewModel.ts',
  'src/panda/components/pageChromePrimitives.tsx',
  'src/panda/components/pageContractViewModel.ts',
  'src/panda/components/pageContractPrimitives.tsx',
  'src/panda/components/homeTaskComposer.tsx',
  'src/panda/components/homeActionSections.tsx',
  'src/panda/components/homeNavigationSections.tsx',
  'src/panda/components/homeProjectSectionsViewModel.ts',
  'src/panda/components/homeProjectSections.tsx',
  'src/panda/components/homeStatusSectionsViewModel.ts',
  'src/panda/components/homeStatusSections.tsx',
  'src/panda/components/homeSections.tsx',
  'src/panda/components/resourceStateViewModel.ts',
  'src/panda/components/resourceState.tsx',
  'src/panda/components/statePanelBasePrimitives.tsx',
  'src/panda/components/statePanelPrimitives.tsx',
  'src/panda/components/moduleFallbackSurface.tsx',
  'src/panda/components/moduleDeliverySurfaceViewModel.ts',
  'src/panda/components/moduleDeliverySurface.tsx',
  'src/panda/components/modulePageActionPrimitives.tsx',
  'src/panda/components/modulePagePrimitives.tsx',
  'src/panda/components/progressPrimitives.tsx',
  'src/panda/components/runtimePrimitives.tsx',
  'src/panda/components/metricPrimitives.tsx',
  'src/panda/components/runtimeMetaViewModel.ts',
  'src/panda/components/runtimeMetaPrimitives.tsx',
  'src/panda/components/tagListPrimitives.tsx',
  'src/panda/components/statusDotViewModel.ts',
  'src/panda/components/statusPrimitives.tsx',
  'src/panda/components/workspacePrimitives.tsx',
  'src/panda/components/workspaceInfoPrimitives.tsx',
  'src/panda/components/workspaceTablePrimitives.tsx',
  'src/panda/components/workspaceCardPrimitives.tsx',
  'src/panda/components/workspaceResourceCardPrimitives.tsx',
  'src/panda/components/workspaceListCardHeaderPrimitives.tsx',
  'src/panda/components/workspaceCapabilityCardPrimitives.tsx',
  'src/panda/components/workspaceLayoutPrimitives.tsx',
  'src/panda/components/workspaceActivityPrimitives.tsx',
  'src/panda/components/workspaceRailPrimitives.tsx',
  'src/panda/components/workflowPrimitives.tsx',
  'src/panda/components/workflowEvidencePrimitives.tsx',
  'src/panda/components/workflowExecutionStepPrimitives.tsx',
  'src/panda/components/workflowNodePrimitives.tsx',
  'src/panda/components/workflowActionPrimitives.tsx',
  'src/panda/components/workflowCanvasViewModel.ts',
  'src/panda/components/auditReplayViewModel.ts',
  'src/panda/components/taskQueueViewModel.ts',
  'src/panda/components/automationRulesViewModel.ts',
  'src/panda/components/knowledgeBaseViewModel.ts',
  'src/panda/components/dataCenterViewModel.ts',
  'src/panda/components/toolCenterViewModel.ts',
  'src/panda/components/settingsCenterViewModel.ts',
  'src/panda/components/agentProfileCardViewModel.ts',
  'src/panda/components/projectWorkspaceViewModel.ts',
  'src/panda/components/agentRolePresetViewModel.ts',
  'src/panda/components/rightRailResourceCardViewModel.ts',
  'src/panda/components/rightRailActivityCardViewModel.ts',
  'src/panda/components/rightRailCards.tsx',
  'src/panda/components/rightRailActivityCard.tsx',
  'src/panda/components/rightRailWorkflowCard.tsx',
  'src/panda/components/rightRailWorkflowCardViewModel.ts',
  'src/panda/components/rightRailResourceCard.tsx',
  'src/panda/components/rightRailStatusCardsViewModel.tsx',
  'src/panda/components/rightRailStatusCards.tsx',
  'src/panda/components/rightRailFallbacks.ts',
  'src/panda/components/threadWorkspaceViewModel.ts',
  'src/panda/components/threadWorkspace.tsx',
  'src/panda/components/threadExecutionWorkspaceViewModel.ts',
  'src/panda/components/threadExecutionWorkspace.tsx',
  'src/panda/components/agentOrganization.tsx',
  'src/panda/components/agentOrganizationViewModel.ts',
  'src/panda/components/agentProfileCards.tsx',
  'src/panda/components/agentRolePresetSelector.tsx',
  'src/panda/components/workflowCanvas.tsx',
  'src/panda/components/taskQueue.tsx',
  'src/panda/components/projectWorkspace.tsx',
  'src/panda/components/auditReplay.tsx',
  'src/panda/components/automationRules.tsx',
  'src/panda/components/toolCenter.tsx',
  'src/panda/components/dataCenter.tsx',
  'src/panda/components/knowledgeBase.tsx',
  'src/panda/components/settingsCenter.tsx',
  'src/panda/components/agentRolePresetCards.tsx',
  'src/panda/components/agentRolePresetDetail.tsx',
  'src/panda/components/moduleFallback.tsx',
  'src/vite-env.d.ts',
  '.env.example',
  'docs/PANDA_FRONTEND_BACKEND_ALIGNMENT.md',
  'scripts/panda-frontend-closeout-plan.mjs',
  'scripts/panda-alignment-report.mjs',
  'scripts/panda-alignment-context.mjs',
  'scripts/panda-closeout-evidence.mjs',
  'scripts/panda-module-page-structure.mjs',
  'scripts/panda-route-rollover-plan.mjs',
  'scripts/panda-qa-smoke.mjs',
  'scripts/panda-contract-parser.mjs',
  'scripts/panda-script-utils.mjs',
  'scripts/panda-ts-probe-utils.mjs',
  'scripts/panda-workbench-verify-config.mjs',
  'scripts/verify-panda-component-primitives.mjs',
  'scripts/verify-panda-adapters.mjs',
  'scripts/verify-panda-resource-contracts.mjs',
  'scripts/verify-panda-resource-validation.mjs',
  'scripts/verify-panda-resource-dry-run.mjs',
  'public/assets/panda-agent-logo.png',
]

export const pandaWorkbenchPageIds = [
  'home',
  'threads',
  'tasks',
  'projects',
  'workflows',
  'agents',
  'knowledge',
  'tools',
  'data',
  'audit',
  'automation',
  'settings',
]

export const pandaVisualReviewRouteIds = ['home', 'threads', 'workflows', 'audit', 'settings']

export const pandaRequiredFrontendTaskIds = [
  'visual-review',
  'resource-bff-dry-run',
  'page-api-rollover',
  'accessibility-pass',
]

export const pandaVerifyConfigInventoryNames = [
  'pandaAlignmentReportRequiredSymbols',
  'pandaScriptedQaRequiredSymbols',
  'pandaAdapterCheckNames',
  'pandaResourceContractSourceNames',
  'pandaResourceContractCheckNames',
  'pandaResourceDryRunCheckNames',
  'pandaResourceValidationCheckNames',
  'pandaScriptUtilityNames',
  'pandaTsProbeUtilityNames',
  'pandaDeliveryReadinessExpectations',
  'pandaBaseRuntimeFields',
  'pandaProgressRuntimeFields',
  'pandaProgressRuntimeRouteIds',
  'pandaEvidenceRuntimeRouteIds',
  'pandaShellRequiredSymbols',
  'pandaShellLayoutClasses',
  'pandaShellBrandingSymbols',
  'pandaPageRegistryRequiredSymbols',
  'pandaAlignmentDocRequiredPhrases',
  'pandaResourceValidationRequiredSymbols',
  'pandaResourceKeyBoundarySymbols',
  'pandaResourceKeyPairExpectations',
  'pandaResourcesHttpClientRequiredSymbols',
  'pandaResourcesBffConfigRequiredSymbols',
  'pandaBootstrapResourcesRequiredSymbols',
  'pandaResourcesBffEnvNames',
  'pandaResourceContractTypeSymbols',
  'pandaResourceRuntimeFieldSymbols',
  'pandaPageResourceContractSymbols',
  'pandaResourceContractBarrelSymbols',
  'pandaCoreRuntimeFieldNames',
  'pandaResourceSnapshotViewKeys',
  'pandaPageBffEndpoints',
  'pandaResourceReadinessRequiredSymbols',
  'pandaCloseoutPlanRequiredSymbols',
  'pandaAlignmentContextConsumerScripts',
  'pandaCloseoutEvidenceRequiredSymbols',
  'pandaWorkspaceCompatibilitySymbols',
  'pandaWorkspaceTypeSymbols',
  'pandaWorkspaceProviderSymbols',
  'pandaModulePageResourceHookSymbols',
  'pandaModulePageResourceTypeSymbols',
  'pandaModulePageResourceTypeByPage',
  'pandaModulePageResourceHookByPage',
  'pandaAdapterBarrelSymbols',
  'pandaRuntimeAdapterModuleNames',
  'pandaExecutionResourceAdapterSymbols',
  'pandaOrganizationResourceAdapterSymbols',
  'pandaKnowledgeResourceAdapterSymbols',
  'pandaGovernanceResourceAdapterSymbols',
  'pandaPureAdapterModuleNames',
  'pandaHomeApiContractSymbols',
  'pandaExecutionApiContractSymbols',
  'pandaOrganizationApiContractSymbols',
  'pandaKnowledgeApiContractSymbols',
  'pandaGovernanceApiContractSymbols',
  'pandaSnapshotApiContractSymbols',
  'pandaApiContractBarrelSymbols',
  'pandaRuntimeApiFieldNames',
  'pandaRuntimeMetadataContractSources',
  'pandaApiSnapshotResourceKeys',
  'pandaRuntimeMappingSymbols',
  'pandaAdapterFixtureBarrelSources',
  'pandaAdapterOutputFixtureSymbols',
  'pandaResourceSnapshotFixtureSymbols',
  'pandaResourceClientFixtureSymbols',
  'pandaTypeBarrelSources',
  'pandaRouteTypeNames',
  'pandaRuntimeTypeNames',
  'pandaResourceViewModelTypeNames',
  'pandaWorkbenchTypeNames',
  'pandaAlignmentContextRequiredSymbols',
  'pandaRuntimeViewFieldNames',
  'pandaHomeContentSymbols',
  'pandaHomeActionContentSymbols',
  'pandaModuleFallbackContentSymbols',
  'pandaModulePageContentSymbols',
  'pandaMockWorkspaceResourceSymbols',
  'pandaMockExecutionResourceSymbols',
  'pandaMockKnowledgeResourceSymbols',
  'pandaMockOrganizationResourceSymbols',
  'pandaMockResourceBarrelSources',
  'pandaHomePageComponentSymbols',
  'pandaHomeActionComponentSymbols',
  'pandaModuleFallbackComponentSymbols',
  'pandaModuleFallbackSurfaceSymbols',
  'pandaModulePagePrimitiveSymbols',
  'pandaPageFiles',
  'pandaPageFileById',
  'pandaThreadWorkspaceSymbols',
  'pandaTaskQueueSymbols',
  'pandaProjectWorkspaceSymbols',
  'pandaAuditReplaySymbols',
  'pandaAutomationRulesSymbols',
  'pandaToolCenterSymbols',
  'pandaDataCenterSymbols',
  'pandaKnowledgeBaseSymbols',
  'pandaSettingsCenterSymbols',
  'pandaWorkflowCanvasSymbols',
  'pandaAgentOrganizationSymbols',
  'pandaAgentRolePresetSelectorSymbols',
  'pandaManagementRowPageIds',
  'pandaSectionHeaderPageIds',
  'pandaRightRailFocusedCardSymbols',
  'pandaRightRailCardSymbols',
  'pandaRightRailResourceCardSymbols',
  'pandaRightRailStatusCardSymbols',
]

export const pandaAlignmentContextConsumerScripts = [
  'panda-alignment-report.mjs',
  'panda-frontend-closeout-plan.mjs',
]

export const pandaScriptUtilityConsumerScripts = [
  'panda-qa-smoke.mjs',
  'verify-panda-resource-contracts.mjs',
]

export const pandaManifestVerificationCommands = [
  'npm run verify:panda',
  'npm run plan:panda',
  'npm run plan:panda:json',
  'npm run report:panda',
  'npm run report:panda:json',
  'npm run report:panda:strict',
  'npm run qa:panda',
  'npm run qa:panda:json',
  'npm run qa:panda:browser',
  'npm run verify:panda:components',
  'npm run verify:panda:adapters',
  'npm run verify:panda:adapters:json',
  'npm run verify:panda:contracts',
  'npm run verify:panda:contracts:json',
  'npm run verify:panda:resources',
  'npm run verify:panda:resources:json',
  'npm run verify:panda:dry-run',
  'npm run verify:panda:dry-run:json',
  'npm run type-check',
  'npm run build',
  'python -m py_compile backend\\app\\api\\workbench.py',
]

export const pandaPackageScriptExpectations = [
  ['plan:panda', 'node scripts/panda-frontend-closeout-plan.mjs', 'package.json must expose plan:panda'],
  ['plan:panda:json', 'node scripts/panda-frontend-closeout-plan.mjs --json', 'package.json must expose plan:panda:json'],
  ['report:panda', 'node scripts/panda-alignment-report.mjs', 'package.json must expose report:panda'],
  ['report:panda:json', 'node scripts/panda-alignment-report.mjs --json', 'package.json must expose report:panda:json'],
  ['report:panda:strict', 'node scripts/panda-alignment-report.mjs --strict', 'package.json must expose report:panda:strict'],
  ['qa:panda', 'node scripts/panda-qa-smoke.mjs', 'package.json must expose qa:panda'],
  ['qa:panda:json', 'node scripts/panda-qa-smoke.mjs --json', 'package.json must expose qa:panda:json'],
  ['qa:panda:browser', 'node scripts/panda-qa-smoke.mjs --browser', 'package.json must expose qa:panda:browser'],
  ['verify:panda:components', 'node scripts/verify-panda-component-primitives.mjs', 'package.json must expose verify:panda:components'],
  ['verify:panda:adapters', 'node scripts/verify-panda-adapters.mjs', 'package.json must expose verify:panda:adapters'],
  ['verify:panda:adapters:json', 'node scripts/verify-panda-adapters.mjs --json', 'package.json must expose verify:panda:adapters:json'],
  ['verify:panda:contracts', 'node scripts/verify-panda-resource-contracts.mjs', 'package.json must expose verify:panda:contracts'],
  ['verify:panda:contracts:json', 'node scripts/verify-panda-resource-contracts.mjs --json', 'package.json must expose verify:panda:contracts:json'],
  ['verify:panda:resources', 'node scripts/verify-panda-resource-validation.mjs', 'package.json must expose verify:panda:resources'],
  ['verify:panda:resources:json', 'node scripts/verify-panda-resource-validation.mjs --json', 'package.json must expose verify:panda:resources:json'],
  ['verify:panda:dry-run', 'node scripts/verify-panda-resource-dry-run.mjs', 'package.json must expose verify:panda:dry-run'],
  ['verify:panda:dry-run:json', 'node scripts/verify-panda-resource-dry-run.mjs --json', 'package.json must expose verify:panda:dry-run:json'],
]

export const pandaAlignmentReportRequiredSymbols = [
  'pandaFrontendManifest.json',
  'resourceContracts.ts',
  'pageResourceContracts.ts',
  'resourceRuntimeFields.ts',
  'resourceContractTypes.ts',
  'apiContracts.ts',
  'homeApiContracts.ts',
  'resourceApiContracts.ts',
  'snapshotApiContracts.ts',
  'resourceReadiness.ts',
  'Backend alignment pending',
  'runtimeFields',
  'deliveryReadiness',
  'Visual review target',
  'frontendCloseout',
  'visualReviewTargets',
  'accessibilityEvidence',
  'visualReviewEvidence',
  'scriptedQaEvidence',
  'adapterEvidence',
  'resourceKeyBoundary',
  'Resource key boundary',
  'resourcesValidationEvidence',
  'resourcesContractEvidence',
  'routeApiResourcesEvidence',
  'unknownRouteApiResources',
  'missingRouteApiResources',
  'comparedSources',
  'panda-route-rollover-plan.mjs',
  'panda-alignment-context.mjs',
  'panda-closeout-evidence.mjs',
  'resourceReadiness',
  'Resource readiness source',
  'frontendCompletion',
  'backendAlignmentBlockers',
  'backendAlignmentHandoff',
  'nextFrontendTasks',
  'Frontend closeout',
  'Backend alignment handoff',
  'handoffRule',
  'frontendOwnedCommands',
  'backendOwnedCommands',
  'Visual review targets',
  'Visual review evidence',
  'Accessibility evidence',
  'Scripted QA evidence',
  'Adapter evidence',
  'Resources validation evidence',
  'Resources contract evidence',
  'Route API resources evidence',
  'unknownRouteApiResources',
  'missingRouteApiResources',
  'Frontend completed evidence',
  'Backend alignment blockers',
  'Next frontend tasks',
  'Strict readiness failures',
  'strictFailures',
  'getPandaStrictFailures',
  'console.table',
  'process.argv.includes',
  'JSON.stringify(summary',
]

export const pandaScriptedQaRequiredSymbols = [
  'pandaFrontendManifest.json',
  'PANDA_QA_URL',
  'PANDA_QA_SCREENSHOT_DIR',
  'PANDA_QA_RESULT_PATH',
  'probeStaticContracts',
  'probeRoutes',
  'probeBrowser',
  'playwright',
  'skip-link',
  'progress-semantics',
  'status-semantics',
  'statusPrimitives.tsx',
  'resources-bff-validation',
  'resource-dry-run-fixture',
  'route-api-resources-evidence',
  'manifest-api-vs-resource-boundary-api',
  'manifest-view-vs-resource-boundary-view',
  'resource-boundary-api-vs-api-snapshot',
  'resource-boundary-view-vs-view-snapshot',
  'resourceKeys.ts',
  'pandaResourceKeyPairs',
  'unknownRouteApiResources',
  'missingRouteApiResources',
]

export const pandaAdapterCheckNames = [
  'tone-fallback',
  'progress-clamp',
  'runtime-snake-case-mapping',
  'task-runtime-mapping',
  'activity-runtime-mapping',
  'evidence-refs-copy',
  'agent-permissions-copy',
  'resource-snapshot-mapping',
]

export const pandaResourceContractSourceNames = [
  'manifest',
  'routeTypes',
  'modulePageContent',
  'modulePageStructure',
  'modulePageResources',
  'resourceKeys',
  'apiContracts',
  'adapters',
  'resourceSnapshotAdapter',
  'resourcesClient',
  'resourceContracts',
  'resourceReadiness',
]

export const pandaResourceContractCheckNames = [
  'module-page-content-ownership',
  'module-content-vs-standard-module-pages',
  'module-content-key-vs-page-field',
  'module-resource-hooks-vs-type-bindings',
  'module-resource-types-vs-type-map',
  'mock-ready-contract-field-completeness',
  'closeout-pending-routes-vs-route-rollover',
  'route-rollover-api-resources-vs-resource-boundary-api',
  'pending-route-api-resources-vs-closeout-api-resources',
  'manifest-api-vs-resource-boundary-api',
  'manifest-view-vs-resource-boundary-view',
  'resource-boundary-api-vs-api-snapshot',
  'resource-boundary-view-vs-view-snapshot',
  'validation-vs-api-snapshot',
  'mapper-vs-api-snapshot',
  'view-snapshot-vs-fallback',
  'contracts-vs-view-snapshot',
  'readiness-routes-vs-contract-routes',
  'readiness-resources-vs-contract-resources',
  'readiness-api-resources-vs-resource-boundary-api',
  'readiness-endpoints-vs-contract-endpoints',
  'readiness-pending-routes-vs-mock-ready-contracts',
]

export const pandaResourceDryRunCheckNames = [
  'resources-bootstrap-import-safe-default-env',
  'resources-bff-explicit-disabled',
  'resources-bff-explicit-enabled',
  'resources-bootstrap-disabled-clears-loader',
  'resources-bootstrap-enabled-registers-loader',
  'resources-client-mock-fallback',
  'resources-client-api-success',
  'resources-client-invalid-api-fallback',
  'all-view-slices-present',
  'all-runtime-metadata-shapes',
  'aggregate-fixture-core-runtime-fields',
  'task-runtime-fields',
  'home-activity-runtime-fields',
  'workflow-node-runtime-fields',
  'cross-resource-runtime-fields',
  'audit-evidence-fields',
  'settings-readonly-runtime',
]

export const pandaResourceValidationCheckNames = [
  'valid-array-fields',
  'partial-snapshot',
  'non-object-root',
  'array-root',
  'non-array-resource-field',
  'non-object-resource-item',
  'unknown-resource-field',
]

export const pandaScriptUtilityNames = [
  'readJson',
  'extractResourceKeyPairs',
  'buildResourceKeyBoundary',
  'buildRouteApiResourcesEvidence',
  'buildPendingRouteSignature',
  'extractApiResourcesFromPendingRouteSignatures',
  'sameMembers',
  'requestStatus',
  'runNodeJson',
]

export const pandaTsProbeUtilityNames = [
  'createPandaTsProbeTempDir',
  'transpilePandaTsFile',
  'transpilePandaApiProbeFiles',
  'rewriteProbeImports',
  'rewritePandaApiProbeImports',
  'importProbeModule',
  'cleanupPandaTsProbeTempDir',
]

export const pandaDeliveryReadinessExpectations = [
  ['frontendShell', 'ready'],
  ['pageContracts', 'ready'],
  ['mockFallback', 'ready'],
  ['apiAdapters', 'ready'],
  ['visibleContractStrip', 'ready'],
  ['strictBackendGate', 'ready'],
]

export const pandaBaseRuntimeFields = ['status', 'risk_level', 'updated_at']

export const pandaProgressRuntimeFields = ['progress', 'owner_agent']

export const pandaProgressRuntimeRouteIds = [
  'home',
  'threads',
  'tasks',
  'projects',
  'workflows',
  'agents',
  'knowledge',
  'tools',
  'data',
  'audit',
  'automation',
]

export const pandaEvidenceRuntimeRouteIds = [
  'threads',
  'tasks',
  'workflows',
  'tools',
  'audit',
  'automation',
]

export const pandaShellRequiredSymbols = [
  'PandaShellFrame',
  'Sidebar',
  'TopBar',
  'PandaShellFrameProps',
  'BrandLockup',
  'ShellNavigation',
  'WorkspaceSwitcher',
  'MobileStatusRow',
  'TopBarStatus',
  'TopBarActions',
]

export const pandaShellLayoutClasses = [
  'className="panda-shell"',
  'className="panda-main-shell"',
  'className="panda-content"',
]

export const pandaShellBrandingSymbols = [
  'BrandLockup',
  'WorkspaceSwitcher',
  'TopBarActions',
]

export const pandaPageRegistryRequiredSymbols = [
  'pandaPageIds',
  'pandaPageComponents',
  'isPandaPage',
  'getPandaPageComponent',
]

export const pandaAlignmentDocRequiredPhrases = [
  'Frontend Engineering Goal',
  'Panda Closeout Plan Command',
  'Proposed BFF Endpoint Matrix',
  'Adapter Boundary',
  'Frontend Adapter Order',
  'Readonly Display Model',
  'Page Registry',
  'Resource Contracts',
  'Frontend Closeout Scope',
  'Backend Alignment Handoff',
  'Accessibility QA Evidence',
  'Visual QA Evidence',
  'frontend/src/panda/api/resourceKeys.ts',
  'pandaResourceKeyPairs',
  'frontend/src/panda/data/modulePageContent.tsx',
  'frontend/src/panda/components/modulePagePrimitives.tsx',
  'frontend/src/panda/state/useModulePageResources.ts',
  'frontend/scripts/panda-alignment-context.mjs',
  'frontend/scripts/panda-closeout-evidence.mjs',
  'frontend/scripts/panda-module-page-structure.mjs',
  'frontend/scripts/panda-route-rollover-plan.mjs',
  'backendAlignmentHandoff',
  'frontendOwnedCommands',
  'backendOwnedCommands',
  'handoffRule',
  'VITE_PANDA_RESOURCES_BFF=true',
  '/api/v1/workbench/resources',
  'StandardModulePageShell',
  'ModuleResourcePage',
  'pandaModulePageContent',
  'modulePageStructure.resourceHooks',
  'modulePageStructure.resourceTypes',
  'PageResources type bindings',
  'standard module page selector boundary',
  'evidence-refs-copy',
  'mapRuntimeMetadata()',
  'mapAuditEvent()',
  'permissions?: readonly string[]',
  'ApiPandaResourceSnapshot',
  'PandaResourceLoadResult.resources',
  'workspace context `resources`',
  'apiResourceSnapshotFixture',
  'aggregateResourcesBffDryRunFixture',
  'memoized derived payloads',
  'useModulePageResources.ts',
  'PandaStandardModulePage',
  'modulePageContent.tsx',
  'getModuleFallbackMeta(page)',
  'moduleFallbackContent.ts',
  '`PandaWorkbenchHome` collections',
  '`PandaResourceSnapshot` resource collections',
  'Mock fallback arrays',
  'mockExecutionResources.ts',
  'moduleFallbackContent.ts',
  'closeout pending routes',
  'API resources',
  'API needs',
]

export const pandaResourceValidationRequiredSymbols = [
  'PandaResourceValidationError',
  'validatePandaResourceSnapshot',
  'pandaResourceValidationKeys',
  'pandaApiResourceKeys',
]

export const pandaResourceKeyBoundarySymbols = [
  'pandaResourceKeyPairs',
  'PandaViewResourceKey',
  'PandaApiResourceKey',
  'pandaViewResourceKeys',
  'pandaApiResourceKeys',
  'pandaApiResourceKeySet',
]

export const pandaResourceKeyPairExpectations = [
  ['workflowNodes', 'workflow_nodes'],
  ['knowledgeSources', 'knowledge_sources'],
  ['dataSources', 'data_sources'],
  ['auditEvents', 'audit_events'],
  ['automationRules', 'automation_rules'],
  ['settingsSections', 'settings_sections'],
]

export const pandaResourcesHttpClientRequiredSymbols = [
  'PANDA_RESOURCES_BFF_ENDPOINT',
  'createPandaResourcesFetchClient',
  'PandaResourcesFetchClientOptions',
  'resolvePandaResourcesEndpoint',
]

export const pandaResourcesBffConfigRequiredSymbols = [
  'PANDA_RESOURCES_BFF_FLAG',
  'PandaResourcesBffEnv',
  'shouldUsePandaResourcesBff',
  'getPandaResourcesBffConfig',
  'resolvePandaResourcesEndpoint',
]

export const pandaBootstrapResourcesRequiredSymbols = [
  'bootstrapPandaResources',
  'shouldUsePandaResourcesBff',
  'getPandaResourcesBffConfig',
  'setPandaResourcesApiLoader',
  'createPandaResourcesFetchClient',
]

export const pandaResourcesBffEnvNames = [
  'VITE_PANDA_RESOURCES_BFF',
  'VITE_PANDA_RESOURCES_BFF_ENDPOINT',
]

export const pandaResourceContractTypeSymbols = [
  'PandaRuntimeField',
  'PandaPageResourceContract',
]

export const pandaResourceRuntimeFieldSymbols = ['pandaCoreRuntimeFields']

export const pandaPageResourceContractSymbols = [
  'pandaPageResourceContracts',
  'pandaResourceContractKeys',
]

export const pandaResourceContractBarrelSymbols = [
  'PandaRuntimeField',
  'pandaCoreRuntimeFields',
  'PandaPageResourceContract',
  'pandaPageResourceContracts',
  'pandaResourceContractKeys',
]

export const pandaCoreRuntimeFieldNames = [
  'status',
  'risk_level',
  'progress',
  'owner_agent',
  'updated_at',
  'evidence_refs',
]

export const pandaResourceSnapshotViewKeys = [
  'tasks',
  'projects',
  'threads',
  'workflows',
  'workflowNodes',
  'agents',
  'knowledgeSources',
  'tools',
  'dataSources',
  'auditEvents',
  'automationRules',
  'settingsSections',
]

export const pandaPageBffEndpoints = [
  '/api/v1/workbench/home',
  '/api/v1/workbench/threads',
  '/api/v1/workbench/tasks',
  '/api/v1/workbench/projects',
  '/api/v1/workbench/workflows',
  '/api/v1/workbench/agents',
  '/api/v1/workbench/knowledge',
  '/api/v1/workbench/tools',
  '/api/v1/workbench/data',
  '/api/v1/workbench/audit',
  '/api/v1/workbench/automation',
  '/api/v1/workbench/settings',
]

export const pandaResourceReadinessRequiredSymbols = [
  'PandaRouteReadinessItem',
  'pandaRouteReadiness',
  'pandaBackendAlignmentReadiness',
]

export const pandaCloseoutPlanRequiredSymbols = [
  'frontendEngineerGoal',
  'routeRolloverPlan',
  'routeRolloverSource',
  'alignmentContextSource',
  'closeoutEvidenceSource',
  'backendAlignmentHandoff',
  'modulePageStructure',
  'Backend Alignment Handoff',
  'panda-alignment-context.mjs',
  'panda-closeout-evidence.mjs',
  'resourceHooks',
  'expectedStrictFailure',
  'getPandaExpectedStrictFailure',
  'PANDA_CLOSEOUT_PLAN_PATH',
]

export const pandaCloseoutEvidenceRequiredSymbols = [
  'PANDA_CLOSEOUT_EVIDENCE_SOURCE',
  'buildPandaBackendAlignmentHandoff',
  'buildPandaCloseoutEvidence',
  'routeApiResourcesEvidence',
  'route-api-resources-evidence',
  'unknownRouteApiResources',
  'missingRouteApiResources',
  'frontendCompletion',
  'backendAlignmentBlockers',
  'backendAlignmentHandoff',
  'frontendBoundary',
  'frontendEvidence',
  'backendPendingTasks',
  'pendingRoutes',
]

export const pandaWorkspaceCompatibilitySymbols = [
  'PandaWorkspaceProvider',
  'usePandaWorkspace',
  'usePandaWorkspaceLifecycle',
  'usePandaWorkspaceResource',
]

export const pandaWorkspaceTypeSymbols = [
  'PandaWorkspaceStatus',
  'PandaWorkspaceContextValue',
  'PandaWorkspaceLifecycle',
  'PandaResourceSnapshot',
  'PandaResourceSource',
]

export const pandaWorkspaceProviderSymbols = [
  'PandaWorkspaceProvider',
  'loadPandaResources',
  'status',
  'source',
  'refreshedAt',
  'refresh',
]

export const pandaModulePageResourceHookSymbols = [
  'useTasksPageResources',
  'useProjectsPageResources',
  'useWorkflowsPageResources',
  'useAgentsPageResources',
  'useKnowledgePageResources',
  'useToolsPageResources',
  'useDataPageResources',
  'useAuditPageResources',
  'useAutomationPageResources',
  'useSettingsPageResources',
]

export const pandaModulePageResourceTypeSymbols = [
  'TasksPageResources',
  'ProjectsPageResources',
  'WorkflowsPageResources',
  'AgentsPageResources',
  'KnowledgePageResources',
  'ToolsPageResources',
  'DataPageResources',
  'AuditPageResources',
  'AutomationPageResources',
  'SettingsPageResources',
]

export const pandaModulePageResourceTypeByPage = {
  tasks: 'TasksPageResources',
  projects: 'ProjectsPageResources',
  workflows: 'WorkflowsPageResources',
  agents: 'AgentsPageResources',
  knowledge: 'KnowledgePageResources',
  tools: 'ToolsPageResources',
  data: 'DataPageResources',
  audit: 'AuditPageResources',
  automation: 'AutomationPageResources',
  settings: 'SettingsPageResources',
}

export const pandaModulePageResourceHookByPage = {
  tasks: 'useTasksPageResources',
  projects: 'useProjectsPageResources',
  workflows: 'useWorkflowsPageResources',
  agents: 'useAgentsPageResources',
  knowledge: 'useKnowledgePageResources',
  tools: 'useToolsPageResources',
  data: 'useDataPageResources',
  audit: 'useAuditPageResources',
  automation: 'useAutomationPageResources',
  settings: 'useSettingsPageResources',
}

export const pandaAdapterBarrelSymbols = [
  'ApiRuntimeMetadata',
  'ApiPandaResourceSnapshot',
  'mapRuntimeMetadata',
  'mapPandaResourceSnapshot',
  'mapWorkbenchHome',
  'mapTaskSummary',
  'mapAgentProfile',
  'mapAuditEvent',
  'mapSettingsSection',
  'toStatusTone',
  'clampProgress',
]

export const pandaRuntimeAdapterModuleNames = [
  'executionResourceAdapters',
  'organizationResourceAdapters',
  'knowledgeResourceAdapters',
  'governanceResourceAdapters',
]

export const pandaExecutionResourceAdapterSymbols = [
  'mapTaskSummary',
  'mapThreadItem',
  'mapWorkflowNode',
]

export const pandaOrganizationResourceAdapterSymbols = [
  'mapProjectItem',
  'mapAgentProfile',
]

export const pandaAgentRoleAdapterSymbols = [
  'mapAgentRolePreset',
  'mapAgentRolePresets',
]

export const pandaKnowledgeResourceAdapterSymbols = [
  'mapKnowledgeSource',
  'mapDataSource',
  'mapToolCapability',
]

export const pandaGovernanceResourceAdapterSymbols = [
  'mapAuditEvent',
  'mapAutomationRule',
  'mapSettingsSection',
]

export const pandaPureAdapterModuleNames = [
  'adapters',
  'homeAdapters',
  'executionResourceAdapters',
  'organizationResourceAdapters',
  'knowledgeResourceAdapters',
  'governanceResourceAdapters',
  'agentRoleAdapters',
  'resourceItemAdapters',
  'resourceSnapshotAdapter',
]

export const pandaHomeApiContractSymbols = [
  'ApiWorkbenchHome',
  'ApiWorkbenchActivityItem',
  'ApiWorkbenchWorkflowRun',
]

export const pandaExecutionApiContractSymbols = [
  'ApiTaskSummary',
  'ApiThreadItem',
  'ApiWorkflowNode',
]

export const pandaOrganizationApiContractSymbols = [
  'ApiProjectItem',
  'ApiAgentProfile',
  'ApiAgentRolePreset',
]

export const pandaKnowledgeApiContractSymbols = [
  'ApiKnowledgeSource',
  'ApiDataSource',
  'ApiToolCapability',
]

export const pandaGovernanceApiContractSymbols = [
  'ApiAuditEvent',
  'ApiAutomationRule',
  'ApiSettingsSection',
]

export const pandaSnapshotApiContractSymbols = ['ApiPandaResourceSnapshot']

export const pandaApiContractBarrelSymbols = [
  'ApiWorkbenchHome',
  'ApiTaskSummary',
  'ApiProjectItem',
  'ApiThreadItem',
  'ApiWorkflowNode',
  'ApiAgentProfile',
  'ApiAgentRolePreset',
  'ApiKnowledgeSource',
  'ApiDataSource',
  'ApiAuditEvent',
  'ApiToolCapability',
  'ApiAutomationRule',
  'ApiSettingsSection',
  'ApiPandaResourceSnapshot',
]

export const pandaRuntimeApiFieldNames = [
  'risk_level',
  'owner_agent',
  'updated_at',
  'evidence_refs',
]

export const pandaRuntimeMetadataContractSources = [
  ['homeApiContracts', 2],
  ['executionApiContracts', 3],
  ['organizationApiContracts', 3],
  ['knowledgeApiContracts', 3],
  ['governanceApiContracts', 3],
]

export const pandaApiSnapshotResourceKeys = [
  'workflow_nodes',
  'knowledge_sources',
  'data_sources',
  'audit_events',
  'automation_rules',
  'settings_sections',
]

export const pandaRuntimeMappingSymbols = [
  'ApiTone',
  'ApiRuntimeMetadata',
  'toStatusTone',
  'clampProgress',
  'stringValue',
  'mapRuntimeMetadata',
]

export const pandaAdapterFixtureBarrelSources = [
  './adapterOutputFixtures',
  './resourceSnapshotFixtures',
  './resourceClientFixtures',
]

export const pandaAdapterOutputFixtureSymbols = ['adapterFixtureOutputs']

export const pandaResourceSnapshotFixtureSymbols = [
  'apiResourceSnapshotFixture',
  'runtimeFixture',
  'aggregateResourcesBffDryRunFixture',
  'workbenchActivityDryRunFixture',
  'resourceSnapshotAdapterFixture',
  'validatedResourceSnapshotFixture',
  'pandaResourceValidationFixture',
  'mapPandaResourceSnapshot',
  'validatePandaResourceSnapshot',
  'ApiPandaResourceSnapshot',
]

export const pandaResourceClientFixtureSymbols = [
  'pandaResourcesHttpClientFixture',
  'pandaResourcesApiLoaderFixture',
  'pandaResourcesFetchClientFixture',
  'resolvePandaResourcesEndpoint',
  'createPandaResourcesApiLoader',
]

export const pandaTypeBarrelSources = [
  './types/routeTypes',
  './types/runtimeTypes',
  './types/agentRoleTypes',
  './types/resourceTypes',
  './types/workbenchTypes',
]

export const pandaRouteTypeNames = [
  'PandaPage',
  'PandaStandardModulePage',
  'NavItem',
  'ModuleCard',
  'QuickAction',
  'CapabilityRow',
]

export const pandaRuntimeTypeNames = [
  'RuntimeMetadata',
  'WithRuntimeMetadata',
  'StatusTone',
]

export const pandaResourceViewModelTypeNames = [
  'TaskSummary',
  'AgentProfile',
  'AuditEvent',
  'ToolCapability',
  'AutomationRule',
]

export const pandaAgentRoleTypeNames = [
  'AgentRoleIcon',
  'AgentRolePreset',
]

export const pandaWorkbenchTypeNames = [
  'PandaWorkbenchHome',
  'PandaWorkbenchMetrics',
  'ActivityItem',
]

export const pandaAlignmentContextRequiredSymbols = [
  'PANDA_ALIGNMENT_CONTEXT_SOURCE',
  'getPandaAlignmentContext',
  'pandaFrontendManifest.json',
  'pageResourceContractCatalog.ts',
  'pageResourceContracts.ts',
  'resourceKeys.ts',
  'buildPandaRouteRolloverPlan',
  'getPandaModulePageStructure',
  'apiKeyByViewKey',
]

export const pandaRuntimeViewFieldNames = [
  'riskLevel',
  'ownerAgent',
  'updatedAt',
  'evidenceRefs',
]

export const pandaHomeContentSymbols = [
  'quickActions',
  'promptActions',
  'activities',
  'moduleCards',
  'capabilityRows',
]

export const pandaHomeActionContentSymbols = [
  'quickActions',
  'promptActions',
  'activities',
]

export const pandaModuleFallbackContentSymbols = [
  'moduleCards',
  'capabilityRows',
]

export const pandaModulePageContentSymbols = [
  'pandaModulePageContent',
  'ModulePageContent',
  'moduleActions',
]

export const pandaMockWorkspaceResourceSymbols = [
  'projects',
  'threads',
  'workflowNodes',
  'agentProfiles',
  'auditEvents',
  'toolCapabilities',
  'taskSummaries',
  'knowledgeSources',
  'dataSources',
  'automationRules',
  'settingsSections',
]

export const pandaMockExecutionResourceSymbols = [
  'threads',
  'workflows',
  'workflowNodes',
  'auditEvents',
  'taskSummaries',
]

export const pandaMockKnowledgeResourceSymbols = [
  'toolCapabilities',
  'knowledgeSources',
  'dataSources',
]

export const pandaMockOrganizationResourceSymbols = [
  'projects',
  'agentProfiles',
  'automationRules',
  'settingsSections',
]

export const pandaMockResourceBarrelSources = [
  './mockExecutionResources',
  './mockKnowledgeResources',
  './mockOrganizationResources',
]

export const pandaHomePageComponentSymbols = [
  'RecentProjects',
  'PlatformSnapshot',
]

export const pandaHomeActionComponentSymbols = [
  'TaskComposer',
  'PromptActionRow',
  'QuickActionGrid',
  'ModuleCardGrid',
]

export const pandaModuleFallbackComponentSymbols = [
  'ModuleFallbackWorkspace',
  'ModuleFallbackHero',
  'ModuleCapabilityGrid',
  'ModuleDeliverySurface',
]

export const pandaModuleFallbackSurfaceSymbols = [
  'ModuleFallbackHero',
  'ModuleCapabilityGrid',
]

export const pandaModuleDeliverySurfaceSymbols = [
  'ModuleDeliverySurface',
]

export const pandaModulePagePrimitiveSymbols = [
  'ModulePageActions',
  'ModuleResourcePage',
  'StandardModulePageShell',
]

export const pandaPageFiles = [
  'src/panda/pages/HomePage.tsx',
  'src/panda/pages/ThreadsPage.tsx',
  'src/panda/pages/TasksPage.tsx',
  'src/panda/pages/ProjectsPage.tsx',
  'src/panda/pages/WorkflowsPage.tsx',
  'src/panda/pages/AgentsPage.tsx',
  'src/panda/pages/KnowledgePage.tsx',
  'src/panda/pages/ToolsPage.tsx',
  'src/panda/pages/DataPage.tsx',
  'src/panda/pages/AuditPage.tsx',
  'src/panda/pages/AutomationPage.tsx',
  'src/panda/pages/SettingsPage.tsx',
  'src/panda/components/RightRail.tsx',
]

export const pandaPageFileById = {
  home: 'src/panda/pages/HomePage.tsx',
  threads: 'src/panda/pages/ThreadsPage.tsx',
  tasks: 'src/panda/pages/TasksPage.tsx',
  projects: 'src/panda/pages/ProjectsPage.tsx',
  workflows: 'src/panda/pages/WorkflowsPage.tsx',
  agents: 'src/panda/pages/AgentsPage.tsx',
  knowledge: 'src/panda/pages/KnowledgePage.tsx',
  tools: 'src/panda/pages/ToolsPage.tsx',
  data: 'src/panda/pages/DataPage.tsx',
  audit: 'src/panda/pages/AuditPage.tsx',
  automation: 'src/panda/pages/AutomationPage.tsx',
  settings: 'src/panda/pages/SettingsPage.tsx',
}

export const pandaThreadWorkspaceSymbols = [
  'ThreadListPanel',
  'ThreadWorkPanel',
]

export const pandaTaskQueueSymbols = [
  'TaskQueueWorkspace',
  'TaskQueuePanel',
  'TaskQueueRow',
]

export const pandaProjectWorkspaceSymbols = [
  'ProjectWorkspace',
  'ProjectTable',
  'ProjectTableRow',
]

export const pandaAuditReplaySymbols = [
  'AuditReplayWorkspace',
  'AuditTimeline',
  'AuditRiskSummary',
]

export const pandaAutomationRulesSymbols = [
  'AutomationRulesPanel',
  'AutomationRuleRow',
]

export const pandaToolCenterSymbols = [
  'ToolCapabilityGrid',
  'ToolCapabilityCard',
  'ToolAccessBoundary',
]

export const pandaDataCenterSymbols = [
  'DataSourceGrid',
  'DataSourceCard',
]

export const pandaKnowledgeBaseSymbols = [
  'KnowledgeSourceGrid',
  'KnowledgeSourceCard',
]

export const pandaSettingsCenterSymbols = [
  'SettingsSectionGrid',
  'SettingsSectionCard',
]

export const pandaWorkflowCanvasSymbols = [
  'WorkflowCanvas',
  'WorkflowRunGrid',
  'WorkflowRunCard',
]

export const pandaAgentOrganizationSymbols = [
  'AgentOrganizationOverview',
  'AgentProfileGrid',
]

export const pandaAgentProfileCardSymbols = [
  'AgentProfileCard',
]

export const pandaAgentRolePresetSelectorSymbols = [
  'AgentRolePresetSelector',
  'AgentRolePresetCard',
  'AgentRolePresetDetail',
]

export const pandaManagementRowPageIds = ['tasks', 'automation']

export const pandaSectionHeaderPageIds = ['tasks', 'projects', 'automation']

export const pandaRightRailFocusedCardSymbols = [
  'ResourceSnapshotCard',
  'AgentActivityCard',
  'WorkflowRunsCard',
  'ApprovalRiskCard',
  'SystemStatusCard',
]

export const pandaRightRailCardSymbols = [
  'AgentActivityCard',
  'WorkflowRunsCard',
]

export const pandaRightRailResourceCardSymbols = [
  'ResourceSnapshotCard',
  'ResourceSnapshotCardProps',
]

export const pandaRightRailStatusCardSymbols = [
  'ApprovalRiskCard',
  'SystemStatusCard',
]

export const pandaManifestRequiredSafeScopeEntries = [
  ['frontend/src/panda/**', 'Panda manifest must keep the frontend safe edit scope explicit'],
  ['frontend/src/panda/data/homeActionContent.ts', 'Panda manifest must include focused home action content in the frontend safe edit scope'],
  ['frontend/src/panda/data/moduleFallbackContent.ts', 'Panda manifest must include focused module fallback content in the frontend safe edit scope'],
  ['frontend/src/panda/data/modulePageTypes.ts', 'Panda manifest must include focused module page content types in the frontend safe edit scope'],
  ['frontend/src/panda/data/modulePageActions.tsx', 'Panda manifest must include focused module page action factory in the frontend safe edit scope'],
  ['frontend/src/panda/data/modulePageContentCatalog.tsx', 'Panda manifest must include focused module page content catalog in the frontend safe edit scope'],
  ['frontend/src/panda/data/modulePageContent.tsx', 'Panda manifest must include focused module page content in the frontend safe edit scope'],
  ['frontend/src/panda/data/agentRolePresetFixtures.ts', 'Panda manifest must include backend-shaped built-in role card fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/data/agentRolePresets.ts', 'Panda manifest must include built-in agent role presets in the frontend safe edit scope'],
  ['frontend/src/panda/data/agentRolePortraits.ts', 'Panda manifest must include agent role portrait registry in the frontend safe edit scope'],
  ['frontend/src/panda/types/routeTypes.ts', 'Panda manifest must include route type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/runtimeTypes.ts', 'Panda manifest must include runtime type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/agentRoleTypes.ts', 'Panda manifest must include agent role type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/resourceTypes.ts', 'Panda manifest must include resource type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/executionResourceTypes.ts', 'Panda manifest must include execution resource type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/organizationResourceTypes.ts', 'Panda manifest must include organization resource type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/knowledgeResourceTypes.ts', 'Panda manifest must include knowledge resource type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/governanceResourceTypes.ts', 'Panda manifest must include governance resource type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/types/workbenchTypes.ts', 'Panda manifest must include workbench type boundary in the frontend safe edit scope'],
  ['frontend/src/panda/resourceContractTypes.ts', 'Panda manifest must include focused resource contract types in the frontend safe edit scope'],
  ['frontend/src/panda/state/workspaceTypes.ts', 'Panda manifest must include focused workspace types in the frontend safe edit scope'],
  ['frontend/src/panda/state/workspaceProvider.tsx', 'Panda manifest must include focused workspace provider runtime in the frontend safe edit scope'],
  ['frontend/src/panda/state/workspaceLifecycleViewModel.ts', 'Panda manifest must include workspace refresh lifecycle view model in the frontend safe edit scope'],
  ['frontend/src/panda/state/workspaceHooks.ts', 'Panda manifest must include focused workspace hooks in the frontend safe edit scope'],
  ['frontend/src/panda/state/usePandaHashRoute.ts', 'Panda manifest must include focused hash route hook in the frontend safe edit scope'],
  ['frontend/src/panda/state/usePandaHomeWorkbench.ts', 'Panda manifest must include focused home workbench hook in the frontend safe edit scope'],
  ['frontend/src/panda/state/homeWorkbenchViewModel.ts', 'Panda manifest must include the home workbench view model helper in the frontend safe edit scope'],
  ['frontend/src/panda/state/modulePageResourceTypes.ts', 'Panda manifest must include focused module page resource types in the frontend safe edit scope'],
  ['frontend/src/panda/state/useCountedModulePageResource.ts', 'Panda manifest must include the counted module resource selector helper in the frontend safe edit scope'],
  ['frontend/src/panda/state/modulePageResourceHooks.ts', 'Panda manifest must include focused module page resource hook implementations in the frontend safe edit scope'],
  ['frontend/src/panda/state/useModulePageResources.ts', 'Panda manifest must include focused module page resource hooks in the frontend safe edit scope'],
  ['frontend/src/panda/resourceRuntimeFields.ts', 'Panda manifest must include focused resource runtime fields in the frontend safe edit scope'],
  ['frontend/src/panda/pageResourceContractCatalog.ts', 'Panda manifest must include focused page resource contract catalog in the frontend safe edit scope'],
  ['frontend/src/panda/pageResourceContracts.ts', 'Panda manifest must include focused page resource contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/apiContracts.ts', 'Panda manifest must include API contract compatibility barrel in the frontend safe edit scope'],
  ['frontend/src/panda/api/homeApiContracts.ts', 'Panda manifest must include focused home API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/executionApiContracts.ts', 'Panda manifest must include focused execution API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/organizationApiContracts.ts', 'Panda manifest must include focused organization API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/knowledgeApiContracts.ts', 'Panda manifest must include focused knowledge API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/governanceApiContracts.ts', 'Panda manifest must include focused governance API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceApiContracts.ts', 'Panda manifest must include focused resource API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/snapshotApiContracts.ts', 'Panda manifest must include focused snapshot API contracts in the frontend safe edit scope'],
  ['frontend/src/panda/api/executionResourceAdapters.ts', 'Panda manifest must include focused execution resource adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/organizationResourceAdapters.ts', 'Panda manifest must include focused organization resource adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/agentRoleAdapters.ts', 'Panda manifest must include focused agent role adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/knowledgeResourceAdapters.ts', 'Panda manifest must include focused knowledge resource adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/governanceResourceAdapters.ts', 'Panda manifest must include focused governance resource adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceReadiness.ts', 'Panda manifest must include resource readiness in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourcesValidation.ts', 'Panda manifest must include resource validation in the frontend safe edit scope'],
  ['frontend/src/panda/api/homeAdapters.ts', 'Panda manifest must include home adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceItemAdapters.ts', 'Panda manifest must include resource item adapters in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceSnapshotAdapter.ts', 'Panda manifest must include resource snapshot adapter in the frontend safe edit scope'],
  ['frontend/src/panda/api/adapterOutputFixtures.ts', 'Panda manifest must include adapter output fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceSnapshotFixtures.ts', 'Panda manifest must include resource snapshot fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceRuntimeFixtures.ts', 'Panda manifest must include resource runtime fixture helpers in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceAdapterFixtures.ts', 'Panda manifest must include adapter snapshot fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceDryRunFixtures.ts', 'Panda manifest must include aggregate resource dry-run fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/homeActivityFixtures.ts', 'Panda manifest must include home activity dry-run fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourceClientFixtures.ts', 'Panda manifest must include resource client fixtures in the frontend safe edit scope'],
  ['frontend/src/panda/api/resourcesLoadResult.ts', 'Panda manifest must include resource load result builders in the frontend safe edit scope'],
  ['frontend/src/panda/api/workbenchHomeLoadResult.ts', 'Panda manifest must include home workbench load result builders in the frontend safe edit scope'],
  ['frontend/src/panda/data/threadExecutionContent.ts', 'Panda manifest must include thread execution content in the frontend safe edit scope'],
  ['frontend/src/panda/data/mockExecutionResources.ts', 'Panda manifest must include execution mock resources in the frontend safe edit scope'],
  ['frontend/src/panda/data/mockKnowledgeResources.ts', 'Panda manifest must include knowledge mock resources in the frontend safe edit scope'],
  ['frontend/src/panda/data/mockOrganizationResources.ts', 'Panda manifest must include organization mock resources in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeActionSections.tsx', 'Panda manifest must include home action sections in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeNavigationSections.tsx', 'Panda manifest must include home navigation sections in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeProjectSectionsViewModel.ts', 'Panda manifest must include home project sections view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeProjectSections.tsx', 'Panda manifest must include home project sections in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeStatusSectionsViewModel.ts', 'Panda manifest must include home status metric view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeStatusSections.tsx', 'Panda manifest must include home status sections in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellBranding.tsx', 'Panda manifest must include shell branding in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellChrome.tsx', 'Panda manifest must include shell chrome in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellControls.tsx', 'Panda manifest must include shell controls in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellActionControls.tsx', 'Panda manifest must include shell action controls in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellTopbar.tsx', 'Panda manifest must include shell topbar in the frontend safe edit scope'],
  ['frontend/src/panda/components/shellConnectionViewModel.ts', 'Panda manifest must include shell connection view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/pageChromePrimitives.tsx', 'Panda manifest must include page chrome primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/pageContractViewModel.ts', 'Panda manifest must include page contract view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/pageContractPrimitives.tsx', 'Panda manifest must include page contract primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/homeTaskComposer.tsx', 'Panda manifest must include home task composer in the frontend safe edit scope'],
  ['frontend/src/panda/components/resourceStateViewModel.ts', 'Panda manifest must include resource lifecycle view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/resourceState.tsx', 'Panda manifest must include resource state primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/statePanelBasePrimitives.tsx', 'Panda manifest must include the base state panel shell in the frontend safe edit scope'],
  ['frontend/src/panda/components/statePanelPrimitives.tsx', 'Panda manifest must include state panel primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/moduleFallbackSurface.tsx', 'Panda manifest must include module fallback surface primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/moduleDeliverySurfaceViewModel.ts', 'Panda manifest must include module delivery surface view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/moduleDeliverySurface.tsx', 'Panda manifest must include module delivery surface primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/modulePageActionPrimitives.tsx', 'Panda manifest must include module page action primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/modulePagePrimitives.tsx', 'Panda manifest must include module page primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/progressPrimitives.tsx', 'Panda manifest must include progress primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/metricPrimitives.tsx', 'Panda manifest must include metric primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/runtimeMetaViewModel.ts', 'Panda manifest must include runtime meta view model helpers in the frontend safe edit scope'],
  ['frontend/src/panda/components/runtimeMetaPrimitives.tsx', 'Panda manifest must include runtime meta primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/tagListPrimitives.tsx', 'Panda manifest must include tag list primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/statusDotViewModel.ts', 'Panda manifest must include status dot view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/statusPrimitives.tsx', 'Panda manifest must include status primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspacePrimitives.tsx', 'Panda manifest must include workspace primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceInfoPrimitives.tsx', 'Panda manifest must include workspace info primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceTablePrimitives.tsx', 'Panda manifest must include workspace table primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceCardPrimitives.tsx', 'Panda manifest must include workspace card primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceResourceCardPrimitives.tsx', 'Panda manifest must include workspace resource card primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceListCardHeaderPrimitives.tsx', 'Panda manifest must include workspace list-card header primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceCapabilityCardPrimitives.tsx', 'Panda manifest must include workspace capability card primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceLayoutPrimitives.tsx', 'Panda manifest must include workspace layout primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceActivityPrimitives.tsx', 'Panda manifest must include workspace activity primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workspaceRailPrimitives.tsx', 'Panda manifest must include workspace rail primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workflowPrimitives.tsx', 'Panda manifest must include workflow primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workflowEvidencePrimitives.tsx', 'Panda manifest must include workflow evidence primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workflowExecutionStepPrimitives.tsx', 'Panda manifest must include workflow execution step primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workflowNodePrimitives.tsx', 'Panda manifest must include workflow node primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/workflowActionPrimitives.tsx', 'Panda manifest must include workflow action primitives in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailActivityCardViewModel.ts', 'Panda manifest must include right rail activity card view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailActivityCard.tsx', 'Panda manifest must include right rail activity card in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailWorkflowCard.tsx', 'Panda manifest must include right rail workflow card in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailWorkflowCardViewModel.ts', 'Panda manifest must include right rail workflow card view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailResourceCard.tsx', 'Panda manifest must include right rail resource card in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailStatusCardsViewModel.tsx', 'Panda manifest must include right rail status card view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailStatusCards.tsx', 'Panda manifest must include right rail status cards in the frontend safe edit scope'],
  ['frontend/src/panda/components/rightRailFallbacks.ts', 'Panda manifest must include right rail fallback mapping helpers in the frontend safe edit scope'],
  ['frontend/src/panda/components/threadWorkspaceViewModel.ts', 'Panda manifest must include thread workspace view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/threadWorkspace.tsx', 'Panda manifest must include thread workspace in the frontend safe edit scope'],
  ['frontend/src/panda/components/threadExecutionWorkspaceViewModel.ts', 'Panda manifest must include thread execution workspace view model in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentOrganization.tsx', 'Panda manifest must include agent organization composition in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentOrganizationViewModel.ts', 'Panda manifest must include agent organization view model helpers in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentProfileCards.tsx', 'Panda manifest must include agent profile cards in the frontend safe edit scope'],
  ['frontend/src/panda/components/threadExecutionWorkspace.tsx', 'Panda manifest must include thread execution workspace in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentRolePresetCards.tsx', 'Panda manifest must include focused agent role preset cards in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentRolePresetDetail.tsx', 'Panda manifest must include focused agent role preset detail in the frontend safe edit scope'],
  ['frontend/src/panda/components/agentRolePresetSelector.tsx', 'Panda manifest must include the focused agent role preset selector in the frontend safe edit scope'],
  ['frontend/scripts/panda-frontend-closeout-plan.mjs', 'Panda manifest must include the frontend closeout plan script in the frontend safe edit scope'],
  ['frontend/scripts/panda-alignment-context.mjs', 'Panda manifest must include shared alignment context utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-closeout-evidence.mjs', 'Panda manifest must include shared closeout evidence utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-contract-parser.mjs', 'Panda manifest must include shared contract parser in the frontend safe edit scope'],
  ['frontend/scripts/panda-script-utils.mjs', 'Panda manifest must include shared script utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-module-page-structure.mjs', 'Panda manifest must include shared module page structure utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-route-rollover-plan.mjs', 'Panda manifest must include shared route rollover plan utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-ts-probe-utils.mjs', 'Panda manifest must include shared TS probe utilities in the frontend safe edit scope'],
  ['frontend/scripts/panda-workbench-verify-config.mjs', 'Panda manifest must include the workbench verify config in the frontend safe edit scope'],
  ['frontend/scripts/verify-panda-component-primitives.mjs', 'Panda manifest must include component primitive verification in the frontend safe edit scope'],
  ['frontend/scripts/panda-qa-smoke.mjs', 'Panda manifest must include scripted QA in the frontend safe edit scope'],
  ['frontend/scripts/verify-panda-resource-dry-run.mjs', 'Panda manifest must include resources dry-run verification in the frontend safe edit scope'],
]

export const pandaResourceBoundaryExpectedEntries = [
  ['validation', 'src/panda/api/resourcesValidation.ts', 'Panda manifest must record the resource validation boundary'],
  ['provider', 'src/panda/state/PandaWorkspaceContext.tsx', 'Panda manifest must record the workspace compatibility provider boundary'],
  ['providerTypes', 'src/panda/state/workspaceTypes.ts', 'Panda manifest must record the focused workspace type boundary'],
  ['providerRuntime', 'src/panda/state/workspaceProvider.tsx', 'Panda manifest must record the focused workspace provider runtime boundary'],
  ['providerLifecycleViewModel', 'src/panda/state/workspaceLifecycleViewModel.ts', 'Panda manifest must record the focused workspace lifecycle view model boundary'],
  ['providerHooks', 'src/panda/state/workspaceHooks.ts', 'Panda manifest must record the focused workspace hooks boundary'],
  ['hashRouteHook', 'src/panda/state/usePandaHashRoute.ts', 'Panda manifest must record the focused hash route hook boundary'],
  ['homeWorkbenchHook', 'src/panda/state/usePandaHomeWorkbench.ts', 'Panda manifest must record the focused home workbench hook boundary'],
  ['homeWorkbenchLoadResult', 'src/panda/api/workbenchHomeLoadResult.ts', 'Panda manifest must record the focused home workbench load result builder boundary'],
  ['resourceLoadResult', 'src/panda/api/resourcesLoadResult.ts', 'Panda manifest must record the focused resource load result builder boundary'],
  ['keyMap', 'src/panda/api/resourceKeys.ts', 'Panda manifest must record the resource key mapping boundary'],
  ['contracts', 'src/panda/resourceContracts.ts', 'Panda manifest must record the compatibility resource contract boundary'],
  ['pageContractCatalog', 'src/panda/pageResourceContractCatalog.ts', 'Panda manifest must record the focused page resource contract catalog boundary'],
  ['pageContracts', 'src/panda/pageResourceContracts.ts', 'Panda manifest must record the focused page resource contract boundary'],
  ['runtimeFields', 'src/panda/resourceRuntimeFields.ts', 'Panda manifest must record the focused runtime field boundary'],
  ['contractTypes', 'src/panda/resourceContractTypes.ts', 'Panda manifest must record the focused contract type boundary'],
  ['readiness', 'src/panda/api/resourceReadiness.ts', 'Panda manifest must record the resource readiness boundary'],
  ['adapterProbe', 'scripts/verify-panda-adapters.mjs', 'Panda manifest must record the executable adapter behavior probe'],
  ['apiContracts', 'src/panda/api/apiContracts.ts', 'Panda manifest must record the API contract compatibility barrel'],
  ['homeApiContracts', 'src/panda/api/homeApiContracts.ts', 'Panda manifest must record the focused home API contract boundary'],
  ['executionApiContracts', 'src/panda/api/executionApiContracts.ts', 'Panda manifest must record the focused execution API contract boundary'],
  ['organizationApiContracts', 'src/panda/api/organizationApiContracts.ts', 'Panda manifest must record the focused organization API contract boundary'],
  ['knowledgeApiContracts', 'src/panda/api/knowledgeApiContracts.ts', 'Panda manifest must record the focused knowledge API contract boundary'],
  ['governanceApiContracts', 'src/panda/api/governanceApiContracts.ts', 'Panda manifest must record the focused governance API contract boundary'],
  ['resourceApiContracts', 'src/panda/api/resourceApiContracts.ts', 'Panda manifest must record the focused resource API contract boundary'],
  ['snapshotApiContracts', 'src/panda/api/snapshotApiContracts.ts', 'Panda manifest must record the focused snapshot API contract boundary'],
  ['agentRoleTypes', 'src/panda/types/agentRoleTypes.ts', 'Panda manifest must record the agent role view type boundary'],
  ['agentRolePresetFixtures', 'src/panda/data/agentRolePresetFixtures.ts', 'Panda manifest must record backend-shaped built-in role card fixtures'],
  ['agentRolePresets', 'src/panda/data/agentRolePresets.ts', 'Panda manifest must record mapped built-in role card view models'],
  ['agentRolePortraits', 'src/panda/data/agentRolePortraits.ts', 'Panda manifest must record the role portrait key registry'],
  ['agentRoleAdapters', 'src/panda/api/agentRoleAdapters.ts', 'Panda manifest must record the agent role adapter boundary'],
  ['agentRoleApiContract', 'ApiAgentRolePreset', 'Panda manifest must record the agent role API DTO contract'],
  ['adapterOutputFixtures', 'src/panda/api/adapterOutputFixtures.ts', 'Panda manifest must record the focused adapter output fixture boundary'],
  ['resourceSnapshotFixtures', 'src/panda/api/resourceSnapshotFixtures.ts', 'Panda manifest must record the focused resource snapshot fixture boundary'],
  ['resourceRuntimeFixtures', 'src/panda/api/resourceRuntimeFixtures.ts', 'Panda manifest must record the resource runtime fixture helper boundary'],
  ['resourceAdapterFixtures', 'src/panda/api/resourceAdapterFixtures.ts', 'Panda manifest must record the adapter resource fixture boundary'],
  ['resourceDryRunFixtures', 'src/panda/api/resourceDryRunFixtures.ts', 'Panda manifest must record the aggregate dry-run fixture boundary'],
  ['homeActivityFixtures', 'src/panda/api/homeActivityFixtures.ts', 'Panda manifest must record the home activity fixture boundary'],
  ['resourceClientFixtures', 'src/panda/api/resourceClientFixtures.ts', 'Panda manifest must record the focused resource client fixture boundary'],
  ['executionResourceAdapters', 'src/panda/api/executionResourceAdapters.ts', 'Panda manifest must record the focused execution resource adapter boundary'],
  ['organizationResourceAdapters', 'src/panda/api/organizationResourceAdapters.ts', 'Panda manifest must record the focused organization resource adapter boundary'],
  ['knowledgeResourceAdapters', 'src/panda/api/knowledgeResourceAdapters.ts', 'Panda manifest must record the focused knowledge resource adapter boundary'],
  ['governanceResourceAdapters', 'src/panda/api/governanceResourceAdapters.ts', 'Panda manifest must record the focused governance resource adapter boundary'],
  ['validationProbe', 'scripts/verify-panda-resource-validation.mjs', 'Panda manifest must record the executable resource validation probe'],
  ['contractProbe', 'scripts/verify-panda-resource-contracts.mjs', 'Panda manifest must record the executable resource contract probe'],
  ['dryRunProbe', 'scripts/verify-panda-resource-dry-run.mjs', 'Panda manifest must record the executable resources dry-run probe'],
  ['invalidApiFallback', 'mock-with-error', 'Panda manifest must record invalid API fallback behavior'],
]
