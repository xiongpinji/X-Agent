module.exports = {
  displayName: 'X-Agent Chrome Extension Tests',
  testEnvironment: 'jsdom',
  testMatch: [
    '**/tests/**/*.test.js'
  ],
  collectCoverageFrom: [
    '*.js',
    '!node_modules/**',
    '!tests/**',
    '!dist/**',
    // Entry points / config that require a live browser environment
    // (jsdom cannot execute them meaningfully) or are not shipped code:
    '!jest.config.js',
    '!babel.config.cjs',
    '!scripts/**',
    '!injected.js', // page-context bridge (window.postMessage world)
    '!popup.js', // UI wiring over the covered api-client.js
    '!options.js' // UI wiring over the covered api-client.js
  ],
  coverageThreshold: {
    global: {
      branches: 35,
      functions: 35,
      lines: 40,
      statements: 40
    }
  },
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  moduleNameMapper: {
    '^chrome://(.*)$': '<rootDir>/tests/__mocks__/chrome.js'
  },
  testTimeout: 10000,
  verbose: true,
  bail: false,
  maxWorkers: '50%'
};
