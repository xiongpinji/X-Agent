/**
 * X-Agent Chrome Extension - Content Script
 * Runs in the context of web pages to interact with DOM
 */

class ContentScriptManager {
  constructor() {
    this.elementRefs = new Map();
    this.refCounter = 0;
    this.highlightedElements = new Set();
    this.sidebarVisible = false;
    this.recordingMode = false;
    this.actionHistory = [];
  }

  initialize() {
    console.log('[X-Agent] Content script initialized');

    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      this.handleMessage(request, sendResponse);
      return true;
    });

    // Inject page script for DOM access
    this.injectPageScript();

    // Setup event listeners
    this.setupEventListeners();
  }

  injectPageScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('injected.js');
    script.onload = () => script.remove();
    (document.head || document.documentElement).appendChild(script);
  }

  setupEventListeners() {
    // Track form interactions
    document.addEventListener('input', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        this.recordAction('input', {
          selector: this.getSelector(e.target),
          value: e.target.value
        });
      }
    }, true);

    // Track clicks
    document.addEventListener('click', (e) => {
      if (this.recordingMode) {
        this.recordAction('click', {
          selector: this.getSelector(e.target),
          text: e.target.textContent?.substring(0, 100)
        });
      }
    }, true);

    // Track navigation
    window.addEventListener('beforeunload', () => {
      this.recordAction('navigation', {
        url: window.location.href
      });
    });
  }

  async handleMessage(request, sendResponse) {
    try {
      const { type, selector, refId, fields, color, duration, includeHidden, includeText, includeLinks, includeImages } = request;

      switch (type) {
        case 'GET_ELEMENTS':
          sendResponse(this.getElements(selector, includeHidden));
          break;

        case 'GET_ELEMENT_INFO':
          sendResponse(this.getElementInfo(selector, refId));
          break;

        case 'FILL_FORM':
          sendResponse(await this.fillForm(fields));
          break;

        case 'CLICK_ELEMENT':
          sendResponse(this.clickElement(selector, refId));
          break;

        case 'EXTRACT_CONTENT':
          sendResponse(this.extractContent(includeText, includeLinks, includeImages));
          break;

        case 'HIGHLIGHT_ELEMENTS':
          sendResponse(this.highlightElements(request.selectors, color, duration));
          break;

        case 'TOGGLE_SIDEBAR':
          sendResponse(this.toggleSidebar());
          break;

        case 'TOGGLE_ELEMENT_HIGHLIGHT':
          sendResponse(this.toggleElementHighlight());
          break;

        case 'PAGE_READY':
          sendResponse({ success: true });
          break;

        default:
          sendResponse({ success: false, error: `Unknown message type: ${type}` });
      }
    } catch (error) {
      console.error('[X-Agent] Error handling message:', error);
      sendResponse({ success: false, error: error.message });
    }
  }

  getElements(selector, includeHidden = false) {
    try {
      const elements = document.querySelectorAll(selector || '*');
      const result = [];

      elements.forEach((el, index) => {
        if (!includeHidden && el.offsetParent === null) return;

        const refId = `ref_${++this.refCounter}`;
        this.elementRefs.set(refId, el);

        result.push({
          refId,
          tag: el.tagName,
          text: el.textContent?.substring(0, 100),
          selector: this.getSelector(el),
          visible: el.offsetParent !== null,
          rect: el.getBoundingClientRect()
        });
      });

      return { success: true, elements: result, count: result.length };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  getElementInfo(selector, refId) {
    try {
      let element;

      if (refId && this.elementRefs.has(refId)) {
        element = this.elementRefs.get(refId);
      } else if (selector) {
        element = document.querySelector(selector);
      } else {
        return { success: false, error: 'No selector or refId provided' };
      }

      if (!element) {
        return { success: false, error: 'Element not found' };
      }

      const rect = element.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(element);

      return {
        success: true,
        data: {
          tag: element.tagName,
          id: element.id,
          className: element.className,
          text: element.textContent?.substring(0, 200),
          value: element.value,
          placeholder: element.placeholder,
          type: element.type,
          name: element.name,
          selector: this.getSelector(element),
          rect: {
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height
          },
          visible: element.offsetParent !== null,
          disabled: element.disabled,
          readonly: element.readOnly,
          attributes: this.getAttributes(element),
          styles: {
            display: computedStyle.display,
            visibility: computedStyle.visibility,
            opacity: computedStyle.opacity
          }
        }
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async fillForm(fields) {
    try {
      for (const field of fields) {
        const { selector, refId, value, action = 'set' } = field;

        let element;
        if (refId && this.elementRefs.has(refId)) {
          element = this.elementRefs.get(refId);
        } else if (selector) {
          element = document.querySelector(selector);
        }

        if (!element) {
          console.warn(`[X-Agent] Element not found: ${selector || refId}`);
          continue;
        }

        // Focus element
        element.focus();

        // Clear existing value
        if (action === 'set' || action === 'replace') {
          element.value = '';
          element.dispatchEvent(new Event('input', { bubbles: true }));
          element.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Set new value
        if (value !== undefined) {
          element.value = value;
          element.dispatchEvent(new Event('input', { bubbles: true }));
          element.dispatchEvent(new Event('change', { bubbles: true }));

          // Trigger blur for validation
          element.blur();
        }

        // Wait for potential async handlers
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      return { success: true, filled: fields.length };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  clickElement(selector, refId) {
    try {
      let element;

      if (refId && this.elementRefs.has(refId)) {
        element = this.elementRefs.get(refId);
      } else if (selector) {
        element = document.querySelector(selector);
      }

      if (!element) {
        return { success: false, error: 'Element not found' };
      }

      // Scroll into view
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Wait for scroll
      setTimeout(() => {
        element.click();
      }, 100);

      return { success: true, clicked: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  extractContent(includeText = true, includeLinks = true, includeImages = true) {
    try {
      const content = {
        url: window.location.href,
        title: document.title,
        text: includeText ? document.body.innerText : null,
        links: [],
        images: [],
        forms: [],
        metadata: this.extractMetadata()
      };

      if (includeLinks) {
        document.querySelectorAll('a').forEach(link => {
          content.links.push({
            text: link.textContent?.substring(0, 100),
            href: link.href,
            title: link.title
          });
        });
      }

      if (includeImages) {
        document.querySelectorAll('img').forEach(img => {
          content.images.push({
            src: img.src,
            alt: img.alt,
            title: img.title
          });
        });
      }

      // Extract form information
      document.querySelectorAll('form').forEach(form => {
        const fields = [];
        form.querySelectorAll('input, textarea, select').forEach(field => {
          fields.push({
            name: field.name,
            type: field.type,
            value: field.value,
            placeholder: field.placeholder,
            required: field.required
          });
        });

        content.forms.push({
          id: form.id,
          name: form.name,
          action: form.action,
          method: form.method,
          fields
        });
      });

      return { success: true, content };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  highlightElements(selectors, color = '#FFD700', duration = 3000) {
    try {
      const highlighted = [];

      selectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
          const originalStyle = el.style.cssText;
          el.style.outline = `3px solid ${color}`;
          el.style.outlineOffset = '2px';
          el.style.backgroundColor = `${color}33`;

          this.highlightedElements.add(el);
          highlighted.push(selector);

          // Auto-remove highlight after duration
          setTimeout(() => {
            el.style.cssText = originalStyle;
            this.highlightedElements.delete(el);
          }, duration);
        });
      });

      return { success: true, highlighted: highlighted.length };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  toggleSidebar() {
    this.sidebarVisible = !this.sidebarVisible;

    if (this.sidebarVisible) {
      this.createSidebar();
    } else {
      this.removeSidebar();
    }

    return { success: true, visible: this.sidebarVisible };
  }

  toggleElementHighlight() {
    this.recordingMode = !this.recordingMode;

    if (this.recordingMode) {
      document.body.style.cursor = 'crosshair';
      this.setupElementPicker();
    } else {
      document.body.style.cursor = 'auto';
      this.removeElementPicker();
    }

    return { success: true, recording: this.recordingMode };
  }

  createSidebar() {
    if (document.getElementById('xagent-sidebar')) return;

    const sidebar = document.createElement('div');
    sidebar.id = 'xagent-sidebar';
    sidebar.innerHTML = `
      <div style="
        position: fixed;
        right: 0;
        top: 0;
        width: 350px;
        height: 100vh;
        background: white;
        border-left: 1px solid #ddd;
        box-shadow: -2px 0 8px rgba(0,0,0,0.1);
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        overflow-y: auto;
      ">
        <div style="padding: 16px; border-bottom: 1px solid #eee;">
          <h2 style="margin: 0; font-size: 16px; color: #333;">X-Agent</h2>
          <p style="margin: 4px 0 0 0; font-size: 12px; color: #999;">浏览器自动化助手</p>
        </div>
        <div style="padding: 16px;">
          <div id="xagent-actions" style="display: flex; flex-direction: column; gap: 8px;">
            <button id="xagent-extract-btn" style="
              padding: 8px 12px;
              background: #007AFF;
              color: white;
              border: none;
              border-radius: 4px;
              cursor: pointer;
              font-size: 14px;
            ">提取页面内容</button>
            <button id="xagent-highlight-btn" style="
              padding: 8px 12px;
              background: #34C759;
              color: white;
              border: none;
              border-radius: 4px;
              cursor: pointer;
              font-size: 14px;
            ">高亮元素</button>
            <button id="xagent-record-btn" style="
              padding: 8px 12px;
              background: #FF3B30;
              color: white;
              border: none;
              border-radius: 4px;
              cursor: pointer;
              font-size: 14px;
            ">录制操作</button>
          </div>
          <div id="xagent-history" style="margin-top: 16px; font-size: 12px; color: #666;">
            <h3 style="margin: 0 0 8px 0; font-size: 13px; color: #333;">操作历史</h3>
            <div id="xagent-history-list" style="max-height: 300px; overflow-y: auto;"></div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(sidebar);

    // Setup button handlers
    document.getElementById('xagent-extract-btn').addEventListener('click', () => {
      chrome.runtime.sendMessage({
        type: 'EXTRACT_PAGE_CONTENT',
        payload: { includeText: true, includeLinks: true, includeImages: true }
      });
    });

    document.getElementById('xagent-highlight-btn').addEventListener('click', () => {
      this.highlightElements(['button', 'a', 'input', '[role="button"]']);
    });

    document.getElementById('xagent-record-btn').addEventListener('click', () => {
      this.recordingMode = !this.recordingMode;
      const btn = document.getElementById('xagent-record-btn');
      btn.textContent = this.recordingMode ? '停止录制' : '录制操作';
      btn.style.background = this.recordingMode ? '#FF9500' : '#FF3B30';
    });
  }

  removeSidebar() {
    const sidebar = document.getElementById('xagent-sidebar');
    if (sidebar) {
      sidebar.remove();
    }
  }

  setupElementPicker() {
    const overlay = document.createElement('div');
    overlay.id = 'xagent-picker-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 999998;
      background: rgba(0, 0, 0, 0.1);
    `;

    overlay.addEventListener('mouseover', (e) => {
      if (e.target !== overlay) {
        e.target.style.outline = '2px solid #007AFF';
        e.target.style.outlineOffset = '2px';
      }
    });

    overlay.addEventListener('mouseout', (e) => {
      if (e.target !== overlay) {
        e.target.style.outline = '';
      }
    });

    overlay.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const selector = this.getSelector(e.target);
      chrome.runtime.sendMessage({
        type: 'GET_ELEMENT_REF',
        payload: { selector }
      });

      this.removeElementPicker();
      this.recordingMode = false;
    }, true);

    document.body.appendChild(overlay);
  }

  removeElementPicker() {
    const overlay = document.getElementById('xagent-picker-overlay');
    if (overlay) {
      overlay.remove();
    }
  }

  getSelector(element) {
    if (element.id) {
      return `#${element.id}`;
    }

    const path = [];
    let current = element;

    while (current && current !== document.body) {
      let selector = current.tagName.toLowerCase();

      if (current.id) {
        selector += `#${current.id}`;
        path.unshift(selector);
        break;
      } else {
        const siblings = current.parentNode.querySelectorAll(selector);
        if (siblings.length > 1) {
          const index = Array.from(siblings).indexOf(current) + 1;
          selector += `:nth-of-type(${index})`;
        }
      }

      path.unshift(selector);
      current = current.parentNode;
    }

    return path.join(' > ');
  }

  getAttributes(element) {
    const attrs = {};
    for (const attr of element.attributes) {
      attrs[attr.name] = attr.value;
    }
    return attrs;
  }

  extractMetadata() {
    const metadata = {};

    // Extract meta tags
    document.querySelectorAll('meta').forEach(meta => {
      const name = meta.getAttribute('name') || meta.getAttribute('property');
      const content = meta.getAttribute('content');
      if (name && content) {
        metadata[name] = content;
      }
    });

    return metadata;
  }

  recordAction(type, details) {
    this.actionHistory.push({
      type,
      timestamp: new Date().toISOString(),
      details
    });

    // Keep only last 100 actions
    if (this.actionHistory.length > 100) {
      this.actionHistory.shift();
    }

    // Send to background script
    chrome.runtime.sendMessage({
      type: 'RECORD_ACTION',
      payload: { action: type, details }
    }).catch(() => {
      // Background script might not be ready
    });
  }
}

// Initialize content script
const contentScript = new ContentScriptManager();
contentScript.initialize();

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ContentScriptManager };
}
