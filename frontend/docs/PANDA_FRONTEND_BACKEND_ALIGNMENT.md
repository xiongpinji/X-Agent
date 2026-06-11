# Panda Agent Frontend/Backend Alignment

This document tracks what the Panda Agent frontend needs once the backend mainline reaches delivery readiness. It is a frontend handoff checklist, not a request to change backend behavior during backend closeout.

## Frontend Engineering Goal

As the Panda Agent frontend engineer, the target during backend closeout is to keep the product shell complete, demonstrable, and mechanically verifiable without changing backend-owned policy. The frontend stream owns the Codex-style workbench UI, Panda/X-Agent branding, module routing, mock fallback data, typed resource contracts, adapter behavior, accessibility checks, and handoff evidence.

The current finish line is not to force `npm run report:panda:strict` green. The correct finish line is:

- Frontend-owned verification stays green.
- Every mock-ready route has a declared endpoint, resource slice, runtime field list, and API need.
- The aggregate resources BFF flag stays off until backend returns a validated `ApiPandaResourceSnapshot`.
- Approval, sandbox, auth, secret, and high-risk execution policy remain backend-owned.

## Panda Closeout Plan Command

`npm run plan:panda` prints the frontend closeout plan as Markdown. `npm run plan:panda:json` emits the same plan as machine-readable JSON, and `PANDA_CLOSEOUT_PLAN_PATH` can persist either output outside the repository.

The plan is derived through `frontend/scripts/panda-alignment-context.mjs`, which reads `frontend/src/panda/pandaFrontendManifest.json`, `frontend/src/panda/pageResourceContracts.ts`, and `frontend/src/panda/api/resourceKeys.ts`, so it should not drift from the real route/resource contract ledger. Use it before front/back alignment to see:

- the frontend engineer goal and safe edit scope;
- current frontend completion boundaries;
- the resources BFF enablement rule;
- the route-by-route backend rollover plan;
- frontend-owned verification commands;
- expected strict-gate failure while backend routes remain `mock-ready`.

## Current Frontend Boundary

