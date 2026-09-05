/**
 * X-Agent Chrome Extension - Options Page Script
 * Backend connection settings + optional native messaging status.
 */

import { DEFAULT_BACKEND_SETTINGS, checkHealth, loadBackendSettings, saveBackendSettings } from './api-client.js';

class OptionsManager {
  constructor() {
    this.settings = null;
  }

  async initialize() {
    this.settings = await loadBackendSettings();
    this.populateForm();
    this.bindEvents();
    this.updateNativeStatus();
  }

  populateForm() {
    document.getElementById('opt-backend-url').value = this.settings.baseUrl;
    document.getElementById('opt-api-key').value = this.settings.apiKey;
    document.getElementById('opt-attach-page').checked = this.settings.attachPageContent !== false;
    document.getElementById('opt-stream').checked = this.settings.useStreaming === true;
    document.getElementById('opt-max-chars').value = this.settings.maxPageTextChars || DEFAULT_BACKEND_SETTINGS.maxPageTextChars;
  }

  readForm() {
    const maxChars = parseInt(document.getElementById('opt-max-chars').value, 10);
    return {
      baseUrl: document.getElementById('opt-backend-url').value,
      apiKey: document.getElementById('opt-api-key').value,
      attachPageContent: document.getElementById('opt-attach-page').checked,
      useStreaming: document.getElementById('opt-stream').checked,
      maxPageTextChars: Number.isFinite(maxChars) && maxChars >= 500 ? maxChars : DEFAULT_BACKEND_SETTINGS.maxPageTextChars
    };
  }

  bindEvents() {
    document.getElementById('opt-save-btn').addEventListener('click', async () => {
      const status = document.getElementById('opt-status');
      try {
        this.settings = await saveBackendSettings(this.readForm());
        this.populateForm();
        status.textContent = '已保存';
        status.className = 'status-line ok';
      } catch (error) {
        status.textContent = `保存失败：${error.message}`;
        status.className = 'status-line fail';
      }
    });

    document.getElementById('opt-test-btn').addEventListener('click', async () => {
      const status = document.getElementById('opt-status');
      const button = document.getElementById('opt-test-btn');
      button.disabled = true;
      status.textContent = '测试中…';
      status.className = 'status-line';
      try {
        this.settings = await saveBackendSettings(this.readForm());
        this.populateForm();
      } catch {
        // Keep going with a health check even if persisting raced.
      }
      const health = await checkHealth(this.settings.baseUrl, this.settings.apiKey);
      button.disabled = false;
      if (health.ok) {
        status.textContent = `连接成功（${health.latencyMs}ms，服务: ${health.service || 'x-agent'}）`;
        status.className = 'status-line ok';
      } else {
        status.textContent = `连接失败：${health.error || '未知错误'}`;
        status.className = 'status-line fail';
      }
    });
  }

  updateNativeStatus() {
    const el = document.getElementById('opt-native-status');
    try {
      chrome.runtime.sendMessage({ type: 'GET_STATUS' }, (response) => {
        if (chrome.runtime.lastError || !response) {
          el.textContent = '无法获取状态（后台服务未响应），直连后端模式不受影响。';
          el.className = 'status-line';
          return;
        }
        if (response.nativeMcp && response.nativeMcp.available) {
          el.textContent = '桌面端已连接（native messaging 工作正常）。';
          el.className = 'status-line ok';
        } else {
          el.textContent = '未检测到桌面端 - 正在使用直连后端模式，全部功能可用。';
          el.className = 'status-line';
        }
      });
    } catch {
      el.textContent = '未检测到桌面端 - 正在使用直连后端模式，全部功能可用。';
      el.className = 'status-line';
    }
  }
}

const manager = new OptionsManager();
manager.initialize().catch((error) => {
  console.error('[X-Agent Options] Initialization error:', error);
});
