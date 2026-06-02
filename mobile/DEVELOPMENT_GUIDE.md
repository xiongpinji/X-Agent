# X-Agent 移动端开发指南

**版本：** v1.0  
**日期：** 2026-05-27

---

## 1. 快速开始

### 1.1 环境设置

```bash
# 安装Node.js 18+
node --version

# 安装Expo CLI
npm install -g expo-cli

# 克隆项目
git clone https://github.com/xagent/mobile.git
cd mobile

# 安装依赖
npm install

# 安装iOS依赖（仅Mac）
cd ios && pod install && cd ..

# 安装Android依赖
cd android && ./gradlew build && cd ..
```

### 1.2 开发服务器

```bash
# 启动Expo开发服务器
npm start

# 在iOS模拟器中运行
npm run ios

# 在Android模拟器中运行
npm run android

# 在Web浏览器中运行
npm run web
```

### 1.3 项目结构

```
mobile/
├── src/
│   ├── screens/           # 页面组件
│   ├── components/        # 可复用组件
│   ├── services/          # 业务逻辑服务
│   │   ├── apiClient.ts   # API客户端
│   │   ├── database.ts    # SQLite数据库
│   │   ├── syncManager.ts # 离线同步
│   │   └── pushNotificationManager.ts
│   ├── store/             # 状态管理
│   │   ├── authStore.ts
│   │   ├── taskStore.ts
│   │   └── workflowStore.ts
│   ├── types/             # TypeScript类型
│   ├── native/            # 原生模块
│   ├── utils/             # 工具函数
│   └── App.tsx            # 应用入口
├── ios/                   # iOS原生代码
├── android/               # Android原生代码
├── app.json               # Expo配置
├── eas.json               # EAS Build配置
├── package.json           # 项目配置
└── tsconfig.json          # TypeScript配置
```

---

## 2. 核心功能开发

### 2.1 添加新页面

```typescript
// src/screens/NewScreen.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface NewScreenProps {
  navigation: any;
  route: any;
}

export const NewScreen: React.FC<NewScreenProps> = ({ navigation, route }) => {
  return (
    <View style={styles.container}>
      <Text>New Screen</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
```

### 2.2 添加新API端点

```typescript
// src/services/taskService.ts
import { apiClient } from './apiClient';
import { Task } from '../types';

export const taskService = {
  async getTasks(page = 1, pageSize = 20): Promise<Task[]> {
    return apiClient.get(`/tasks?page=${page}&pageSize=${pageSize}`);
  },

  async getTask(id: string): Promise<Task> {
    return apiClient.get(`/tasks/${id}`);
  },

  async createTask(task: Omit<Task, 'id' | 'createdAt' | 'updatedAt'>): Promise<Task> {
    return apiClient.post('/tasks', task);
  },

  async updateTask(id: string, updates: Partial<Task>): Promise<Task> {
    return apiClient.put(`/tasks/${id}`, updates);
  },

  async deleteTask(id: string): Promise<void> {
    return apiClient.delete(`/tasks/${id}`);
  },
};
```

### 2.3 添加新状态管理

```typescript
// src/store/newStore.ts
import { create } from 'zustand';

interface NewStore {
  data: any[];
  loading: boolean;
  error?: string;

  fetchData: () => Promise<void>;
  setData: (data: any[]) => void;
  clearError: () => void;
}

export const useNewStore = create<NewStore>((set) => ({
  data: [],
  loading: false,

  fetchData: async () => {
    set({ loading: true, error: undefined });
    try {
      // 获取数据
      set({ loading: false });
    } catch (error) {
      set({ error: String(error), loading: false });
    }
  },

  setData: (data: any[]) => set({ data }),
  clearError: () => set({ error: undefined }),
}));
```

---

## 3. 离线功能开发

### 3.1 离线操作

```typescript
// 在离线时添加操作到队列
import { syncManager } from '../services/syncManager';

async function createTaskOffline(task: Task) {
  // 先保存到本地数据库
  await database.insertTask(task);

  // 添加到同步队列
  await syncManager.queueOperation('create', 'task', task.id, task);
}
```

### 3.2 监听同步状态

```typescript
// 在组件中监听同步状态
import { useEffect, useState } from 'react';
import { syncManager } from '../services/syncManager';

export function useSyncStatus() {
  const [syncStatus, setSyncStatus] = useState({
    isSyncing: false,
    queueSize: 0,
    lastSyncTime: undefined,
  });

  useEffect(() => {
    const interval = setInterval(async () => {
      const status = await syncManager.getSyncStatus();
      setSyncStatus(status);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return syncStatus;
}
```

---

## 4. 原生模块开发

### 4.1 iOS原生模块

```swift
// ios/BiometricAuthModule.swift
import Foundation
import LocalAuthentication
import React

@objc(BiometricAuthModule)
class BiometricAuthModule: NSObject {
  @objc
  func authenticate(_ reason: String,
                   resolver resolve: @escaping RCTPromiseResolveBlock,
                   rejecter reject: @escaping RCTPromiseRejectBlock) {
    let context = LAContext()
    var error: NSError?

    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
      reject("BIOMETRIC_NOT_AVAILABLE", "Biometric authentication not available", error)
      return
    }

    context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, error in
      DispatchQueue.main.async {
        if success {
          resolve(["success": true])
        } else {
          reject("BIOMETRIC_AUTH_FAILED", "Biometric authentication failed", error)
        }
      }
    }
  }
}
```

### 4.2 Android原生模块