- The main app shell is `frontend/src/panda/PandaAgentApp.tsx`.
- Shell layout composition lives in `frontend/src/panda/components/Shell.tsx`; shell sidebar and navigation live in `frontend/src/panda/components/shellChrome.tsx`, topbar search/status/mobile connection chrome lives in `frontend/src/panda/components/shellTopbar.tsx`, brand lockup lives in `frontend/src/panda/components/shellBranding.tsx`, workspace switching controls live in `frontend/src/panda/components/shellControls.tsx`, and topbar command/user controls live in `frontend/src/panda/components/shellActionControls.tsx`. Focused shell parts are re-exported through `shellChrome.tsx`, `shellBranding.tsx`, and `shellControls.tsx` for compatibility.
- Static product data is split by responsibility: `frontend/src/panda/data/homeActionContent.ts` owns home quick actions, prompt chips, and activity rows; `frontend/src/panda/data/moduleFallbackContent.ts` owns module cards and fallback capability rows; standard module page content is split across `frontend/src/panda/data/modulePageTypes.ts` for the content shape, `frontend/src/panda/data/modulePageActions.tsx` for the shared action pair factory, and `frontend/src/panda/data/modulePageContentCatalog.tsx` for page heading/action/empty-state content, while `frontend/src/panda/data/modulePageContent.tsx` remains a compatibility barrel; `frontend/src/panda/data/agentRolePresetFixtures.ts` owns backend-shaped built-in role-card fixtures for the create-agent surface, `frontend/src/panda/data/agentRolePresets.ts` maps them into readonly view models and preserves compatibility exports, and `frontend/src/panda/data/agentRolePortraits.ts` owns the local role portrait key registry; `frontend/src/panda/data/homeContent.ts` remains a compatibility barrel. `frontend/src/panda/data/mockHome.ts` owns the home fallback; `frontend/src/panda/data/mockExecutionResources.ts`, `frontend/src/panda/data/mockKnowledgeResources.ts`, and `frontend/src/panda/data/mockOrganizationResources.ts` own page resource fallback data, while `frontend/src/panda/data/mockResources.ts` and `frontend/src/panda/data/mockWorkspace.ts` remain compatibility barrels.
- Shared frontend types are exported through `frontend/src/panda/types.ts`. Focused type ownership lives in `frontend/src/panda/types/routeTypes.ts`, `frontend/src/panda/types/runtimeTypes.ts`, `frontend/src/panda/types/agentRoleTypes.ts`, `frontend/src/panda/types/resourceTypes.ts`, and `frontend/src/panda/types/workbenchTypes.ts`.
- Shared aggregate resource key mapping lives in `frontend/src/panda/api/resourceKeys.ts`; this is the single frontend boundary for camelCase view resource keys and backend-facing snake_case API resource keys.
- API DTO contract ownership is split by backend alignment surface: `frontend/src/panda/api/homeApiContracts.ts` owns home DTOs; `frontend/src/panda/api/executionApiContracts.ts`, `frontend/src/panda/api/organizationApiContracts.ts`, `frontend/src/panda/api/knowledgeApiContracts.ts`, and `frontend/src/panda/api/governanceApiContracts.ts` own page resource DTOs by domain; `frontend/src/panda/api/organizationApiContracts.ts` also owns `ApiAgentRolePreset` for future role-template library alignment; `frontend/src/panda/api/snapshotApiContracts.ts` owns the aggregate `ApiPandaResourceSnapshot`. Resource DTOs attach shared `ApiRuntimeMetadata` from `frontend/src/panda/api/runtimeMapping.ts` instead of copying runtime fields across files. `frontend/src/panda/api/apiContracts.ts` and `frontend/src/panda/api/resourceApiContracts.ts` remain compatibility barrels.
- Backend-to-Panda view model mapping is exported through `frontend/src/panda/api/adapters.ts`. Focused adapter ownership lives in `frontend/src/panda/api/homeAdapters.ts`, `frontend/src/panda/api/executionResourceAdapters.ts`, `frontend/src/panda/api/organizationResourceAdapters.ts`, `frontend/src/panda/api/agentRoleAdapters.ts`, `frontend/src/panda/api/knowledgeResourceAdapters.ts`, `frontend/src/panda/api/governanceResourceAdapters.ts`, and `frontend/src/panda/api/resourceSnapshotAdapter.ts`. `frontend/src/panda/api/resourceItemAdapters.ts` remains a compatibility barrel.
- Adapter fixtures are split for backend alignment: `frontend/src/panda/api/adapterOutputFixtures.ts` owns mapped view-model examples; `frontend/src/panda/api/resourceAdapterFixtures.ts` owns the compact `ApiPandaResourceSnapshot` adapter input; `frontend/src/panda/api/resourceDryRunFixtures.ts` owns the representative aggregate resources BFF dry-run payload; `frontend/src/panda/api/homeActivityFixtures.ts` owns the right-rail home activity dry-run payload; `frontend/src/panda/api/resourceRuntimeFixtures.ts` owns the shared runtime metadata fixture helper; `frontend/src/panda/api/resourceSnapshotFixtures.ts` remains the compatibility aggregation entrypoint; and `frontend/src/panda/api/resourceClientFixtures.ts` owns loader/client examples. `frontend/src/panda/api/adapterFixtures.ts` remains a compatibility barrel.
- Panda-specific data loading lives in `frontend/src/panda/api/workbenchClient.ts`.
- Page resource loading is exposed through `frontend/src/panda/api/resourcesClient.ts` as a compatibility/loading entrypoint until each page has a stable BFF endpoint.
- Page resource snapshot ownership is split by responsibility: `frontend/src/panda/api/resourceSnapshotTypes.ts` owns `PandaResourceSnapshot`, `PandaResourceLoadResult`, and `PandaResourceSource`; `frontend/src/panda/api/resourceFallbackSnapshot.ts` owns the mock fallback snapshot; `frontend/src/panda/api/resourcesApiLoader.ts` owns BFF loader injection, validation, and API-to-view mapping.
- Page workspace state is split by responsibility: `frontend/src/panda/state/workspaceTypes.ts` owns workspace state types; `frontend/src/panda/state/workspaceProvider.tsx` owns provider runtime and refresh lifecycle; `frontend/src/panda/state/workspaceHooks.ts` owns selectors and lifecycle hooks. `frontend/src/panda/state/PandaWorkspaceContext.tsx` remains the page-facing compatibility entrypoint.
- Standard non-home module resource selectors are split by responsibility: `frontend/src/panda/state/modulePageResourceTypes.ts` owns `*PageResources` return types derived from `PandaResourceSnapshot`, `frontend/src/panda/state/useCountedModulePageResource.ts` owns the shared counted slice helper, `frontend/src/panda/state/modulePageResourceHooks.ts` owns the hook implementations, and `frontend/src/panda/state/useModulePageResources.ts` remains the compatibility import boundary for standard pages.
- App-level state is split from the entry component: `frontend/src/panda/state/usePandaHashRoute.ts` owns hash routing and navigation, while `frontend/src/panda/state/usePandaHomeWorkbench.ts` owns the home BFF/mock fallback lifecycle.
- Page registration lives in `frontend/src/panda/pageRegistry.tsx`; `PandaAgentApp.tsx` should compose the shell and home page, then resolve non-home module pages through this registry.
- Page-to-resource contracts live in `frontend/src/panda/pageResourceContracts.ts`; this file maps each first-level module to its current resource slices, future BFF endpoint, and backend data needs. `frontend/src/panda/resourceContracts.ts` remains a compatibility barrel.
- Resource contract type ownership lives in `frontend/src/panda/resourceContractTypes.ts`, and shared runtime field ownership lives in `frontend/src/panda/resourceRuntimeFields.ts`.
- Route readiness handoff metadata lives in `frontend/src/panda/api/resourceReadiness.ts`; it derives from `pageResourceContracts.ts` and exposes `pandaRouteReadiness` plus `pandaBackendAlignmentReadiness` for reports and backend alignment. In route readiness rows, `resources` are Panda view keys and `apiResources` are backend API keys derived through `frontend/src/panda/api/resourceKeys.ts`.
- Frontend readiness metadata lives in `frontend/src/panda/pandaFrontendManifest.json`; it records routes, BFF flags, verification commands, and backend alignment pending items.
- Shared Panda alignment context lives in `frontend/scripts/panda-alignment-context.mjs`; the alignment report and closeout plan import it as the single source for manifest data, page contracts, resource key pairs, module page structure, and route rollover state.
- Shared Panda closeout evidence lives in `frontend/scripts/panda-closeout-evidence.mjs`; the alignment report and closeout plan import it as the single source for frontend completion evidence, current boundary state, and backend alignment blockers.
- Panda page resource contract parsing for scripts lives in `frontend/scripts/panda-contract-parser.mjs`; the shared alignment context owns this parser dependency so route/resource/runtime-field rollover data cannot drift between reports.
- Shared Panda script utilities live in `frontend/scripts/panda-script-utils.mjs`; report, plan, contract, QA, dry-run, and workbench verification scripts reuse it for file reads, JSON loading, resource-key parsing, member comparison, route status checks, and child JSON command execution.
- Shared standard module page structure lives in `frontend/scripts/panda-module-page-structure.mjs`; the alignment report and closeout plan import it as the single source for `modulePageStructure.resourceHooks`, `modulePageStructure.resourceTypes`, standard page ids, and direct selector exceptions.
- Shared route rollover planning lives in `frontend/scripts/panda-route-rollover-plan.mjs`; the alignment report and closeout plan import it as the single source for pending routes, API-wired routes, route rollover acceptance, and expected strict-gate failure text.
- Shared TypeScript probe utilities live in `frontend/scripts/panda-ts-probe-utils.mjs`; executable probes can transpile selected Panda TypeScript modules into temporary ESM modules without duplicating probe setup.
- Workbench verification inventory lives in `frontend/scripts/panda-workbench-verify-config.mjs`; `verify-panda-workbench.mjs` imports it so the main verifier owns checks, not expanding file/page inventory data.
- `deliveryReadiness` in the manifest records frontend-closeout status, the strict backend gate, and the current visual review target.
- `npm run report:panda` prints a read-only alignment report from the manifest, resource contracts, shared resource keys, standard module page resource hook bindings, and per-route Panda/API resource keys; run it before the backend/front-end alignment pass.
- `npm run report:panda:json` prints the same readiness data as machine-readable JSON for backend handoff threads or automation scripts, including `modulePageStructure.resourceHooks` with page, hook, and `resourceType` plus `modulePageStructure.resourceTypes` for the standard module page selector/type boundary.
- `npm run report:panda:strict` is the post-backend-closeout hard gate. It is expected to fail during frontend closeout while non-home modules are still `mock-ready`.
- `npm run plan:panda` prints the frontend closeout plan and backend route rollover matrix.
- `npm run plan:panda:json` prints the same closeout plan as JSON.
- `npm run qa:panda` runs repeatable scripted QA for Panda visual-review routes, route reachability when a dev server is available, and static accessibility probes.
- `npm run qa:panda:json` emits the same QA result as machine-readable JSON; set `PANDA_QA_RESULT_PATH` to persist the result outside the repo.
- `npm run qa:panda:browser` is an optional screenshot mode for environments with Playwright installed. It captures screenshots under the OS temp directory and exercises the home-to-workflows interaction.
- `npm run verify:panda:adapters` runs executable adapter behavior checks for tone fallback, progress clamping, task/activity runtime metadata mapping, and aggregate resource snapshot mapping.
- `npm run verify:panda:adapters:json` emits the same adapter behavior result as JSON; set `PANDA_ADAPTER_RESULT_PATH` to persist the result outside the repo.
- `npm run verify:panda:contracts` verifies that resource keys, mock-ready contract field completeness, closeout pending route handoff fields, standard module page content keys/page fields, PageResources type bindings for each standard module page `page -> hook -> PageResources` handoff, and route readiness stay aligned across the manifest, shared key pairs, validation, API snapshot types, mapper reads, fallback snapshots, page contracts, `modulePageStructure`, and `resourceReadiness.ts`.
- `npm run verify:panda:contracts:json` emits the same resource contract consistency result as JSON; set `PANDA_RESOURCE_CONTRACT_RESULT_PATH` to persist the result outside the repo.
- `npm run verify:panda:resources` runs the executable aggregate resources BFF validation probe. It checks valid snapshots, partial snapshots, invalid roots, invalid resource fields, non-object resource items, and unknown resource keys.
- `npm run verify:panda:resources:json` emits the same validation probe result as JSON; set `PANDA_RESOURCE_VALIDATION_RESULT_PATH` to persist the result outside the repo.
- `npm run verify:panda:dry-run` validates the shared representative aggregate resources BFF payload from `resourceSnapshotFixtures.ts` through `resourcesValidation.ts` and `adapters.ts`, validates every mapped runtime object against the frontend `RuntimeMetadata` shape, verifies the aggregate and home activity fixtures carry every shared `pandaCoreRuntimeFields` API field, validates the shared home activity runtime fixture through `mapActivityItem()`, then checks default import safety, default-disabled BFF config, explicit opt-in config, bootstrap loader behavior, and `loadPandaResources()` mock/api/error fallback behavior without enabling `VITE_PANDA_RESOURCES_BFF` by default.
- `npm run verify:panda:dry-run:json` emits the same dry-run fixture result as JSON; set `PANDA_RESOURCE_DRY_RUN_RESULT_PATH` to persist the result outside the repo.
- `npm run verify:panda:components` runs the focused component primitive ownership probe for `common.tsx`, `pageChromePrimitives.tsx`, `pageContractPrimitives.tsx`, `statePanelPrimitives.tsx`, `resourceState.tsx`, `modulePageActionPrimitives.tsx`, `modulePagePrimitives.tsx`, `progressPrimitives.tsx`, `metricPrimitives.tsx`, `runtimeMetaPrimitives.tsx`, `tagListPrimitives.tsx`, `statusPrimitives.tsx`, `runtimePrimitives.tsx`, `workspacePrimitives.tsx`, `workspaceCardPrimitives.tsx`, `workspaceResourceCardPrimitives.tsx`, `workspaceActivityPrimitives.tsx`, `workspaceRailPrimitives.tsx`, `workspaceLayoutPrimitives.tsx`, `workflowPrimitives.tsx`, `workflowEvidencePrimitives.tsx`, and `workflowActionPrimitives.tsx`; `npm run verify:panda` also calls this probe.
- Standard module pages consume non-home resources through focused selectors in `frontend/src/panda/state/useModulePageResources.ts`, not by importing mock data or API clients directly. `ThreadsPage` and home project sections remain explicit direct-selector exceptions because their layouts are custom workspaces.
- Panda-specific loading, empty, and degraded-data display primitives live in `frontend/src/panda/components/statePanelPrimitives.tsx`; `PandaStatePanel` centralizes their shared panel shell while `PandaLoadingState`, `PandaEmptyState`, and `PandaErrorState` keep semantic entry points for callers. Resource lifecycle handling stays in `frontend/src/panda/components/resourceState.tsx` through `PandaResourceState`, which composes the pure state panel primitives with `usePandaWorkspaceLifecycle()`. Page headings and command buttons live in `frontend/src/panda/components/pageChromePrimitives.tsx`; visible page resource contracts live in `frontend/src/panda/components/pageContractPrimitives.tsx`. These are re-exported through `common.tsx` for compatibility.
- Standard module page composition lives in `frontend/src/panda/components/modulePagePrimitives.tsx`; standard pages render `StandardModulePageShell`, while the shell binds `pandaModulePageContent` into `ModuleResourcePage` so headings, actions, counts, and empty states stay consistent across mock-ready pages. Module action typing and button rendering live in `frontend/src/panda/components/modulePageActionPrimitives.tsx`; `modulePagePrimitives.tsx` preserves the compatibility export, and `moduleActions()` centralizes the secondary + primary action pair convention for standard module pages.
- Right rail dynamic cards are split by responsibility: agent activity lives in `frontend/src/panda/components/rightRailActivityCard.tsx`, workflow progress lives in `frontend/src/panda/components/rightRailWorkflowCard.tsx`, the resource snapshot/BFF status card lives in `frontend/src/panda/components/rightRailResourceCard.tsx`, and static approval/risk plus system status cards live in `frontend/src/panda/components/rightRailStatusCards.tsx`. Agent activity rows render shared runtime metadata tags through `RuntimeMetaStrip`; right rail key-value status rows render through shared `KeyValueList` instead of duplicating row layout. Focused cards are re-exported through `rightRailCards.tsx` for compatibility.
- Home task input lives in `frontend/src/panda/components/homeTaskComposer.tsx`; home prompt actions live in `frontend/src/panda/components/homeActionSections.tsx`; home quick/module navigation grids live in `frontend/src/panda/components/homeNavigationSections.tsx`; recent project resources live in `frontend/src/panda/components/homeProjectSections.tsx`; home BFF status and X-Agent core summary live in `frontend/src/panda/components/homeStatusSections.tsx`. Home quick/module navigation grids compose shared `NavigationCardGrid`, and module summary card bodies compose shared `ModuleSummaryCard`. All are re-exported through `homeSections.tsx` for compatibility, with `homeActionSections.tsx` preserving compatibility exports for the split navigation sections.
- Thread list and resource-state shell live in `frontend/src/panda/components/threadWorkspace.tsx`; the execution workspace renderer lives in `frontend/src/panda/components/threadExecutionWorkspace.tsx`, while execution tabs, plan steps, terminal output, execution controls, and artifact labels live in `frontend/src/panda/data/threadExecutionContent.ts` so they can be replaced by backend execution payloads without changing layout code. The execution workspace is re-exported through `threadWorkspace.tsx` for compatibility.
- Agent organization overview lives in `frontend/src/panda/components/agentOrganization.tsx`; it owns the team topology panel, team actions, and agent grid composition, while `frontend/src/panda/components/agentProfileCards.tsx` owns individual agent runtime cards. Create-agent role card selection lives in `frontend/src/panda/components/agentRolePresetSelector.tsx`; it owns the role selector state and layout, while `frontend/src/panda/components/agentRolePresetCards.tsx` owns card and detail panel rendering. Agent profile and role-card components are re-exported through `frontend/src/panda/components/agentOrganization.tsx` for compatibility.
- Progress primitives such as `ProgressMeter` and `ProgressSummary` live in `frontend/src/panda/components/progressPrimitives.tsx`; metric strips live in `frontend/src/panda/components/metricPrimitives.tsx`; runtime metadata tags live in `frontend/src/panda/components/runtimeMetaPrimitives.tsx`; shared mini tags and key-value rows live in `frontend/src/panda/components/tagListPrimitives.tsx`; accessible status dots live in `frontend/src/panda/components/statusPrimitives.tsx`. `metricPrimitives.tsx` and `runtimePrimitives.tsx` remain compatibility barrels for existing imports.
- Workspace card primitives are split by responsibility: `frontend/src/panda/components/workspaceCardPrimitives.tsx` owns generic card grids and module summary bodies, `frontend/src/panda/components/workspaceResourceCardPrimitives.tsx` owns resource runtime cards, resource info cards, and list-card headers, while `frontend/src/panda/components/workspaceCapabilityCardPrimitives.tsx` owns tool-card headers and `CapabilityMetricCard`; `frontend/src/panda/components/workspaceInfoPrimitives.tsx` owns `InfoPairGrid` and `InsetInfoBlock`; `frontend/src/panda/components/workspaceTablePrimitives.tsx` owns `WorkspaceTable` and `WorkspaceTableHeader`. `workspaceResourceCardPrimitives.tsx`, `workspaceCardPrimitives.tsx`, and `workspacePrimitives.tsx` re-export focused card/info/table primitives for compatibility. Activity rows live in `frontend/src/panda/components/workspaceActivityPrimitives.tsx`; right-rail card shells live in `frontend/src/panda/components/workspaceRailPrimitives.tsx`; workspace panels and section headers live in `frontend/src/panda/components/workspaceLayoutPrimitives.tsx`, which preserves the activity-row and rail-card compatibility exports. `WorkspacePanel` centralizes the common `panda-card p-4` workspace shell across home status, tasks, projects, audit, automation, and tool access boundary sections while preserving semantic `section`, `div`, or `aside` containers. `frontend/src/panda/components/workflowEvidencePrimitives.tsx` owns audit event rows and execution steps, `frontend/src/panda/components/workflowNodePrimitives.tsx` owns workflow canvas node cards, and `frontend/src/panda/components/workflowActionPrimitives.tsx` owns action panels, `PanelActionButton`, and management rows; panel action buttons centralize contextual accessible labels for execution/control panels, and management rows render runtime evidence through `RuntimeMetaStrip` so tasks and automation keep the same owner, update, risk, and evidence tag semantics as other resource surfaces. `workspacePrimitives.tsx` and `workflowPrimitives.tsx` remain compatibility barrels re-exported through `common.tsx`.
- Current backend data touchpoint is `GET /api/v1/workbench/home`.
- Do not use this frontend branch to change approval, sandbox, auth, secret, or high-risk execution policy.

