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
    '!dist/**'
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 75,
      lines: 75,
      statements: 75
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
