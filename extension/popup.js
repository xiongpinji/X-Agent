/**
 * X-Agent Chrome Extension - Popup Script
 * Handles popup UI interactions and communication with background script
 */

class PopupManager {
  constructor() {
    this.currentSession = null;
    this.tabGroups = [];
    this.actionHistory = [];
  }

  async initialize() {
    console.log('[X-Agent Popup] Initializing...');

    // Load current session
    await this.loadSession();

    // Load tab groups
    await this.loadTabGroups();

    // Load action history
    await this.loadActionHistory();

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

    // Check connection status
    chrome.runtime.sendMessage({ type: 'GET_STATUS' }, (response) => {
      if (response && response.connected) {
        dot.classList.add('connected');
        dot.classList.remove('disconnected');
        text.textContent = '已连接';
      } else {
        dot.classList.add('disconnected');
        dot.classList.remove('connected');
        text.textContent = '未连接';
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

快速操作:
• 提取内容: 提取当前页面的文本、链接和图片
• 高亮元素: 高亮页面上的交互元素
• 录制操作: 记录您在页面上的操作
• 侧边栏: 打开/关闭操作侧边栏

快捷键:
• Ctrl+Shift+X: 切换侧边栏
• Ctrl+Shift+H: 切换元素高亮

更多帮助请访问: https://x-agent.example.com/help`);
  }

  showAbout() {
    alert(`X-Agent 浏览器扩展
版本: 1.0.0

X-Agent 是一个强大的浏览器自动化工具，
帮助您自动化重复的网页操作。

官网: https://x-agent.example.com
文档: https://docs.x-agent.example.com`);
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
