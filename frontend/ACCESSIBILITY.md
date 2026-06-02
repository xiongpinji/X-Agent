# X-Agent Web UI 可访问性指南

## 概述

本指南确保X-Agent Web UI符合WCAG 2.1 AA级别的可访问性标准。

## 实现的可访问性功能

### 1. ARIA标签和属性

#### 按钮和链接
```tsx
<button aria-label="Close dialog" onClick={onClose}>
  <X size={20} />
</button>

<a href="/docs" aria-label="Documentation">
  Docs
</a>
```

#### 表单控件
```tsx
<input
  id="email"
  type="email"
  aria-label="Email address"
  aria-describedby="email-help"
/>
<p id="email-help">We'll never share your email</p>
```

#### 动态内容
```tsx
<div role="status" aria-live="polite" aria-atomic="true">
  {message}
</div>
```

### 2. 键盘导航

#### Tab键导航
- 所有交互元素都可通过Tab键访问
- Tab顺序逻辑合理
- 焦点指示器清晰可见

#### 快捷键
```tsx
useKeyboardShortcuts({
  'ctrl+s': handleSave,
  'escape': handleClose,
  'enter': handleSubmit,
})
```

### 3. 屏幕阅读器支持

#### 语义化HTML
```tsx
<nav aria-label="Main navigation">
  <ul>
    <li><a href="/">Home</a></li>
    <li><a href="/about">About</a></li>
  </ul>
</nav>
```

#### 跳过链接
```tsx
<a href="#main-content" className="sr-only">
  Skip to main content
</a>
```

#### 标题结构
```tsx
<h1>Page Title</h1>
<h2>Section Title</h2>
<h3>Subsection Title</h3>
```

### 4. 颜色和对比度

- 文本对比度至少为4.5:1（正常文本）
- 大文本对比度至少为3:1
- 不仅依赖颜色传达信息

### 5. 响应式设计

- 支持缩放至200%
- 支持横屏和竖屏
- 触摸目标最小为44x44像素

## 测试清单

### 自动化测试
- [ ] 使用axe DevTools检查
- [ ] 使用WAVE浏览器扩展
- [ ] 使用Lighthouse审计

### 手动测试
- [ ] 仅使用键盘导航
- [ ] 使用屏幕阅读器（NVDA/JAWS）
- [ ] 测试高对比度模式
- [ ] 测试缩放功能

### 浏览器测试
- [ ] Chrome + ChromeVox
- [ ] Firefox + NVDA
- [ ] Safari + VoiceOver
- [ ] Edge + Narrator

## 常见问题

### Q: 如何添加ARIA标签？
A: 使用`aria-label`、`aria-labelledby`或`aria-describedby`属性。

### Q: 如何测试键盘导航？
A: 使用Tab、Shift+Tab、Enter和Escape键进行导航。

### Q: 如何改进屏幕阅读器支持？
A: 使用语义化HTML、ARIA标签和`role`属性。

## 资源

- [WCAG 2.1指南](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA实践指南](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM](https://webaim.org/)
- [A11y Project](https://www.a11yproject.com/)

## 合规性声明

X-Agent Web UI致力于符合WCAG 2.1 AA级别标准。如发现任何可访问性问题，请报告给我们。
