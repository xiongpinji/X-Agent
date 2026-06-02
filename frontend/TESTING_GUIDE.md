# X-Agent 测试指南

## 测试策略

X-Agent采用分层测试策略，确保代码质量和用户体验。

```
┌─────────────────────────────────────┐
│      E2E测试 (Playwright)           │ 用户场景
├─────────────────────────────────────┤
│   集成测试 (React Testing Library)   │ 组件交互
├─────────────────────────────────────┤
│    单元测试 (Jest)                   │ 函数逻辑
└─────────────────────────────────────┘
```

## 单元测试

### 使用Jest

```bash
npm install --save-dev jest @types/jest ts-jest
```

### 测试工具函数

```typescript
// src/utils/__tests__/performance.test.ts
import { checkPerformanceTargets } from '@/utils/performance'

describe('Performance Utils', () => {
  test('should check performance targets', () => {
    const targets = checkPerformanceTargets()
    expect(targets).toHaveProperty('fcp')
    expect(targets).toHaveProperty('lcp')
    expect(targets).toHaveProperty('cls')
    expect(targets).toHaveProperty('fid')
  })
})
```

### 测试无障碍工具

```typescript
// src/utils/__tests__/accessibility.test.ts
import { checkContrast, generateId, isNavigationKey } from '@/utils/accessibility'

describe('Accessibility Utils', () => {
  test('should check color contrast', () => {
    const isValid = checkContrast('#0284c7', '#ffffff')
    expect(isValid).toBe(true)
  })

  test('should generate unique IDs', () => {
    const id1 = generateId('test')
    const id2 = generateId('test')
    expect(id1).not.toBe(id2)
    expect(id1).toMatch(/^test-/)
  })

  test('should identify navigation keys', () => {
    expect(isNavigationKey('ArrowUp')).toBe(true)
    expect(isNavigationKey('Enter')).toBe(false)
  })
})
```

### 测试国际化

```typescript
// src/i18n/__tests__/config.test.ts
import { getLanguageConfig, isRTL, SUPPORTED_LANGUAGES } from '@/i18n/config'

describe('I18n Config', () => {
  test('should get language config', () => {
    const config = getLanguageConfig('en')
    expect(config.code).toBe('en')
    expect(config.direction).toBe('ltr')
  })

  test('should detect RTL languages', () => {
    expect(isRTL('ar')).toBe(true)
    expect(isRTL('en')).toBe(false)
  })

  test('should support all languages', () => {
    Object.keys(SUPPORTED_LANGUAGES).forEach((lang) => {
      expect(getLanguageConfig(lang as any)).toBeDefined()
    })
  })
})
```

## 组件测试

### 使用React Testing Library

```bash
npm install --save-dev @testing-library/react @testing-library/jest-dom
```

### 测试Button组件

```typescript
// src/components/ui/__tests__/Button.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '@/components/ui/Button'

describe('Button Component', () => {
  test('should render button with text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
  })

  test('should handle click events', async () => {
    const handleClick = jest.fn()
    render(<Button onClick={handleClick}>Click</Button>)

    await userEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  test('should be disabled when isDisabled is true', () => {
    render(<Button isDisabled>Disabled</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  test('should show loading state', () => {
    render(<Button isLoading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  test('should apply correct variant styles', () => {
    const { rerender } = render(<Button variant="primary">Primary</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-primary-600')

    rerender(<Button variant="danger">Danger</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-error-600')
  })

  test('should have proper ARIA attributes', () => {
    render(<Button ariaLabel="Close dialog">×</Button>)
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Close dialog')
  })
})
```

### 测试ErrorBoundary

```typescript
// src/components/ui/__tests__/ErrorBoundary.test.tsx
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'

const ThrowError = () => {
  throw new Error('Test error')
}

describe('ErrorBoundary Component', () => {
  beforeEach(() => {
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  test('should catch errors and display fallback', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  test('should reset error state', async () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()

    const resetButton = screen.getByRole('button', { name: /try again/i })
    await userEvent.click(resetButton)

    rerender(
      <ErrorBoundary>
        <div>Success</div>
      </ErrorBoundary>
    )

    expect(screen.getByText('Success')).toBeInTheDocument()
  })
})
```

## 集成测试

### 测试页面流程

