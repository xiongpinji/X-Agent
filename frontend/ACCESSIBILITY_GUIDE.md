# X-Agent 无障碍指南

## WCAG 2.1 AA 标准

X-Agent遵循WCAG 2.1 AA标准，确保所有用户都能访问应用。

## 四大原则

### 1. 可感知 (Perceivable)

#### 文本替代
- 所有图片必须有`alt`属性
- 视频必须有字幕和音频描述
- 图标必须有`aria-label`

```tsx
<img src="logo.png" alt="X-Agent logo" />
<button aria-label="Close dialog">×</button>
```

#### 颜色对比度
- 正常文本: 最小 4.5:1
- 大文本 (18pt+): 最小 3:1
- UI组件: 最小 3:1

```typescript
import { checkContrast } from '@/utils/accessibility'

// 检查颜色对比度
const isValid = checkContrast('#0284c7', '#ffffff') // true
```

#### 响应式设计
- 支持缩放到200%
- 不依赖固定尺寸
- 支持横竖屏切换

### 2. 可操作 (Operable)

#### 键盘导航
- 所有功能可通过键盘访问
- Tab键导航顺序合理
- 焦点指示清晰可见

```tsx
// 焦点指示
button:focus-visible {
  outline: 2px solid #0284c7;
  outline-offset: 2px;
}
```

#### 焦点管理
```typescript
import { FocusManager } from '@/utils/accessibility'

const focusManager = new FocusManager()

// 保存焦点
focusManager.saveFocus()

// 恢复焦点
focusManager.restoreFocus()

// 焦点陷阱 (模态框)
focusManager.trapFocus(modalElement, event)
```

#### 足够的时间
- 没有时间限制的内容
- 可暂停/停止自动播放
- 可调整超时时间

#### 防止癫痫
- 避免每秒闪烁超过3次
- 避免红色闪烁

### 3. 可理解 (Understandable)

#### 可读性
- 使用清晰的语言
- 避免复杂的句子
- 提供定义和解释

#### 可预测
- 一致的导航
- 一致的命名
- 避免意外的上下文变化

```tsx
// ✓ 好 - 一致的按钮标签
<button>Save</button>
<button>Cancel</button>

// ✗ 差 - 不一致的标签
<button>OK</button>
<button>Abort</button>
```

#### 输入帮助
- 清晰的标签
- 错误提示
- 建议和确认

```tsx
<label htmlFor="email">Email address</label>
<input
  id="email"
  type="email"
  aria-describedby="email-error"
  required
/>
<span id="email-error" role="alert">
  Please enter a valid email
</span>
```

### 4. 健壮 (Robust)

#### 兼容性
- 有效的HTML
- 正确的ARIA用法
- 支持辅助技术

```tsx
// ✓ 好 - 正确的ARIA
<button aria-pressed="false">Toggle</button>

// ✗ 差 - 错误的ARIA
<div role="button" aria-pressed="false">Toggle</div>
```

## ARIA属性

### 标签和描述

```tsx
// aria-label: 为元素提供标签
<button aria-label="Close dialog">×</button>

// aria-labelledby: 关联标签元素
<h2 id="dialog-title">Confirm Action</h2>
<div role="dialog" aria-labelledby="dialog-title">
  Are you sure?
</div>

// aria-describedby: 提供描述
<input aria-describedby="password-hint" type="password" />
<span id="password-hint">At least 8 characters</span>
```

### 状态和属性

```tsx
// aria-disabled: 禁用状态
<button aria-disabled="true">Disabled</button>

// aria-expanded: 展开/折叠状态
<button aria-expanded="false" aria-controls="menu">
  Menu
</button>
<div id="menu" hidden>Menu items</div>

// aria-checked: 复选框状态
<input type="checkbox" aria-checked="true" />

// aria-pressed: 按钮按下状态
<button aria-pressed="false">Toggle</button>

// aria-selected: 选中状态
<option aria-selected="true">Option 1</option>

// aria-invalid: 验证错误
<input aria-invalid="true" aria-describedby="error" />
<span id="error">This field is required</span>

// aria-required: 必填字段
<input aria-required="true" />
```

### 活跃区域

