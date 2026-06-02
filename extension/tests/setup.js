/**
 * Jest Setup File
 * Configures test environment and global mocks
 */

// Mock Chrome API globally
global.chrome = {
  runtime: {
    sendMessage: jest.fn(),
    onMessage: {
      addListener: jest.fn()
    },
    getURL: jest.fn(path => `chrome-extension://id/${path}`),
    connectNative: jest.fn(),
    id: 'test-extension-id'
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

// Mock window.location
delete window.location;
window.location = {
  href: 'https://example.com',
  origin: 'https://example.com',
  protocol: 'https:',
  host: 'example.com',
  hostname: 'example.com',
  port: '',
  pathname: '/',
  search: '',
  hash: ''
};

// Mock console methods
global.console = {
  ...console,
  log: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
  info: jest.fn(),
  debug: jest.fn()
};

// Setup test timeout
jest.setTimeout(10000);

// Suppress console output during tests
beforeAll(() => {
  jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
  jest.spyOn(console, 'warn').mockImplementation(() => {});
});

afterAll(() => {
  console.log.mockRestore();
  console.error.mockRestore();
  console.warn.mockRestore();
});
