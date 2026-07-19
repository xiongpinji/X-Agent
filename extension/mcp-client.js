/**
 * X-Agent Chrome Extension - MCP Client
 * Handles communication with X-Agent desktop application via MCP protocol
 */

export class MCPClient {
  constructor() {
    this.connected = false;
    this.port = null;
    this.messageId = 0;
    this.pendingRequests = new Map();
    this.eventHandlers = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }

  async connect() {
    try {
      console.log('[X-Agent MCP] Attempting to connect...');

      // Try to connect to desktop app via native messaging
      this.port = chrome.runtime.connectNative('com.xagent.extension');

      this.port.onMessage.addListener((message) => {
        this.handleMessage(message);
      });

      this.port.onDisconnect.addListener(() => {
        this.handleDisconnect();
      });

      this.connected = true;
      this.reconnectAttempts = 0;

      console.log('[X-Agent MCP] Connected successfully');

      // Send handshake
      await this.send({
        type: 'initialize',
        version: '1.0.0',
        capabilities: [
          'page_elements',
          'form_filling',
          'element_clicking',
          'content_extraction',
          'screenshot',
          'tab_management',
          'element_reference'
        ]
      });

      return true;
    } catch (error) {
      console.error('[X-Agent MCP] Connection failed:', error);
      this.handleConnectionError();
      return false;
    }
  }

  async send(message) {
    if (!this.connected || !this.port) {
      throw new Error('MCP client not connected');
    }

    const messageId = ++this.messageId;
    const envelope = {
      id: messageId,
      timestamp: new Date().toISOString(),
      ...message
    };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(messageId);
        reject(new Error(`MCP request timeout: ${message.type}`));
      }, 30000); // 30 second timeout

      this.pendingRequests.set(messageId, {
        resolve: (data) => {
          clearTimeout(timeout);
          resolve(data);
        },
        reject: (error) => {
          clearTimeout(timeout);
          reject(error);
        }
      });

      try {
        this.port.postMessage(envelope);
      } catch (error) {
        clearTimeout(timeout);
        this.pendingRequests.delete(messageId);
        reject(error);
      }
    });
  }

  handleMessage(message) {
    const { id, type, error, data } = message;

    // Handle response to previous request
    if (id && this.pendingRequests.has(id)) {
      const handler = this.pendingRequests.get(id);
      this.pendingRequests.delete(id);

      if (error) {
        handler.reject(new Error(error));
      } else {
        handler.resolve(data);
      }
      return;
    }

    // Handle server-initiated messages
    switch (type) {
      case 'execute_action':
        this.handleExecuteAction(message);
        break;

      case 'query_elements':
        this.handleQueryElements(message);
        break;

      case 'fill_form':
        this.handleFillForm(message);
        break;

      case 'click_element':
        this.handleClickElement(message);
        break;

      case 'extract_content':
        this.handleExtractContent(message);
        break;

      case 'highlight':
        this.handleHighlight(message);
        break;

      case 'event':
        this.emitEvent(message.event, message.data);
        break;

      default:
        console.warn('[X-Agent MCP] Unknown message type:', type);
    }
  }

  async handleExecuteAction(message) {
    try {
      const { id, action, params } = message;

      // Dispatch to content script
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: action.toUpperCase(),
        ...params
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  async handleQueryElements(message) {
    try {
      const { id, selector, includeHidden } = message;

      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'GET_ELEMENTS',
        selector,
        includeHidden
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  async handleFillForm(message) {
    try {
      const { id, fields } = message;

      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'FILL_FORM',
        fields
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  async handleClickElement(message) {
    try {
      const { id, selector, refId } = message;

      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'CLICK_ELEMENT',
        selector,
        refId
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  async handleExtractContent(message) {
    try {
      const { id, includeText, includeLinks, includeImages } = message;

      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'EXTRACT_CONTENT',
        includeText,
        includeLinks,
        includeImages
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  async handleHighlight(message) {
    try {
      const { id, selectors, color, duration } = message;

      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs.length === 0) {
        this.sendResponse(id, { error: 'No active tab' });
        return;
      }

      const result = await chrome.tabs.sendMessage(tabs[0].id, {
        type: 'HIGHLIGHT_ELEMENTS',
        selectors,
        color,
        duration
      });

      this.sendResponse(id, result);
    } catch (error) {
      this.sendResponse(message.id, { error: error.message });
    }
  }

  sendResponse(id, data) {
    if (!this.port) return;

    try {
      this.port.postMessage({
        id,
        type: 'response',
        data,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('[X-Agent MCP] Failed to send response:', error);
    }
  }

  handleDisconnect() {
    console.warn('[X-Agent MCP] Disconnected from desktop app');
    this.connected = false;
    this.port = null;

    // Attempt to reconnect
    this.attemptReconnect();
  }

  handleConnectionError() {
    console.error('[X-Agent MCP] Connection error');
    this.connected = false;
    this.attemptReconnect();
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[X-Agent MCP] Max reconnection attempts reached');
      this.emitEvent('connection_failed', {
        attempts: this.reconnectAttempts
      });
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[X-Agent MCP] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect().catch(error => {
        console.error('[X-Agent MCP] Reconnection failed:', error);
      });
    }, delay);
  }

  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event).push(handler);
  }

  off(event, handler) {
    if (!this.eventHandlers.has(event)) return;

    const handlers = this.eventHandlers.get(event);
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  emitEvent(event, data) {
    if (!this.eventHandlers.has(event)) return;

    const handlers = this.eventHandlers.get(event);
    handlers.forEach(handler => {
      try {
        handler(data);
      } catch (error) {
        console.error(`[X-Agent MCP] Error in event handler for ${event}:`, error);
      }
    });
  }

  isConnected() {
    return this.connected && this.port !== null;
  }

  disconnect() {
    if (this.port) {
      this.port.disconnect();
      this.port = null;
    }
    this.connected = false;
  }
}

export default MCPClient;
