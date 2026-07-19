# X-Agent 国际化指南

## 支持的语言

X-Agent支持10+语言，包括RTL语言。

| 语言 | 代码 | 本地名称 | 方向 | 货币 |
|------|------|---------|------|------|
| English | en | English | LTR | USD |
| 简体中文 | zh | 简体中文 | LTR | CNY |
| 日本語 | ja | 日本語 | LTR | JPY |
| 한국어 | ko | 한국어 | LTR | KRW |
| Français | fr | Français | LTR | EUR |
| Deutsch | de | Deutsch | LTR | EUR |
| Español | es | Español | LTR | EUR |
| Português | pt | Português | LTR | BRL |
| Русский | ru | Русский | LTR | RUB |
| العربية | ar | العربية | RTL | AED |

## 使用国际化

### 设置I18nProvider

```tsx
import { I18nProvider } from '@/i18n/context'

function App() {
  return (
    <I18nProvider defaultLanguage="en">
      <YourApp />
    </I18nProvider>
  )
}
```

### 使用翻译Hook

```tsx
import { useI18n } from '@/i18n/context'

function MyComponent() {
  const { language, t, formatDate, formatTime, formatCurrency, isRTL } = useI18n()

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'}>
      <h1>{t('common.title')}</h1>
      <p>{formatDate(new Date())}</p>
      <p>{formatCurrency(99.99)}</p>
    </div>
  )
}
```

### 切换语言

```tsx
import { useI18n } from '@/i18n/context'
import { SUPPORTED_LANGUAGES } from '@/i18n/config'

function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()

  return (
    <select value={language} onChange={(e) => setLanguage(e.target.value)}>
      {Object.entries(SUPPORTED_LANGUAGES).map(([code, config]) => (
        <option key={code} value={code}>
          {config.nativeName}
        </option>
      ))}
    </select>
  )
}
```

## 翻译文件结构

```
src/i18n/
├── config.ts              # 语言配置
├── context.tsx            # I18n上下文
└── translations/
    ├── en.json           # 英文翻译
    ├── zh.json           # 中文翻译
    ├── ja.json           # 日文翻译
    ├── ko.json           # 韩文翻译
    ├── fr.json           # 法文翻译
    ├── de.json           # 德文翻译
    ├── es.json           # 西班牙文翻译
    ├── pt.json           # 葡萄牙文翻译
    ├── ru.json           # 俄文翻译
    └── ar.json           # 阿拉伯文翻译
```

## 翻译文件格式

```json
{
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "success": "Success"
  },
  "navigation": {
    "dashboard": "Dashboard",
    "chat": "Chat",
    "tasks": "Tasks"
  },
  "errors": {
    "notFound": "Not found",
    "unauthorized": "Unauthorized"
  }
}
```

## 日期和时间格式

### 自动本地化

```tsx
import { useI18n } from '@/i18n/context'

function DateDisplay() {
  const { formatDate, formatTime } = useI18n()

  const date = new Date('2026-05-28')

  return (
    <div>
      <p>Date: {formatDate(date)}</p>
      <p>Time: {formatTime(date)}</p>
    </div>
  )
}
```

### 日期格式示例

| 语言 | 格式 | 示例 |
|------|------|------|
| English | MM/dd/yyyy | 05/28/2026 |
| 中文 | yyyy/MM/dd | 2026/05/28 |
| 日本語 | yyyy/MM/dd | 2026/05/28 |
| 한국어 | yyyy.MM.dd | 2026.05.28 |
| Français | dd/MM/yyyy | 28/05/2026 |
| Deutsch | dd.MM.yyyy | 28.05.2026 |
| Español | dd/MM/yyyy | 28/05/2026 |
| Português | dd/MM/yyyy | 28/05/2026 |
| Русский | dd.MM.yyyy | 28.05.2026 |
| العربية | dd/MM/yyyy | 28/05/2026 |

## 货币格式

### 自动本地化

```tsx
import { useI18n } from '@/i18n/context'

function PriceDisplay() {
  const { formatCurrency } = useI18n()

  return (
    <div>
      <p>Price: {formatCurrency(99.99)}</p>
    </div>
  )
}
```

### 货币格式示例

| 语言 | 货币 | 示例 |
|------|------|------|
| English | USD | $99.99 |
| 中文 | CNY | ¥99.99 |
| 日本語 | JPY | ¥99 |
| 한국어 | KRW | ₩99,990 |
| Français | EUR | 99,99 € |
| Deutsch | EUR | 99,99 € |
| Español | EUR | 99,99 € |
| Português | BRL | R$ 99,99 |
| Русский | RUB | 99,99 ₽ |
| العربية | AED | د.إ 99.99 |

