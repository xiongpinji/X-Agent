// mobile/babel.config.js
// Babel 配置：Expo 预设 + Reanimated 插件（必须放在最后）

module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: ['react-native-reanimated/plugin'],
  };
};