```typescript
// src/__tests__/integration/dashboard.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dashboard } from '@/pages/Dashboard'
import { I18nProvider } from '@/i18n/context'

describe('Dashboard Integration', () => {
  test('should load and display dashboard', async () => {
    render(
      <I18nProvider>
        <Dashboard />
      </I18nProvider>
    )

    await waitFor(() => {
      expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
    })
  })

  test('should handle user interactions', async () => {
    render(
      <I18nProvider>
        <Dashboard />
      </I18nProvider>
    )

    const button = screen.getByRole('button', { name: /action/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument()
    })
  })
})
```

## E2E测试

### 使用Playwright

```bash
npm install --save-dev @playwright/test
```

### 配置Playwright

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
```

### 编写E2E测试

```typescript
// e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test('should load dashboard', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/X-Agent/)
    await expect(page.locator('h1')).toContainText('Dashboard')
  })

  test('should navigate between pages', async ({ page }) => {
    await page.goto('/')
    await page.click('a[href="/chat"]')
    await expect(page).toHaveURL('/chat')
    await expect(page.locator('h1')).toContainText('Chat')
  })

  test('should handle form submission', async ({ page }) => {
    await page.goto('/')
    await page.fill('input[name="search"]', 'test')
    await page.click('button[type="submit"]')
    await expect(page.locator('.results')).toBeVisible()
  })

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Tab')
    await expect(page.locator(':focus')).toBeTruthy()
  })
})
```

## 性能测试

### 使用Lighthouse

```bash
npm install --save-dev lighthouse
```

### 性能测试脚本

```typescript
// scripts/performance-test.ts
import lighthouse from 'lighthouse'
import * as chromeLauncher from 'chrome-launcher'

async function runPerformanceTest() {
  const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless'] })

  const options = {
    logLevel: 'info',
    output: 'json',
    port: chrome.port,
  }

  const runnerResult = await lighthouse('http://localhost:3000', options)

  const scores = {
    performance: runnerResult.lhr.categories.performance.score * 100,
    accessibility: runnerResult.lhr.categories.accessibility.score * 100,
    bestPractices: runnerResult.lhr.categories['best-practices'].score * 100,
    seo: runnerResult.lhr.categories.seo.score * 100,
  }

  console.log('Lighthouse Scores:', scores)

  // 检查目标
  if (scores.performance < 95) {
    console.error('Performance score below target!')
    process.exit(1)
  }

  await chromeLauncher.kill(chrome.pid)
}

runPerformanceTest()
```

## 无障碍测试

### 使用axe-core

```bash
npm install --save-dev @axe-core/react jest-axe
```

### 无障碍测试示例

```typescript
// src/components/__tests__/accessibility.test.tsx
import { render } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { Button } from '@/components/ui/Button'

expect.extend(toHaveNoViolations)

describe('Accessibility', () => {
  test('Button should not have accessibility violations', async () => {
    const { container } = render(<Button>Click me</Button>)
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  test('Form should have proper labels', async () => {
    const { container } = render(
      <form>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" />
      </form>
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
```

## 测试覆盖率

### 配置覆盖率目标

```javascript
// jest.config.js
module.exports = {
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/main.tsx',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
}
```

### 生成覆盖率报告

```bash
npm test -- --coverage
```

## 测试最佳实践

1. **测试行为，不是实现**: 关注用户看到的内容
2. **使用有意义的测试名称**: 描述测试的目的
3. **保持测试独立**: 每个测试应该独立运行
4. **使用测试数据**: 创建可重用的测试数据
5. **模拟外部依赖**: 使用jest.mock()
6. **测试错误情况**: 不仅测试成功路径
7. **保持测试快速**: 避免不必要的等待

## 运行测试

```bash
# 运行所有测试
npm test

# 运行特定测试文件
npm test Button.test.tsx

# 运行测试并生成覆盖率报告
npm test -- --coverage

# 监视模式
npm test -- --watch

# E2E测试
npm run test:e2e

# 性能测试
npm run test:performance

# 无障碍测试
npm test -- --testPathPattern=accessibility
```

## CI/CD集成

### GitHub Actions示例

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm test -- --coverage
      - run: npm run test:e2e
      - run: npm run test:performance
```

## 参考资源

- [Jest文档](https://jestjs.io/)
- [React Testing Library](https://testing-library.com/react)
- [Playwright文档](https://playwright.dev/)
- [axe-core](https://github.com/dequelabs/axe-core)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)
