// mobile/UI_DESIGN_SPECIFICATION.md
# X-Agent 移动端UI设计规范

**版本：** v1.0  
**日期：** 2026-05-27  
**状态：** 完成

---

## 1. 设计系统概览

### 1.1 设计原则

1. **简洁性**：最小化视觉复杂度，专注于核心功能
2. **一致性**：统一的设计语言和交互模式
3. **可访问性**：支持无障碍访问，适配各种用户
4. **响应式**：适配不同屏幕尺寸和方向
5. **性能**：快速加载和流畅交互

### 1.2 设计目标

- 提供直观的用户界面
- 支持高效的工作流操作
- 实现跨平台一致体验
- 优化移动端性能

---

## 2. 色彩系统

### 2.1 亮色主题

```typescript
// 基础颜色
primary: '#007AFF'        // 主色 - 蓝色
secondary: '#5AC8FA'      // 辅助色 - 浅蓝
tertiary: '#34C759'       // 第三色 - 绿色

// 背景色
background: '#FFFFFF'     // 主背景
surface: '#F2F2F7'        // 卡片背景
surfaceVariant: '#E5E5EA' // 次级背景

// 文本色
text: '#000000'           // 主文本
textSecondary: '#666666'  // 次级文本
textTertiary: '#999999'   // 辅助文本
textInverse: '#FFFFFF'    // 反色文本

// 状态色
success: '#34C759'        // 成功 - 绿色
warning: '#FF9500'        // 警告 - 橙色
error: '#FF3B30'          // 错误 - 红色
info: '#00C7FF'           // 信息 - 青色
```

### 2.2 深色主题

```typescript
// 基础颜色
primary: '#0A84FF'        // 主色 - 蓝色
secondary: '#00B0FF'      // 辅助色 - 浅蓝
tertiary: '#30B0C0'       // 第三色 - 青色

// 背景色
background: '#000000'     // 主背景
surface: '#1C1C1E'        // 卡片背景
surfaceVariant: '#2C2C2E' // 次级背景

// 文本色
text: '#FFFFFF'           // 主文本
textSecondary: '#A0A0A0'  // 次级文本
textTertiary: '#666666'   // 辅助文本
textInverse: '#000000'    // 反色文本

// 状态色
success: '#30B0C0'        // 成功 - 青色
warning: '#FF9500'        // 警告 - 橙色
error: '#FF453A'          // 错误 - 红色
info: '#00B0FF'           // 信息 - 蓝色
```

### 2.3 颜色使用指南

| 用途 | 颜色 | 说明 |
|------|------|------|
| 主要操作 | primary | 按钮、链接、强调 |
| 次要操作 | secondary | 次级按钮、标签 |
| 成功状态 | success | 完成、通过、启用 |
| 警告状态 | warning | 待处理、进行中 |
| 错误状态 | error | 失败、禁用、删除 |
| 信息状态 | info | 提示、通知 |

---

## 3. 排版系统

### 3.1 字体

- **字体族**：系统默认字体（iOS: SF Pro Display, Android: Roboto）
- **字重**：Regular (400), Medium (500), Semibold (600), Bold (700)

### 3.2 字体大小和行高

| 用途 | 大小 | 行高 | 字重 | 用例 |
|------|------|------|------|------|
| h1 | 32px | 40px | 700 | 页面标题 |
| h2 | 28px | 36px | 700 | 主要标题 |
| h3 | 24px | 32px | 700 | 次级标题 |
| h4 | 20px | 28px | 600 | 小标题 |
| h5 | 18px | 26px | 600 | 卡片标题 |
| h6 | 16px | 24px | 600 | 列表项标题 |
| body1 | 16px | 24px | 400 | 正文 |
| body2 | 14px | 20px | 400 | 次级正文 |
| button | 16px | 24px | 600 | 按钮文本 |
| caption | 12px | 16px | 400 | 辅助文本 |
| overline | 11px | 16px | 600 | 标签 |

---

## 4. 间距系统

### 4.1 间距单位

基础间距单位：8px

```
xs: 4px    (0.5x)
sm: 8px    (1x)
md: 16px   (2x)
lg: 24px   (3x)
xl: 32px   (4x)
xxl: 48px  (6x)
```

### 4.2 应用场景