```kotlin
// android/app/src/main/java/com/xagent/BiometricAuthModule.kt
package com.xagent

import androidx.biometric.BiometricPrompt
import com.facebook.react.bridge.*

class BiometricAuthModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

  @ReactMethod
  fun authenticate(reason: String, promise: Promise) {
    try {
      val activity = currentActivity as? FragmentActivity
        ?: throw Exception("Activity not available")

      val biometricPrompt = BiometricPrompt(
        activity,
        Executor { command -> command.run() },
        object : BiometricPrompt.AuthenticationCallback() {
          override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
            super.onAuthenticationSucceeded(result)
            val response = Arguments.createMap()
            response.putBoolean("success", true)
            promise.resolve(response)
          }

          override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
            super.onAuthenticationError(errorCode, errString)
            promise.reject("AUTH_ERROR", errString.toString())
          }
        }
      )

      val promptInfo = BiometricPrompt.PromptInfo.Builder()
        .setTitle("Biometric Authentication")
        .setSubtitle(reason)
        .setNegativeButtonText("Cancel")
        .build()

      biometricPrompt.authenticate(promptInfo)
    } catch (e: Exception) {
      promise.reject("ERROR", e.message)
    }
  }
}
```

---

## 5. 测试

### 5.1 单元测试

```typescript
// src/__tests__/taskStore.test.ts
import { useTaskStore } from '../store/taskStore';

describe('TaskStore', () => {
  it('should fetch tasks', async () => {
    const store = useTaskStore.getState();
    await store.fetchTasks();
    expect(store.tasks.length).toBeGreaterThan(0);
  });

  it('should create task', async () => {
    const store = useTaskStore.getState();
    const initialLength = store.tasks.length;
    await store.createTask({
      title: 'Test Task',
      description: 'Test',
      status: 'pending',
      priority: 'high',
      parameters: {},
      syncStatus: 'pending',
    });
    expect(store.tasks.length).toBe(initialLength + 1);
  });
});
```

### 5.2 集成测试

```typescript
// e2e/taskFlow.e2e.ts
describe('Task Flow', () => {
  beforeAll(async () => {
    await device.launchApp();
  });

  beforeEach(async () => {
    await device.reloadReactNative();
  });

  it('should create and view task', async () => {
    await element(by.id('createTaskButton')).tap();
    await element(by.id('taskTitleInput')).typeText('Test Task');
    await element(by.id('submitButton')).tap();
    await expect(element(by.text('Test Task'))).toBeVisible();
  });
});
```

---

## 6. 性能优化

### 6.1 列表虚拟化

```typescript
import { FlatList } from 'react-native';

<FlatList
  data={tasks}
  renderItem={renderTaskItem}
  keyExtractor={(item) => item.id}
  removeClippedSubviews={true}
  maxToRenderPerBatch={10}
  updateCellsBatchingPeriod={50}
/>
```

### 6.2 图片优化

```typescript
import { Image } from 'react-native';

<Image
  source={{ uri: imageUrl }}
  style={{ width: 200, height: 200 }}
  resizeMode="contain"
  progressiveRenderingEnabled={true}
/>
```

### 6.3 内存管理

```typescript
useEffect(() => {
  const subscription = eventEmitter.addListener('event', handleEvent);

  return () => {
    subscription.remove();
  };
}, []);
```

---

## 7. 调试

### 7.1 Expo DevTools

```bash
# 启动Expo DevTools
npm start

# 按 'd' 打开DevTools
# 按 'i' 在iOS模拟器中打开
# 按 'a' 在Android模拟器中打开
```

### 7.2 React DevTools

```bash
# 安装React DevTools
npm install -g react-devtools

# 启动React DevTools
react-devtools
```

### 7.3 Redux DevTools

```typescript
import { devtools } from 'zustand/middleware';

export const useStore = create<Store>()(
  devtools((set) => ({
    // store implementation
  }))
);
```

---

## 8. 常见问题

### Q1: 如何处理网络超时？

```typescript
const apiClient = axios.create({
  timeout: 30000, // 30秒
});

// 添加重试逻辑
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.code === 'ECONNABORTED') {
      // 处理超时
    }
  }
);
```

### Q2: 如何优化启动时间？

```typescript
// 1. 延迟加载非关键资源
const HeavyComponent = lazy(() => import('./HeavyComponent'));

// 2. 预加载关键数据
useEffect(() => {
  preloadCriticalData();
}, []);

// 3. 使用启动屏幕
<SplashScreen />
```

### Q3: 如何处理内存泄漏？

```typescript
// 1. 清理事件监听
useEffect(() => {
  const subscription = eventEmitter.addListener('event', handler);
  return () => subscription.remove();
}, []);

// 2. 取消网络请求
useEffect(() => {
  const controller = new AbortController();
  fetch(url, { signal: controller.signal });
  return () => controller.abort();
}, []);
```

---

## 9. 部署

### 9.1 构建iOS应用

```bash
# 构建iOS应用
eas build --platform ios

# 提交到App Store
eas submit --platform ios
```

### 9.2 构建Android应用

```bash
# 构建Android应用
eas build --platform android

# 提交到Google Play
eas submit --platform android
```

---

## 10. 资源和参考

- [React Native官方文档](https://reactnative.dev/)
- [Expo官方文档](https://docs.expo.dev/)
- [TypeScript官方文档](https://www.typescriptlang.org/)
- [Zustand文档](https://github.com/pmndrs/zustand)
- [React Navigation文档](https://reactnavigation.org/)