## Page/API Needs

| Page | Current frontend state | Backend alignment needed |
| --- | --- | --- |
| Home | Usable shell with task composer, quick actions, recent projects, system status, right rail | Aggregate dashboard endpoint with projects, task shortcuts, metrics, approvals, activity, and workflow run summaries |
| Threads | Static high-fidelity execution workspace | Thread/run list, active run detail, plan steps, terminal events, file changes, diff summaries, artifacts, audit evidence |
| Tasks | Static task queue with progress, owner agent, priority, and execution actions | Task list, task creation, task status, retry/cancel/approve actions |
| Projects | Static project workspace table with project type, owner agent, update time, and status | Project/workspace list, Git/worktree state, recent files, linked runs, PR status |
| Workflows | Static orchestration canvas with node statuses, run list, approval gateway, and audit node | Workflow definitions, workflow run graph, node statuses, approvals, compensation/failure state |
| Agents | Static multi-agent organization view with profiles, permissions, team actions, load state, and backend-shaped built-in role card fixtures | Agent profiles, teams, role templates, online status, permissions, handoff state, and optional create-agent role-template endpoint shaped like `ApiAgentRolePreset` |
| Knowledge | Static knowledge source grid with indexing status, document counts, and sync state | Knowledge sources, memory references, retrieval results, ingestion state |
| Tools/MCP | Static tool catalog with MCP/channel/tool status, permission display, and invocation summaries | Tool catalog, MCP server state, tool permissions, invocation history |
| Data | Static data source inventory with source status, record counts, and sync state | Dataset/source inventory, sync jobs, cost/storage metrics |
| Audit | Static audit replay timeline with risk summary and evidence references | Audit event stream, replay payloads, risk levels, evidence references |
| Automation | Static automation rule list with triggers, destinations, enabled state, and last run | Automation rules, schedules, monitors, enabled state, last run |
| Settings | Static settings hub for tenant, model routing, permissions, and branding boundaries | Tenant, model routing, permissions, branding, integration settings |

