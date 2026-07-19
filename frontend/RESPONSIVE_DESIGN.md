# X-Agent Web UI 响应式设计指南

## 断点定义

```
xs: 0px      - 手机竖屏
sm: 640px    - 手机横屏
md: 768px    - 平板竖屏
lg: 1024px   - 平板横屏
xl: 1280px   - 桌面
2xl: 1536px  - 大屏桌面
```

## 移动优先设计

### 布局原则

1. **单列布局**
   ```tsx
   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
     {/* 内容 */}
   </div>
   ```

2. **灵活的间距**
   ```tsx
   <div className="p-4 md:p-6 lg:p-8">
     {/* 内容 */}
   </div>
   ```

3. **可读的字体大小**
   ```tsx
   <h1 className="text-2xl md:text-3xl lg:text-4xl">
     标题
   </h1>
   ```

### 导航适配

#### 移动端
- 汉堡菜单
- 底部导航栏
- 全屏菜单

#### 平板端
- 侧边栏
- 顶部导航
- 混合导航

#### 桌面端
- 固定侧边栏
- 顶部导航栏
- 下拉菜单

### 表格适配

#### 移动端
```tsx
// 卡片视图
<div className="space-y-4">
  {data.map(item => (
    <Card key={item.id}>
      <div className="flex justify-between">
        <span>{item.name}</span>
        <span>{item.value}</span>
      </div>
    </Card>
  ))}
</div>
```

#### 桌面端
```tsx
// 表格视图
<DataTable columns={columns} data={data} />
```

### 模态框适配

```tsx
<Modal
  className="max-w-sm md:max-w-md lg:max-w-lg"
  // 内容
/>
```

## 触摸交互

### 触摸目标大小
- 最小：44x44像素
- 推荐：48x48像素
- 间距：至少8像素

### 手势支持
- 点击
- 长按
- 滑动
- 捏合缩放

### 反馈
```tsx
<button
  className="active:scale-95 transition-transform"
  onTouchStart={handleTouchStart}
  onTouchEnd={handleTouchEnd}
>
  按钮
</button>
```

## 性能优化

### 图片优化
```tsx
<img
  src="image.jpg"
  srcSet="image-sm.jpg 640w, image-md.jpg 1024w"
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
  alt="描述"
/>
```

### 代码分割
```tsx
const HeavyComponent = lazy(() => import('./HeavyComponent'))

<Suspense fallback={<LoadingState />}>
  <HeavyComponent />
</Suspense>
```

### 虚拟滚动
```tsx
<VirtualList
  items={items}
  itemHeight={50}
  renderItem={renderItem}
/>
```

## 测试清单

### 移动设备
- [ ] iPhone SE (375px)
- [ ] iPhone 12 (390px)
- [ ] iPhone 14 Pro Max (430px)
- [ ] Android 手机 (360px-412px)

### 平板设备
- [ ] iPad (768px)
- [ ] iPad Pro (1024px)
- [ ] Android 平板 (600px-1200px)

### 桌面设备
- [ ] 1280x720 (小屏)
- [ ] 1920x1080 (标准)
- [ ] 2560x1440 (高分辨率)

### 浏览器
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

## 常见问题

### Q: 如何处理不同屏幕尺寸的图片？
A: 使用`srcSet`和`sizes`属性，或使用图片CDN。

### Q: 如何优化移动端性能？
A: 使用代码分割、懒加载和虚拟滚动。

### Q: 如何测试响应式设计？
A: 使用浏览器开发者工具的设备模拟功能。

## 最佳实践

1. **移动优先**：从移动设计开始，逐步增强
2. **灵活布局**：使用Flexbox和Grid
3. **相对单位**：使用rem和em而不是px
4. **媒体查询**：使用Tailwind的响应式前缀
5. **测试**：在真实设备上测试
