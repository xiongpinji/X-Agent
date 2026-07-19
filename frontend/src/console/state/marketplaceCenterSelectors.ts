import type { ConsoleState } from "./consoleReducer";

export function selectMarketplaceCenterOverviewData(state: ConsoleState) {
  const api = state.marketplaceCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      totalCapabilities: api.primary.total_capabilities,
      publishedCapabilities: api.primary.published_capabilities,
      installedCapabilities: api.primary.installed_capabilities,
      pendingApprovals: api.primary.pending_approvals,
      riskLevel: api.primary.risk_level,
      linkedCapabilitiesSummary: api.linked_summaries.capabilities,
      linkedPluginsSummary: api.linked_summaries.plugins,
      linkedReleasesSummary: api.linked_summaries.releases,
      linkedHistorySummary: api.linked_summaries.history,
    };
  }

  return {
    resourceType: "marketplace_center_overview",
    resourceId: state.console.session_id || state.console.user_id,
    totalCapabilities: 0,
    publishedCapabilities: 0,
    installedCapabilities: 0,
    pendingApprovals: 0,
    riskLevel: "低",
    linkedCapabilitiesSummary: { summary: { title: "capabilities" }, data: {} },
    linkedPluginsSummary: { summary: { title: "plugins" }, data: {} },
    linkedReleasesSummary: { summary: { title: "releases" }, data: {} },
    linkedHistorySummary: { summary: { title: "history" }, data: {} },
  };
}