## Delivery Readiness

The current frontend closeout status is stored in `frontend/src/panda/pandaFrontendManifest.json`.

| Readiness item | Current value | Meaning |
| --- | --- | --- |
| `frontendShell` | `ready` | Panda Agent shell, navigation, brand, and module routing are in place. |
| `pageContracts` | `ready` | Every first-level module has a resource/BFF/runtime field contract. |
| `mockFallback` | `ready` | Non-home modules can render with local fallback data while backend closes. |
| `apiAdapters` | `ready` | API payloads can map into Panda view models through adapter functions. |
| `visibleContractStrip` | `ready` | Pages show resource, BFF, readiness, runtime fields, and refresh state. |
| `strictBackendGate` | `pending-backend` | Strict report remains red until backend resources are API-wired. |
| `visualReviewTarget` | `http://127.0.0.1:3000/#threads` | Browser entry point for checking visible contracts and execution-workspace layout. |

## Handoff Gates

The frontend closeout and backend alignment gates are intentionally separate.

| Gate | Owner | Current state | Evidence |
| --- | --- | --- | --- |
| Frontend evidence gate | Frontend | `passed` | `npm run verify:panda`, `npm run verify:panda:adapters`, `npm run verify:panda:contracts`, `npm run verify:panda:resources`, `npm run verify:panda:dry-run`, `npm run report:panda:json`, `npm run qa:panda:json`, `npm run type-check`, `npm run build` |
| Strict backend gate | Frontend + backend | `pending-backend` | `npm run report:panda:strict` remains red until resources BFF/page APIs are wired. |

`npm run report:panda:json` exposes this split as `frontendCompletion` and `backendAlignmentBlockers`, and it exposes `modulePageStructure.resourceHooks`/`resourceTypes` so backend alignment can see which focused hook and explicit `*PageResources` type each standard module page consumes. `npm run plan:panda:json` exposes the same completion payload as `frontendCompletionEvidence`, while keeping `frontendCompletion` as the boundary-state table. A red strict report during frontend closeout should be read as a backend alignment blocker when `frontendCompletion.status` remains `passed`.

## Backend Alignment Handoff

`npm run report:panda`, `npm run report:panda:json`, `npm run plan:panda`, and `npm run plan:panda:json` all expose the same `backendAlignmentHandoff` payload. The payload is built in `frontend/scripts/panda-closeout-evidence.mjs` from the manifest and route rollover plan, so backend alignment gets the same command list, BFF flag, endpoint, and pending-route list from both report and plan commands.

| Field | Source of truth | Current meaning |
| --- | --- | --- |
| `frontendOwnedCommands` | `frontend/src/panda/pandaFrontendManifest.json` | Frontend commands that should stay green during backend closeout: `npm run verify:panda`, focused Panda probes, JSON report/QA, `npm run type-check`, and `npm run build`. |
| `backendOwnedCommands` | `frontend/src/panda/pandaFrontendManifest.json` | Commands that become final gates after backend alignment, especially `npm run report:panda:strict` and the backend workbench compile check. |
| `handoffRule` | `frontend/src/panda/pandaFrontendManifest.json` | Frontend closeout can pass while `strictBackendGate` remains `pending-backend`; strict mode turns green only after resources BFF/page APIs are wired. |
| `resourcesBffFlag` | `frontend/src/panda/pandaFrontendManifest.json` | Keep `VITE_PANDA_RESOURCES_BFF=false` until the aggregate resources endpoint returns a validated `ApiPandaResourceSnapshot`. |
| `resourcesBffEndpoint` | `frontend/src/panda/pandaFrontendManifest.json` | The planned aggregate endpoint is `/api/v1/workbench/resources`. |
| `pendingRouteIds` | `frontend/src/panda/pageResourceContracts.ts` through `frontend/scripts/panda-route-rollover-plan.mjs` | The 11 non-home routes that remain `mock-ready` until page APIs or the aggregate resources BFF are wired. |
| `backendAlignmentBlockers.pendingRoutes` | `frontend/scripts/panda-route-rollover-plan.mjs` through `frontend/scripts/panda-closeout-evidence.mjs` | Per-route backend handoff rows preserve endpoint, Panda view resources, backend API resources, runtime fields, and API needs. |

The verifier requires the human-readable report, JSON report, closeout plan, and this document to keep these handoff fields visible. If backend alignment changes the route rollout order or the BFF shape, update the manifest/contracts first, then let the scripts regenerate the handoff view.

closeout pending routes must keep API resources and API needs visible in the report handoff rows, not only route ids and display resources.

## Frontend Closeout Scope

The frontend stream remains intentionally non-blocking while backend closeout continues. The manifest records the current closeout metadata under `frontendCloseout`, `visualReviewTargets`, and `nextFrontendTasks`.

| Area | Current frontend rule |
| --- | --- |
| Safe edit scope | Keep closeout work inside `frontend/src/panda/**`, Panda scripts, and this alignment document unless a later backend alignment task explicitly needs more. |
| Backend dependency | Non-home modules stay `mock-ready` until the resources BFF or page-specific BFF endpoints return stable data. |
| Blocked scope | Approval policy, sandbox execution policy, auth, secrets, and high-risk backend execution logic remain backend-owned. |
| Visual evidence | Use the manifest `visualReviewTargets` for browser screenshots: home, threads, workflows, audit, and mobile settings. |
| Next tasks | `nextFrontendTasks` tracks visual review, resources BFF dry run, page API rollover, and accessibility pass. |

## Accessibility QA Evidence

The current accessibility pass is recorded in `frontend/src/panda/pandaFrontendManifest.json` under `accessibilityEvidence`.

| Item | Evidence |
| --- | --- |
| Keyboard focus | Panda-scoped `:focus-visible` ring covers buttons, inputs, textareas, selects, and tabindex targets. |
| Skip link | Shell exposes a `跳到主工作区` link targeting `#panda-main-content`. |
| Active navigation | Main navigation exposes `aria-current="page"` on the active module. |
| Main landmark | `#panda-main-content` exposes the active workspace label. |
| Live status | Mobile status row uses `aria-live="polite"`. |
| Runtime semantics | Status dots expose readable `aria-label` text; progress bars expose `aria-valuetext`. |
| Action labels | Right rail refresh and rail-card actions expose contextual labels. |
| Browser proof | Browser verified the skip link targets `#panda-main-content`, workflow navigation keeps `aria-current=工作流`, the main landmark updates to `工作流 工作区`, and progressbar/status-dot semantics are present. |
| Screenshot directory | `C:\Users\canqu\AppData\Local\Temp\panda-a11y-qa-1781026693295` |

