/**
 * X-Agent Chrome Extension - Background Service Worker
 * Handles MCP communication, tab management, and extension lifecycle
 */

import { MCPClient } from './mcp-client.js';
import { TabGroupManager } from './tab-group-manager.js';
import { StorageManager } from './storage-manager.js';

class BackgroundWorker {
  constructor() {
    this.mcpClient = new MCPClient();
    this.tabGroupManager = new TabGroupManager();
    this.storageManager = new StorageManager();
    this.activeSession = null;
    this.elementRefs = new Map(); // ref_id -> element info
    this.refCounter = 0;
  }

  async initialize() {
    console.log('[X-Agent] Background worker initializing...');

    // Initialize MCP connection
    await this.mcpClient.connect();

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
  }

  async handleMessage(request, sender, sendResponse) {
    try {
      const { type, payload } = request;

      switch (type) {
        case 'CREATE_SESSION':
          sendResponse(await this.createSession(payload));
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

    // Notify MCP server
    await this.mcpClient.send({
      type: 'session_created',
      session
    });

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
