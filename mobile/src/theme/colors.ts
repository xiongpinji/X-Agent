// mobile/src/theme/colors.ts
// 主题颜色定义

export const lightColors = {
  // 基础颜色
  primary: '#007AFF',
  secondary: '#5AC8FA',
  tertiary: '#34C759',

  // 背景色
  background: '#FFFFFF',
  surface: '#F2F2F7',
  surfaceVariant: '#E5E5EA',

  // 文本色
  text: '#000000',
  textSecondary: '#666666',
  textTertiary: '#999999',
  textInverse: '#FFFFFF',

  // 状态色
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',
  info: '#00C7FF',

  // 边框和分割线
  border: '#E5E5EA',
  divider: '#F2F2F7',

  // 阴影
  shadow: 'rgba(0, 0, 0, 0.1)',
  shadowDark: 'rgba(0, 0, 0, 0.2)',

  // 状态指示器
  statusPending: '#FFF3CD',
  statusRunning: '#CFE2FF',
  statusCompleted: '#D1E7DD',
  statusFailed: '#F8D7DA',

  // 优先级颜色
  priorityLow: '#34C759',
  priorityMedium: '#FF9500',
  priorityHigh: '#FF3B30',
};

export const darkColors = {
  // 基础颜色
  primary: '#0A84FF',
  secondary: '#00B0FF',
  tertiary: '#30B0C0',

  // 背景色
  background: '#000000',
  surface: '#1C1C1E',
  surfaceVariant: '#2C2C2E',

  // 文本色
  text: '#FFFFFF',
  textSecondary: '#A0A0A0',
  textTertiary: '#666666',
  textInverse: '#000000',

  // 状态色
  success: '#30B0C0',
  warning: '#FF9500',
  error: '#FF453A',
  info: '#00B0FF',

  // 边框和分割线
  border: '#3A3A3C',
  divider: '#2C2C2E',

  // 阴影
  shadow: 'rgba(0, 0, 0, 0.3)',
  shadowDark: 'rgba(0, 0, 0, 0.5)',

  // 状态指示器
  statusPending: '#664D03',
  statusRunning: '#084298',
  statusCompleted: '#0F5132',
  statusFailed: '#842029',

  // 优先级颜色
  priorityLow: '#30B0C0',
  priorityMedium: '#FF9500',
  priorityHigh: '#FF453A',
};

export type ColorScheme = typeof lightColors;
