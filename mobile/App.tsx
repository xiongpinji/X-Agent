// mobile/App.tsx
// 根组件：挂载主题 Provider 与根导航

import React from 'react';
import { ThemeProvider } from './src/theme';
import { RootNavigator } from './src/navigation';

export default function App() {
  return (
    <ThemeProvider>
      <RootNavigator />
    </ThemeProvider>
  );
}
