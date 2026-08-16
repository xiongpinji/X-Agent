// mobile/src/services/pushNotificationManager.ts
// 推送通知管理

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { v4 as uuidv4 } from 'uuid';
import { PushNotification } from '../types';
import { apiClient } from './apiClient';

const DEVICE_ID_KEY = 'mobile_device_id';

class PushNotificationManager {
  async initialize(): Promise<void> {
    // 请求权限
    if (Device.isDevice) {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== 'granted') {
        console.warn('Failed to get push token for push notification!');
        return;
      }

      // 获取推送token
      const token = await this.getPushToken();

      // 将token发送到后端
      await this.registerPushToken(token);
    }

    // 设置通知处理器
    this.setupNotificationHandlers();
  }

  private async getPushToken(): Promise<string> {
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    if (!projectId) {
      throw new Error('Project ID not found');
    }

    const token = await Notifications.getExpoPushTokenAsync({
      projectId,
    });

    return token.data;
  }

  private async registerPushToken(token: string): Promise<void> {
    let deviceId = await SecureStore.getItemAsync(DEVICE_ID_KEY);
    if (!deviceId) {
      deviceId = uuidv4();
      await SecureStore.setItemAsync(DEVICE_ID_KEY, deviceId);
    }
    await apiClient.post('/api/v1/mobile/push/register', {
      device_id: deviceId,
      platform: Platform.OS,
      push_token: token,
    });
  }

  private setupNotificationHandlers(): void {
    // 处理前台通知
    Notifications.setNotificationHandler({
      handleNotification: async (_notification) => {
        return {
          shouldShowAlert: true,
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: true,
          shouldSetBadge: true,
        };
      },
    });

    // 处理通知响应
    Notifications.addNotificationResponseReceivedListener((response) => {
      this.handleNotificationResponse(response);
    });

    // 处理后台通知
    Notifications.addNotificationReceivedListener((notification) => {
      this.handleNotificationReceived(notification);
    });
  }

  private handleNotificationResponse(response: any): void {
    const notification = response.notification.request.content.data as PushNotification;

    // 处理深度链接
    if (notification.deepLink) {
      // 导航到指定页面
    }
  }

  private handleNotificationReceived(_notification: any): void {}

  async sendLocalNotification(notification: PushNotification): Promise<void> {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: notification.title,
        body: notification.body,
        badge: notification.badge,
        sound: notification.sound,
        data: notification.data,
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
        seconds: 1,
      },
    });
  }

  async cancelAllNotifications(): Promise<void> {
    await Notifications.cancelAllScheduledNotificationsAsync();
  }
}

export const pushNotificationManager = new PushNotificationManager();
