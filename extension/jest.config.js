module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/tests/commercial.test.js'],
  collectCoverageFrom: [
    'extension-api.js',
    'popup.js',
    'scripts/package-extension.js',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 75,
      lines: 75,
      statements: 75,
    },
  },
  testTimeout: 10000,
}
