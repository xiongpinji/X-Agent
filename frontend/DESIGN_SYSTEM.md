# X-Agent Design System

## 概述

X-Agent设计系统是一套完整的UI/UX指南，确保整个应用的一致性、可访问性和性能。

## 颜色系统

### 主色调 (Primary)
- **50**: `#f0f9ff` - 最浅
- **100**: `#e0f2fe`
- **200**: `#bae6fd`
- **300**: `#7dd3fc`
- **400**: `#38bdf8`
- **500**: `#0ea5e9` - 标准
- **600**: `#0284c7` - 深色
- **700**: `#0369a1`
- **800**: `#075985`
- **900**: `#0c3d66` - 最深

### 次色调 (Secondary)
- **50**: `#f5f3ff`
- **100**: `#ede9fe`
- **500**: `#8b5cf6` - 标准
- **600**: `#7c3aed` - 深色
- **900**: `#4c1d95` - 最深

### 状态颜色

#### 成功 (Success)
- **50**: `#f0fdf4`
- **500**: `#22c55e` - 标准
- **600**: `#16a34a` - 深色
- **900**: `#145231` - 最深

#### 警告 (Warning)
- **50**: `#fffbeb`
- **500**: `#f59e0b` - 标准
- **600**: `#d97706` - 深色
- **900**: `#78350f` - 最深

#### 错误 (Error)
- **50**: `#fef2f2`
- **500**: `#ef4444` - 标准
- **600**: `#dc2626` - 深色
- **900**: `#7f1d1d` - 最深

#### 信息 (Info)
- **50**: `#f0f9ff`
- **500**: `#0ea5e9` - 标准
- **600**: `#0284c7` - 深色
- **900**: `#0c3d66` - 最深

### 中性色 (Slate)
- **50**: `#f8fafc` - 背景
- **100**: `#f1f5f9`
- **200**: `#e2e8f0`
- **300**: `#cbd5e1`
- **400**: `#94a3b8`
- **500**: `#64748b` - 标准
- **600**: `#475569` - 深色
- **700**: `#334155`
- **800**: `#1e293b`
- **900**: `#0f172a`
- **950**: `#020617` - 最深

## 排版系统

### 字体族

```css
/* 无衬线字体 (默认) */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;

/* 等宽字体 (代码) */
font-family: 'Fira Code', 'Courier New', monospace;

/* 显示字体 */
font-family: system-ui, -apple-system, sans-serif;
```

### 标题尺寸

| 级别 | 尺寸 | 行高 | 字重 | 用途 |
|------|------|------|------|------|
| H1 | 2.5rem (40px) | 1.2 | 700 | 页面标题 |
| H2 | 2rem (32px) | 1.3 | 700 | 主要章节 |
| H3 | 1.5rem (24px) | 1.4 | 600 | 子章节 |
| H4 | 1.25rem (20px) | 1.4 | 600 | 小标题 |
| H5 | 1.125rem (18px) | 1.5 | 600 | 标签 |
| H6 | 1rem (16px) | 1.5 | 600 | 小标签 |

### 正文尺寸

| 级别 | 尺寸 | 行高 | 用途 |
|------|------|------|------|
| Body Large | 1.125rem (18px) | 1.75 | 大段落 |
| Body Medium | 1rem (16px) | 1.5 | 标准段落 |
| Body Small | 0.875rem (14px) | 1.5 | 辅助文本 |
| Body XS | 0.75rem (12px) | 1.5 | 标签、提示 |

## 间距系统

```
xs: 0.25rem (4px)
sm: 0.5rem (8px)
md: 1rem (16px)
lg: 1.5rem (24px)
xl: 2rem (32px)
2xl: 3rem (48px)
3xl: 4rem (64px)
```

## 圆角系统

```
xs: 0.25rem (4px)
sm: 0.375rem (6px)
md: 0.5rem (8px)
lg: 0.75rem (12px)
xl: 1rem (16px)
2xl: 1.5rem (24px)
3xl: 2rem (32px)
```

## 阴影系统

```
xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)
xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1)
2xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25)
inner: inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)
focus: 0 0 0 3px rgba(59, 130, 246, 0.1)
```

## 动画系统

### 过渡时长

```
75ms: 快速反馈
100ms: 标准反馈
150ms: 中等反馈
200ms: 缓慢反馈
300ms: 页面过渡
500ms: 长过渡
700ms: 很长过渡
1000ms: 非常长过渡
```

### 预定义动画

