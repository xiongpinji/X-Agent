# X-Agent Desktop Application - Test Execution Guide

## Quick Start

### 1. Setup Test Environment

```bash
# Navigate to desktop frontend directory
cd "D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划\desktop\frontend"

# Install dependencies
npm install

# Install Playwright browsers
npx playwright install
```

### 2. Start Development Server

```bash
# In one terminal, start the dev server
npm run dev
# Server will be available at http://localhost:5173
```

### 3. Run Tests

```bash
# In another terminal, run tests
npm run test:all
```

---

## Test Execution Scenarios

### Scenario 1: Quick Smoke Test
**Purpose**: Verify basic functionality
**Time**: ~5 minutes

```bash
# Run functional completeness tests only
npx playwright test tests/e2e/functional-completeness.spec.ts --project=chromium
```

### Scenario 2: Full Integration Test
**Purpose**: Complete test coverage
**Time**: ~30 minutes

```bash
# Run all E2E tests
npm run test:e2e
```

### Scenario 3: Performance Baseline
**Purpose**: Establish performance metrics
**Time**: ~15 minutes

```bash
# Run performance tests
npx playwright test tests/e2e/performance.spec.ts
```

### Scenario 4: Cross-Platform Verification
**Purpose**: Verify multi-browser compatibility
**Time**: ~20 minutes

```bash
# Run cross-platform tests on all browsers
npx playwright test tests/e2e/cross-platform.spec.ts
```

### Scenario 5: API Integration Check
**Purpose**: Verify backend integration
**Time**: ~15 minutes

```bash
# Run API integration tests
npx playwright test tests/e2e/api-integration.spec.ts
```

### Scenario 6: UI/UX Verification
**Purpose**: Verify user interface
**Time**: ~10 minutes

```bash
# Run UI interaction tests
npx playwright test tests/e2e/ui-interaction.spec.ts
```

---

## Test Execution with Different Options

### Run Tests with HTML Report
```bash
npm run test:e2e
# Report will be generated at: test-results/playwright/index.html
# Open in browser: npx playwright show-report
```

### Run Tests with UI Mode
```bash
npm run test:e2e:ui
# Opens interactive test UI where you can:
# - Watch tests run in real-time
# - Step through tests
# - Inspect elements
# - View test logs
```

### Run Tests in Debug Mode
```bash
npm run test:e2e:debug
# Opens Playwright Inspector for step-by-step debugging
```

### Run Tests with Coverage
```bash
npm run test:coverage
# Generates coverage report at: coverage/index.html
```

### Run Specific Test File
```bash
npx playwright test tests/e2e/ui-interaction.spec.ts
```

### Run Specific Test Case
```bash
npx playwright test tests/e2e/ui-interaction.spec.ts -g "should navigate to Agents page"
```

### Run Tests on Specific Browser
```bash
# Chromium only
npx playwright test --project=chromium

# Firefox only
npx playwright test --project=firefox

# WebKit only
npx playwright test --project=webkit

# Multiple browsers
npx playwright test --project=chromium --project=firefox
```

### Run Tests in Parallel
```bash
# Default: parallel execution
npm run test:e2e

# Sequential execution (slower but easier to debug)
npx playwright test --workers=1
```

### Run Tests with Retries
```bash
# Retry failed tests 3 times
npx playwright test --retries=3
```

---

## Interpreting Test Results

### Success Output
```
✓ [chromium] › tests/e2e/ui-interaction.spec.ts › UI Interaction Tests › Navigation › should render main layout
✓ [chromium] › tests/e2e/ui-interaction.spec.ts › UI Interaction Tests › Navigation › should navigate to Agents page
...
123 passed (45s)
```

### Failure Output
```
✗ [chromium] › tests/e2e/ui-interaction.spec.ts › UI Interaction Tests › Navigation › should navigate to Agents page
Error: Timeout 30000ms exceeded waiting for locator('a[href="/agents"]')
```

### Performance Metrics Output
```
Home page load time: 1234ms
Initial UI render time: 567ms
First Contentful Paint: 890ms
Navigation response time: 234ms
Button click response time: 123ms
Memory before: 45.23MB
Memory after: 67.89MB
Memory increase: 22.66MB
```

