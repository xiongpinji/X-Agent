# X-Agent 国际化（i18n）指南

## 概述

X-Agent 提供完整的多语言和地区化支持，包括：

- **5种语言支持**：英文、中文、日文、韩文、西班牙文
- **8个地区配置**：美国、中国、日本、韩国、西班牙、英国、德国、法国
- **地区化功能**：时区、货币、日期/时间格式、数字格式

## 后端使用

### 基本使用

```python
from backend.app.core.i18n import Language, Region, Locale, i18n

# 设置地区
i18n.set_locale(Language.CHINESE, Region.CN)

# 获取国际化上下文
context = i18n.get_context()

# 获取翻译
message = context.t("common.loading")  # "加载中..."

# 格式化日期
from datetime import datetime
now = datetime.now()
formatted_date = context.format_date(now)  # "2026-05-29"

# 格式化货币
formatted_currency = context.format_currency(1234.56)  # "¥1,234.56"

# 格式化数字
formatted_number = context.format_number(1234.56)  # "1,234.56"

# 获取时区和货币
timezone = context.get_timezone()  # "Asia/Shanghai"
currency = context.get_currency()  # "CNY"
```

### 翻译管理

```python
from backend.app.core.i18n import TranslationManager, Language

manager = TranslationManager("locales")

# 获取翻译
translation = manager.get_translation(Language.ENGLISH, "common.loading")

# 添加翻译
manager.add_translation(Language.ENGLISH, "custom.key", "Custom Value")

# 保存翻译
manager.save_translations(Language.ENGLISH)

# 获取所有翻译
all_translations = manager.get_translations(Language.ENGLISH)
```

### 地区化配置

```python
from backend.app.core.i18n import LocalizationConfig, Region

# 获取时区
timezone = LocalizationConfig.get_timezone(Region.CN)  # "Asia/Shanghai"

# 获取货币
currency = LocalizationConfig.get_currency(Region.US)  # "USD"

# 获取日期格式
date_format = LocalizationConfig.get_date_format(Region.JP)  # "YYYY年MM月DD日"

# 获取数字格式
number_format = LocalizationConfig.get_number_format(Region.ES)
# {"decimal": ",", "thousands": "."}

# 获取货币格式
currency_format = LocalizationConfig.get_currency_format(Region.KR)
# {"symbol": "₩", "position": "suffix", "space": true}
```

## 前端使用

### 设置提供者

在应用根组件中包装 `I18nProvider`：

```tsx
import { I18nProvider } from '@/i18n';

function App() {
  return (
    <I18nProvider>
      <YourApp />
    </I18nProvider>
  );
}
```

### 使用 Hook

```tsx
import { useI18n, useTranslation, useLocalization, useLanguageSettings } from '@/i18n';

function MyComponent() {
  // 获取完整的i18n上下文
  const { t, formatDate, formatCurrency, language, region } = useI18n();

  // 或使用特定的hook
  const { t } = useTranslation();
  const { formatDate, formatCurrency, formatNumber } = useLocalization();
  const { language, setLanguage, region, setRegion } = useLanguageSettings();

  return (
    <div>
      <p>{t('common.loading')}</p>
      <p>{formatCurrency(1234.56)}</p>
      <p>{formatDate(new Date())}</p>
    </div>
  );
}
```

### 语言切换器

```tsx
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

function Settings() {
  return (
    <div>
      <LanguageSwitcher />
    </div>
  );
}
```

## API 端点

### 获取支持的语言

```
GET /api/i18n/supported-languages

Response:
[
  { "code": "en", "name": "English" },
  { "code": "zh", "name": "中文" },
  ...
]
```

### 获取支持的地区

```
GET /api/i18n/supported-regions

Response:
[
  { "code": "US", "name": "United States" },
  { "code": "CN", "name": "China" },
  ...
]
```

### 设置地区

```
POST /api/i18n/set-locale

Request:
{
  "language": "zh",
  "region": "CN"
}

Response:
{
  "status": "success",
  "locale": "zh_CN"
}
```

### 获取当前地区配置

```
GET /api/i18n/locale

Response:
{
  "language": "zh",
  "region": "CN",
  "timezone": "Asia/Shanghai",
  "currency": "CNY",
  "dateFormat": "YYYY-MM-DD",
  "timeFormat": "HH:mm:ss"
}
```

### 获取翻译

```
GET /api/i18n/translations/{language}

Response:
{
  "language": "en",
  "translations": { ... }
}
```

### 获取单个翻译

```
GET /api/i18n/translation?language=en&key=common.loading&default=Loading

Response:
{
  "language": "en",
  "key": "common.loading",
  "value": "Loading..."
}
```

### 获取地区化配置