- **fadeIn**: 淡入 (0.3s)
- **slideIn**: 向上滑入 (0.3s)
- **slideUp**: 向上滑入 (0.3s)
- **scaleIn**: 缩放进入 (0.2s)
- **shimmer**: 闪烁加载 (2s)
- **spin**: 旋转 (1s)
- **pulse**: 脉冲 (2s)
- **bounce**: 弹跳 (1s)

## 组件库

### Button (按钮)

```tsx
<Button variant="primary" size="md">
  Click me
</Button>
```

**变体**: primary, secondary, danger, ghost, success, warning
**尺寸**: xs, sm, md, lg, xl
**属性**: isLoading, isDisabled, icon, iconPosition, fullWidth, ariaLabel

### Card (卡片)

```tsx
<Card>
  <Card.Header>Title</Card.Header>
  <Card.Body>Content</Card.Body>
  <Card.Footer>Footer</Card.Footer>
</Card>
```

### Alert (警告)

```tsx
<Alert variant="success" title="Success">
  Operation completed successfully
</Alert>
```

**变体**: success, warning, error, info

### Input (输入框)

```tsx
<Input
  type="text"
  placeholder="Enter text"
  label="Name"
  error="This field is required"
/>
```

### Select (选择框)

```tsx
<Select label="Choose option">
  <option>Option 1</option>
  <option>Option 2</option>
</Select>
```

### Modal (模态框)

```tsx
<Modal isOpen={isOpen} onClose={onClose}>
  <Modal.Header>Title</Modal.Header>
  <Modal.Body>Content</Modal.Body>
  <Modal.Footer>
    <Button onClick={onClose}>Close</Button>
  </Modal.Footer>
</Modal>
```

### Tabs (标签页)

```tsx
<Tabs defaultValue="tab1">
  <Tabs.List>
    <Tabs.Trigger value="tab1">Tab 1</Tabs.Trigger>
    <Tabs.Trigger value="tab2">Tab 2</Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="tab1">Content 1</Tabs.Content>
  <Tabs.Content value="tab2">Content 2</Tabs.Content>
</Tabs>
```

## 无障碍指南

### WCAG 2.1 AA 标准

1. **颜色对比度**: 最小 4.5:1 (正常文本)
2. **焦点指示**: 清晰可见的焦点环
3. **键盘导航**: 所有功能可通过键盘访问
4. **屏幕阅读器**: 完整的ARIA标签
5. **动画**: 尊重 `prefers-reduced-motion`

### ARIA 属性

```tsx
// 标签
<button aria-label="Close dialog">×</button>

// 描述
<input aria-describedby="error-message" />
<span id="error-message">This field is required</span>

// 活跃区域
<div aria-live="polite" aria-atomic="true">
  Loading...
</div>

// 按钮状态
<button aria-pressed="false">Toggle</button>
<button aria-expanded="false">Menu</button>
```

### 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| Tab | 导航到下一个元素 |
| Shift+Tab | 导航到上一个元素 |
| Enter | 激活按钮/链接 |
| Space | 激活按钮/复选框 |
| Escape | 关闭模态框/菜单 |
| Arrow Keys | 导航列表/菜单 |

## 响应式设计

### 断点

```
xs: 0px (手机)
sm: 640px (小平板)
md: 768px (平板)
lg: 1024px (小桌面)
xl: 1280px (桌面)
2xl: 1536px (大桌面)
```

### 移动优先

所有样式从移动开始，然后使用媒体查询扩展到更大的屏幕。

```css
/* 移动 */
.container {
  padding: 1rem;
}

/* 平板及以上 */
@media (min-width: 768px) {
  .container {
    padding: 2rem;
  }
}
```

## 深色模式

使用 `dark:` 前缀为深色模式添加样式。

```tsx
<div className="bg-white dark:bg-slate-950 text-slate-900 dark:text-white">
  Content
</div>
```

## 国际化

支持10+语言，包括RTL语言。

```tsx
import { useI18n } from '@/i18n/context'

export function MyComponent() {
  const { language, t, formatDate, isRTL } = useI18n()

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'}>
      <h1>{t('common.title')}</h1>
      <p>{formatDate(new Date())}</p>
    </div>
  )
}
```

## 性能最佳实践

1. **代码分割**: 按路由和功能分割代码
2. **懒加载**: 延迟加载图片和组件
3. **缓存**: 使用Service Worker缓存资源
4. **优化**: 压缩图片，使用WebP格式
5. **监控**: 跟踪Core Web Vitals

## 测试

- **单元测试**: Jest + React Testing Library
- **组件测试**: Storybook
- **E2E测试**: Playwright
- **性能测试**: Lighthouse
- **无障碍测试**: axe-core

## 版本历史

- **v1.0.0** (2026-05-28): 初始版本
