# X-Agent 移动端应用

完整的iOS/Android跨平台移动应用实现方案，为X-Agent提供原生移动体验。

## 快速开始

### 前置要求

- Node.js 18+
- Expo CLI
- Xcode 15+ (iOS开发)
- Android Studio 2023+ (Android开发)

### 安装

```bash
# 克隆项目
git clone https://github.com/xagent/mobile.git
cd mobile

# 安装依赖
npm install

# 安装iOS依赖
cd ios && pod install && cd ..
```

### 开发

```bash
# 启动开发服务器
npm start

# 在iOS模拟器中运行
npm run ios

# 在Android模拟器中运行
npm run android
```

## 项目结构

```
mobile/
├── src/                          # 源代码
│   ├── screens/                  # 页面组件
│   ├── components/               # 可复用组件
│   ├── services/                 # 业务逻辑服务
│   ├── store/                    # 状态管理
│   ├── types/                    # TypeScript类型
│   ├── native/                   # 原生模块
│   ├── utils/                    # 工具函数
│   └── App.tsx                   # 应用入口
├── ios/                          # iOS原生代码
├── android/                      # Android原生代码
├── app.json                      # Expo配置
├── eas.json                      # EAS Build配置
├── package.json                  # 项目配置
├── MOBILE_ARCHITECTURE.md        # 架构设计
├── API_INTEGRATION_GUIDE.md      # API集成指南
├── DEVELOPMENT_GUIDE.md          # 开发指南
├── RELEASE_CHECKLIST.md          # 发布清单
└── PROJECT_SUMMARY.md            # 项目总结
```

## 核心功能

### 1. 离线优先架构
- SQLite本地数据库
- 自动同步机制
- 智能缓存策略
- 冲突解决

### 2. 实时同步
- WebSocket推送
- 增量数据同步
- 自动重试
- 网络感知

### 3. 推送通知
- iOS APNs
- Android FCM
- 本地通知
- 深度链接

### 4. 生物识别认证
- Face ID / Touch ID (iOS)
- 生物识别 (Android)
- 安全Token存储
- 会话管理

### 5. 性能优化
- 冷启动 < 2秒
- 热启动 < 500ms
- 列表虚拟化
- 图片优化

## 技术栈

- **框架**: React Native 0.73+, Expo 50.0+
- **语言**: TypeScript 5.3+
- **状态管理**: Zustand 4.4+
- **网络**: Axios 1.6+
- **存储**: SQLite, AsyncStorage, Secure Store
- **导航**: React Navigation 6.1+
- **UI**: React Native Paper 5.11+

## 文档

- [架构设计](./MOBILE_ARCHITECTURE.md) - 完整的系统架构
- [API集成](./API_INTEGRATION_GUIDE.md) - 后端API集成指南
- [开发指南](./DEVELOPMENT_GUIDE.md) - 开发流程和最佳实践
- [发布清单](./RELEASE_CHECKLIST.md) - iOS/Android发布流程
- [项目总结](./PROJECT_SUMMARY.md) - 项目概览和交付物

## 常用命令

```bash
# 开发
npm start              # 启动开发服务器
npm run ios           # 在iOS模拟器中运行
npm run android       # 在Android模拟器中运行

# 测试
npm test              # 运行单元测试
npm run lint          # 代码检查
npm run type-check    # TypeScript检查

# 构建
npm run build:ios     # 构建iOS应用
npm run build:android # 构建Android应用

# 发布
npm run submit:ios    # 提交iOS应用
npm run submit:android # 提交Android应用
```

## 性能指标

| 指标 | 目标 | 状态 |
|------|------|------|
| 冷启动时间 | < 2秒 | ✓ |
| 热启动时间 | < 500ms | ✓ |
| 内存占用 | < 100MB | ✓ |
| 列表帧率 | 60fps | ✓ |
| 电池优化 | 优化 | ✓ |
| 流量优化 | 优化 | ✓ |

## 安全特性

- HTTPS/TLS 1.3传输加密
- SQLite数据库加密
- Keychain/Keystore安全存储
- OAuth 2.0 + PKCE认证
- 生物识别认证
- Token刷新机制

## 支持的平台

- **iOS**: 14.0+
- **Android**: 8.0+

## 支持的设备

- iPhone 12, 13, 14, 15及以上
- iPad (各代)
- Android手机 (各种屏幕尺寸)
- Android平板

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 技术支持: tech-support@xagent.local
- 功能建议: features@xagent.local
- 安全问题: security@xagent.local

## 致谢

感谢所有贡献者和用户的支持！

---

**最后更新**: 2026-05-27  
**版本**: 1.0.0