```tsx
// aria-live: 实时更新
<div aria-live="polite" aria-atomic="true">
  Loading...
</div>

// aria-busy: 加载状态
<div aria-busy="true">Processing...</div>
```

### 使用AriaBuilder

```typescript
import { AriaBuilder } from '@/utils/accessibility'

const attrs = new AriaBuilder()
  .label('Close dialog')
  .role('button')
  .disabled(false)
  .build()

// 结果: { 'aria-label': 'Close dialog', role: 'button', 'aria-disabled': false }
```

## 屏幕阅读器支持

### 宣布消息

```typescript
import { announceToScreenReader } from '@/utils/accessibility'

// 礼貌宣布 (等待用户暂停)
announceToScreenReader('File saved successfully', 'polite')

// 立即宣布 (中断用户)
announceToScreenReader('Error: Invalid input', 'assertive')
```

### 隐藏内容

```tsx
// 屏幕阅读器可见，视觉上隐藏
<span className="sr-only">Loading</span>

// 屏幕阅读器隐藏
<span aria-hidden="true">→</span>
```

## 键盘快捷键

```typescript
import { KeyCode, isNavigationKey, isActivationKey } from '@/utils/accessibility'

// 处理键盘事件
function handleKeyDown(event: KeyboardEvent) {
  if (event.key === KeyCode.ESCAPE) {
    closeDialog()
  }

  if (isNavigationKey(event.key)) {
    navigateList(event.key)
  }

  if (isActivationKey(event.key)) {
    activateButton()
  }
}
```

## 跳过链接

```tsx
import { createSkipLink } from '@/utils/accessibility'

// 在页面顶部添加跳过链接
const skipLink = createSkipLink('main-content', 'Skip to main content')
document.body.insertBefore(skipLink, document.body.firstChild)
```

## 表单无障碍

### 标签关联

```tsx
// ✓ 好 - 显式关联
<label htmlFor="name">Name</label>
<input id="name" type="text" />

// ✗ 差 - 隐式关联
<label>
  Name
  <input type="text" />
</label>
```

### 错误处理

```tsx
<div>
  <label htmlFor="email">Email</label>
  <input
    id="email"
    type="email"
    aria-describedby="email-error"
    aria-invalid={hasError}
  />
  {hasError && (
    <span id="email-error" role="alert">
      Please enter a valid email address
    </span>
  )}
</div>
```

### 必填字段

```tsx
<label htmlFor="password">
  Password
  <span aria-label="required">*</span>
</label>
<input
  id="password"
  type="password"
  required
  aria-required="true"
/>
```

## 测试无障碍

### 自动化测试

```bash
# 安装axe-core
npm install --save-dev @axe-core/react

# 在测试中使用
import { axe, toHaveNoViolations } from 'jest-axe'

test('should not have accessibility violations', async () => {
  const { container } = render(<MyComponent />)
  const results = await axe(container)
  expect(results).toHaveNoViolations()
})
```

### 手动测试

1. **键盘导航**: 使用Tab键导航所有功能
2. **屏幕阅读器**: 使用NVDA (Windows) 或VoiceOver (Mac)
3. **颜色对比**: 使用WebAIM对比度检查器
4. **缩放**: 缩放到200%并检查布局
5. **焦点指示**: 确保焦点清晰可见

### 浏览器工具

- **Chrome DevTools**: Lighthouse无障碍审计
- **axe DevTools**: 浏览器扩展
- **WAVE**: 网页无障碍评估工具
- **Lighthouse**: 内置无障碍检查

## 常见问题

### Q: 如何为图标添加标签?
A: 使用`aria-label`或`aria-labelledby`

```tsx
<button aria-label="Close">
  <CloseIcon />
</button>
```

### Q: 如何处理动态内容?
A: 使用`aria-live`区域

```tsx
<div aria-live="polite" aria-atomic="true">
  {message}
</div>
```

### Q: 如何改进表单无障碍?
A: 使用正确的标签、错误提示和ARIA属性

```tsx
<label htmlFor="input">Label</label>
<input id="input" aria-describedby="error" />
<span id="error" role="alert">Error message</span>
```

## 参考资源

- [WCAG 2.1指南](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA实践指南](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM](https://webaim.org/)
- [MDN无障碍](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [A11y项目](https://www.a11yproject.com/)
