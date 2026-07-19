// mobile/src/services/pushNotificationManager.ts
// 推送通知管理

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { PushNotification } from '../types';

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
      console.log('Push token:', token);

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
    try {
      await fetch('https://api.xagent.local/notifications/register-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
    } catch (error) {
      console.error('Register push token error:', error);
    }
  }

  private setupNotificationHandlers(): void {
    // 处理前台通知
    Notifications.setNotificationHandler({
      handleNotification: async (notification) => {
        return {
          shouldShowAlert: true,
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
    console.log('Notification response:', notification);

    // 处理深度链接
    if (notification.deepLink) {
      // 导航到指定页面
    }
  }

  private handleNotificationReceived(notification: any): void {
    const data = notification.request.content.data as PushNotification;
    console.log('Notification received:', data);

    // 更新应用状态
    // 例如：刷新任务列表、更新工作流状态等
  }

  async sendLocalNotification(notification: PushNotification): Promise<void> {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: notification.title,
        body: notification.body,
        badge: notification.badge,
        sound: notification.sound,
        data: notification.data,
      },
      trigger: { seconds: 1 },
    });
  }

  async cancelAllNotifications(): Promise<void> {
    await Notifications.cancelAllScheduledNotificationsAsync();
  }
}

export const pushNotificationManager = new PushNotificationManager();
