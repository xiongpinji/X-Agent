# X-Agent Web UI 性能优化指南

## 性能指标

### 核心Web Vitals目标
- **LCP (Largest Contentful Paint)**: < 2.5s
- **FID (First Input Delay)**: < 100ms
- **CLS (Cumulative Layout Shift)**: < 0.1

### 其他指标
- **首屏加载时间**: < 2s
- **交互时间**: < 100ms
- **内存使用**: < 50MB
- **包大小**: < 200KB (gzipped)

## 优化策略

### 1. 代码分割

```tsx
// 路由级别代码分割
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Chat = lazy(() => import('@/pages/ChatPage'))

<Suspense fallback={<LoadingState />}>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/chat" element={<Chat />} />
  </Routes>
</Suspense>
```

### 2. 图片优化

```tsx
// 使用响应式图片
<img
  src="image.jpg"
  srcSet="image-sm.jpg 640w, image-md.jpg 1024w, image-lg.jpg 1920w"
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
  alt="描述"
  loading="lazy"
/>

// 使用WebP格式
<picture>
  <source srcSet="image.webp" type="image/webp" />
  <img src="image.jpg" alt="描述" />
</picture>
```

### 3. 虚拟滚动

```tsx
// 对于大列表使用虚拟滚动
import { FixedSizeList } from 'react-window'

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={50}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>
      {items[index].name}
    </div>
  )}
</FixedSizeList>
```

### 4. 缓存策略

```tsx
// 使用React Query进行数据缓存
import { useQuery } from '@tanstack/react-query'

const { data } = useQuery({
  queryKey: ['tasks'],
  queryFn: () => apiClient.listTasks(),
  staleTime: 5 * 60 * 1000, // 5分钟
  cacheTime: 10 * 60 * 1000, // 10分钟
})
```

### 5. 防抖和节流

```tsx
// 防抖搜索输入
const debouncedSearch = useDebounce(searchQuery, 300)

useEffect(() => {
  if (debouncedSearch) {
    handleSearch(debouncedSearch)
  }
}, [debouncedSearch])

// 节流滚动事件
const handleScroll = useThrottle(() => {
  updateScrollPosition()
}, 100)
```

### 6. 组件优化

```tsx
// 使用React.memo避免不必要的重新渲染
const TaskCard = React.memo(({ task, onDelete }) => {
  return (
    <Card>
      <CardBody>
        {task.name}
      </CardBody>
    </Card>
  )
})

// 使用useMemo缓存计算结果
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(data)
}, [data])

// 使用useCallback缓存函数
const handleDelete = useCallback((id) => {
  deleteTask(id)
}, [])
```

### 7. WebSocket优化

```tsx
// 消息去重和批处理
class OptimizedWebSocketService {
  private messageQueue: Map<string, any> = new Map()
  private batchTimer: NodeJS.Timeout | null = null

  send(type: string, data: any) {
    this.messageQueue.set(type, data)
    
    if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        this.flushQueue()
        this.batchTimer = null
      }, 50)
    }
  }

  private flushQueue() {
    for (const [type, data] of this.messageQueue) {
      this.ws.send(JSON.stringify({ type, data }))
    }
    this.messageQueue.clear()
  }
}
```

### 8. 构建优化

```javascript
// vite.config.ts
export default {
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'ui-vendor': ['lucide-react', 'clsx'],
        },
      },
    },
    minify: 'terser',
    sourcemap: false,
  },
}
```

## 监控和测试

### 性能监控

```tsx
// 使用Web Vitals库
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

getCLS(console.log)
getFID(console.log)
getFCP(console.log)
getLCP(console.log)
getTTFB(console.log)
```

### 性能测试

```bash
# Lighthouse审计
npm run build
npx lighthouse http://localhost:3000 --view

# 性能基准测试
npm run test:performance
```

## 性能检查清单

- [ ] 代码分割已实现
- [ ] 图片已优化
- [ ] 虚拟滚动已应用
- [ ] 缓存策略已配置
- [ ] 防抖/节流已使用
- [ ] 组件已优化
- [ ] WebSocket已优化
- [ ] 构建已优化
- [ ] 性能指标已监控
- [ ] Lighthouse评分 > 90

## 常见问题

### Q: 如何减少包大小？
A: 使用代码分割、tree-shaking和动态导入。

### Q: 如何改进首屏加载时间？
A: 优化关键资源、使用预加载和预连接。

### Q: 如何处理大列表？
A: 使用虚拟滚动和分页。

### Q: 如何监控性能？
A: 使用Web Vitals和Lighthouse。

## 参考资源

- [Web Vitals](https://web.dev/vitals/)
- [React性能优化](https://react.dev/reference/react/memo)
- [Vite优化指南](https://vitejs.dev/guide/features.html)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)