---

## Troubleshooting

### Issue: Tests Timeout
**Solution**:
```bash
# Increase timeout
npx playwright test --timeout=60000

# Or modify playwright.config.ts:
# timeout: 60000
```

### Issue: Port Already in Use
**Solution**:
```bash
# Kill process on port 5173
# Windows:
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:5173 | xargs kill -9
```

### Issue: Playwright Browsers Not Installed
**Solution**:
```bash
npx playwright install
npx playwright install-deps
```

### Issue: Tests Pass Locally but Fail in CI
**Solution**:
```bash
# Run tests in headed mode to see what's happening
npx playwright test --headed

# Run with trace for debugging
npx playwright test --trace on
```

### Issue: Memory Issues
**Solution**:
```bash
# Run tests with limited workers
npx playwright test --workers=1

# Or increase Node memory
NODE_OPTIONS=--max-old-space-size=4096 npm run test:e2e
```

---

## Performance Benchmarking

### Establish Baseline
```bash
# Run performance tests and record results
npx playwright test tests/e2e/performance.spec.ts > baseline.txt
```

### Compare Against Baseline
```bash
# Run tests again and compare
npx playwright test tests/e2e/performance.spec.ts > current.txt
diff baseline.txt current.txt
```

### Performance Targets
- Startup Time: < 2 seconds
- Response Time: < 500ms
- Memory Usage: < 200MB
- FPS: > 30fps
- Load Time: < 1 second

---

## Continuous Integration Setup

### GitHub Actions Example
```yaml
name: Desktop App Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd desktop/frontend && npm install
      - run: npx playwright install
      - run: npm run test:all
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: test-results/playwright/
```

---

## Test Maintenance

### Adding New Tests
1. Create new test file in `tests/e2e/`
2. Follow existing test structure
3. Use descriptive test names
4. Add comments for complex logic
5. Run tests to verify

### Updating Existing Tests
1. Modify test file
2. Run specific test to verify changes
3. Check for side effects on other tests
4. Update documentation if needed

### Removing Tests
1. Delete test file or test case
2. Run full test suite to verify
3. Update documentation

---

## Test Reporting

### Generate HTML Report
```bash
npm run test:e2e
npx playwright show-report
```

### Generate JSON Report
```bash
# Already configured in playwright.config.ts
# Output: test-results/playwright/results.json
```

### Generate JUnit Report
```bash
# Already configured in playwright.config.ts
# Output: test-results/playwright/junit.xml
```

### Custom Report Generation
```bash
# Parse results and generate custom report
node scripts/generate-report.js
```

---

## Best Practices

1. **Run tests regularly**: Execute full test suite before commits
2. **Keep tests isolated**: Each test should be independent
3. **Use descriptive names**: Test names should clearly describe what they test
4. **Avoid flaky tests**: Use proper waits and retries
5. **Monitor performance**: Track performance metrics over time
6. **Document failures**: Record and analyze test failures
7. **Update tests**: Keep tests in sync with application changes
8. **Review coverage**: Ensure adequate test coverage

---

## Support and Resources

- **Playwright Docs**: https://playwright.dev
- **Vitest Docs**: https://vitest.dev
- **Vue 3 Testing**: https://vuejs.org/guide/scaling-up/testing.html
- **Tauri Docs**: https://tauri.app

---

## Test Execution Checklist

- [ ] Development server running on http://localhost:5173
- [ ] All dependencies installed (`npm install`)
- [ ] Playwright browsers installed (`npx playwright install`)
- [ ] No other tests running on the same port
- [ ] Sufficient disk space for test artifacts
- [ ] Network connectivity for API tests
- [ ] System resources available (RAM, CPU)

---

## Next Steps

1. Execute full test suite: `npm run test:all`
2. Review test results and reports
3. Fix any failing tests
4. Establish performance baseline
5. Integrate tests into CI/CD pipeline
6. Schedule regular test runs
7. Monitor and optimize performance
