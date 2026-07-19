# GitHub Actions 最佳实践

## 目录

1. [工作流设计](#工作流设计)
2. [安全性](#安全性)
3. [性能优化](#性能优化)
4. [错误处理](#错误处理)
5. [监控和日志](#监控和日志)
6. [成本优化](#成本优化)

## 工作流设计

### 1. 模块化设计

将大型工作流分解为可重用的组件:

```yaml
# ✓ 好的做法
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: pip install ruff
      - run: ruff check .

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: pip install -e ".[test]"
      - run: pytest

# ✗ 避免
jobs:
  everything:
    runs-on: ubuntu-latest
    steps:
      # 所有步骤混在一起
```

### 2. 使用矩阵策略

对多个配置进行并行测试:

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12"]
    os: [ubuntu-latest, macos-latest, windows-latest]
  fail-fast: false  # 继续运行其他配置

runs-on: ${{ matrix.os }}

steps:
  - uses: actions/setup-python@v4
    with:
      python-version: ${{ matrix.python-version }}
```

### 3. 条件执行

根据事件类型或分支有条件地运行步骤:

```yaml
jobs:
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying to production"

  test-pr:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Testing PR"
```

### 4. 并发控制

防止重复的工作流运行:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

这会取消同一分支的旧工作流，节省资源。

### 5. 依赖管理

使用`needs`关键字定义工作流依赖:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying ${{ needs.build.outputs.image-tag }}"
```

## 安全性

### 1. 使用最小权限原则

```yaml
permissions:
  contents: read
  packages: write
  security-events: write
```

不要使用默认的`write-all`权限。

### 2. 保护Secrets

```yaml
# ✓ 好的做法
- name: Deploy
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: |
    # 不要在日志中打印secrets
    ./deploy.sh

# ✗ 避免
- run: echo "API_KEY=${{ secrets.API_KEY }}"  # 会暴露在日志中
```

### 3. 使用环境保护规则

为敏感环境配置审批:

```yaml
environment:
  name: production
  url: https://example.com
  # GitHub会要求审批才能部署到此环境
```

### 4. 验证Action版本

始终使用特定版本，不要使用`@main`:

```yaml
# ✓ 好的做法
- uses: actions/checkout@v4
- uses: docker/build-push-action@v4

# ✗ 避免
- uses: actions/checkout@main
- uses: docker/build-push-action@main
```

### 5. 审计日志

启用详细日志用于调试:

```yaml
- name: Debug info
  if: runner.debug == '1'
  run: |
    echo "Debug mode enabled"
    env | sort
```

## 性能优化

### 1. 缓存依赖

```yaml
- uses: actions/setup-python@v4
  with:
    python-version: "3.11"
    cache: 'pip'  # 自动缓存pip依赖

- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### 2. Docker层缓存

```yaml
- uses: docker/build-push-action@v4
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### 3. 并行执行

```yaml
jobs:
  test-unit:
    runs-on: ubuntu-latest
    # 与其他job并行运行

  test-integration:
    runs-on: ubuntu-latest
    # 与其他job并行运行

  deploy:
    needs: [test-unit, test-integration]
    # 等待两个测试完成后运行
```

### 4. 使用更快的Runner

```yaml
# ✓ 对于快速任务
runs-on: ubuntu-latest

# ✓ 对于需要更多资源的任务
runs-on: ubuntu-latest-8-cores
```

### 5. 早期失败

```yaml
strategy:
  fail-fast: true  # 第一个失败时停止其他job
```

## 错误处理

### 1. Continue on Error

```yaml
- name: Optional step
  run: npm run lint
  continue-on-error: true  # 失败不会停止工作流

- name: Required step
  run: npm test
  # 失败会停止工作流
```

### 2. 条件步骤

```yaml
- name: Upload coverage
  if: always()  # 即使前面步骤失败也运行
  uses: codecov/codecov-action@v3

- name: Notify on failure
  if: failure()  # 仅在前面步骤失败时运行
  run: echo "Build failed"

- name: Notify on success
  if: success()  # 仅在所有前面步骤成功时运行
  run: echo "Build succeeded"
```

### 3. 重试逻辑

```yaml
- name: Deploy with retry
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    retry_wait_seconds: 5
    command: ./deploy.sh
```

### 4. 超时设置

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # 30分钟后超时

    steps:
      - run: long-running-command
        timeout-minutes: 10  # 此步骤10分钟后超时
```

## 监控和日志

### 1. 结构化日志

```yaml
- name: Log deployment info
  run: |
    echo "::group::Deployment Details"
    echo "Environment: ${{ env.ENVIRONMENT }}"
    echo "Version: ${{ github.ref }}"
    echo "::endgroup::"
```

### 2. 注解和警告

```yaml
- name: Check code quality
  run: |
    if [ $COVERAGE -lt 80 ]; then
      echo "::warning::Coverage below 80%: $COVERAGE%"
    fi
    if [ $ERRORS -gt 0 ]; then
      echo "::error::Found $ERRORS errors"
      exit 1
    fi
```

### 3. 上传工件

```yaml
- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: test-results-${{ matrix.python-version }}
    path: |
      coverage.xml
      test-report.html
    retention-days: 30
```

### 4. 发布测试结果

```yaml
- name: Publish test results
  if: always()
  uses: EnricoMi/publish-unit-test-result-action@v2
  with:
    files: test-results.xml
```

## 成本优化

### 1. 限制工作流运行

```yaml
on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - 'pyproject.toml'
      # 仅当这些路径变化时运行
```

### 2. 使用Self-hosted Runners

对于频繁运行的工作流，使用自托管Runner可以节省成本:

```yaml
runs-on: [self-hosted, linux, x64]
```

### 3. 按需运行

```yaml
on:
  workflow_dispatch:  # 手动触发
  schedule:
    - cron: '0 2 * * *'  # 每天2AM运行
```

### 4. 清理工件

```yaml
- name: Delete old artifacts
  uses: geekyeggo/delete-artifact@v2
  with:
    name: test-results-*
```

## 工作流模板

### 最小化测试工作流

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - run: pip install -e ".[test]"
      - run: pytest --cov
      - uses: codecov/codecov-action@v3
```

### 完整的CI/CD工作流

```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main, develop]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    # ... 测试步骤

  lint:
    runs-on: ubuntu-latest
    # ... 代码质量检查

  security:
    runs-on: ubuntu-latest
    # ... 安全扫描

  build:
    needs: [test, lint, security]
    runs-on: ubuntu-latest
    # ... Docker构建

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production
    if: startsWith(github.ref, 'refs/tags/v')
    # ... 部署步骤
```

## 常见问题

### Q: 如何在工作流中使用环境变量?

A: 使用`env`关键字:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Building $IMAGE_NAME"
```

### Q: 如何在工作流间共享数据?

A: 使用outputs:

```yaml
jobs:
  build:
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - id: meta
        run: echo "tags=v1.0.0" >> $GITHUB_OUTPUT

  deploy:
    needs: build
    steps:
      - run: echo "Deploying ${{ needs.build.outputs.image-tag }}"
```

### Q: 如何调试工作流?

A: 启用调试日志:

```bash
# 在仓库设置中启用
# Settings > Secrets and variables > Actions > New repository secret
# 名称: ACTIONS_STEP_DEBUG
# 值: true
```

## 参考资源

- [GitHub Actions官方文档](https://docs.github.com/en/actions)
- [Workflow语法参考](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Actions市场](https://github.com/marketplace?type=actions)
- [GitHub Actions最佳实践](https://docs.github.com/en/actions/guides)
