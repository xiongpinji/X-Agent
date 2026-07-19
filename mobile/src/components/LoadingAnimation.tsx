// mobile/src/components/LoadingAnimation.tsx
// 加载动画组件

import React, { useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  ActivityIndicator,
  Text,
} from 'react-native';
import { useTheme } from '../theme';

interface LoadingAnimationProps {
  visible: boolean;
  message?: string;
  size?: 'small' | 'large';
}

export const LoadingAnimation: React.FC<LoadingAnimationProps> = ({
  visible,
  message,
  size = 'large',
}) => {
  const { theme } = useTheme();
  const opacityAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.timing(opacityAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();
    } else {
      Animated.timing(opacityAnim, {
        toValue: 0,
        duration: 300,
        useNativeDriver: true,
      }).start();
    }
  }, [visible, opacityAnim]);

  if (!visible) {
    return null;
  }

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: theme.colors.background,
          opacity: opacityAnim,
        },
      ]}
    >
      <View style={styles.content}>
        <ActivityIndicator
          size={size}
          color={theme.colors.primary}
          style={styles.spinner}
        />
        {message && (
          <Text style={[styles.message, { color: theme.colors.textSecondary }]}>
            {message}
          </Text>
        )}
      </View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  content: {
    alignItems: 'center',
  },
  spinner: {
    marginBottom: 16,
  },
  message: {
    fontSize: 14,
    fontWeight: '500',
  },
});

// 同步状态指示器组件
interface SyncStatusIndicatorProps {
  status: 'synced' | 'syncing' | 'failed' | 'offline';
  lastSyncTime?: Date;
}

export const SyncStatusIndicator: React.FC<SyncStatusIndicatorProps> = ({
  status,
  lastSyncTime,
}) => {
  const { theme } = useTheme();
  const rotateAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (status === 'syncing') {
      Animated.loop(
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        })
      ).start();
    } else {
      rotateAnim.setValue(0);
    }
  }, [status, rotateAnim]);

  const getStatusColor = () => {
    switch (status) {
      case 'synced':
        return theme.colors.success;
      case 'syncing':
        return theme.colors.warning;
      case 'failed':
        return theme.colors.error;
      case 'offline':
        return theme.colors.textTertiary;
      default:
        return theme.colors.textTertiary;
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'synced':
        return 'check-circle';
      case 'syncing':
        return 'sync';
      case 'failed':
        return 'alert-circle';
      case 'offline':
        return 'wifi-off';
      default:
        return 'help-circle';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'synced':
        return lastSyncTime
          ? `Synced ${formatTimeAgo(lastSyncTime)}`
          : 'Synced';
      case 'syncing':
        return 'Syncing...';
      case 'failed':
        return 'Sync failed';
      case 'offline':
        return 'Offline';
      default:
        return 'Unknown';
    }
  };

  const rotation = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <View style={styles.syncContainer}>
      <Animated.View
        style={[
          styles.syncIcon,
          status === 'syncing' && { transform: [{ rotate: rotation }] },
        ]}
      >
        {/* Icon would be rendered here */}
      </Animated.View>
      <Text
        style={[
          styles.syncText,
          { color: getStatusColor() },
        ]}
      >
        {getStatusText()}
      </Text>
    </View>
  );
};

const syncStyles = StyleSheet.create({
  syncContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  syncIcon: {
    marginRight: 8,
  },
  syncText: {
    fontSize: 12,
    fontWeight: '500',
  },
});

// 错误提示组件
interface ErrorAlertProps {
  visible: boolean;
  message: string;
  onDismiss?: () => void;
  type?: 'error' | 'warning' | 'info';
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  visible,
  message,
  onDismiss,
  type = 'error',
}) => {
  const { theme } = useTheme();
  const slideAnim = useRef(new Animated.Value(-100)).current;

  useEffect(() => {
    if (visible) {
      Animated.spring(slideAnim, {
        toValue: 0,
        useNativeDriver: true,
      }).start();

      const timer = setTimeout(() => {
        onDismiss?.();
      }, 4000);

      return () => clearTimeout(timer);
    } else {
      Animated.timing(slideAnim, {
        toValue: -100,
        duration: 300,
        useNativeDriver: true,
      }).start();
    }
  }, [visible, slideAnim, onDismiss]);

  const getBackgroundColor = () => {
    switch (type) {
      case 'error':
        return theme.colors.error + '20';
      case 'warning':
        return theme.colors.warning + '20';
      case 'info':
        return theme.colors.info + '20';
      default:
        return theme.colors.error + '20';
    }
  };

  const getTextColor = () => {
    switch (type) {
      case 'error':
        return theme.colors.error;
      case 'warning':
        return theme.colors.warning;
      case 'info':
        return theme.colors.info;
      default:
        return theme.colors.error;
    }
  };

  if (!visible) {
    return null;
  }

  return (
    <Animated.View
      style={[
        styles.alertContainer,
        {
          backgroundColor: getBackgroundColor(),
          transform: [{ translateY: slideAnim }],
        },
      ]}
    >
      <Text style={[styles.alertText, { color: getTextColor() }]}>
        {message}
      </Text>
    </Animated.View>
  );
};

const alertStyles = StyleSheet.create({
  alertContainer: {
    marginHorizontal: 16,
    marginVertical: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
  },
  alertText: {
    fontSize: 14,
    fontWeight: '500',
  },
});

// 合并样式
Object.assign(styles, syncStyles, alertStyles);
