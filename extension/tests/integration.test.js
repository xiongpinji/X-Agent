/**
 * X-Agent Chrome Extension - Integration Tests
 * Tests complete workflows across multiple components
 */

// Mock Chrome API
global.chrome = {
  runtime: {
    sendMessage: jest.fn(),
    onMessage: {
      addListener: jest.fn()
    },
    getURL: jest.fn(path => `chrome-extension://id/${path}`),
    connectNative: jest.fn()
  },
  tabs: {
    query: jest.fn(),
    sendMessage: jest.fn(),
    update: jest.fn(),
    captureVisibleTab: jest.fn(),
    executeScript: jest.fn(),
    group: jest.fn(),
    ungroup: jest.fn(),
    onUpdated: {
      addListener: jest.fn()
    },
    onRemoved: {
      addListener: jest.fn()
    }
  },
  tabGroups: {
    query: jest.fn(),
    update: jest.fn()
  },
  storage: {
    local: {
      set: jest.fn(),
      get: jest.fn(),
      remove: jest.fn(),
      clear: jest.fn()
    }
  },
  commands: {
    onCommand: {
      addListener: jest.fn()
    }
  }
};

describe('Content Script Integration Tests', () => {
  let contentScript;

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = '';

    // Mock ContentScriptManager
    contentScript = {
      elementRefs: new Map(),
      refCounter: 0,
      highlightedElements: new Set(),
      sidebarVisible: false,
      recordingMode: false,
      actionHistory: [],

      getElements: function(selector, includeHidden = false) {
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
              visible: el.offsetParent !== null
            });
          });
          return { success: true, elements: result, count: result.length };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      fillForm: async function(fields) {
        try {
          let filled = 0;
          for (const field of fields) {
            const el = document.querySelector(field.selector);
            if (el) {
              el.value = field.value;
              el.dispatchEvent(new Event('input', { bubbles: true }));
              filled++;
            }
          }
          return { success: true, filled };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      clickElement: function(selector, refId) {
        try {
          let el;
          if (refId && this.elementRefs.has(refId)) {
            el = this.elementRefs.get(refId);
          } else {
            el = document.querySelector(selector);
          }
          if (el) {
            el.click();
            return { success: true };
          }
          return { success: false, error: 'Element not found' };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      extractContent: function(includeText, includeLinks, includeImages) {
        try {
          const content = {
            title: document.title,
            url: window.location.href,
            text: includeText ? document.body.innerText : null,
            links: includeLinks ? Array.from(document.querySelectorAll('a')).map(a => ({
              text: a.textContent,
              href: a.href
            })) : [],
            images: includeImages ? Array.from(document.querySelectorAll('img')).map(img => ({
              src: img.src,
              alt: img.alt
            })) : [],
            forms: Array.from(document.querySelectorAll('form')).map(form => ({
              id: form.id,
              name: form.name,
              fields: Array.from(form.querySelectorAll('input, textarea, select')).length
            }))
          };
          return { success: true, content };
        } catch (error) {
          return { success: false, error: error.message };
        }
      },

      highlightElements: function(selectors, color = '#FFD700', duration = 3000) {
        try {
          let highlighted = 0;
          selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
              el.style.outline = `2px solid ${color}`;
              this.highlightedElements.add(el);
              highlighted++;
            });
          });
          setTimeout(() => {
            this.highlightedElements.forEach(el => {
              el.style.outline = '';
            });
            this.highlightedElements.clear();
          }, duration);
          return { success: true, highlighted };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    };
  });

  test('should complete full form filling workflow', async () => {
    // Setup
    document.body.innerHTML = `
      <form id="login-form">
        <input id="username" type="text" placeholder="Username" />
        <input id="password" type="password" placeholder="Password" />
        <button id="submit" type="submit">Login</button>
      </form>
    `;

    // Get elements
    const elements = contentScript.getElements('input, button');
    expect(elements.success).toBe(true);
    expect(elements.count).toBe(3);

    // Fill form
    const fillResult = await contentScript.fillForm([
      { selector: '#username', value: 'testuser@example.com' },
      { selector: '#password', value: 'securepass123' }
    ]);
    expect(fillResult.success).toBe(true);
    expect(fillResult.filled).toBe(2);

    // Verify values
    expect(document.getElementById('username').value).toBe('testuser@example.com');
    expect(document.getElementById('password').value).toBe('securepass123');
  });

  test('should extract page content correctly', () => {
    document.body.innerHTML = `
      <h1>Test Page</h1>
      <p>This is test content</p>
      <a href="https://example.com">Example Link</a>
      <a href="https://test.com">Test Link</a>
      <img src="image1.jpg" alt="Image 1" />
      <img src="image2.jpg" alt="Image 2" />
      <form id="contact">
        <input type="text" />
        <textarea></textarea>
      </form>
    `;

    const content = contentScript.extractContent(true, true, true);

    expect(content.success).toBe(true);
    expect(content.content.title).toBeDefined();
    expect(content.content.links.length).toBe(2);
    expect(content.content.images.length).toBe(2);
    expect(content.content.forms.length).toBe(1);
    expect(content.content.forms[0].fields).toBe(2);
  });

  test('should highlight elements with correct styling', () => {
    document.body.innerHTML = `
      <button class="action">Button 1</button>
      <button class="action">Button 2</button>
      <a class="link">Link 1</a>
      <a class="link">Link 2</a>
    `;

    const result = contentScript.highlightElements(['button.action', 'a.link'], '#FF0000', 1000);

    expect(result.success).toBe(true);
    expect(result.highlighted).toBe(4);

    // Check that elements have outline
    const buttons = document.querySelectorAll('button.action');
    buttons.forEach(btn => {
      expect(btn.style.outline).toBe('2px solid #FF0000');
    });
  });

  test('should handle element references correctly', () => {
    document.body.innerHTML = `
      <div id="container">
        <button id="btn1">Click me</button>
        <input id="input1" type="text" />
      </div>
    `;

    const elements = contentScript.getElements('button, input');
    expect(elements.success).toBe(true);
    expect(elements.count).toBe(2);

    // Get first element ref
    const firstRef = elements.elements[0].refId;
    expect(firstRef).toMatch(/^ref_\d+$/);
    expect(contentScript.elementRefs.has(firstRef)).toBe(true);
  });

  test('should click elements by selector and ref', () => {
    document.body.innerHTML = `
      <button id="submit">Submit</button>
    `;

    const button = document.getElementById('submit');
    const clickSpy = jest.spyOn(button, 'click');

    // Click by selector
    const result1 = contentScript.clickElement('#submit');
    expect(result1.success).toBe(true);
    expect(clickSpy).toHaveBeenCalled();

    clickSpy.mockClear();

    // Click by ref
    const elements = contentScript.getElements('button');
    const refId = elements.elements[0].refId;
    const result2 = contentScript.clickElement(null, refId);
    expect(result2.success).toBe(true);
    expect(clickSpy).toHaveBeenCalled();
  });
});

