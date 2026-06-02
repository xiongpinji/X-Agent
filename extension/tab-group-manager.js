/**
 * X-Agent Chrome Extension - Tab Group Manager
 * Manages tab groups for organizing browser automation workflows
 */

export class TabGroupManager {
  constructor() {
    this.groups = new Map();
  }

  async getGroups() {
    try {
      const tabGroups = await chrome.tabGroups.query({});
      const groups = [];

      for (const group of tabGroups) {
        const tabs = await chrome.tabs.query({ groupId: group.id });
        groups.push({
          id: group.id,
          title: group.title,
          color: group.color,
          collapsed: group.collapsed,
          tabs: tabs.map(tab => ({
            id: tab.id,
            title: tab.title,
            url: tab.url,
            active: tab.active,
            favIconUrl: tab.favIconUrl
          }))
        });
      }

      return groups;
    } catch (error) {
      console.error('[X-Agent] Error getting tab groups:', error);
      return [];
    }
  }

  async createGroup(options) {
    try {
      const { title, color = 'blue', tabs = [] } = options;

      // Create tab group
      const groupId = await chrome.tabs.group({
        tabIds: tabs.map(t => t.id || t)
      });

      // Update group properties
      await chrome.tabGroups.update(groupId, {
        title,
        color
      });

      return {
        id: groupId,
        title,
        color,
        tabs
      };
    } catch (error) {
      console.error('[X-Agent] Error creating tab group:', error);
      throw error;
    }
  }

  async updateGroup(groupId, options) {
    try {
      const { title, color, collapsed } = options;

      const updateData = {};
      if (title !== undefined) updateData.title = title;
      if (color !== undefined) updateData.color = color;
      if (collapsed !== undefined) updateData.collapsed = collapsed;

      await chrome.tabGroups.update(groupId, updateData);

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error updating tab group:', error);
      throw error;
    }
  }

  async deleteGroup(groupId) {
    try {
      const tabs = await chrome.tabs.query({ groupId });

      // Ungroup tabs
      await chrome.tabs.ungroup(tabs.map(t => t.id));

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error deleting tab group:', error);
      throw error;
    }
  }

  async addTabsToGroup(groupId, tabIds) {
    try {
      await chrome.tabs.group({
        groupId,
        tabIds
      });

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error adding tabs to group:', error);
      throw error;
    }
  }

  async removeTabsFromGroup(tabIds) {
    try {
      await chrome.tabs.ungroup(tabIds);

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error removing tabs from group:', error);
      throw error;
    }
  }
}

export default TabGroupManager;
