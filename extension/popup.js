/**
 * X-Agent Chrome Extension - Popup Script
 * Handles popup UI interactions and communication with background script
 */

import {
  ApiClientError,
  buildPageContext,
  checkHealth,
  loadBackendSettings,
  normalizeBaseUrl,
  runAgent,
  runAgentStream,
  saveBackendSettings
} from './api-client.js';

class PopupManager {
  constructor() {
    this.currentSession = null;
    this.tabGroups = [];
    this.actionHistory = [];
    this.backendSettings = null;
    this.chatBusy = false;
    this.activeTabId = null;
  }

  async initialize() {
    console.log('[X-Agent Popup] Initializing...');

    // Track the active tab (used to attach page content to chat tasks)
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      this.activeTabId = tabs.length > 0 ? tabs[0].id : null;
    } catch {
      this.activeTabId = null;
    }

    // Load current session
    await this.loadSession();

    // Load tab groups
    await this.loadTabGroups();

    // Load action history
    await this.loadActionHistory();

    // Load backend settings into the settings form
    await this.loadBackendSettingsIntoUI();

    // Setup event listeners
    this.setupEventListeners();

    // Update status
    this.updateStatus();

    console.log('[X-Agent Popup] Initialized');
  }

  setupEventListeners() {
    // Session buttons
    document.getElementById('create-session-btn').addEventListener('click', () => {
      this.createSession();
    });

    // Chat / agent run
    document.getElementById('chat-send-btn').addEventListener('click', () => {
      this.sendChat();
    });
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.sendChat();
      }
    });

    // Quick action buttons
    document.getElementById('extract-btn').addEventListener('click', () => {
      this.executeAction('EXTRACT_PAGE_CONTENT', {
        includeText: true,
        includeLinks: true,
        includeImages: true
      });
    });

    document.getElementById('highlight-btn').addEventListener('click', () => {
      this.executeAction('HIGHLIGHT_ELEMENTS', {
        selectors: ['button', 'a', 'input', '[role="button"]'],
        color: '#FFD700',
        duration: 3000
      });
    });

    document.getElementById('record-btn').addEventListener('click', () => {
      this.toggleRecording();
    });

    document.getElementById('sidebar-btn').addEventListener('click', () => {
      this.toggleSidebar();
    });

    // Tab group button
    document.getElementById('create-group-btn').addEventListener('click', () => {
      this.createTabGroup();
    });

    // Backend settings
    document.getElementById('test-connection-btn').addEventListener('click', () => {
      this.testBackendConnection();
    });
    document.getElementById('backend-url-input').addEventListener('change', () => {
      this.persistBackendSettings();
    });
    document.getElementById('api-key-input').addEventListener('change', () => {
      this.persistBackendSettings();
    });
    document.getElementById('open-options-link').addEventListener('click', (e) => {
      e.preventDefault();
      chrome.runtime.openOptionsPage();
    });

    // Settings
    document.getElementById('auto-highlight-toggle').addEventListener('change', (e) => {
      this.saveSetting('autoHighlight', e.target.checked);
    });

    document.getElementById('notifications-toggle').addEventListener('change', (e) => {
      this.saveSetting('enableNotifications', e.target.checked);
    });

    document.getElementById('debug-toggle').addEventListener('change', (e) => {
      this.saveSetting('debugMode', e.target.checked);
    });

    // Footer buttons
    document.getElementById('settings-btn').addEventListener('click', () => {
      chrome.runtime.openOptionsPage();
    });

    document.getElementById('help-btn').addEventListener('click', () => {
      this.showHelp();
    });

    document.getElementById('about-btn').addEventListener('click', () => {
      this.showAbout();
    });
  }

  /* ---------------------------------------------------------------- */
  /* Backend settings + connectivity                                  */
  /* ---------------------------------------------------------------- */

  async loadBackendSettingsIntoUI() {
    try {
      this.backendSettings = await loadBackendSettings();
      document.getElementById('backend-url-input').value = this.backendSettings.baseUrl;
      document.getElementById('api-key-input').value = this.backendSettings.apiKey;
      document.getElementById('attach-page-toggle').checked = this.backendSettings.attachPageContent !== false;
      document.getElementById('stream-toggle').checked = this.backendSettings.useStreaming === true;
    } catch (error) {
      console.error('[X-Agent Popup] Error loading backend settings:', error);
    }
  }

  async persistBackendSettings() {
    try {
      const partial = {
        baseUrl: document.getElementById('backend-url-input').value,
        apiKey: document.getElementById('api-key-input').value,
        attachPageContent: document.getElementById('attach-page-toggle').checked,
        useStreaming: document.getElementById('stream-toggle').checked
      };
      this.backendSettings = await saveBackendSettings(partial);
      document.getElementById('backend-url-input').value = this.backendSettings.baseUrl;
      return this.backendSettings;
    } catch (error) {
      console.error('[X-Agent Popup] Error saving backend settings:', error);
      this.showNotification('保存设置失败', 'error');
      return null;
    }
  }

  async testBackendConnection() {
    const button = document.getElementById('test-connection-btn');
    const statusEl = document.getElementById('connection-status');
    button.disabled = true;
    statusEl.textContent = '测试中…';
    statusEl.className = 'connection-status testing';

    const settings = (await this.persistBackendSettings()) || this.backendSettings;
    const health = await checkHealth(settings.baseUrl, settings.apiKey);

    button.disabled = false;
    if (health.ok) {
      statusEl.textContent = `已连接（${health.latencyMs}ms）`;
      statusEl.className = 'connection-status ok';
    } else {
      statusEl.textContent = health.error || '连接失败';
      statusEl.className = 'connection-status fail';
    }
  }

  /* ---------------------------------------------------------------- */
  /* Chat / agent run                                                 */
  /* ---------------------------------------------------------------- */

  async extractActivePage() {
    if (this.activeTabId == null) {
      return buildPageContext({ success: false, error: '没有活跃的标签页' });
    }
    try {
      const extract = await chrome.tabs.sendMessage(this.activeTabId, {
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

  async sendChat() {
    if (this.chatBusy) return;

    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const output = document.getElementById('chat-output');
    const statusEl = document.getElementById('chat-status');
    const answerEl = document.getElementById('chat-answer');
    const task = input.value.trim();

    if (!task) {
      this.showNotification('请输入任务内容', 'warning');
      return;
    }

    this.chatBusy = true;
    sendBtn.disabled = true;
    sendBtn.textContent = '执行中…';
    output.hidden = false;
    statusEl.textContent = this.backendSettings && this.backendSettings.useStreaming
      ? '已提交，等待后端响应…'
      : '任务执行中（可能需要数十秒）…';
    statusEl.className = 'chat-status running';
    answerEl.textContent = '';

    try {
      const settings = (await this.persistBackendSettings()) || this.backendSettings;
      const attachPage = document.getElementById('attach-page-toggle').checked;
      const extraContext = attachPage ? await this.extractActivePage() : {};
      const options = {
        task,
        extraContext,
        sessionId: this.currentSession ? this.currentSession.traceId : undefined
      };

      const finish = (result) => {
        const answer = (result && result.answer) || '';
        const failed = result && ['failed', 'error'].includes(String(result.status || ''));
        if (failed) {
          statusEl.textContent = `执行失败${result.error ? `：${result.error}` : ''}`;
          statusEl.className = 'chat-status error';
          answerEl.textContent = answer || '';
        } else {
          statusEl.textContent = `完成（trace: ${(result && result.trace_id || '').slice(0, 8)}）`;
          statusEl.className = 'chat-status done';
          answerEl.textContent = answer || '(无输出)';
        }
      };

      if (document.getElementById('stream-toggle').checked) {
        let traceCount = 0;
        const result = await runAgentStream(options, settings, {
          onTraceEvent: () => {
            traceCount += 1;
            statusEl.textContent = `执行中…（已收到 ${traceCount} 个事件）`;
          }
        });
        finish(result);
      } else {
        const result = await runAgent(options, settings);
        finish(result);
      }
    } catch (error) {
      statusEl.textContent = error instanceof ApiClientError ? error.message : `请求失败：${error.message}`;
      statusEl.className = 'chat-status error';
    } finally {
      this.chatBusy = false;
      sendBtn.disabled = false;
      sendBtn.textContent = '发送任务';
    }
  }

  async loadSession() {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'GET_SESSION'
      });

      if (response.success && response.session) {
        this.currentSession = response.session;
        this.updateSessionInfo();
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error loading session:', error);
    }
  }

  async createSession() {
    try {
      const sessionName = prompt('输入会话名称:', '新会话');
      if (!sessionName) return;

      const response = await chrome.runtime.sendMessage({
        type: 'CREATE_SESSION',
        payload: {
          sessionName,
          traceId: this.generateId(),
          runId: this.generateId()
        }
      });

      if (response.success) {
        this.currentSession = response.session;
        this.updateSessionInfo();
        this.showNotification('会话已创建', 'success');
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error creating session:', error);
      this.showNotification('创建会话失败', 'error');
    }
  }

  updateSessionInfo() {
    const sessionInfo = document.getElementById('session-info');

    if (this.currentSession) {
      sessionInfo.innerHTML = `
        <div class="session-details">
          <p><strong>名称:</strong> ${this.currentSession.name}</p>
          <p><strong>ID:</strong> ${this.currentSession.id.substring(0, 12)}...</p>
          <p><strong>创建时间:</strong> ${new Date(this.currentSession.createdAt).toLocaleString('zh-CN')}</p>
          <p><strong>操作数:</strong> ${this.currentSession.actions?.length || 0}</p>
        </div>
      `;
    } else {
      sessionInfo.innerHTML = '<p class="info-text">未创建会话</p>';
    }
  }

  async loadTabGroups() {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'GET_TAB_GROUPS'
      });

      if (response.success) {
        this.tabGroups = response.groups || [];
        this.updateTabGroupsUI();
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error loading tab groups:', error);
    }
  }

  updateTabGroupsUI() {
    const container = document.getElementById('tab-groups');

    if (this.tabGroups.length === 0) {
      container.innerHTML = '<p class="info-text">暂无标签组</p>';
      return;
    }

    container.innerHTML = this.tabGroups.map(group => `
      <div class="tab-group-item" data-group-id="${group.id}">
        <div class="tab-group-title">${group.title}</div>
        <div class="tab-group-count">${group.tabs.length} 个标签</div>
      </div>
    `).join('');

    // Add click handlers
    container.querySelectorAll('.tab-group-item').forEach(item => {
      item.addEventListener('click', () => {
        const groupId = item.dataset.groupId;
        this.selectTabGroup(groupId);
      });
    });
  }

  async createTabGroup() {
    try {
      const title = prompt('输入标签组名称:', '新标签组');
      if (!title) return;

      const tabs = await chrome.tabs.query({ currentWindow: true });
      const selectedTabs = tabs.filter(tab => tab.active);

      if (selectedTabs.length === 0) {
        this.showNotification('请先选择标签', 'warning');
        return;
      }

      const response = await chrome.runtime.sendMessage({
        type: 'CREATE_TAB_GROUP',
        payload: {
          title,
          color: 'blue',
          tabs: selectedTabs.map(t => t.id)
        }
      });

      if (response.success) {
        await this.loadTabGroups();
        this.showNotification('标签组已创建', 'success');
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error creating tab group:', error);
      this.showNotification('创建标签组失败', 'error');
    }
  }

  selectTabGroup(groupId) {
    const group = this.tabGroups.find(g => g.id === groupId);
    if (group) {
      this.showNotification(`已选择: ${group.title}`, 'info');
    }
  }

  async loadActionHistory() {
    try {
      // Get from background script
      const response = await chrome.runtime.sendMessage({
        type: 'GET_ACTION_HISTORY'
      });

      if (response.success) {
        this.actionHistory = response.history || [];
        this.updateActionHistoryUI();
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error loading action history:', error);
    }
  }

  updateActionHistoryUI() {
    const container = document.getElementById('action-history');

    if (this.actionHistory.length === 0) {
      container.innerHTML = '<p class="info-text">暂无操作记录</p>';
      return;
    }

    container.innerHTML = this.actionHistory.slice(0, 5).map(action => `
      <div class="history-item">
        <div class="history-action">${this.getActionLabel(action.type)}</div>
        <div class="history-time">${new Date(action.timestamp).toLocaleTimeString('zh-CN')}</div>
      </div>
    `).join('');
  }

  getActionLabel(type) {
    const labels = {
      'click': '点击元素',
      'fill': '填充表单',
      'navigate': '页面导航',
      'screenshot': '截图',
      'extract': '提取内容',
      'highlight': '高亮元素'
    };
    return labels[type] || type;
  }

  async executeAction(type, payload) {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.showNotification('没有活跃的标签页', 'warning');
        return;
      }

      const response = await chrome.tabs.sendMessage(tabs[0].id, {
        type,
        ...payload
      });

      if (response.success) {
        this.showNotification('操作成功', 'success');
        await this.loadActionHistory();
      } else {
        this.showNotification(`操作失败: ${response.error}`, 'error');
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error executing action:', error);
      this.showNotification('执行操作失败', 'error');
    }
  }

  async toggleRecording() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) return;

      const response = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'TOGGLE_ELEMENT_HIGHLIGHT'
      });

      if (response.success) {
        const status = response.recording ? '已启动' : '已停止';
        this.showNotification(`录制${status}`, 'info');
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error toggling recording:', error);
    }
  }

  async toggleSidebar() {
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) return;

      const response = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'TOGGLE_SIDEBAR'
      });

      if (response.success) {
        const status = response.visible ? '已打开' : '已关闭';
        this.showNotification(`侧边栏${status}`, 'info');
      }
    } catch (error) {
      console.error('[X-Agent Popup] Error toggling sidebar:', error);
    }
  }

  async saveSetting(key, value) {
    try {
      await chrome.runtime.sendMessage({
        type: 'SAVE_SETTING',
        payload: { [key]: value }
      });
    } catch (error) {
      console.error('[X-Agent Popup] Error saving setting:', error);
    }
  }

  updateStatus() {
    const indicator = document.querySelector('.status-indicator');
    const dot = document.querySelector('.status-dot');
    const text = document.querySelector('.status-text');

    // Check connection status (backend direct mode + optional desktop app)
    chrome.runtime.sendMessage({ type: 'GET_STATUS' }, (response) => {
      if (!response) {
        dot.classList.add('disconnected');
        dot.classList.remove('connected');
        text.textContent = '后台未响应';
        return;
      }
      if (response.backend && response.backend.ok) {
        dot.classList.add('connected');
        dot.classList.remove('disconnected');
        const native = response.nativeMcp && response.nativeMcp.available ? ' + 桌面端' : '';
        text.title = response.backend.baseUrl;
        text.textContent = `后端已连接${native}`;
      } else {
        dot.classList.add('disconnected');
        dot.classList.remove('connected');
        text.title = (response.backend && response.backend.error) || '';
        text.textContent = '后端未连接';
      }
    });
  }

  showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      padding: 12px 16px;
      background-color: ${type === 'success' ? '#34C759' : type === 'error' ? '#FF3B30' : '#007AFF'};
      color: white;
      border-radius: 4px;
      font-size: 12px;
      z-index: 10000;
      animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  showHelp() {
    alert(`X-Agent 浏览器扩展帮助

对话:
• 在顶部输入任务，默认附带当前页面内容
• 需要在设置中配置后端地址与 API Key

快速操作:
• 提取内容: 提取当前页面的文本、链接和图片
• 高亮元素: 高亮页面上的交互元素
• 录制操作: 记录您在页面上的操作
• 侧边栏: 打开/关闭操作侧边栏

右键菜单:
• 在任意网页上右键选择"让 X-Agent 分析此页"

快捷键:
• Ctrl+Shift+X: 切换侧边栏
• Ctrl+Shift+H: 切换元素高亮

后端默认地址: http://localhost:8000`);
  }

  showAbout() {
    alert(`X-Agent 浏览器扩展
版本: ${chrome.runtime.getManifest ? chrome.runtime.getManifest().version : '0.3.0'}

X-Agent 是一个强大的浏览器自动化工具，
帮助您自动化重复的网页操作。

直连后端模式：无需桌面端，直接访问 X-Agent 后端 API。`);
  }

  generateId() {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Initialize popup manager
const popupManager = new PopupManager();
popupManager.initialize().catch(error => {
  console.error('[X-Agent Popup] Initialization error:', error);
});