| 场景 | 间距 | 说明 |
|------|------|------|
| 组件内部 | 8-12px | 元素之间的间距 |
| 组件之间 | 16px | 卡片、列表项间距 |
| 区域间距 | 24px | 不同区域之间 |
| 页面边距 | 16px | 页面左右边距 |
| 顶部间距 | 32px | 页面顶部 |
| 底部间距 | 32px | 页面底部 |

---

## 5. 圆角系统

### 5.1 圆角半径

```
xs: 4px    - 小元素（标签、徽章）
sm: 8px    - 输入框、小按钮
md: 12px   - 卡片、对话框
lg: 16px   - 大卡片、模态框
xl: 24px   - 特殊组件
full: 50%  - 圆形（头像、FAB）
```

### 5.2 应用场景

| 组件 | 圆角 | 说明 |
|------|------|------|
| 按钮 | 12px | 标准按钮 |
| 输入框 | 12px | 文本输入 |
| 卡片 | 12px | 任务卡片、工作流卡片 |
| 徽章 | 8px | 状态徽章 |
| 头像 | 50% | 圆形头像 |
| FAB | 50% | 浮动操作按钮 |

---

## 6. 阴影系统

### 6.1 阴影定义

```typescript
// 浅阴影
shadowLight: {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 1 },
  shadowOpacity: 0.08,
  shadowRadius: 2,
  elevation: 1,
}

// 标准阴影
shadowMedium: {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.1,
  shadowRadius: 4,
  elevation: 3,
}

// 深阴影
shadowDark: {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 4 },
  shadowOpacity: 0.15,
  shadowRadius: 8,
  elevation: 5,
}
```

### 6.2 应用场景

| 组件 | 阴影 | 说明 |
|------|------|------|
| 卡片 | 标准 | 任务卡片、工作流卡片 |
| 按钮 | 浅 | 普通按钮 |
| FAB | 深 | 浮动操作按钮 |
| 模态框 | 深 | 对话框、底部表单 |
| 输入框 | 浅 | 文本输入框 |

---

## 7. 组件规范

### 7.1 按钮

#### 主按钮
- 背景色：primary
- 文本色：textInverse
- 高度：48px
- 圆角：12px
- 字体：button (16px, 600)

#### 次按钮
- 背景色：surface
- 文本色：primary
- 边框：1px primary
- 高度：48px
- 圆角：12px

#### 文本按钮
- 背景色：transparent
- 文本色：primary
- 高度：auto
- 字体：button

### 7.2 输入框

- 高度：48px
- 圆角：12px
- 边框：1px border
- 内边距：12px
- 字体：body1
- 占位符色：textTertiary

### 7.3 卡片

- 背景色：surface
- 圆角：12px
- 内边距：16px
- 阴影：标准
- 边框：无

### 7.4 列表项

- 高度：56px（最小）
- 内边距：12px
- 圆角：8px
- 间距：6px

### 7.5 徽章

- 高度：24px
- 内边距：8px
- 圆角：8px
- 字体：caption
- 背景色：状态色 + 20% 透明度

---

## 8. 交互设计

### 8.1 触摸反馈

- **按下状态**：opacity 0.7
- **禁用状态**：opacity 0.5
- **悬停状态**：背景色变暗 10%

### 8.2 动画

| 动画 | 时长 | 缓动 | 用途 |
|------|------|------|------|
| 快速 | 200ms | easeOut | 按钮、切换 |
| 标准 | 300ms | easeInOut | 页面转换 |
| 缓慢 | 500ms | easeInOut | 加载、进度 |

### 8.3 手势

- **点击**：激活按钮、导航
- **长按**：显示菜单、删除确认
- **滑动**：列表滚动、页面切换
- **下拉**：刷新数据
- **上拉**：加载更多

---

## 9. 屏幕适配

### 9.1 断点

```
Small:  < 375px   (iPhone SE)
Medium: 375-414px (iPhone 12/13)
Large:  > 414px   (iPhone 14 Plus, iPad)
```

### 9.2 响应式设计

- **小屏幕**：单列布局，简化信息
- **中等屏幕**：标准布局，完整信息
- **大屏幕**：多列布局，侧边栏

### 9.3 横屏支持

- 调整布局为横向
- 隐藏底部导航
- 显示侧边栏导航

---

## 10. 深色模式

### 10.1 实现方式

- 使用 ThemeContext 管理主题
- 支持自动、亮色、深色三种模式
- 自动跟随系统设置

### 10.2 颜色映射

