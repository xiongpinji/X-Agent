import type { ConsoleState } from "./consoleReducer";

export function selectMarketplaceCenterOverviewData(state: ConsoleState) {
  const api = state.marketplaceCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      totalItems: api.primary.total_items,
      publishedItems: api.primary.published_items,
      installedItems: api.primary.installed_items,
      pendingApprovals: api.primary.pending_approvals,
      riskLevel: api.primary.risk_level,
      linkedMarketSummary: api.linked_summaries.market,
      linkedPluginsSummary: api.linked_summaries.plugins,
      linkedToolsSummary: api.linked_summaries.tools,
      linkedHistorySummary: api.linked_summaries.history,
    };
  }

  return {
    resourceType: "marketplace_center_overview",
    resourceId: state.console.session_id || state.console.user_id,
    totalItems: 0,
    publishedItems: 0,
    installedItems: 0,
    pendingApprovals: 0,
    riskLevel: "低",
    linkedMarketSummary: { summary: { title: "market" }, data: {} },
    linkedPluginsSummary: { summary: { title: "plugins" }, data: {} },
    linkedToolsSummary: { summary: { title: "tools" }, data: {} },
    linkedHistorySummary: { summary: { title: "history" }, data: {} },
  };
}
