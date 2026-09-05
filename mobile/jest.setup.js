// mobile/jest.setup.js
// 测试环境全局 mock

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    // 默认无 app.json extra；测试文件可通过重新 jest.mock 覆盖以验证优先级
    expoConfig: undefined,
  },
}));
