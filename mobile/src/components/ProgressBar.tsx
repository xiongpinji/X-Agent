// mobile/src/components/ProgressBar.tsx
// 跨平台进度条组件
// 说明：RN 0.73 已移除 ProgressViewIOS，ProgressBarAndroid 也已弃用，
// 这里用纯 View 实现，保证双端一致且不引入额外原生依赖。

import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';

interface ProgressBarProps {
  /** 0 ~ 1 之间的进度值 */
  progress: number;
  color?: string;
  trackColor?: string;
  height?: number;
  style?: ViewStyle;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  color = '#007AFF',
  trackColor = '#E5E5EA',
  height = 6,
  style,
}) => {
  const clamped = Math.min(1, Math.max(0, progress));

  return (
    <View
      style={[
        styles.track,
        { backgroundColor: trackColor, height, borderRadius: height / 2 },
        style,
      ]}
    >
      <View
        style={{
          backgroundColor: color,
          height,
          borderRadius: height / 2,
          width: `${clamped * 100}%`,
        }}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  track: {
    width: '100%',
    overflow: 'hidden',
  },
});
