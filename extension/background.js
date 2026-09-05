/**
 * X-Agent Chrome Extension - Background Service Worker
 * Handles backend API communication, optional MCP (native messaging),
 * tab management, and extension lifecycle.
 */

import { MCPClient } from './mcp-client.js';
import { TabGroupManager } from './tab-group-manager.js';
import { StorageManager } from './storage-manager.js';
import {
  ApiClientError,
  buildPageContext,
  checkHealth,
  loadBackendSettings,
  runAgent,
  runAgentStream,
  saveBackendSettings
} from './api-client.js';

const ANALYZE_PAGE_MENU_ID = 'xagent-analyze-page';
const DEFAULT_ANALYZE_TASK = '请分析当前网页的内容：总结主题、关键信息，并给出要点。';

class BackgroundWorker {
  constructor() {
    // Native messaging (desktop app) is OPTIONAL: when the host is not
    // installed the client degrades silently and direct-backend mode is used.
    this.mcpClient = new MCPClient({ silent: true, autoReconnect: false });
    this.tabGroupManager = new TabGroupManager();
    this.storageManager = new StorageManager();
    this.activeSession = null;
    this.elementRefs = new Map(); // ref_id -> element info
    this.refCounter = 0;
    this.backendSettings = null;
    this.lastHealth = null; // cached health result
    this.lastHealthAt = 0;
  }

  async initialize() {
    console.log('[X-Agent] Background worker initializing...');

    // Load backend settings (direct HTTP mode - works without desktop app)
    this.backendSettings = await loadBackendSettings();

    // Initialize MCP connection (best-effort, silent when host missing)
    try {
      await this.mcpClient.connect();
    } catch {
      // Native host unavailable - expected in direct-backend mode.
    }

    // Restore previous session if exists
    const savedSession = await this.storageManager.getSession();
    if (savedSession) {
      this.activeSession = savedSession;
    }

    // Setup event listeners
    this.setupEventListeners();

    console.log('[X-Agent] Background worker initialized');
  }