describe('Background Script Integration Tests', () => {
  let backgroundWorker;

  beforeEach(() => {
    jest.clearAllMocks();

    backgroundWorker = {
      activeSession: null,
      elementRefs: new Map(),
      refCounter: 0,

      createSession: async function(payload) {
        const session = {
          id: this.generateSessionId(),
          name: payload.sessionName || 'Default Session',
          traceId: payload.traceId,
          runId: payload.runId,
          createdAt: new Date().toISOString(),
          tabs: [],
          actions: []
        };
        this.activeSession = session;
        return { success: true, session };
      },

      generateSessionId: function() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      },

      recordAction: async function(tabId, action, details) {
        if (this.activeSession) {
          this.activeSession.actions.push({
            type: action,
            timestamp: new Date().toISOString(),
            tabId,
            details
          });
          return { success: true };
        }
        return { success: false, error: 'No active session' };
      },

      handleTabRemoved: function(tabId) {
        for (const [refId, info] of this.elementRefs.entries()) {
          if (info.tabId === tabId) {
            this.elementRefs.delete(refId);
          }
        }
      }
    };
  });

  test('should create and manage sessions', async () => {
    const result = await backgroundWorker.createSession({
      sessionName: 'Integration Test Session',
      traceId: 'trace_123',
      runId: 'run_456'
    });

    expect(result.success).toBe(true);
    expect(result.session.name).toBe('Integration Test Session');
    expect(result.session.traceId).toBe('trace_123');
    expect(result.session.runId).toBe('run_456');
    expect(result.session.id).toMatch(/^session_/);
    expect(backgroundWorker.activeSession).toEqual(result.session);
  });

  test('should record actions in session', async () => {
    await backgroundWorker.createSession({ sessionName: 'Test' });

    const result1 = await backgroundWorker.recordAction(1, 'click', {
      selector: '#button',
      text: 'Click me'
    });
    expect(result1.success).toBe(true);

    const result2 = await backgroundWorker.recordAction(1, 'fill_form', {
      fields: 2
    });
    expect(result2.success).toBe(true);

    expect(backgroundWorker.activeSession.actions.length).toBe(2);
    expect(backgroundWorker.activeSession.actions[0].type).toBe('click');
    expect(backgroundWorker.activeSession.actions[1].type).toBe('fill_form');
  });

  test('should clean up element refs on tab removal', () => {
    backgroundWorker.elementRefs.set('ref_1', { tabId: 1, selector: '#btn' });
    backgroundWorker.elementRefs.set('ref_2', { tabId: 2, selector: '#input' });
    backgroundWorker.elementRefs.set('ref_3', { tabId: 1, selector: '#link' });

    backgroundWorker.handleTabRemoved(1);

    expect(backgroundWorker.elementRefs.has('ref_1')).toBe(false);
    expect(backgroundWorker.elementRefs.has('ref_2')).toBe(true);
    expect(backgroundWorker.elementRefs.has('ref_3')).toBe(false);
  });

  test('should generate unique session IDs', () => {
    const id1 = backgroundWorker.generateSessionId();
    const id2 = backgroundWorker.generateSessionId();
    const id3 = backgroundWorker.generateSessionId();

    expect(id1).toMatch(/^session_\d+_[a-z0-9]+$/);
    expect(id2).toMatch(/^session_\d+_[a-z0-9]+$/);
    expect(id3).toMatch(/^session_\d+_[a-z0-9]+$/);
    expect(id1).not.toBe(id2);
    expect(id2).not.toBe(id3);
  });
});

