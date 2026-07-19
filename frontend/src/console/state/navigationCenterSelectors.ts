import type { ConsoleState } from "./consoleReducer";

export function selectNavigationCenterOverviewData(state: ConsoleState) {
  const api = state.navigationCenterOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      recentPages: api.primary.recent_pages,
      favoritePages: api.primary.favorite_pages,
      searchEnabled: api.primary.search_enabled,
      riskLevel: api.primary.risk_level,
      linkedRecentSummary: api.linked_summaries.recent,
      linkedFavoritesSummary: api.linked_summaries.favorites,
      linkedSearchSummary: api.linked_summaries.search,
      linkedShortcutsSummary: api.linked_summaries.shortcuts,
    };
  }

  return {
    resourceType: "navigation_center_overview",
    resourceId: state.console.user_id,
    recentPages: ["overview", "execution_overview", "tools_overview"],
    favoritePages: ["overview", "market_overview", "org_overview"],
    searchEnabled: true,
    riskLevel: "低",
    linkedRecentSummary: { summary: { title: "recent pages" }, data: {} },
    linkedFavoritesSummary: { summary: { title: "favorite pages" }, data: {} },
    linkedSearchSummary: { summary: { title: "search index" }, data: {} },
    linkedShortcutsSummary: { summary: { title: "quick shortcuts" }, data: {} },
  };
}
