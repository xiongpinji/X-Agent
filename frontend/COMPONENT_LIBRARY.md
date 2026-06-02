# X-Agent Web UI 组件库文档

## 快速开始

### 基础组件

#### Button
```tsx
import { Button } from '@/components/ui'

<Button variant="primary" size="md">
  Click me
</Button>

<Button variant="danger" isLoading>
  Loading...
</Button>
```

**Props:**
- `variant`: 'primary' | 'secondary' | 'danger' | 'ghost'
- `size`: 'sm' | 'md' | 'lg'
- `isLoading`: boolean
- `icon`: React.ReactNode

#### Card
```tsx
import { Card, CardHeader, CardBody, CardFooter } from '@/components/ui'

<Card>
  <CardHeader>标题</CardHeader>
  <CardBody>内容</CardBody>
  <CardFooter>页脚</CardFooter>
</Card>
```

#### Alert
```tsx
import { Alert } from '@/components/ui'

<Alert variant="success" title="Success">
  操作成功完成
</Alert>
```

**Variants:** 'info' | 'success' | 'warning' | 'error'

### 表单组件

#### Input
```tsx
import { Input } from '@/components/ui'

<Input
  label="Email"
  type="email"
  placeholder="Enter email"
  error="Invalid email"
  helperText="We'll never share your email"
/>
```

#### Select
```tsx
import { Select } from '@/components/ui'

<Select
  label="Choose option"
  options={[
    { value: '1', label: 'Option 1' },
    { value: '2', label: 'Option 2' },
  ]}
/>
```

#### Textarea
```tsx
import { Textarea } from '@/components/ui'

<Textarea
  label="Message"
  placeholder="Enter your message"
  rows={6}
/>
```

#### Checkbox
```tsx
import { Checkbox } from '@/components/ui'

<Checkbox label="I agree to terms" />
```

### 数据展示

#### DataTable
```tsx
import { DataTable } from '@/components/ui'

<DataTable
  columns={[
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
  ]}
  data={users}
  onRowClick={handleRowClick}
/>
```

#### Timeline
```tsx
import { Timeline } from '@/components/ui'

<Timeline
  items={[
    { id: '1', title: 'Step 1', status: 'completed' },
    { id: '2', title: 'Step 2', status: 'active' },
  ]}
/>
```

#### StepIndicator
```tsx
import { StepIndicator } from '@/components/ui'

<StepIndicator
  steps={[
    { id: '1', label: 'Step 1', status: 'completed' },
    { id: '2', label: 'Step 2', status: 'active' },
  ]}
/>
```

### 进度指示

#### ProgressBar
```tsx
import { ProgressBar } from '@/components/ui'

<ProgressBar value={65} max={100} showLabel />
```

#### CircularProgress
```tsx
import { CircularProgress } from '@/components/ui'

<CircularProgress value={75} size="md" />
```

### 状态组件

#### LoadingState
```tsx
import { LoadingState } from '@/components/ui'

<LoadingState message="Loading data..." />
```

#### EmptyState
```tsx
import { EmptyState } from '@/components/ui'

<EmptyState
  title="No data"
  description="Create a new item to get started"
  action={<Button>Create</Button>}
/>
```

#### Skeleton
```tsx
import { Skeleton } from '@/components/ui'

<Skeleton count={3} height="h-4" />
```

## 高级组件

### ExecutionPanel
```tsx
import { ExecutionPanel } from '@/components/ExecutionPanel'

<ExecutionPanel
  steps={[
    { id: '1', name: 'Initialize', status: 'completed' },
    { id: '2', name: 'Process', status: 'running' },
  ]}
  isRunning
/>
```

### WorkflowVisualizer
```tsx
import { WorkflowVisualizer } from '@/components/WorkflowVisualizer'

<WorkflowVisualizer
  nodes={[
    { id: '1', name: 'Start', status: 'completed' },
    { id: '2', name: 'Process', status: 'running' },
  ]}
  onNodeClick={handleNodeClick}
/>
```

## 自定义主题

### 颜色变量
```css
:root {
  --color-primary: #3b82f6;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
}
```

### 使用自定义颜色
```tsx
<Button className="bg-custom-color">
  Custom Button
</Button>
```

## 最佳实践

1. **使用TypeScript**：获得完整的类型支持
2. **组件组合**：组合小组件构建复杂UI
3. **可访问性**：始终添加ARIA标签
4. **响应式**：使用Tailwind的响应式前缀
5. **性能**：使用React.memo优化重新渲染

## 常见问题

### Q: 如何自定义组件样式？
A: 使用`className`属性传递自定义Tailwind类。

### Q: 如何扩展组件功能？
A: 创建包装组件或使用组件组合。

### Q: 如何处理表单验证？
A: 使用`error`和`helperText`属性。

## 更新日志

### v1.0.0
- 初始发布
- 15个基础组件
- 完整的TypeScript支持
- 响应式设计
- 可访问性支持