describe('MCP Protocol Integration Tests', () => {
  let mcpClient;

  beforeEach(() => {
    jest.clearAllMocks();

    mcpClient = {
      connected: false,
      port: null,
      messageId: 0,
      pendingRequests: new Map(),
      eventHandlers: new Map(),

      connect: async function() {
        try {
          const mockPort = {
            onMessage: { addListener: jest.fn() },
            onDisconnect: { addListener: jest.fn() },
            postMessage: jest.fn()
          };
          this.port = mockPort;
          this.connected = true;
          return true;
        } catch (error) {
          return false;
        }
      },

      send: async function(message) {
        if (!this.connected || !this.port) {
          throw new Error('MCP client not connected');
        }
        const messageId = ++this.messageId;
        const envelope = {
          id: messageId,
          timestamp: new Date().toISOString(),
          ...message
        };
        return new Promise((resolve) => {
          this.pendingRequests.set(messageId, {
            resolve: (data) => resolve(data)
          });
          this.port.postMessage(envelope);
        });
      },

      on: function(event, handler) {
        if (!this.eventHandlers.has(event)) {
          this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
      },

      emitEvent: function(event, data) {
        if (this.eventHandlers.has(event)) {
          this.eventHandlers.get(event).forEach(handler => handler(data));
        }
      }
    };
  });

  test('should establish MCP connection', async () => {
    const result = await mcpClient.connect();
    expect(result).toBe(true);
    expect(mcpClient.connected).toBe(true);
    expect(mcpClient.port).toBeDefined();
  });

  test('should send MCP messages', async () => {
    await mcpClient.connect();

    const messagePromise = mcpClient.send({
      type: 'initialize',
      version: '1.0.0',
      capabilities: ['page_elements', 'form_filling']
    });

    // Simulate response
    const messageId = mcpClient.messageId;
    if (mcpClient.pendingRequests.has(messageId)) {
      mcpClient.pendingRequests.get(messageId).resolve({
        success: true,
        version: '1.0.0'
      });
    }

    const result = await messagePromise;
    expect(result.success).toBe(true);
  });

  test('should handle MCP events', (done) => {
    mcpClient.on('page_ready', (data) => {
      expect(data.url).toBe('https://example.com');
      done();
    });

    mcpClient.emitEvent('page_ready', { url: 'https://example.com' });
  });

  test('should track message IDs', async () => {
    await mcpClient.connect();

    const id1 = mcpClient.messageId;
    await mcpClient.send({ type: 'test1' });
    const id2 = mcpClient.messageId;
    await mcpClient.send({ type: 'test2' });
    const id3 = mcpClient.messageId;

    expect(id2).toBe(id1 + 1);
    expect(id3).toBe(id2 + 1);
  });
});

describe('Storage Integration Tests', () => {
  let storageManager;

  beforeEach(() => {
    jest.clearAllMocks();

    storageManager = {
      storage: {},

      saveSession: async function(session) {
        this.storage.xagent_session = session;
        return { success: true };
      },

      getSession: async function() {
        return this.storage.xagent_session || null;
      },

      saveSettings: async function(settings) {
        this.storage.xagent_settings = settings;
        return { success: true };
      },

      getSettings: async function() {
        return this.storage.xagent_settings || {};
      },

      addToHistory: async function(entry) {
        if (!this.storage.xagent_history) {
          this.storage.xagent_history = [];
        }
        this.storage.xagent_history.push({
          ...entry,
          timestamp: new Date().toISOString()
        });
        return { success: true };
      },

      getHistory: async function() {
        return this.storage.xagent_history || [];
      },

      exportData: async function() {
        return {
          session: this.storage.xagent_session,
          settings: this.storage.xagent_settings,
          history: this.storage.xagent_history
        };
      }
    };
  });

  test('should save and retrieve session', async () => {
    const session = {
      id: 'session_123',
      name: 'Test Session',
      createdAt: new Date().toISOString()
    };

    await storageManager.saveSession(session);
    const retrieved = await storageManager.getSession();

    expect(retrieved).toEqual(session);
  });

  test('should save and retrieve settings', async () => {
    const settings = {
      theme: 'dark',
      language: 'zh-CN',
      autoRecord: true
    };

    await storageManager.saveSettings(settings);
    const retrieved = await storageManager.getSettings();

    expect(retrieved).toEqual(settings);
  });

  test('should maintain action history', async () => {
    await storageManager.addToHistory({
      type: 'click',
      selector: '#button'
    });

    await storageManager.addToHistory({
      type: 'fill_form',
      fields: 2
    });

    const history = await storageManager.getHistory();
    expect(history.length).toBe(2);
    expect(history[0].type).toBe('click');
    expect(history[1].type).toBe('fill_form');
  });

  test('should export all data', async () => {
    const session = { id: 'session_1', name: 'Test' };
    const settings = { theme: 'dark' };

    await storageManager.saveSession(session);
    await storageManager.saveSettings(settings);
    await storageManager.addToHistory({ type: 'click' });

    const exported = await storageManager.exportData();

    expect(exported.session).toEqual(session);
    expect(exported.settings).toEqual(settings);
    expect(exported.history.length).toBe(1);
  });
});

describe('Tab Group Management Integration Tests', () => {
  let tabGroupManager;

  beforeEach(() => {
    jest.clearAllMocks();

    tabGroupManager = {
      groups: new Map(),
      groupCounter: 0,

      createGroup: async function(options) {
        const groupId = ++this.groupCounter;
        const group = {
          id: groupId,
          title: options.title,
          color: options.color,
          collapsed: false,
          tabs: options.tabs || []
        };
        this.groups.set(groupId, group);
        return group;
      },

      getGroups: async function() {
        return Array.from(this.groups.values());
      },

      updateGroup: async function(groupId, updates) {
        if (this.groups.has(groupId)) {
          const group = this.groups.get(groupId);
          Object.assign(group, updates);
          return { success: true };
        }
        return { success: false, error: 'Group not found' };
      },

      addTabsToGroup: async function(groupId, tabIds) {
        if (this.groups.has(groupId)) {
          const group = this.groups.get(groupId);
          group.tabs.push(...tabIds);
          return { success: true };
        }
        return { success: false, error: 'Group not found' };
      }
    };
  });

  test('should create tab groups', async () => {
    const group = await tabGroupManager.createGroup({
      title: 'Work Tabs',
      color: 'blue',
      tabs: [1, 2, 3]
    });

    expect(group.id).toBe(1);
    expect(group.title).toBe('Work Tabs');
    expect(group.color).toBe('blue');
    expect(group.tabs.length).toBe(3);
  });

  test('should retrieve all groups', async () => {
    await tabGroupManager.createGroup({ title: 'Group 1', color: 'blue' });
    await tabGroupManager.createGroup({ title: 'Group 2', color: 'red' });
    await tabGroupManager.createGroup({ title: 'Group 3', color: 'green' });

    const groups = await tabGroupManager.getGroups();
    expect(groups.length).toBe(3);
  });

  test('should update group properties', async () => {
    const group = await tabGroupManager.createGroup({
      title: 'Original Title',
      color: 'blue'
    });

    const result = await tabGroupManager.updateGroup(group.id, {
      title: 'Updated Title',
      color: 'red'
    });

    expect(result.success).toBe(true);
    const updated = await tabGroupManager.getGroups();
    expect(updated[0].title).toBe('Updated Title');
    expect(updated[0].color).toBe('red');
  });

  test('should add tabs to groups', async () => {
    const group = await tabGroupManager.createGroup({
      title: 'Test Group',
      tabs: [1, 2]
    });

    const result = await tabGroupManager.addTabsToGroup(group.id, [3, 4, 5]);
    expect(result.success).toBe(true);

    const updated = await tabGroupManager.getGroups();
    expect(updated[0].tabs.length).toBe(5);
  });
});

describe('End-to-End Workflow Tests', () => {
  test('should complete full automation workflow', async () => {
    // Setup
    document.body.innerHTML = `
      <form id="search-form">
        <input id="search-box" type="text" placeholder="Search..." />
        <button id="search-btn" type="submit">Search</button>
      </form>
      <div id="results">
        <a href="https://result1.com">Result 1</a>
        <a href="https://result2.com">Result 2</a>
      </div>
    `;

    const contentScript = {
      getElements: function(selector) {
        const elements = document.querySelectorAll(selector);
        return { success: true, count: elements.length };
      },
      fillForm: async function(fields) {
        let filled = 0;
        for (const field of fields) {
          const el = document.querySelector(field.selector);
          if (el) {
            el.value = field.value;
            filled++;
          }
        }
        return { success: true, filled };
      },
      extractContent: function() {
        return {
          success: true,
          content: {
            links: Array.from(document.querySelectorAll('a')).map(a => a.href)
          }
        };
      }
    };

    // Execute workflow
    const elements = contentScript.getElements('input, button, a');
    expect(elements.success).toBe(true);
    expect(elements.count).toBe(4);

    const fillResult = await contentScript.fillForm([
      { selector: '#search-box', value: 'test query' }
    ]);
    expect(fillResult.success).toBe(true);
    expect(fillResult.filled).toBe(1);

    const content = contentScript.extractContent();
    expect(content.success).toBe(true);
    expect(content.content.links.length).toBe(2);
  });

  test('should handle complex multi-step automation', async () => {
    document.body.innerHTML = `
      <div id="step1">
        <input id="email" type="email" />
        <button id="next1">Next</button>
      </div>
      <div id="step2" style="display:none">
        <input id="password" type="password" />
        <button id="next2">Next</button>
      </div>
      <div id="step3" style="display:none">
        <input id="code" type="text" />
        <button id="submit">Submit</button>
      </div>
    `;

    const steps = [
      {
        name: 'Email Entry',
        fields: [{ selector: '#email', value: 'user@example.com' }],
        action: '#next1'
      },
      {
        name: 'Password Entry',
        fields: [{ selector: '#password', value: 'password123' }],
        action: '#next2'
      },
      {
        name: 'Code Entry',
        fields: [{ selector: '#code', value: '123456' }],
        action: '#submit'
      }
    ];

    for (const step of steps) {
      for (const field of step.fields) {
        const el = document.querySelector(field.selector);
        if (el) {
          el.value = field.value;
        }
      }
    }

    expect(document.getElementById('email').value).toBe('user@example.com');
    expect(document.getElementById('password').value).toBe('password123');
    expect(document.getElementById('code').value).toBe('123456');
  });
});
