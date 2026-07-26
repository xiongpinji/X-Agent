// mobile/jest.config.js
// 组件/服务级测试基建 (首次引入, 供 npm test 使用)
module.exports = {
  preset: 'react-native',
  setupFiles: ['<rootDir>/jest.setup.js'],
  testMatch: ['<rootDir>/src/**/__tests__/**/*.test.{ts,tsx}'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transformIgnorePatterns: [
    'node_modules/(?!(react-native|@react-native|@react-navigation|react-native-.*|@expo|expo.*)/)',
  ],
};