## Visual QA Evidence

The current visual QA result is recorded in `frontend/src/panda/pandaFrontendManifest.json` under `visualReviewEvidence`.

| Item | Evidence |
| --- | --- |
| Browser | Codex In-app Browser |
| Dev server | `http://127.0.0.1:3000` |
| Routes checked | home, threads, workflows, audit, settings |
| Desktop coverage | 1440x960 and 1728x1080 targets |
| Mobile coverage | settings at 390x844 |
| Interaction proof | Home task composer accepts input, then navigation to `#workflows` with `aria-current=工作流` |
| Screenshot directory | `C:\Users\canqu\AppData\Local\Temp\panda-visual-qa-1781026152103` |
| Console notes | No framework error overlay or console error; local dev browser reported non-blocking long-task warnings. |
| Layout fix verified | Topbar status text stayed single-line with ellipsis after the desktop layout fix. |

## Scripted QA Evidence

The repeatable frontend QA entry point is `frontend/scripts/panda-qa-smoke.mjs`.

| Command | Purpose |
| --- | --- |
| `npm run qa:panda` | Runs static semantic probes and route reachability checks for the manifest visual-review targets when `http://127.0.0.1:3000` is available. |
| `npm run qa:panda:json` | Emits the same result as JSON for handoff reports or automation. |
| `npm run qa:panda:browser` | Optional Playwright screenshot pass. If Playwright is not installed, it reports a skip reason unless `--require-browser` is used directly. |
| `frontend/scripts/panda-alignment-context.mjs` | Owns the shared script context consumed by the alignment report and closeout plan: manifest, page contracts, resource key pairs, module structure, and route rollover state. |
| `frontend/scripts/panda-closeout-evidence.mjs` | Owns shared closeout evidence consumed by the alignment report and closeout plan: frontend boundary, frontend completion, and backend alignment blockers. |
| `frontend/scripts/panda-contract-parser.mjs` | Owns shared Panda page resource contract parsing used by the shared alignment context. |
| `frontend/scripts/panda-script-utils.mjs` | Owns shared Panda script helpers used by alignment reports, closeout plans, resource contract probes, QA smoke checks, resources dry-run probes, and workbench verification. |
| `frontend/scripts/panda-ts-probe-utils.mjs` | Owns shared temporary TypeScript-to-ESM probe helpers used by executable Panda validation probes. |
| `frontend/scripts/panda-workbench-verify-config.mjs` | Owns the Panda verifier file inventory and first-level page list consumed by `npm run verify:panda`. |
| `npm run verify:panda:components` | Checks shared Panda component primitive ownership, compatibility exports, accessibility primitives, runtime metadata display, and workflow evidence rows. |
| `npm run verify:panda:adapters` | Runs executable adapter behavior checks against `src/panda/api/adapters.ts`, including role-card `ApiAgentRolePreset -> AgentRolePreset` mapping. |
| `npm run verify:panda:adapters:json` | Emits the adapter behavior result as JSON for handoff reports or automation. |
| `npm run verify:panda:contracts` | Checks that Panda resource keys, mock-ready contract field completeness, closeout pending route handoff fields, standard module page content keys/page fields, standard module page `page -> hook -> PageResources` type bindings, and route readiness do not drift across the manifest, shared key pairs, validation, adapters, fallback snapshots, page contracts, `modulePageStructure`, and `resourceReadiness.ts`. |
| `npm run verify:panda:contracts:json` | Emits the resource contract consistency result as JSON for handoff reports or automation. |
| `npm run verify:panda:resources` | Runs the executable resources BFF validation probe against `src/panda/api/resourcesValidation.ts`. |
| `npm run verify:panda:resources:json` | Emits the resources validation probe as JSON for handoff reports or automation. |
| `npm run verify:panda:dry-run` | Runs the shared representative aggregate resources BFF dry-run fixture from `resourceSnapshotFixtures.ts` through validation and adapter mapping, validates every mapped runtime object against the frontend `RuntimeMetadata` shape, verifies the aggregate and home activity fixtures carry every shared `pandaCoreRuntimeFields` API field, validates the shared home activity runtime fixture through `mapActivityItem()`, then verifies default import safety, default-disabled BFF config, explicit opt-in config, bootstrap loader behavior, and `loadPandaResources()` mock/api/error fallback behavior without turning on the real BFF flag by default. |
| `npm run verify:panda:dry-run:json` | Emits the dry-run fixture result as JSON for handoff reports or automation. |

The default QA command is intentionally safe during backend closeout. If the dev server is not running, the route check is marked skipped while static probes still verify the skip link, main landmark, active navigation, focus styling, status labels, progress semantics, resources validation probe wiring, contract consistency wiring, adapter behavior wiring including role-card DTO mapping, and the shared resources dry-run fixtures including cross-resource runtime metadata, runtime shape stability, core runtime API field coverage, home activity runtime metadata, default import safety, BFF config/bootstrap coverage, and `loadPandaResources()` fallback coverage.

## Minimum Resource Shapes

These are frontend-facing shapes. Backend can expose them directly or through a BFF adapter.

```ts
type StatusTone = "success" | "warning" | "danger" | "neutral";

type RuntimeMetadata = {
  status: string;
  riskLevel: StatusTone;
  progress: number;
  ownerAgent: string;
  updatedAt: string;
  evidenceRefs: string[];
};

type ApiAgentRolePreset = {
  id?: string;
  name?: string;
  tagline?: string;
  description?: string;
  abilities?: string[];
  tools?: string[];
  default_permissions?: string[];
  icon?: "briefcase" | "palette" | "code" | "finance" | "camera" | "pen" | "cart" | "scale" | "megaphone" | "headset";
  portrait_key?: "ceo" | "designer" | "engineer" | "finance" | "director" | "screenwriter" | "procurement" | "legal" | "media-operator" | "support";
  tone?: StatusTone;
};

type ThreadSummary = {
  id: string;
  title: string;
  project: string;
  status: string;
  owner_agent: string;
  progress: number;
  updated_at: string;
  runtime?: RuntimeMetadata;
};

type AgentRunDetail = {
  id: string;
  thread_id: string;
  status: string;
  risk_level: StatusTone;
  owner_agent: string;
  plan_steps: Array<{ id: string; title: string; status: string; evidence_refs: string[] }>;
  terminal_events: Array<{ id: string; text: string; created_at: string }>;
  file_changes: Array<{ path: string; change_type: string; risk_level: StatusTone }>;
  artifacts: Array<{ id: string; title: string; kind: string; url?: string }>;
  audit_events: Array<{ id: string; title: string; risk_level: StatusTone; evidence_refs: string[] }>;
};

type WorkflowRunSummary = {
  id: string;
  name: string;
  state: string;
  progress: number;
  owner: string;
  tone: StatusTone;
};

type ApprovalItem = {
  id: string;
  title: string;
  status: "pending" | "approved" | "rejected" | "expired";
  risk_level: StatusTone;
  requested_by: string;
  evidence_refs: string[];
};
```

## Proposed BFF Endpoint Matrix

These endpoints are frontend-facing suggestions for the post-closeout alignment pass. They should aggregate existing backend capabilities without moving approval, sandbox, secret, or high-risk policy into the browser.

