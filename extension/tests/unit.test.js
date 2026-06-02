/**
 * X-Agent Chrome Extension - Unit Tests
 * 使用Jest框架进行单元测试
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
    ungroup: jest.fn()
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

describe('StorageManager', () => {
  let storageManager;

  beforeEach(() => {
    jest.clearAllMocks();
    // Import after mocking
    const { StorageManager } = require('../storage-manager.js');
    storageManager = new StorageManager();
  });

  test('should save and retrieve session', async () => {
    const session = {
      id: 'session_1',
      name: 'Test Session',
      createdAt: new Date().toISOString()
    };

    chrome.storage.local.set.mockResolvedValue(undefined);
    chrome.storage.local.get.mockResolvedValue({
      xagent_session: session
    });

    await storageManager.saveSession(session);
    const retrieved = await storageManager.getSession();

    expect(retrieved).toEqual(session);
  });

  test('should save and retrieve settings', async () => {
    const settings = {
      theme: 'dark',
      language: 'zh-CN'
    };

    chrome.storage.local.set.mockResolvedValue(undefined);
    chrome.storage.local.get.mockResolvedValue({
      xagent_settings: settings
    });

    await storageManager.saveSettings(settings);
    const retrieved = await storageManager.getSettings();

    expect(retrieved).toEqual(settings);
  });

  test('should add to history', async () => {
    const entry = {
      type: 'click',
      selector: '#button'
    };

    chrome.storage.local.set.mockResolvedValue(undefined);
    chrome.storage.local.get.mockResolvedValue({
      xagent_history: []
    });

    const result = await storageManager.addToHistory(entry);

    expect(result.success).toBe(true);
  });

  test('should handle cache with TTL', async () => {
    const value = { data: 'test' };

    chrome.storage.local.set.mockResolvedValue(undefined);
    chrome.storage.local.get.mockResolvedValue({
      xagent_cache: {
        'test_key': {
          value,
          timestamp: Date.now(),
          ttl: 3600000
        }
      }
    });

    await storageManager.saveCache('test_key', value);
    const retrieved = await storageManager.getCache('test_key');

    expect(retrieved).toEqual(value);
  });

  test('should export data', async () => {
    const session = { id: 'session_1' };
    const settings = { theme: 'dark' };
    const history = [];

    chrome.storage.local.get
      .mockResolvedValueOnce({ xagent_session: session })
      .mockResolvedValueOnce({ xagent_settings: settings })
      .mockResolvedValueOnce({ xagent_history: history });

    const exported = await storageManager.exportData();

    expect(exported.session).toEqual(session);
    expect(exported.settings).toEqual(settings);
    expect(exported.history).toEqual(history);
  });
});

describe('TabGroupManager', () => {
  let tabGroupManager;

  beforeEach(() => {
    jest.clearAllMocks();
    const { TabGroupManager } = require('../tab-group-manager.js');
    tabGroupManager = new TabGroupManager();
  });

  test('should get tab groups', async () => {
    const mockGroups = [
      {
        id: 1,
        title: 'Group 1',
        color: 'blue',
        collapsed: false
      }
    ];

    chrome.tabGroups.query.mockResolvedValue(mockGroups);
    chrome.tabs.query.mockResolvedValue([
      { id: 1, title: 'Tab 1', url: 'https://example.com' }
    ]);

    const groups = await tabGroupManager.getGroups();

    expect(groups.length).toBeGreaterThan(0);
  });

  test('should create tab group', async () => {
    chrome.tabs.group.mockResolvedValue(1);
    chrome.tabGroups.update.mockResolvedValue(undefined);

    const group = await tabGroupManager.createGroup({
      title: 'New Group',
      color: 'blue',
      tabs: [1, 2, 3]
    });

    expect(group.title).toBe('New Group');
    expect(group.color).toBe('blue');
  });

  test('should update tab group', async () => {
    chrome.tabGroups.update.mockResolvedValue(undefined);

    const result = await tabGroupManager.updateGroup(1, {
      title: 'Updated Group',
      color: 'red'
    });

    expect(result.success).toBe(true);
  });

  test('should add tabs to group', async () => {
    chrome.tabs.group.mockResolvedValue(undefined);

    const result = await tabGroupManager.addTabsToGroup(1, [4, 5, 6]);

    expect(result.success).toBe(true);
  });
});

describe('MCPClient', () => {
  let mcpClient;

  beforeEach(() => {
    jest.clearAllMocks();
    const { MCPClient } = require('../mcp-client.js');
    mcpClient = new MCPClient();
  });

  test('should initialize connection', async () => {
    const mockPort = {
      onMessage: { addListener: jest.fn() },
      onDisconnect: { addListener: jest.fn() },
      postMessage: jest.fn()
    };

    chrome.runtime.connectNative.mockReturnValue(mockPort);

    const result = await mcpClient.connect();

    expect(result).toBe(true);
    expect(mcpClient.connected).toBe(true);
  });

  test('should send message', async () => {
    const mockPort = {
      onMessage: { addListener: jest.fn() },
      onDisconnect: { addListener: jest.fn() },
      postMessage: jest.fn()
    };

    chrome.runtime.connectNative.mockReturnValue(mockPort);
    mcpClient.port = mockPort;
    mcpClient.connected = true;

    const promise = mcpClient.send({ type: 'test' });

    // Simulate response
    const handlers = mockPort.onMessage.addListener.mock.calls[0];
    if (handlers) {
      handlers[0]({ id: 1, data: { success: true } });
    }

    const result = await promise;
    expect(result).toBeDefined();
  });

  test('should handle reconnection', async () => {
    const mockPort = {
      onMessage: { addListener: jest.fn() },
      onDisconnect: { addListener: jest.fn() },
      postMessage: jest.fn()
    };

    chrome.runtime.connectNative.mockReturnValue(mockPort);

    mcpClient.handleDisconnect();

    expect(mcpClient.connected).toBe(false);
  });

  test('should emit events', (done) => {
    mcpClient.on('test_event', (data) => {
      expect(data).toEqual({ message: 'test' });
      done();
    });

    mcpClient.emitEvent('test_event', { message: 'test' });
  });
});

describe('ContentScriptManager', () => {
  let contentScript;

  beforeEach(() => {
    jest.clearAllMocks();
    const { ContentScriptManager } = require('../content.js');
    contentScript = new ContentScriptManager();
  });

  test('should get elements', () => {
    // Mock DOM
    document.body.innerHTML = `
      <button id="btn1">Click me</button>
      <input id="input1" type="text" />
      <a href="#">Link</a>
    `;

    const result = contentScript.getElements('button, input, a');

    expect(result.success).toBe(true);
    expect(result.count).toBe(3);
  });

  test('should get element info', () => {
    document.body.innerHTML = `
      <input id="test-input" type="text" value="test" placeholder="Enter text" />
    `;

    const result = contentScript.getElementInfo('#test-input');

    expect(result.success).toBe(true);
    expect(result.data.tag).toBe('INPUT');
    expect(result.data.value).toBe('test');
  });

  test('should fill form', async () => {
    document.body.innerHTML = `
      <input id="username" type="text" />
      <input id="password" type="password" />
    `;

    const result = await contentScript.fillForm([
      { selector: '#username', value: 'user@example.com' },
      { selector: '#password', value: 'password123' }
    ]);

    expect(result.success).toBe(true);
    expect(result.filled).toBe(2);
  });

  test('should extract content', () => {
    document.body.innerHTML = `
      <h1>Test Page</h1>
      <p>Test content</p>
      <a href="https://example.com">Link</a>
      <img src="image.jpg" alt="Test image" />
    `;

    const result = contentScript.extractContent(true, true, true);

    expect(result.success).toBe(true);
    expect(result.content.title).toBeDefined();
    expect(result.content.links.length).toBeGreaterThan(0);
    expect(result.content.images.length).toBeGreaterThan(0);
  });

  test('should highlight elements', () => {
    document.body.innerHTML = `
      <button>Button 1</button>
      <button>Button 2</button>
      <a>Link</a>
    `;

    const result = contentScript.highlightElements(['button', 'a'], '#FFD700', 1000);

    expect(result.success).toBe(true);
    expect(result.highlighted).toBeGreaterThan(0);
  });

  test('should generate selector', () => {
    document.body.innerHTML = `
      <div id="container">
        <form id="login-form">
          <input id="username" type="text" />
        </form>
      </div>
    `;

    const input = document.getElementById('username');
    const selector = contentScript.getSelector(input);

    expect(selector).toContain('username');
  });
});

describe('BackgroundWorker', () => {
  let backgroundWorker;

  beforeEach(() => {
    jest.clearAllMocks();
    const { BackgroundWorker } = require('../background.js');
    backgroundWorker = new BackgroundWorker();
  });

  test('should create session', async () => {
    const result = await backgroundWorker.createSession({
      sessionName: 'Test Session'
    });

    expect(result.success).toBe(true);
    expect(result.session.name).toBe('Test Session');
  });

  test('should generate session ID', () => {
    const id1 = backgroundWorker.generateSessionId();
    const id2 = backgroundWorker.generateSessionId();

    expect(id1).toMatch(/^session_/);
    expect(id2).toMatch(/^session_/);
    expect(id1).not.toBe(id2);
  });

  test('should handle tab update', () => {
    chrome.tabs.sendMessage.mockResolvedValue({ success: true });

    backgroundWorker.handleTabUpdate(1, { status: 'complete' }, {
      id: 1,
      url: 'https://example.com'
    });

    expect(chrome.tabs.sendMessage).toHaveBeenCalled();
  });

  test('should handle tab removal', () => {
    backgroundWorker.elementRefs.set('ref_1', { tabId: 1 });
    backgroundWorker.elementRefs.set('ref_2', { tabId: 2 });

    backgroundWorker.handleTabRemoved(1);

    expect(backgroundWorker.elementRefs.has('ref_1')).toBe(false);
    expect(backgroundWorker.elementRefs.has('ref_2')).toBe(true);
  });
});

describe('Integration Tests', () => {
  test('should complete full workflow', async () => {
    // Setup
    document.body.innerHTML = `
      <form id="login">
        <input id="username" type="text" />
        <input id="password" type="password" />
        <button id="submit">Login</button>
      </form>
    `;

    const { ContentScriptManager } = require('../content.js');
    const contentScript = new ContentScriptManager();

    // Get elements
    const elements = contentScript.getElements('input, button');
    expect(elements.success).toBe(true);

    // Fill form
    const fillResult = await contentScript.fillForm([
      { selector: '#username', value: 'user@example.com' },
      { selector: '#password', value: 'password123' }
    ]);
    expect(fillResult.success).toBe(true);

    // Extract content
    const content = contentScript.extractContent(true, true, true);
    expect(content.success).toBe(true);
    expect(content.content.forms.length).toBeGreaterThan(0);
  });
});