  setupEventListeners() {
    // Handle messages from content scripts
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      this.handleMessage(request, sender, sendResponse);
      return true; // Keep channel open for async response
    });

    // Handle tab updates
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      this.handleTabUpdate(tabId, changeInfo, tab);
    });

    // Handle tab removal
    chrome.tabs.onRemoved.addListener((tabId) => {
      this.handleTabRemoved(tabId);
    });

    // Handle extension commands
    chrome.commands.onCommand.addListener((command) => {
      this.handleCommand(command);
    });

    this.setupContextMenus();
  }

  setupContextMenus() {
    // Context menu: "让 X-Agent 分析此页"
    try {
      chrome.runtime.onInstalled.addListener(() => {
        try {
          chrome.contextMenus.removeAll(() => {
            chrome.contextMenus.create({
              id: ANALYZE_PAGE_MENU_ID,
              title: '让 X-Agent 分析此页',
              contexts: ['page', 'selection']
            });
          });
        } catch {
          // contextMenus unavailable - ignore
        }
      });

      chrome.contextMenus.onClicked.addListener((info, tab) => {
        if (info && info.menuItemId === ANALYZE_PAGE_MENU_ID && tab && tab.id != null) {
          this.analyzePageInBackground(tab.id, info.selectionText || '').catch((error) => {
            console.error('[X-Agent] Analyze page failed:', error);
            this.showNotification('X-Agent 分析失败', error.message || '未知错误');
          });
        }
      });
    } catch {
      // contextMenus API unavailable - ignore
    }

    try {
      chrome.notifications.onClicked.addListener((notificationId) => {
        try {
          chrome.notifications.clear(notificationId);
        } catch {
          // ignore
        }
      });
    } catch {
      // notifications API unavailable - ignore
    }
  }

  async handleMessage(request, sender, sendResponse) {
    try {
      const { type, payload } = request;

      switch (type) {
        case 'CREATE_SESSION':
          sendResponse(await this.createSession(payload));
          break;

        case 'GET_SESSION': {
          const session = await this.storageManager.getSession();
          sendResponse({ success: true, session });
          break;
        }

        case 'SAVE_SETTING':
          await this.storageManager.saveSettings(payload || {});
          sendResponse({ success: true });
          break;

        case 'GET_ACTION_HISTORY': {
          const actions = this.activeSession && Array.isArray(this.activeSession.actions)
            ? this.activeSession.actions
            : [];
          sendResponse({ success: true, history: actions });
          break;
        }

        case 'GET_STATUS':
          sendResponse(await this.getStatus());
          break;

        case 'GET_BACKEND_SETTINGS': {
          const settings = await loadBackendSettings();
          sendResponse({ success: true, settings });
          break;
        }

        case 'SAVE_BACKEND_SETTINGS': {
          const settings = await saveBackendSettings(payload || {});
          this.backendSettings = settings;
          sendResponse({ success: true, settings });
          break;
        }

        case 'TEST_BACKEND_CONNECTION': {
          const settings = await loadBackendSettings();
          const health = await checkHealth(settings.baseUrl, settings.apiKey);
          this.lastHealth = health;
          this.lastHealthAt = Date.now();
          sendResponse({ success: true, health });
          break;
        }

        case 'CHAT_RUN':
          sendResponse(await this.runChatOnTab(payload || {}, sender.tab));
          break;

        case 'ANALYZE_PAGE':
          sendResponse(await this.analyzePageInBackground(payload.tabId, payload.selectionText || ''));
          break;

        case 'GET_PAGE_ELEMENTS':
          sendResponse(await this.getPageElements(sender.tab.id, payload));
          break;

        case 'FILL_FORM':
          sendResponse(await this.fillForm(sender.tab.id, payload));
          break;

        case 'CLICK_ELEMENT':
          sendResponse(await this.clickElement(sender.tab.id, payload));
          break;

        case 'EXTRACT_PAGE_CONTENT':
          sendResponse(await this.extractPageContent(sender.tab.id, payload));
          break;

        case 'RECORD_ACTION':
          sendResponse(await this.recordAction(sender.tab.id, payload));
          break;

        case 'GET_TAB_GROUPS':
          sendResponse(await this.getTabGroups());
          break;

        case 'CREATE_TAB_GROUP':
          sendResponse(await this.createTabGroup(payload));
          break;

        case 'NAVIGATE_TAB':
          sendResponse(await this.navigateTab(sender.tab.id, payload));
          break;

        case 'TAKE_SCREENSHOT':
          sendResponse(await this.takeScreenshot(sender.tab.id, payload));
          break;

        case 'EXECUTE_SCRIPT':
          sendResponse(await this.executeScript(sender.tab.id, payload));
          break;

        case 'GET_ELEMENT_REF':
          sendResponse(await this.getElementRef(sender.tab.id, payload));
          break;

        case 'HIGHLIGHT_ELEMENTS':
          sendResponse(await this.highlightElements(sender.tab.id, payload));
          break;

        default:
          sendResponse({ success: false, error: `Unknown message type: ${type}` });
      }
    } catch (error) {
      console.error('[X-Agent] Error handling message:', error);
      sendResponse({ success: false, error: error.message });
    }
  }

  /**
   * Aggregate status for the popup: backend (direct HTTP) connectivity plus
   * optional native-messaging (desktop app) state.
   */
  async getStatus() {
    const settings = this.backendSettings || await loadBackendSettings();
    let health = this.lastHealth;
    const cacheValid = health && Date.now() - this.lastHealthAt < 15000;
    if (!cacheValid) {
      health = await checkHealth(settings.baseUrl, settings.apiKey, 3000);
      this.lastHealth = health;
      this.lastHealthAt = Date.now();
    }
    return {
      success: true,
      connected: this.mcpClient.isConnected(),
      nativeMcp: {
        available: this.mcpClient.isConnected(),
        optional: true
      },
      backend: {
        baseUrl: settings.baseUrl,
        ok: health.ok,
        latencyMs: health.latencyMs,
        error: health.error || null
      }
    };
  }

  /**
   * Extract the given tab's content via the existing content-script message
   * and turn it into an `extra_context` payload for the backend.
   */
  async buildTabContext(tabId) {
    try {
      const extract = await chrome.tabs.sendMessage(tabId, {
        type: 'EXTRACT_CONTENT',
        includeText: true,
        includeLinks: true,
        includeImages: false
      });
      return buildPageContext(extract, {
        maxChars: this.backendSettings ? this.backendSettings.maxPageTextChars : undefined
      });
    } catch (error) {
      return buildPageContext({ success: false, error: error.message });
    }
  }

  /**
   * Chat entry point used by the popup when streaming is requested from the
   * background (non-stream requests are issued by the popup directly).
   */
  async runChatOnTab(payload, senderTab) {
    const { task, tabId, attachPage = true, stream = false } = payload;
    if (!task || !String(task).trim()) {
      return { success: false, error: '任务内容为空' };
    }
    const targetTabId = tabId != null ? tabId : senderTab && senderTab.id;
    if (targetTabId == null) {
      return { success: false, error: '没有可用的标签页' };
    }

    const settings = await loadBackendSettings();
    const extraContext = attachPage ? await this.buildTabContext(targetTabId) : {};
    const options = {
      task: String(task),
      extraContext,
      sessionId: this.activeSession ? this.activeSession.traceId : undefined
    };

    if (stream) {
      const result = await runAgentStream(options, settings, {});
      return { success: true, result };
    }
    const result = await runAgent(options, settings);
    return { success: true, result };
  }

  /**
   * Context-menu / shortcut action: extract the page, send an analysis task
   * to the backend and notify the user with the result.
   */
  async analyzePageInBackground(tabId, selectionText = '') {
    const settings = await loadBackendSettings();
    const extraContext = await this.buildTabContext(tabId);
    const task = selectionText
      ? `请分析此网页中被选中的内容以及页面背景：\n\n选中内容：${selectionText.slice(0, 2000)}`
      : DEFAULT_ANALYZE_TASK;

    this.showNotification('X-Agent', '已开始分析此页面…');

    let result;
    try {
      result = await runAgent(
        {
          task,
          extraContext,
          sessionId: this.activeSession ? this.activeSession.traceId : undefined
        },
        settings
      );
    } catch (error) {
      const message = error instanceof ApiClientError ? error.message : error.message;
      this.showNotification('X-Agent 分析失败', message);
      return { success: false, error: message };
    }

    const answer = (result && result.answer) || '';
    const failed = result && ['failed', 'error'].includes(String(result.status || ''));
    if (failed) {
      this.showNotification('X-Agent 分析失败', (result && result.error) || '任务执行失败');
      return { success: false, error: result.error || '任务执行失败', result };
    }

    const summary = answer.length > 180 ? `${answer.slice(0, 180)}…` : answer || '(无输出)';
    this.showNotification('X-Agent 分析完成', summary);
    return { success: true, result };
  }

  showNotification(title, message) {
    try {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: chrome.runtime.getURL('images/icon-128.png'),
        title: String(title || 'X-Agent'),
        message: String(message || '')
      });
      return true;
    } catch (error) {
      console.warn('[X-Agent] Notification failed:', error);
      return false;
    }
  }

  async createSession(payload) {
    const { sessionName, traceId, runId } = payload;

    const session = {
      id: this.generateSessionId(),
      name: sessionName || 'Default Session',
      traceId,
      runId,
      createdAt: new Date().toISOString(),
      tabs: [],
      actions: []
    };

    this.activeSession = session;
    await this.storageManager.saveSession(session);

    // Notify MCP server (optional; ignore when desktop app not connected)
    if (this.mcpClient.isConnected()) {
      try {
        await this.mcpClient.send({
          type: 'session_created',
          session
        });
      } catch {
        // Desktop app went away mid-send - not fatal.
      }
    }

    return { success: true, session };
  }

  async getPageElements(tabId, payload) {
    const { selector, includeHidden } = payload;

    const result = await chrome.tabs.sendMessage(tabId, {
      type: 'GET_ELEMENTS',
      selector,
      includeHidden
    });

    return result;
  }

  async fillForm(tabId, payload) {
    const { fields } = payload;

    const result = await chrome.tabs.sendMessage(tabId, {
      type: 'FILL_FORM',
      fields
    });

    if (result.success && this.activeSession) {
      this.activeSession.actions.push({
        type: 'fill_form',
        timestamp: new Date().toISOString(),
        tabId,
        fields
      });
      await this.storageManager.saveSession(this.activeSession);
    }

    return result;
  }

  async clickElement(tabId, payload) {
    const { selector, refId } = payload;

    const result = await chrome.tabs.sendMessage(tabId, {
      type: 'CLICK_ELEMENT',
      selector,
      refId
    });

    if (result.success && this.activeSession) {
      this.activeSession.actions.push({
        type: 'click',
        timestamp: new Date().toISOString(),
        tabId,
        selector,
        refId
      });
      await this.storageManager.saveSession(this.activeSession);
    }

    return result;
  }

  async extractPageContent(tabId, payload) {
    const { includeText, includeLinks, includeImages } = payload;

    const result = await chrome.tabs.sendMessage(tabId, {
      type: 'EXTRACT_CONTENT',
      includeText,
      includeLinks,
      includeImages
    });

    return result;
  }

  async recordAction(tabId, payload) {
    const { action, details } = payload;

    if (this.activeSession) {
      this.activeSession.actions.push({
        type: action,
        timestamp: new Date().toISOString(),
        tabId,
        details
      });
      await this.storageManager.saveSession(this.activeSession);
    }

    return { success: true };
  }

  async getTabGroups() {
    const groups = await this.tabGroupManager.getGroups();
    return { success: true, groups };
  }

  async createTabGroup(payload) {
    const { title, color, tabs } = payload;

    const group = await this.tabGroupManager.createGroup({
      title,
      color,
      tabs
    });

    return { success: true, group };
  }

  async navigateTab(tabId, payload) {
    const { url } = payload;

    try {
      await chrome.tabs.update(tabId, { url });

      if (this.activeSession) {
        this.activeSession.actions.push({
          type: 'navigate',
          timestamp: new Date().toISOString(),
          tabId,
          url
        });
        await this.storageManager.saveSession(this.activeSession);
      }

      return { success: true, url };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async takeScreenshot(tabId, payload) {
    const { format = 'png', quality = 90 } = payload;

    try {
      const dataUrl = await chrome.tabs.captureVisibleTab(tabId, {
        format: format === 'jpeg' ? 'jpeg' : 'png',
        quality
      });

      if (this.activeSession) {
        this.activeSession.actions.push({
          type: 'screenshot',
          timestamp: new Date().toISOString(),
          tabId,
          format
        });
        await this.storageManager.saveSession(this.activeSession);
      }

      return { success: true, dataUrl };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async executeScript(tabId, payload) {
    const { code, args = [] } = payload;

    try {
      const result = await chrome.tabs.executeScript(tabId, {
        function: new Function(...args, code),
        args
      });

      return { success: true, result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getElementRef(tabId, payload) {
    const { selector } = payload;

    const refId = `ref_${++this.refCounter}`;

    const elementInfo = await chrome.tabs.sendMessage(tabId, {
      type: 'GET_ELEMENT_INFO',
      selector,
      refId
    });

    if (elementInfo.success) {
      this.elementRefs.set(refId, {
        tabId,
        selector,
        ...elementInfo.data
      });
    }

    return { success: true, refId, ...elementInfo };
  }

  async highlightElements(tabId, payload) {
    const { selectors, color = '#FFD700', duration = 3000 } = payload;

    const result = await chrome.tabs.sendMessage(tabId, {
      type: 'HIGHLIGHT_ELEMENTS',
      selectors,
      color,
      duration
    });

    return result;
  }

  handleTabUpdate(tabId, changeInfo, tab) {
    if (changeInfo.status === 'complete') {
      // Notify content script that page is ready
      chrome.tabs.sendMessage(tabId, {
        type: 'PAGE_READY'
      }).catch(() => {
        // Content script might not be ready yet
      });
    }
  }

  handleTabRemoved(tabId) {
    // Clean up element refs for this tab
    for (const [refId, info] of this.elementRefs.entries()) {
      if (info.tabId === tabId) {
        this.elementRefs.delete(refId);
      }
    }
  }

  async handleCommand(command) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs.length === 0) return;

    const tabId = tabs[0].id;

    switch (command) {
      case 'toggle-sidebar':
        await chrome.tabs.sendMessage(tabId, {
          type: 'TOGGLE_SIDEBAR'
        });
        break;

      case 'highlight-elements':
        await chrome.tabs.sendMessage(tabId, {
          type: 'TOGGLE_ELEMENT_HIGHLIGHT'
        });
        break;
    }
  }

  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Initialize background worker
const worker = new BackgroundWorker();
worker.initialize().catch(error => {
  console.error('[X-Agent] Failed to initialize background worker:', error);
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { BackgroundWorker };
}