| Endpoint | Primary pages | Frontend resource names |
| --- | --- | --- |
| `GET /api/v1/workbench/home` | Home, right rail | `WorkbenchHome`, `WorkbenchActivityItem`, `WorkbenchWorkflowRun` |
| `GET /api/v1/workbench/threads` | Threads, Tasks | `ThreadSummary`, `AgentRunDetail`, `TaskSummary` |
| `GET /api/v1/workbench/projects` | Projects | `ProjectItem`, Git/worktree summary, PR status |
| `GET /api/v1/workbench/workflows` | Workflows, Automation | `WorkflowRunSummary`, workflow nodes, automation rules |
| `GET /api/v1/workbench/agents` | Agents | `AgentProfile`, agent team, handoff state |
| `GET /api/v1/workbench/knowledge` | Knowledge, Data | `KnowledgeSource`, retrieval summary, ingestion state |
| `GET /api/v1/workbench/tools` | Tools/MCP | `ToolCapability`, MCP server state, tool invocation history |
| `GET /api/v1/workbench/audit` | Audit, Settings risk panels | `AuditEvent`, `ApprovalItem`, evidence references |
| `GET /api/v1/workbench/settings` | Settings | tenant, model routing, branding, readonly policy status |
| `GET /api/v1/workbench/resources` | Non-home Panda modules | aggregate `ApiPandaResourceSnapshot`; optional single-call BFF after backend closeout |

## Runtime Fields

Each page contract in `frontend/src/panda/pageResourceContracts.ts` declares `runtimeFields`. Shared runtime field constants live in `frontend/src/panda/resourceRuntimeFields.ts`. These are the backend-facing fields the frontend expects to map into `RuntimeMetadata`.

| Field | Frontend mapping | Purpose |
| --- | --- | --- |
| `status` | `runtime.status` | Shows running, failed, waiting, approved, indexed, enabled, or readonly state. |
| `risk_level` | `runtime.riskLevel` | Drives warning/danger/success/neutral visual treatment without frontend policy decisions. |
| `progress` | `runtime.progress` | Drives task, workflow, thread, sync, and agent-load progress views. |
| `owner_agent` | `runtime.ownerAgent` | Shows which agent or team owns the current item. |
| `updated_at` | `runtime.updatedAt` | Supports recency, sorting, and stale-state display. |
| `evidence_refs` | `runtime.evidenceRefs` | Links UI state to audit evidence where relevant. |

## Readonly Display Model

- Panda view-model arrays and aggregate resource references that are rendered as display data should stay readonly at the type boundary. Current examples include `RuntimeMetadata.evidenceRefs`, `AuditEvent.evidenceRefs`, `AgentProfile.permissions`, `PandaWorkbenchHome` collections, `PandaResourceSnapshot` resource collections, `PandaResourceLoadResult.resources`, workspace context `resources`, resource contract arrays, and shared primitive list props.
- Panda workspace context separates readonly resource snapshots from lifecycle state; consumers should read page resources through selector hooks and refresh through the lifecycle handle rather than mutating context values.
- Standard module page resource hooks in `modulePageResourceHooks.ts` should keep returning memoized derived payloads from readonly workspace selectors, with explicit `*PageResources` return types from `modulePageResourceTypes.ts`, so module pages can consume `{ resources, count }` style view data without subscribing to unrelated lifecycle changes; `useModulePageResources.ts` remains the page-facing compatibility import, and `StandardModulePageShell` owns the shared content binding and resource-state shell for those pages.
- Standard module content in `modulePageContentCatalog.tsx` should be keyed by `PandaStandardModulePage`, each entry's `page` field should match its object key, `modulePageTypes.ts` should keep action arrays readonly, and `modulePageContent.tsx` should remain the compatibility barrel so page copy/action coverage matches the route set at compile time.
- Module fallback metadata is resolved in `moduleFallbackContent.ts` through static page maps; `ModulePage.tsx` should only consume `getModuleFallbackMeta(page)` and render `ModuleFallbackWorkspace`, not search navigation or module card arrays during render. `moduleFallback.tsx` owns the workspace composition and empty state, `moduleFallbackSurface.tsx` owns the fallback hero, capability grid, and command action primitives, and `moduleDeliverySurface.tsx` owns the module delivery surface. `moduleFallbackSurface.tsx` preserves compatibility exports for the split delivery surface.
- Mock fallback arrays in `mockExecutionResources.ts`, `mockKnowledgeResources.ts`, `mockOrganizationResources.ts`, `homeActionContent.ts`, and `moduleFallbackContent.ts` should also stay readonly so demo data follows the same display-only contract as API-backed view models.
- API DTOs may expose readonly arrays such as `evidence_refs?: readonly string[]`, `permissions?: readonly string[]`, and aggregate `ApiPandaResourceSnapshot` resource arrays; fixture exports such as `apiResourceSnapshotFixture` and `aggregateResourcesBffDryRunFixture` should be typed as `ApiPandaResourceSnapshot` so dry-run data exercises the same readonly DTO boundary. Adapters must copy or map those arrays into Panda view models instead of sharing the API array reference.
- `mapRuntimeMetadata()` and `mapAuditEvent()` are the current evidence reference copy boundary. The executable `evidence-refs-copy` adapter probe protects this behavior so response/cache reuse cannot mutate already-rendered audit evidence.
- These readonly and copy semantics are frontend display guarantees only. They do not move approval, audit, retention, or evidence ownership policy out of the backend.

## Frontend Adapter Order

1. Keep static page resource fallback data in the focused mock resource files while backend mainline closes; keep `mockResources.ts` and `mockWorkspace.ts` as compatibility barrels only.
2. Keep Panda page components on camelCase view models exported from `frontend/src/panda/types.ts`, with focused type ownership under `frontend/src/panda/types/`.
3. Map backend snake_case fields into those view models in `frontend/src/panda/api/adapters.ts`.
4. Keep risk/approval rendering data-driven from backend response fields; do not encode approval or sandbox policy in page components.
5. Route standard module page resource reads through the focused hooks in `frontend/src/panda/state/useModulePageResources.ts`; those hooks use `usePandaWorkspaceResource(key)` from `frontend/src/panda/state/PandaWorkspaceContext.tsx` while the provider uses `loadPandaResources()` until backend endpoints are ready.
6. Keep resource lifecycle metadata in the provider: `status`, `source`, `error`, `refreshedAt`, and `refresh`.
7. Replace the provider/resource client internals one page at a time when BFF endpoints become stable; page components should keep consuming Panda view models.
8. Use `PandaLoadingState`, `PandaEmptyState`, and `PandaErrorState` for loading, empty, permission-denied, failed, and mock-fallback states.
9. Keep `npm run type-check`, `npm run build`, and hash deep-link smoke checks green after each page.

## Page Registry

- `frontend/src/panda/pageRegistry.tsx` is the route-to-page ownership point for all non-home Panda modules.
- The registry derives valid page ids from `navItems`, exports `isPandaPage()` for hash route validation, and exports `getPandaPageComponent()` for module rendering.
- `HomePage` remains explicitly composed in `PandaAgentApp.tsx` because it owns the task composer surface; home BFF/mock fallback state is provided by `usePandaHomeWorkbench()`.
- Adding a new first-level module requires updating `PandaPage`, `navItems`, `pandaPageComponents`, and the related `PandaResourceSnapshot` slice before the route is considered complete.
- `npm run verify:panda` checks that every non-home nav id has a registered page component and that route validation stays registry-driven.

## Resource Contracts

