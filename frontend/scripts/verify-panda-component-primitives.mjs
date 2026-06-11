import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const standaloneRoot = process.cwd()

function standaloneAssert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

function standaloneRead(relativePath) {
  return readFileSync(resolve(standaloneRoot, relativePath), 'utf8')
}

export function verifyPandaComponentPrimitives({ assert, read }) {
  const common = read('src/panda/components/common.tsx')
  const pageChromePrimitives = read('src/panda/components/pageChromePrimitives.tsx')
  const pageContractPrimitives = read('src/panda/components/pageContractPrimitives.tsx')
  const resourceState = read('src/panda/components/resourceState.tsx')
  const statePanelPrimitives = read('src/panda/components/statePanelPrimitives.tsx')
  const modulePagePrimitives = read('src/panda/components/modulePagePrimitives.tsx')
  const modulePageActionPrimitives = read('src/panda/components/modulePageActionPrimitives.tsx')
  const runtimePrimitives = read('src/panda/components/runtimePrimitives.tsx')
  const metricPrimitives = read('src/panda/components/metricPrimitives.tsx')
  const runtimeMetaPrimitives = read('src/panda/components/runtimeMetaPrimitives.tsx')
  const tagListPrimitives = read('src/panda/components/tagListPrimitives.tsx')
  const statusPrimitives = read('src/panda/components/statusPrimitives.tsx')
  const progressPrimitives = read('src/panda/components/progressPrimitives.tsx')
  const workspacePrimitives = read('src/panda/components/workspacePrimitives.tsx')
  const workspaceInfoPrimitives = read('src/panda/components/workspaceInfoPrimitives.tsx')
  const workspaceTablePrimitives = read('src/panda/components/workspaceTablePrimitives.tsx')
  const workspaceCardPrimitives = read('src/panda/components/workspaceCardPrimitives.tsx')
  const workspaceResourceCardPrimitives = read('src/panda/components/workspaceResourceCardPrimitives.tsx')
  const workspaceListCardHeaderPrimitives = read('src/panda/components/workspaceListCardHeaderPrimitives.tsx')
  const workspaceCapabilityCardPrimitives = read('src/panda/components/workspaceCapabilityCardPrimitives.tsx')
  const workspaceLayoutPrimitives = read('src/panda/components/workspaceLayoutPrimitives.tsx')
  const workspaceActivityPrimitives = read('src/panda/components/workspaceActivityPrimitives.tsx')
  const workspaceRailPrimitives = read('src/panda/components/workspaceRailPrimitives.tsx')
  const workflowPrimitives = read('src/panda/components/workflowPrimitives.tsx')
  const workflowEvidencePrimitives = read('src/panda/components/workflowEvidencePrimitives.tsx')
  const workflowNodePrimitives = read('src/panda/components/workflowNodePrimitives.tsx')
  const workflowActionPrimitives = read('src/panda/components/workflowActionPrimitives.tsx')

  for (const symbol of [
    'CapabilityMetricCard',
    'InsetInfoBlock',
    'ListCardHeader',
    'ToolCardHeader',
    'WorkspaceTable',
    'WorkspaceTableHeader',
    'InfoPairGrid',
    'AuditEventRow',
    'ExecutionStepRow',
    'FlowNodeCard',
    'ActivitySummaryRow',
    'SummaryMetricList',
    'RuntimeMetaStrip',
    'ProgressSummary',
    'ManagementRow',
    'PanelActionButton',
    'MetricStrip',
    'MiniTagList',
    'ProgressMeter',
    'SectionHeader',
    'PageActionButton',
    'ModulePageActions',
    'ModuleResourcePage',
    'StandardModulePageShell',
    'PandaStatePanel',
    'PandaLoadingState',
    'PandaEmptyState',
    'PandaErrorState',
    'PandaResourceState',
    'PageContractStrip',
  ]) {
    assert(common.includes(symbol), `Missing Panda state component: ${symbol}`)
  }

  assert(common.includes("from './runtimePrimitives'"), 'common.tsx must preserve compatibility exports from runtimePrimitives')
  assert(common.includes("from './resourceState'"), 'common.tsx must preserve compatibility exports from resourceState')
  assert(common.includes("from './workspacePrimitives'"), 'common.tsx must preserve compatibility exports from workspacePrimitives')
  assert(common.includes("from './pageChromePrimitives'"), 'common.tsx must preserve compatibility exports from pageChromePrimitives')
  assert(common.includes("from './pageContractPrimitives'"), 'common.tsx must preserve compatibility exports from pageContractPrimitives')
  assert(common.includes("from './modulePagePrimitives'"), 'common.tsx must preserve compatibility exports from modulePagePrimitives')
  assert(runtimePrimitives.includes("from './progressPrimitives'"), 'runtimePrimitives must preserve compatibility exports from progressPrimitives')
  assert(runtimePrimitives.includes("from './metricPrimitives'"), 'runtimePrimitives must preserve compatibility exports from metricPrimitives')
  assert(runtimePrimitives.includes("from './statusPrimitives'"), 'runtimePrimitives must preserve compatibility exports from statusPrimitives')
  assert(metricPrimitives.includes("from './runtimeMetaPrimitives'"), 'metricPrimitives must preserve compatibility exports from runtimeMetaPrimitives')
  assert(workspacePrimitives.includes("from './workflowPrimitives'"), 'workspacePrimitives must preserve compatibility exports from workflowPrimitives')
  assert(workspacePrimitives.includes("from './workspaceCardPrimitives'"), 'workspacePrimitives must preserve compatibility exports from workspaceCardPrimitives')
  assert(workspacePrimitives.includes("from './workspaceInfoPrimitives'"), 'workspacePrimitives must preserve compatibility exports from workspaceInfoPrimitives')
  assert(workspacePrimitives.includes("from './workspaceTablePrimitives'"), 'workspacePrimitives must preserve compatibility exports from workspaceTablePrimitives')
  assert(workspacePrimitives.includes("from './workspaceLayoutPrimitives'"), 'workspacePrimitives must preserve compatibility exports from workspaceLayoutPrimitives')
  assert(workflowPrimitives.includes("from './workflowEvidencePrimitives'"), 'workflowPrimitives must preserve compatibility exports from workflowEvidencePrimitives')
  assert(workflowPrimitives.includes("from './workflowNodePrimitives'"), 'workflowPrimitives must preserve compatibility exports from workflowNodePrimitives')
  assert(workflowPrimitives.includes("from './workflowActionPrimitives'"), 'workflowPrimitives must preserve compatibility exports from workflowActionPrimitives')

  for (const symbol of ['AuditEventRow', 'ExecutionStepRow']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must re-export workflow component: ${symbol}`)
    assert(workflowPrimitives.includes(symbol), `workflowPrimitives must preserve compatibility export for workflow evidence component: ${symbol}`)
    assert(workflowEvidencePrimitives.includes(`export function ${symbol}`), `workflowEvidencePrimitives must own shared workflow evidence component: ${symbol}`)
  }
  assert(workspacePrimitives.includes('FlowNodeCard'), 'workspacePrimitives must re-export workflow node component: FlowNodeCard')
  assert(workflowPrimitives.includes('FlowNodeCard'), 'workflowPrimitives must preserve compatibility export for workflow node component: FlowNodeCard')
  assert(workflowEvidencePrimitives.includes("from './workflowNodePrimitives'"), 'workflowEvidencePrimitives must preserve FlowNodeCard compatibility export')
  assert(!workflowEvidencePrimitives.includes('export function FlowNodeCard'), 'workflowEvidencePrimitives must keep FlowNodeCard implementation in workflowNodePrimitives')
  assert(workflowNodePrimitives.includes('export function FlowNodeCard'), 'workflowNodePrimitives must own shared workflow node component: FlowNodeCard')
  for (const symbol of ['ActionPanel', 'ManagementRow', 'PanelActionButton']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must re-export workflow component: ${symbol}`)
    assert(workflowPrimitives.includes(symbol), `workflowPrimitives must preserve compatibility export for workflow action component: ${symbol}`)
    assert(workflowActionPrimitives.includes(`export function ${symbol}`), `workflowActionPrimitives must own shared workflow action component: ${symbol}`)
  }

  for (const symbol of ['CapabilityMetricCard', 'ListCardHeader', 'ToolCardHeader']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must preserve compatibility export for workspace card component: ${symbol}`)
    assert(workspaceCardPrimitives.includes(symbol), `workspaceCardPrimitives must preserve compatibility export for workspace card component: ${symbol}`)
  }
  assert(workspaceResourceCardPrimitives.includes("from './workspaceListCardHeaderPrimitives'"), 'workspaceResourceCardPrimitives must preserve compatibility exports from workspaceListCardHeaderPrimitives')
  assert(!workspaceResourceCardPrimitives.includes('export function ListCardHeader'), 'workspaceResourceCardPrimitives must keep ListCardHeader implementation in workspaceListCardHeaderPrimitives')
  assert(workspaceListCardHeaderPrimitives.includes('export function ListCardHeader'), 'workspaceListCardHeaderPrimitives must own shared list-card header component')
  assert(workspaceResourceCardPrimitives.includes('CapabilityMetricCard'), 'workspaceResourceCardPrimitives must preserve compatibility export for CapabilityMetricCard')
  assert(workspaceResourceCardPrimitives.includes('ToolCardHeader'), 'workspaceResourceCardPrimitives must preserve compatibility export for ToolCardHeader')
  assert(workspaceCapabilityCardPrimitives.includes('export function ToolCardHeader'), 'workspaceCapabilityCardPrimitives must own shared tool-card header component')
  assert(workspaceCapabilityCardPrimitives.includes('export function CapabilityMetricCard'), 'workspaceCapabilityCardPrimitives must own shared capability metric card component')
  for (const symbol of ['InfoPairGrid', 'InsetInfoBlock']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must preserve compatibility export for workspace info component: ${symbol}`)
    assert(workspaceInfoPrimitives.includes(`export function ${symbol}`), `workspaceInfoPrimitives must own shared workspace info component: ${symbol}`)
    assert(workspaceCardPrimitives.includes(symbol), `workspaceCardPrimitives must preserve compatibility export for workspace info component: ${symbol}`)
  }
  for (const symbol of ['WorkspaceTable', 'WorkspaceTableHeader']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must preserve compatibility export for workspace table component: ${symbol}`)
    assert(workspaceTablePrimitives.includes(`export function ${symbol}`), `workspaceTablePrimitives must own shared workspace table component: ${symbol}`)
    assert(workspaceCardPrimitives.includes(symbol), `workspaceCardPrimitives must preserve compatibility export for workspace table component: ${symbol}`)
  }
  assert(workspacePrimitives.includes('ActivitySummaryRow'), 'workspacePrimitives must preserve compatibility export for workspace activity component: ActivitySummaryRow')
  assert(workspaceLayoutPrimitives.includes("from './workspaceActivityPrimitives'"), 'workspaceLayoutPrimitives must preserve compatibility export from workspaceActivityPrimitives')
  assert(!workspaceLayoutPrimitives.includes('export function ActivitySummaryRow'), 'workspaceLayoutPrimitives must keep ActivitySummaryRow implementation in workspaceActivityPrimitives')
  assert(workspaceActivityPrimitives.includes('export function ActivitySummaryRow'), 'workspaceActivityPrimitives must own shared workspace activity component: ActivitySummaryRow')
  assert(workspacePrimitives.includes('RailCard'), 'workspacePrimitives must preserve compatibility export for workspace rail component: RailCard')
  assert(workspaceLayoutPrimitives.includes("from './workspaceRailPrimitives'"), 'workspaceLayoutPrimitives must preserve compatibility export from workspaceRailPrimitives')
  assert(!workspaceLayoutPrimitives.includes('export function RailCard'), 'workspaceLayoutPrimitives must keep RailCard implementation in workspaceRailPrimitives')
  assert(workspaceRailPrimitives.includes('export function RailCard'), 'workspaceRailPrimitives must own shared workspace rail component: RailCard')
  for (const symbol of ['SectionHeader']) {
    assert(workspacePrimitives.includes(symbol), `workspacePrimitives must preserve compatibility export for workspace layout component: ${symbol}`)
    assert(workspaceLayoutPrimitives.includes(`export function ${symbol}`), `workspaceLayoutPrimitives must own shared workspace layout component: ${symbol}`)
  }
  assert(workspaceLayoutPrimitives.includes('export function WorkspacePanel'), 'workspaceLayoutPrimitives must own shared workspace layout component: WorkspacePanel')

  assert(workspaceCardPrimitives.includes("from './workspaceResourceCardPrimitives'"), 'workspaceCardPrimitives must preserve compatibility exports from workspaceResourceCardPrimitives')
  assert(workspaceListCardHeaderPrimitives.includes('flex items-center justify-between'), 'ListCardHeader must own the shared list-card header layout')
  assert(workspaceListCardHeaderPrimitives.includes('StatusDot'), 'ListCardHeader must render the shared status dot primitive')
  assert(workspaceListCardHeaderPrimitives.includes('toneLabel'), 'ListCardHeader must own readable tone labels for card status')
  assert(workspaceCapabilityCardPrimitives.includes('flex items-start justify-between gap-3'), 'ToolCardHeader must own the shared tool-card header layout')
  assert(workspaceCapabilityCardPrimitives.includes('panda-tool-icon'), 'ToolCardHeader must own the shared tool icon shell')
  assert(workspaceCapabilityCardPrimitives.includes('<ToolCardHeader icon={icon} title={title} subtitle={subtitle} tone={tone} />'), 'CapabilityMetricCard must compose ToolCardHeader')
  assert(workspaceCapabilityCardPrimitives.includes('<MetricStrip items={metrics} />'), 'CapabilityMetricCard must compose MetricStrip')
  assert(workspaceCapabilityCardPrimitives.includes('metrics: readonly MetricStripItem[]'), 'CapabilityMetricCard must type metric strip items as readonly')
  assert(workspaceInfoPrimitives.includes('items: readonly InfoPairItem[]'), 'InfoPairGrid must accept readonly info pair items')
  assert(workspaceTablePrimitives.includes('columns: readonly string[]'), 'WorkspaceTable must accept readonly table columns')
  assert(metricPrimitives.includes('items: readonly MetricStripItem[]'), 'MetricStrip must accept readonly metric strip items')
  assert(metricPrimitives.includes('items: readonly SummaryMetricItem[]'), 'SummaryMetricList must accept readonly summary metric items')
  assert(tagListPrimitives.includes('items: readonly string[]'), 'MiniTagList must accept readonly tag items')
  assert(workflowActionPrimitives.includes('items: readonly string[]'), 'ActionPanel must accept readonly action items')
  assert(workflowEvidencePrimitives.includes('evidenceRefs: readonly string[]'), 'AuditEventRow must accept readonly evidence refs')
  assert(workspaceInfoPrimitives.includes('export function InsetInfoBlock'), 'InsetInfoBlock must be owned by workspace info primitives')
  assert(workspaceInfoPrimitives.includes('rounded-lg bg-white/[0.04]'), 'InsetInfoBlock must own the shared inset info block surface')
  assert(workspaceInfoPrimitives.includes("dense ? 'p-4 text-sm text-slate-300' : 'p-4'"), 'InsetInfoBlock must centralize dense inset info styling')
  assert(workspaceTablePrimitives.includes('WorkspaceTableHeader'), 'WorkspaceTable must compose WorkspaceTableHeader')
  assert(workspaceTablePrimitives.includes('columns.map((column)'), 'WorkspaceTableHeader must render caller-provided columns')
  assert(workspaceTablePrimitives.includes('className="panda-table"'), 'WorkspaceTable must own the shared panda table shell')
  assert(workspaceTablePrimitives.includes('<tbody>{children}</tbody>'), 'WorkspaceTable must own the shared table body shell')
  assert(workspaceInfoPrimitives.includes('InfoPairItem'), 'InfoPairGrid must expose typed info pair items')
  assert(workspaceInfoPrimitives.includes('grid grid-cols-2 gap-3 text-sm'), 'InfoPairGrid must own the shared two-column info layout')
  assert(workflowEvidencePrimitives.includes('panda-audit-event'), 'AuditEventRow must own the shared audit event shell')
  assert(workflowEvidencePrimitives.includes('owner_agent: {ownerAgent}'), 'ExecutionStepRow must surface owner_agent for execution evidence')
  assert(workflowEvidencePrimitives.includes('evidence_refs: {evidenceRef}'), 'ExecutionStepRow must surface evidence_refs for execution evidence')
  assert(workflowNodePrimitives.includes('panda-flow-node'), 'FlowNodeCard must own the shared workflow node shell')
  assert(workspaceActivityPrimitives.includes('panda-avatar h-9 w-9'), 'ActivitySummaryRow must own the shared activity avatar layout')
  assert(workspaceActivityPrimitives.includes('toneLabel'), 'ActivitySummaryRow must own readable tone labels for activity status')
  assert(workspaceActivityPrimitives.includes('StatusDot'), 'ActivitySummaryRow must render the shared status dot primitive')
  assert(workspaceRailPrimitives.includes('panda-card p-4'), 'RailCard must own the shared right-rail card shell')
  assert(workspaceRailPrimitives.includes('aria-label={`${title}：${action}`}'), 'RailCard must expose contextual action labels')
  assert(runtimeMetaPrimitives.includes('evidence_refs'), 'RuntimeMetaStrip must surface evidence_refs metadata')
  assert(workflowActionPrimitives.includes('<PanelActionButton key={item} label={item} group={title} />'), 'ActionPanel must compose PanelActionButton for action items')
  assert(workflowActionPrimitives.includes('aria-label={`${group}：${label}`}'), 'PanelActionButton must expose contextual action labels')
  assert(workflowActionPrimitives.includes('className="rounded-lg bg-white/[0.04] px-3 py-2 text-left text-sm text-slate-300"'), 'PanelActionButton must own the shared panel action button styling')
  assert(workflowActionPrimitives.includes('panda-management-row'), 'ManagementRow must own the shared management row layout')
  assert(workspaceLayoutPrimitives.includes('mb-4 flex items-center gap-3'), 'SectionHeader must own the shared section heading layout')
  assert(workflowActionPrimitives.includes('RuntimeMetadata'), 'ManagementRow must accept Panda runtime metadata')
  assert(workflowActionPrimitives.includes('RuntimeMetaStrip'), 'ManagementRow must render runtime metadata through RuntimeMetaStrip')
  assert(workflowActionPrimitives.includes('<RuntimeMetaStrip runtime={runtime} risk={tone} />'), 'ManagementRow must pass runtime metadata into RuntimeMetaStrip')
  assert(!workflowActionPrimitives.includes('runtime?.evidenceRefs.length'), 'ManagementRow must not duplicate evidence rendering outside RuntimeMetaStrip')
  assert(pageChromePrimitives.includes('export function PageHeading'), 'pageChromePrimitives must own PageHeading')
  assert(pageChromePrimitives.includes('export function PageActionButton'), 'pageChromePrimitives must own PageActionButton')
  assert(pageChromePrimitives.includes('React.cloneElement(icon'), 'PageActionButton must normalize page action icons through React.cloneElement')
  assert(pageChromePrimitives.includes("'aria-hidden': 'true'"), 'PageActionButton must hide decorative page action icons from assistive tech')
  assert(pageChromePrimitives.includes("primary ? 'panda-command-primary' : ''"), 'PageActionButton must centralize primary action styling')
  assert(pageChromePrimitives.includes('PageContractStrip page={page}'), 'PageHeading must compose the visible page contract strip')
  assert(pageContractPrimitives.includes('export function PageContractStrip'), 'pageContractPrimitives must own PageContractStrip')
  assert(pageContractPrimitives.includes('pandaPageResourceContracts'), 'PageContractStrip must render Panda resource contracts')
  assert(pageContractPrimitives.includes('usePandaWorkspaceLifecycle'), 'PageContractStrip must show Panda workspace lifecycle metadata through the lifecycle hook')
  assert(!pageContractPrimitives.includes('usePandaWorkspace()'), 'Page contract primitives must not consume the full workspace context directly')
  assert(pageContractPrimitives.includes('contract.runtimeFields.join'), 'PageContractStrip must show Panda runtime field contracts')
  assert(modulePagePrimitives.includes("from './modulePageActionPrimitives'"), 'modulePagePrimitives must preserve compatibility exports from modulePageActionPrimitives')
  assert(!modulePagePrimitives.includes('export function ModulePageActions'), 'modulePagePrimitives must keep ModulePageActions implementation in modulePageActionPrimitives')
  assert(modulePageActionPrimitives.includes('export type ModulePageAction'), 'modulePageActionPrimitives must own the module page action type')
  assert(modulePageActionPrimitives.includes('export function ModulePageActions'), 'modulePageActionPrimitives must own module page action rendering')
  assert(modulePageActionPrimitives.includes('<PageActionButton'), 'ModulePageActions must render shared page action buttons')
  assert(modulePageActionPrimitives.includes('actions: readonly ModulePageAction[]'), 'ModulePageActions must keep readonly action props')
  assert(modulePagePrimitives.includes('<PageHeading'), 'ModuleResourcePage must render the shared page heading')
  assert(modulePagePrimitives.includes('<PandaResourceState'), 'ModuleResourcePage must render shared resource state handling')
  for (const symbol of ['PandaStatePanel', 'PandaLoadingState', 'PandaEmptyState', 'PandaErrorState']) {
    assert(statePanelPrimitives.includes(`export function ${symbol}`), `statePanelPrimitives must own pure state panel component: ${symbol}`)
    assert(resourceState.includes(symbol), `resourceState must preserve compatibility export for state panel component: ${symbol}`)
  }
  assert(resourceState.includes('export function PandaResourceState'), 'resourceState must own shared resource lifecycle component: PandaResourceState')
  assert((statePanelPrimitives.match(/<PandaStatePanel/g) ?? []).length === 3, 'Loading, empty, and error states must compose PandaStatePanel')
  assert(resourceState.includes("status === 'loading'"), 'PandaResourceState must render loading state from workspace lifecycle')
  assert(resourceState.includes("status === 'error'"), 'PandaResourceState must render error state from workspace lifecycle')
  assert(resourceState.includes('count === 0'), 'PandaResourceState must render empty state for empty resource slices')
  assert(statePanelPrimitives.includes('action?: React.ReactNode'), 'PandaErrorState must support an optional recovery action')
  assert(resourceState.includes('const { status, error, refresh } = usePandaWorkspaceLifecycle()'), 'PandaResourceState must read refresh from the workspace lifecycle hook')
  assert(resourceState.includes('onClick={() => void refresh()}'), 'PandaResourceState error action must retry the resource refresh')
  assert(resourceState.includes('重新同步资源'), 'PandaResourceState must expose a user-facing resource retry action')

  for (const symbol of ['SummaryMetricList', 'MetricStrip']) {
    assert(metricPrimitives.includes(`export function ${symbol}`), `Missing Panda metric primitive: ${symbol}`)
    assert(runtimePrimitives.includes(symbol), `runtimePrimitives must preserve compatibility export for metric primitive: ${symbol}`)
  }
  assert(runtimeMetaPrimitives.includes('export function RuntimeMetaStrip'), 'runtimeMetaPrimitives must own RuntimeMetaStrip')
  assert(metricPrimitives.includes('RuntimeMetaStrip'), 'metricPrimitives must preserve compatibility export for RuntimeMetaStrip')
  assert(runtimePrimitives.includes('RuntimeMetaStrip'), 'runtimePrimitives must preserve compatibility export for RuntimeMetaStrip')
  assert(tagListPrimitives.includes('export function MiniTagList'), 'tagListPrimitives must own MiniTagList')
  assert(metricPrimitives.includes('MiniTagList'), 'metricPrimitives must preserve compatibility export for MiniTagList')
  assert(runtimePrimitives.includes('MiniTagList'), 'runtimePrimitives must preserve compatibility export for MiniTagList')
  assert(statusPrimitives.includes('export function StatusDot'), 'statusPrimitives must own StatusDot')
  assert(runtimePrimitives.includes('StatusDot'), 'runtimePrimitives must preserve compatibility export for StatusDot')
  for (const symbol of ['SummaryMetricList', 'RuntimeMetaStrip', 'MetricStrip', 'MiniTagList', 'StatusDot']) {
    assert(runtimePrimitives.includes(symbol), `Missing Panda runtime compatibility export: ${symbol}`)
  }
  for (const symbol of ['ProgressSummary', 'ProgressMeter']) {
    assert(progressPrimitives.includes(`export function ${symbol}`), `Missing Panda progress primitive: ${symbol}`)
    assert(runtimePrimitives.includes(symbol), `runtimePrimitives must preserve compatibility export for progress primitive: ${symbol}`)
  }

  assert(metricPrimitives.includes('SummaryMetricItem'), 'SummaryMetricList must expose typed summary metric items')
  assert(metricPrimitives.includes('space-y-4 text-sm'), 'SummaryMetricList must own the shared summary metric layout')
  assert(runtimeMetaPrimitives.includes('owner_agent'), 'RuntimeMetaStrip must surface owner_agent metadata')
  assert(runtimeMetaPrimitives.includes('updated_at'), 'RuntimeMetaStrip must surface updated_at metadata')
  assert(runtimeMetaPrimitives.includes('risk_level'), 'RuntimeMetaStrip must surface risk_level metadata')
  assert(runtimeMetaPrimitives.includes('evidence_refs'), 'RuntimeMetaStrip must surface evidence_refs metadata')
  assert(runtimeMetaPrimitives.includes('runtime?.ownerAgent ?? owner'), 'RuntimeMetaStrip must support mock fallback owner data')
  assert(runtimeMetaPrimitives.includes('runtime?.updatedAt ?? updatedAt'), 'RuntimeMetaStrip must support mock fallback updated data')
  assert(progressPrimitives.includes('ProgressMeter value={value}'), 'ProgressSummary must compose the accessible ProgressMeter')
  assert(tagListPrimitives.includes('panda-mini-tag'), 'MiniTagList must own the shared mini tag layout')
  assert(metricPrimitives.includes("from './tagListPrimitives'"), 'metricPrimitives must preserve compatibility exports from tagListPrimitives')
  assert(tagListPrimitives.includes('export function KeyValueList'), 'tagListPrimitives must own KeyValueList')
  assert(tagListPrimitives.includes('export function MiniTagList'), 'tagListPrimitives must own MiniTagList')
  assert(tagListPrimitives.includes('flex items-center justify-between gap-3'), 'KeyValueList must own the shared key-value row layout')
  assert(metricPrimitives.includes('MetricStripItem'), 'MetricStrip must expose typed metric strip items')
  assert(progressPrimitives.includes('role="progressbar"'), 'ProgressMeter must expose accessible progress semantics')
  assert(progressPrimitives.includes('aria-label={ariaLabel}'), 'ProgressMeter must expose a caller-provided accessible label')
  assert(progressPrimitives.includes('aria-valuetext={`${clampedValue}%`}'), 'ProgressMeter must expose readable progress value text')
  assert(statusPrimitives.includes('role="img"'), 'StatusDot must expose status tone as an accessible status image')
  assert(statusPrimitives.includes('aria-label={readableLabel}'), 'StatusDot must expose a readable status label')
  assert(!runtimePrimitives.includes('usePandaWorkspace'), 'Runtime primitives must stay independent from workspace context')
  assert(workflowEvidencePrimitives.includes('MiniTagList items={evidenceRefs} prefix="#"'), 'AuditEventRow must render audit evidence refs through MiniTagList')

  return {
    common,
    pageChromePrimitives,
    pageContractPrimitives,
    modulePagePrimitives,
    modulePageActionPrimitives,
    metricPrimitives,
    runtimeMetaPrimitives,
    tagListPrimitives,
    progressPrimitives,
    resourceState,
    statePanelPrimitives,
    runtimePrimitives,
    statusPrimitives,
    workspaceCardPrimitives,
    workspaceResourceCardPrimitives,
    workspaceListCardHeaderPrimitives,
    workspaceCapabilityCardPrimitives,
    workspaceActivityPrimitives,
    workspaceRailPrimitives,
    workspaceInfoPrimitives,
    workspaceTablePrimitives,
    workspaceLayoutPrimitives,
    workflowActionPrimitives,
    workflowEvidencePrimitives,
    workflowNodePrimitives,
    workspacePrimitives,
    workflowPrimitives,
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  verifyPandaComponentPrimitives({
    assert: standaloneAssert,
    read: standaloneRead,
  })
  console.log('Panda component primitives: passed')
}
