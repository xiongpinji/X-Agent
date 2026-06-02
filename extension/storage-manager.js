/**
 * X-Agent Chrome Extension - Storage Manager
 * Manages persistent storage for sessions, settings, and history
 */

export class StorageManager {
  constructor() {
    this.storageArea = chrome.storage.local;
    this.sessionKey = 'xagent_session';
    this.settingsKey = 'xagent_settings';
    this.historyKey = 'xagent_history';
    this.cacheKey = 'xagent_cache';
  }

  async saveSession(session) {
    try {
      await this.storageArea.set({
        [this.sessionKey]: session
      });
      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error saving session:', error);
      throw error;
    }
  }

  async getSession() {
    try {
      const result = await this.storageArea.get(this.sessionKey);
      return result[this.sessionKey] || null;
    } catch (error) {
      console.error('[X-Agent] Error getting session:', error);
      return null;
    }
  }

  async clearSession() {
    try {
      await this.storageArea.remove(this.sessionKey);
      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error clearing session:', error);
      throw error;
    }
  }

  async saveSettings(settings) {
    try {
      const current = await this.getSettings();
      const merged = { ...current, ...settings };

      await this.storageArea.set({
        [this.settingsKey]: merged
      });

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error saving settings:', error);
      throw error;
    }
  }

  async getSettings() {
    try {
      const result = await this.storageArea.get(this.settingsKey);
      return result[this.settingsKey] || this.getDefaultSettings();
    } catch (error) {
      console.error('[X-Agent] Error getting settings:', error);
      return this.getDefaultSettings();
    }
  }

  getDefaultSettings() {
    return {
      theme: 'light',
      language: 'zh-CN',
      autoHighlight: true,
      recordingEnabled: false,
      sidebarPosition: 'right',
      elementRefStyle: 'outline',
      highlightColor: '#FFD700',
      highlightDuration: 3000,
      autoSaveHistory: true,
      maxHistorySize: 1000,
      enableNotifications: true,
      debugMode: false
    };
  }

  async addToHistory(entry) {
    try {
      const history = await this.getHistory();

      history.unshift({
        ...entry,
        timestamp: new Date().toISOString(),
        id: this.generateId()
      });

      // Keep only recent entries
      const settings = await this.getSettings();
      const maxSize = settings.maxHistorySize || 1000;
      if (history.length > maxSize) {
        history.splice(maxSize);
      }

      await this.storageArea.set({
        [this.historyKey]: history
      });

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error adding to history:', error);
      throw error;
    }
  }

  async getHistory(limit = 100) {
    try {
      const result = await this.storageArea.get(this.historyKey);
      const history = result[this.historyKey] || [];
      return history.slice(0, limit);
    } catch (error) {
      console.error('[X-Agent] Error getting history:', error);
      return [];
    }
  }

  async clearHistory() {
    try {
      await this.storageArea.remove(this.historyKey);
      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error clearing history:', error);
      throw error;
    }
  }

  async saveCache(key, value, ttl = 3600000) {
    try {
      const cache = await this.getCache();

      cache[key] = {
        value,
        timestamp: Date.now(),
        ttl
      };

      await this.storageArea.set({
        [this.cacheKey]: cache
      });

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error saving cache:', error);
      throw error;
    }
  }

  async getCache(key) {
    try {
      const result = await this.storageArea.get(this.cacheKey);
      const cache = result[this.cacheKey] || {};

      if (!key) {
        return cache;
      }

      const entry = cache[key];
      if (!entry) {
        return null;
      }

      // Check if expired
      if (Date.now() - entry.timestamp > entry.ttl) {
        delete cache[key];
        await this.storageArea.set({
          [this.cacheKey]: cache
        });
        return null;
      }

      return entry.value;
    } catch (error) {
      console.error('[X-Agent] Error getting cache:', error);
      return null;
    }
  }

  async clearCache(key) {
    try {
      const cache = await this.getCache();

      if (key) {
        delete cache[key];
      } else {
        // Clear all cache
        await this.storageArea.remove(this.cacheKey);
        return { success: true };
      }

      await this.storageArea.set({
        [this.cacheKey]: cache
      });

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error clearing cache:', error);
      throw error;
    }
  }

  async exportData() {
    try {
      const session = await this.getSession();
      const settings = await this.getSettings();
      const history = await this.getHistory(Infinity);

      return {
        version: '1.0.0',
        exportedAt: new Date().toISOString(),
        session,
        settings,
        history
      };
    } catch (error) {
      console.error('[X-Agent] Error exporting data:', error);
      throw error;
    }
  }

  async importData(data) {
    try {
      const { session, settings, history } = data;

      if (session) {
        await this.saveSession(session);
      }

      if (settings) {
        await this.saveSettings(settings);
      }

      if (history && Array.isArray(history)) {
        await this.storageArea.set({
          [this.historyKey]: history
        });
      }

      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error importing data:', error);
      throw error;
    }
  }

  async clearAll() {
    try {
      await this.storageArea.clear();
      return { success: true };
    } catch (error) {
      console.error('[X-Agent] Error clearing all storage:', error);
      throw error;
    }
  }

  generateId() {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

export default StorageManager;