- `frontend/src/panda/pageResourceContracts.ts` is the frontend-owned BFF alignment ledger while backend mainline closes.
- `frontend/src/panda/resourceContracts.ts` is a compatibility barrel that re-exports the focused contract modules for existing imports.
- `frontend/src/panda/resourceContractTypes.ts` owns `PandaResourceKey`, `PandaRuntimeField`, and `PandaPageResourceContract`.
- `frontend/src/panda/resourceRuntimeFields.ts` owns `pandaCoreRuntimeFields`.
- `frontend/src/panda/api/resourceKeys.ts` maps every Panda view resource key to its aggregate BFF API key. Backend-facing aggregate payload keys should match the `apiKeys` side of this mapping, while React pages continue consuming the `viewKeys` side.
- `frontend/src/panda/api/resourceReadiness.ts` derives a route-level readiness list from `pageResourceContracts.ts`; backend alignment should use `pandaRouteReadiness` for route rollout order, `apiResources` for backend resource names, and `pandaBackendAlignmentReadiness` for strict-gate requirements.
- `npm run report:panda:json` exposes `routeApiResourcesEvidence` with `routeApiResources`, `boundaryApiResources`, `unknownRouteApiResources`, and `missingRouteApiResources`; the same check is also recorded as `frontendCompletion.evidence[id=route-api-resources-evidence]`, so closeout evidence proves route API keys stay aligned before backend BFF wiring.
- Every `PandaPage` has one `PandaPageResourceContract` with `resourceKeys`, `bffEndpoint`, `readiness`, and `apiNeeds`.
- Every `mock-ready` contract must keep its object key aligned to `page` and declare a BFF endpoint, at least one resource key, at least one runtime field, and at least one API need before it can be treated as frontend-ready for backend alignment.
- Every `PandaPageResourceContract` also records `runtimeFields`, so the report can show exactly which runtime fields the backend must supply for each route.
- `resourceKeys` must refer to keys on `PandaResourceSnapshot`; standard module pages should continue reading those slices through `useModulePageResources.ts`, while custom workspaces may use `usePandaWorkspaceResource(key)` directly when their layout needs a bespoke selector.
- `readiness: "api-wired"` means the page already has a real frontend API path. `readiness: "mock-ready"` means the page is UI-complete enough for design review but still waits for backend endpoint alignment.
- The contract records suggested frontend-facing BFF endpoints only. It does not create or move backend approval, sandbox, auth, secret, or execution policy into the browser.
- `npm run verify:panda` checks that all first-level pages have contracts, all resource snapshot keys are referenced by contracts, and all planned BFF endpoints remain visible.
- `npm run verify:panda` also checks that `resourceKeys.ts` remains a pure API boundary and that the known camelCase/snake_case mappings are visible to handoff reports.
- `npm run verify:panda` also checks that `resourceReadiness.ts` remains declarative, derives from `pandaPageResourceContracts`, records the resources BFF flag/endpoint, and keeps approval, sandbox, auth, secret, and execution policy backend-owned.
- `npm run verify:panda` also checks that the normal report is closeout-safe and that `npm run report:panda:strict` still fails until backend resources are fully API-wired.
- `PageContractStrip` in `frontend/src/panda/components/pageContractPrimitives.tsx` renders those contracts inside module pages so reviewers can see whether a page is API-wired or still using mock data.
- `PageHeading` in `frontend/src/panda/components/pageChromePrimitives.tsx` accepts a `page` prop for standard modules. Custom workspace pages can render `PageContractStrip` directly through the `common.tsx` compatibility export when their layout does not use `PageHeading`.
- `PandaResourceState` wraps resource-dependent page regions and standardizes loading, error, and empty rendering for future API responses that may return empty slices.
- `frontend/src/panda/api/resourcesClient.ts` keeps `loadPandaResources()` and compatibility exports for existing callers while preserving mock fallback behavior.
- `frontend/src/panda/api/resourcesApiLoader.ts` exposes `setPandaResourcesApiLoader()` as the future BFF injection point for non-home resources.
- `createPandaResourcesApiLoader()` accepts a narrow `PandaResourcesHttpClient` so the real BFF client can be wired after backend closeout without giving pages direct API access.
- `frontend/src/panda/api/resourcesHttpClient.ts` provides `createPandaResourcesFetchClient()` for the future aggregate `GET /api/v1/workbench/resources` BFF. It is intentionally not registered by default while backend mainline is closing.
- `frontend/src/panda/api/bootstrapResources.ts` wires the aggregate resources BFF only when `VITE_PANDA_RESOURCES_BFF=true`; `.env.example` keeps the flag at `false` until the backend endpoint is delivered.
- The visible contract strip is an alignment aid only; backend remains the source of truth for policy, risk, approval, sandbox, and execution behavior.

## Adapter Boundary