| 亮色 | 深色 | 说明 |
|------|------|------|
| #FFFFFF | #000000 | 背景 |
| #F2F2F7 | #1C1C1E | 表面 |
| #000000 | #FFFFFF | 文本 |
| #007AFF | #0A84FF | 主色 |

---

## 11. 无障碍设计

### 11.1 对比度

- 文本与背景对比度 ≥ 4.5:1
- 大文本对比度 ≥ 3:1

### 11.2 触摸目标

- 最小尺寸：44x44px
- 最小间距：8px

### 11.3 文本

- 最小字体：12px
- 支持文本缩放
- 清晰的标签和提示

---

## 12. 屏幕设计

### 12.1 登录屏幕

**布局**：
- 顶部：Logo + 标题
- 中部：表单（邮箱、密码）
- 底部：登录按钮 + 注册链接

**特点**：
- 简洁的表单设计
- 生物识别选项
- 忘记密码链接

### 12.2 主页/仪表板

**布局**：
- 顶部：问候语 + 用户头像
- 中部：统计卡片 + 快速操作
- 下部：最近任务列表

**特点**：
- 一目了然的统计信息
- 快速操作按钮
- 最近活动列表

### 12.3 任务列表

**布局**：
- 顶部：搜索 + 筛选
- 中部：任务卡片列表
- 底部：加载更多 / FAB

**特点**：
- 下拉刷新
- 上拉加载
- 任务卡片展示

### 12.4 工作流监控

**布局**：
- 顶部：工作流信息
- 中部：进度条 + 节点状态
- 底部：操作按钮

**特点**：
- 实时进度显示
- 节点状态可视化
- 错误提示

### 12.5 设置屏幕

**布局**：
- 顶部：用户信息
- 中部：设置分组
- 底部：登出按钮

**特点**：
- 分组设置
- 切换开关
- 主题选择

---

## 13. 组件库

### 13.1 已实现组件

- TaskCard：任务卡片
- WorkflowCard：工作流卡片
- LoadingAnimation：加载动画
- SyncStatusIndicator：同步状态指示器
- ErrorAlert：错误提示

### 13.2 计划组件

- TaskDetailCard：任务详情
- WorkflowNodeVisualization：工作流节点可视化
- ProgressIndicator：进度指示器
- FilterBar：筛选栏
- SearchBar：搜索栏

---

## 14. 最佳实践

### 14.1 性能优化

- 使用 FlatList 虚拟化长列表
- 图片缓存和优化
- 避免不必要的重新渲染
- 异步加载非关键资源

### 14.2 可用性

- 提供清晰的反馈
- 支持撤销操作
- 避免意外操作
- 提供帮助和文档

### 14.3 一致性

- 统一的导航模式
- 一致的交互反馈
- 统一的错误处理
- 统一的加载状态

---

## 15. 设计资源

### 15.1 文件结构

```
mobile/
├── src/
│   ├── theme/
│   │   ├── colors.ts
│   │   ├── typography.ts
│   │   ├── ThemeContext.tsx
│   │   └── index.ts
│   ├── components/
│   │   ├── TaskCard.tsx
│   │   ├── WorkflowCard.tsx
│   │   ├── LoadingAnimation.tsx
│   │   └── index.ts
│   ├── screens/
│   │   ├── LoginScreen.tsx
│   │   ├── HomeScreen.tsx
│   │   ├── TaskListScreen.tsx
│   │   ├── WorkflowMonitorScreen.tsx
│   │   ├── SettingsScreen.tsx
│   │   └── index.ts
│   ├── navigation/
│   │   ├── RootNavigator.tsx
│   │   └── index.ts
│   └── utils/
│       ├── formatters.ts
│       ├── validators.ts
│       └── index.ts
```

### 15.2 导入示例

```typescript
// 使用主题
import { useTheme } from '../theme';
const { theme } = useTheme();

// 使用组件
import { TaskCard, WorkflowCard, LoadingAnimation } from '../components';

// 使用工具函数
import { formatDate, isValidEmail } from '../utils';
```

---

## 16. 版本历史

| 版本 | 日期 | 描述 |
|------|------|------|
| 1.0 | 2026-05-27 | 初始版本，包含完整的UI设计规范 |

---

**文档完成日期：** 2026-05-27  
**维护者：** X-Agent UI Team  
**最后更新：** 2026-05-27