```
GET /api/i18n/localization-config/{region}

Response:
{
  "region": "CN",
  "timezone": "Asia/Shanghai",
  "currency": "CNY",
  "dateFormat": "YYYY-MM-DD",
  "timeFormat": "HH:mm:ss",
  "numberFormat": { "decimal": ".", "thousands": "," },
  "currencyFormat": { "symbol": "¥", "position": "prefix", "space": false }
}
```

### 格式化日期

```
POST /api/i18n/format-date?language=zh&region=CN&timestamp=1685376000&format_str=YYYY-MM-DD

Response:
{
  "formatted": "2026-05-29",
  "timezone": "Asia/Shanghai"
}
```

### 格式化货币

```
POST /api/i18n/format-currency?language=zh&region=CN&amount=1234.56

Response:
{
  "formatted": "¥1,234.56",
  "currency": "CNY"
}
```

### 格式化数字

```
POST /api/i18n/format-number?region=CN&number=1234.56&decimal_places=2

Response:
{
  "formatted": "1,234.56",
  "numberFormat": { "decimal": ".", "thousands": "," }
}
```

## 翻译文件结构

翻译文件位于 `locales/` 目录，每种语言一个JSON文件：

```
locales/
├── en.json
├── zh.json
├── ja.json
├── ko.json
└── es.json
```

### 翻译文件格式

```json
{
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "success": "Success"
  },
  "navigation": {
    "dashboard": "Dashboard",
    "chat": "Chat"
  },
  "validation": {
    "required": "This field is required",
    "email": "Please enter a valid email"
  }
}
```

## 支持的语言和地区

### 语言

| 代码 | 名称 |
|------|------|
| en | English |
| zh | 中文 |
| ja | 日本語 |
| ko | 한국어 |
| es | Español |

### 地区

| 代码 | 名称 | 时区 | 货币 |
|------|------|------|------|
| US | United States | America/New_York | USD |
| CN | China | Asia/Shanghai | CNY |
| JP | Japan | Asia/Tokyo | JPY |
| KR | Korea | Asia/Seoul | KRW |
| ES | Spain | Europe/Madrid | EUR |
| GB | United Kingdom | Europe/London | GBP |
| DE | Germany | Europe/Berlin | EUR |
| FR | France | Europe/Paris | EUR |

## 日期格式

| 地区 | 格式 |
|------|------|
| US | MM/DD/YYYY |
| CN | YYYY-MM-DD |
| JP | YYYY年MM月DD日 |
| KR | YYYY.MM.DD |
| ES | DD/MM/YYYY |
| GB | DD/MM/YYYY |
| DE | DD.MM.YYYY |
| FR | DD/MM/YYYY |

## 数字格式

| 地区 | 小数点 | 千位分隔符 |
|------|--------|----------|
| US | . | , |
| CN | . | , |
| ES | , | . |
| DE | , | . |
| FR | , | (空格) |

## 货币格式

| 地区 | 符号 | 位置 | 空格 |
|------|------|------|------|
| US | $ | 前缀 | 否 |
| CN | ¥ | 前缀 | 否 |
| KR | ₩ | 后缀 | 是 |
| ES | € | 后缀 | 是 |

## 最佳实践

1. **始终使用翻译键**：不要在代码中硬编码文本
2. **使用参数替换**：对于动态内容，使用 `{param}` 语法
3. **保持翻译同步**：确保所有语言的翻译都是最新的
4. **测试所有地区**：验证日期、货币和数字格式
5. **使用地区化上下文**：根据用户地区自动调整格式

## 示例

### 参数替换

```python
# 翻译文件
# "validation.minLength": "Minimum length is {min}"

context.t("validation.minLength", min=5)
# "Minimum length is 5"
```

### 条件翻译

```tsx
const { t } = useTranslation();

function ErrorMessage({ error }) {
  const key = `errors.${error}`;
  return <p>{t(key, error)}</p>;
}
```

### 动态地区切换

```tsx
function RegionSelector() {
  const { region, setRegion } = useLanguageSettings();
  const { formatCurrency } = useLocalization();

  return (
    <div>
      <select value={region} onChange={(e) => setRegion(e.target.value)}>
        <option value="US">US</option>
        <option value="CN">CN</option>
      </select>
      <p>Price: {formatCurrency(99.99)}</p>
    </div>
  );
}
```

## 故障排除

### 翻译未加载

确保 `locales/` 目录存在且包含正确的JSON文件。

### 日期格式不正确

检查地区代码是否正确，并验证日期格式字符串。

### 货币符号显示不正确

确保使用了正确的地区代码，并检查货币格式配置。

## 扩展

### 添加新语言

1. 在 `locales/` 目录中创建新的JSON文件
2. 在 `Language` 枚举中添加新语言
3. 更新支持的语言列表

### 添加新地区

1. 在 `Region` 枚举中添加新地区
2. 在 `LocalizationConfig` 中添加配置
3. 更新支持的地区列表