- `frontend/src/panda/api/adapters.ts` is the compatibility export layer for pure frontend mapping; it must not call axios, mutate global state, or import React.
- `frontend/src/panda/api/apiContracts.ts` is the compatibility export layer for API DTO types.
- `frontend/src/panda/api/homeApiContracts.ts` owns `ApiWorkbenchHome`, `ApiWorkbenchActivityItem`, and `ApiWorkbenchWorkflowRun`.
- `frontend/src/panda/api/executionApiContracts.ts` owns API DTOs for tasks, threads, and workflow nodes.
- `frontend/src/panda/api/organizationApiContracts.ts` owns API DTOs for projects and agents.
- `frontend/src/panda/api/knowledgeApiContracts.ts` owns API DTOs for knowledge sources, data sources, and tool capabilities.
- `frontend/src/panda/api/governanceApiContracts.ts` owns API DTOs for audit events, automation rules, and settings sections.
- `frontend/src/panda/api/resourceApiContracts.ts` remains the compatibility barrel for resource item DTOs.
- `frontend/src/panda/api/snapshotApiContracts.ts` owns the aggregate `ApiPandaResourceSnapshot` shape used by the resources BFF.
- `frontend/src/panda/api/runtimeMapping.ts` owns `ApiRuntimeMetadata`; resource API DTO files attach it to resource contracts so `status`, `risk_level`, `progress`, `owner_agent`, `updated_at`, and `evidence_refs` stay centralized.
- `frontend/src/panda/api/homeAdapters.ts` owns home/workbench activity and workflow-run mapping; both activity rows and workflow runs attach shared runtime metadata for the right rail.
- `frontend/src/panda/api/executionResourceAdapters.ts` owns task, thread, and workflow-node mapping.
- `frontend/src/panda/api/organizationResourceAdapters.ts` owns project and agent mapping.
- `frontend/src/panda/api/knowledgeResourceAdapters.ts` owns knowledge source, data source, and tool capability mapping.
- `frontend/src/panda/api/governanceResourceAdapters.ts` owns audit event, automation rule, and settings section mapping.
- `frontend/src/panda/api/resourceItemAdapters.ts` remains a compatibility barrel for individual resource row/card mapping exports.
- `frontend/src/panda/api/resourceSnapshotAdapter.ts` owns aggregate `ApiPandaResourceSnapshot` to Panda view-resource mapping.
- `frontend/src/panda/api/resourceKeys.ts` is a pure key-boundary module. It exports `pandaResourceKeyPairs`, `pandaViewResourceKeys`, `pandaApiResourceKeys`, and `pandaApiResourceKeySet`; validation and handoff checks should use this file instead of duplicating resource key lists.
- `frontend/scripts/verify-panda-adapters.mjs` executes adapter behavior checks without adding a frontend test framework. It verifies tone fallback, progress clamping, snake_case runtime metadata mapping, task runtime mapping, activity runtime mapping, and aggregate resource snapshot mapping.
- Adapter inputs represent BFF/API payloads and may use snake_case fields such as `owner_agent`, `risk_level`, `updated_at`, `evidence_refs`, `last_sync`, and `sync_state`.
- Adapter outputs must satisfy the Panda view models consumed by pages, such as `TaskSummary`, `AgentProfile`, `WorkflowItem`, `AuditEvent`, and `ToolCapability`.
- Resource adapter outputs may attach `runtime?: RuntimeMetadata`; API-backed resources should populate it from `status`, `risk_level`, `progress`, `owner_agent`, `updated_at`, and `evidence_refs`.
- `HomePage` and `RightRail` consume `PandaWorkbenchHome`; they should not import backend response types or global API methods.
- `frontend/src/panda/api/workbenchClient.ts` owns the current home API call, adapter mapping, and mock fallback. `PandaAgentApp` should call this client instead of importing global API methods directly.
- `frontend/src/panda/api/resourcesClient.ts` owns the compatibility loading contract for non-home pages. It currently returns mock data through `loadPandaResources()` and delegates focused responsibilities to the snapshot type, fallback snapshot, and API loader modules.
- `frontend/src/panda/api/resourceSnapshotTypes.ts` owns the Panda view resource snapshot/load-result types consumed by React state and page resource contracts.
- `frontend/src/panda/api/resourceFallbackSnapshot.ts` owns `getPandaResourceSnapshot()` and the static `pandaResources` fallback sourced from `mockResources.ts`.
- `frontend/src/panda/api/resourcesApiLoader.ts` owns BFF loader injection, `PandaResourcesHttpClient`, `createPandaResourcesApiLoader()`, `loadPandaResourcesFromApi()`, BFF validation, and `mapPandaResourceSnapshot()` handoff.
- `frontend/src/panda/api/resourcesValidation.ts` validates aggregate resources BFF snapshots before mapping. It rejects unknown top-level resource keys, non-array resource fields, and non-object resource items; invalid snapshot shapes fall back to mock data with an explicit error instead of silently rendering empty API-backed pages.
- `frontend/scripts/verify-panda-resource-validation.mjs` executes positive and negative checks against that validator without adding a frontend test framework. This is the lightweight proof that the BFF shape guard rejects invalid roots, non-array resource fields, invalid resource array items, and misspelled resource keys.
- `frontend/scripts/verify-panda-resource-contracts.mjs` compares manifest `apiKeys/viewKeys`, `resourceKeys.ts`, validation keys, `ApiPandaResourceSnapshot` keys, `mapPandaResourceSnapshot()` reads, `PandaResourceSnapshot` keys, fallback keys, page contract keys, mock-ready contract field completeness, closeout pending route handoff fields, standard module content key/page pairs, and standard module `page -> hook -> PageResources` type bindings. This catches resource-slice drift before backend alignment and reports missing keys on both sides of each comparison.
- Resource fixture ownership is focused: `frontend/src/panda/api/resourceAdapterFixtures.ts` owns `apiResourceSnapshotFixture`, `frontend/src/panda/api/resourceDryRunFixtures.ts` owns `aggregateResourcesBffDryRunFixture`, `frontend/src/panda/api/homeActivityFixtures.ts` owns `workbenchActivityDryRunFixture`, and `frontend/src/panda/api/resourceRuntimeFixtures.ts` owns `runtimeFixture()`. `frontend/src/panda/api/resourceSnapshotFixtures.ts` re-exports those focused fixtures and owns only the mapped/validated compatibility fixtures. `runtimeFixture()` centralizes the representative `status`, `risk_level`, `progress`, `owner_agent`, `updated_at`, and `evidence_refs` runtime fields across dry-run payloads.
- `frontend/scripts/verify-panda-resource-dry-run.mjs` validates those fixtures through `validatePandaResourceSnapshot()`, `mapPandaResourceSnapshot()`, and `mapActivityItem()`, verifies every aggregate fixture item carries the shared `pandaCoreRuntimeFields` API fields, and executes the BFF config/bootstrap path with mocked fetch. It proves that `status`, `risk_level`, `progress`, `owner_agent`, `updated_at`, and `evidence_refs` reach Panda view models across execution, organization, knowledge, governance, and right rail home activity models; that each mapped runtime object keeps the frontend `RuntimeMetadata` shape; that the bootstrap module imports safely when `import.meta.env` is unavailable to probes; that `VITE_PANDA_RESOURCES_BFF=false` leaves the loader disabled; that explicit opt-in uses the configured endpoint; and that `loadPandaResources()` returns mock fallback, mapped API resources, or mock-with-error for invalid API shapes before the real BFF flag is enabled by default.
- Non-home resource APIs should return an `ApiPandaResourceSnapshot`-compatible payload and be mapped through `mapPandaResourceSnapshot()` before reaching React state.
- `setPandaResourcesApiLoader()` may be wired to a real BFF client after backend closeout through `resourcesApiLoader.ts`; failed API loads must keep returning `{ source: "mock", error }` from `loadPandaResources()` so the UI labels degraded data instead of crashing.
- `PandaResourcesHttpClient` should be implemented by a small frontend BFF client, not by page components. Standard module pages must remain on `useModulePageResources.ts` hooks; direct `usePandaWorkspaceResource(key)` usage is reserved for shared selectors, `ThreadsPage`, home resource sections, and shell/rail components with custom layout needs.
- `createPandaResourcesFetchClient()` is the prepared fetch implementation for `GET /api/v1/workbench/resources`; do not register it until the backend endpoint exists and mainline closeout has passed.
- `VITE_PANDA_RESOURCES_BFF=false` is the default. Set it to `true` only after the aggregate BFF endpoint is present, returns `ApiPandaResourceSnapshot`, and passes the Panda verification gate.
- `frontend/src/panda/state/PandaWorkspaceContext.tsx` is the provider/resource compatibility entrypoint. Its focused implementation lives in `workspaceTypes.ts`, `workspaceProvider.tsx`, and `workspaceHooks.ts`.
- `frontend/src/panda/state/useModulePageResources.ts` remains the standard module page selector boundary and compatibility import. Its focused implementation is split across `modulePageResourceTypes.ts`, `useCountedModulePageResource.ts`, and `modulePageResourceHooks.ts`; non-home module pages should continue importing the focused page hook from `useModulePageResources.ts` instead of importing `resourcesClient.ts`, `mockWorkspace.ts`, or raw business arrays directly.
- The right rail, `ThreadsPage`, home resource sections, and selector helpers may use workspace hooks from `PandaWorkspaceContext.tsx` directly because they own custom layouts or cross-resource lifecycle state.
- Standard module pages should use the focused hook that returns only the resource slices and `count` they render, then pass `page` and `count` into `StandardModulePageShell`. Each focused hook should keep its explicit `*PageResources` type tied to `PandaResourceSnapshot` instead of importing mock data, API DTOs, or duplicate item types. Full `usePandaWorkspace()` access should be reserved for shell-level components that need lifecycle metadata such as `status`, `source`, `error`, or `refresh`.
- `PandaWorkspaceContext` should preserve the same page-facing shape when moving from mock to API: `{ resources, status, source, error, refreshedAt, refresh }`.
- Unknown or missing API fields should map to explicit safe display fallbacks, not `undefined` text in the UI.
- Progress values should be clamped to `0..100`; unknown risk tones should render as `neutral`.
- `frontend/src/panda/api/adapterFixtures.ts` exists as a typed fixture so `tsc` verifies representative adapter input/output coverage without introducing a new test framework.
- UI state rendering should stay visible and explicit: API failures may fall back to mock data, but the shell should label that degraded state instead of silently presenting demo data as live state.

## Interaction Contracts

- Task composer should eventually submit to a single frontend-facing endpoint that returns a thread/run id.
- Thread workspace needs streaming or polling for plan, terminal, file changes, artifacts, and audit evidence.
- Destructive or privileged actions must surface backend-provided approval requirements instead of encoding policy in frontend.
- Empty, loading, permission-denied, failed, and degraded-data states should be distinguishable by the API response.
- Any backend field used for risk rendering should use a small enum compatible with `StatusTone`.

## Frontend-Only Work Until Backend Closeout

- Refactor UI into maintainable components.
- Build static high-fidelity pages with mock data.
- Prepare typed adapters for future API payloads.
- Keep `npm run type-check` and `npm run build` green.
- Run `npm run verify:panda` after Panda workbench changes to check required files, adapter boundaries, nav coverage, alignment docs, and hash routes when the dev server is available.
- Run `npm run verify:panda:adapters` after changing adapter functions, task/activity runtime metadata mapping, progress/risk fallback behavior, or aggregate resource snapshot mapping.
- Run `npm run verify:panda:contracts` after changing resource keys, resource adapters, fallback snapshots, page contracts, route readiness, mock-ready contract fields, closeout pending route handoff fields, standard module page content keys/page fields, standard module `page -> hook -> PageResources` type bindings, or aggregate BFF validation.
- Run `npm run verify:panda:resources` after changing aggregate BFF validation, resource adapters, or resource client fallback behavior.
- Run `npm run qa:panda` after layout or accessibility changes. Use `npm run qa:panda:browser` only when the local environment has Playwright available for screenshot capture.
- Avoid staging or modifying unrelated backend mainline files.