## RTL (从右到左) 支持

### 自动RTL处理

```tsx
import { useI18n } from '@/i18n/context'

function MyComponent() {
  const { isRTL } = useI18n()

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'}>
      Content
    </div>
  )
}
```

### RTL样式

```css
/* 使用逻辑属性 (推荐) */
.container {
  padding-inline-start: 1rem;
  padding-inline-end: 1rem;
  margin-inline-start: auto;
  margin-inline-end: auto;
}

/* 或使用RTL特定样式 */
.rtl .container {
  padding-right: 1rem;
  padding-left: 1rem;
  margin-right: auto;
  margin-left: auto;
}

.ltr .container {
  padding-left: 1rem;
  padding-right: 1rem;
  margin-left: auto;
  margin-right: auto;
}
```

### RTL组件示例

```tsx
import { useI18n } from '@/i18n/context'
import clsx from 'clsx'

function Sidebar() {
  const { isRTL } = useI18n()

  return (
    <aside
      className={clsx(
        'fixed inset-y-0 w-64 bg-slate-900',
        isRTL ? 'right-0' : 'left-0'
      )}
    >
      {/* Sidebar content */}
    </aside>
  )
}
```

## 翻译最佳实践

### 1. 使用命名空间

```json
{
  "common": { ... },
  "navigation": { ... },
  "errors": { ... },
  "validation": { ... }
}
```

### 2. 避免硬编码字符串

```tsx
// ✗ 差
<button>Click me</button>

// ✓ 好
<button>{t('common.clickMe')}</button>
```

### 3. 使用描述性键名

```json
{
  // ✗ 差
  "msg1": "Loading...",
  "msg2": "Error occurred",

  // ✓ 好
  "loading": "Loading...",
  "error": "Error occurred"
}
```

### 4. 提供上下文

```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel"
  },
  "dialog": {
    "confirmTitle": "Confirm Action",
    "confirmMessage": "Are you sure?"
  }
}
```

### 5. 处理复数形式

```tsx
// 使用条件逻辑
const itemCount = 5
const message = itemCount === 1
  ? t('items.singular')
  : t('items.plural', { count: itemCount })
```

## 浏览器语言检测

```typescript
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES } from '@/i18n/config'

// 获取浏览器语言
function getBrowserLanguage() {
  const browserLang = navigator.language.split('-')[0]
  return SUPPORTED_LANGUAGES[browserLang] ? browserLang : DEFAULT_LANGUAGE
}
```

## 持久化语言选择

```typescript
// 保存到localStorage
localStorage.setItem('language', 'zh')

// 从localStorage读取
const savedLanguage = localStorage.getItem('language')
```

## 测试国际化

### 测试翻译

```tsx
import { render, screen } from '@testing-library/react'
import { I18nProvider } from '@/i18n/context'

test('should display translated text', () => {
  render(
    <I18nProvider defaultLanguage="zh">
      <MyComponent />
    </I18nProvider>
  )

  expect(screen.getByText('中文文本')).toBeInTheDocument()
})
```

### 测试RTL

```tsx
test('should apply RTL direction for Arabic', () => {
  const { container } = render(
    <I18nProvider defaultLanguage="ar">
      <MyComponent />
    </I18nProvider>
  )

  expect(container.firstChild).toHaveAttribute('dir', 'rtl')
})
```

## 常见问题

### Q: 如何添加新语言?
A: 
1. 在`config.ts`中添加语言配置
2. 创建翻译文件`translations/[lang].json`
3. 更新`SUPPORTED_LANGUAGES`对象

### Q: 如何处理缺失的翻译?
A: 使用默认值或回退到英文

```tsx
const { t } = useI18n()
const text = t('key', 'Default text')
```

### Q: 如何支持方言?
A: 使用语言代码 (如 `en-US`, `en-GB`)

```typescript
const SUPPORTED_LANGUAGES = {
  'en-US': { ... },
  'en-GB': { ... },
  'zh-CN': { ... },
  'zh-TW': { ... },
}
```

## 参考资源

- [MDN国际化](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Internationalization)
- [Unicode CLDR](https://cldr.unicode.org/)
- [W3C语言标签](https://www.w3.org/International/articles/language-tags/)
- [RTL最佳实践](https://www.w3.org/International/questions/qa-html-dir)
