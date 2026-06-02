# 插件市场前端组件指南

## 概述

本文档描述了 X-Agent 插件市场的前端组件架构、UI 设计和交互流程。

## 目录

1. [组件架构](#组件架构)
2. [页面设计](#页面设计)
3. [交互流程](#交互流程)
4. [UI 组件](#ui-组件)
5. [状态管理](#状态管理)
6. [API 集成](#api-集成)

## 组件架构

### 目录结构

```
frontend/
├── components/
│   ├── marketplace/
│   │   ├── PluginBrowser.tsx          # 插件浏览器
│   │   ├── PluginSearch.tsx           # 搜索组件
│   │   ├── PluginCard.tsx             # 插件卡片
│   │   ├── PluginDetail.tsx           # 插件详情
│   │   ├── PluginInstaller.tsx        # 安装器
│   │   ├── PluginReviews.tsx          # 评论组件
│   │   ├── PluginRating.tsx           # 评分组件
│   │   └── PluginStats.tsx            # 统计信息
│   ├── developer/
│   │   ├── PluginScaffold.tsx         # 脚手架生成
│   │   ├── PluginBuilder.tsx          # 构建工具
│   │   ├── PluginTester.tsx           # 测试工具
│   │   ├── PluginPublisher.tsx        # 发布工具
│   │   └── PluginDocs.tsx             # 文档生成
│   └── admin/
│       ├── PluginReview.tsx           # 审核面板
│       ├── PluginModeration.tsx       # 审核管理
│       └── PluginAnalytics.tsx        # 分析面板
├── pages/
│   ├── marketplace/
│   │   ├── index.tsx                  # 市场首页
│   │   ├── [id].tsx                   # 插件详情页
│   │   └── search.tsx                 # 搜索结果页
│   ├── developer/
│   │   ├── dashboard.tsx              # 开发者仪表板
│   │   ├── create.tsx                 # 创建插件
│   │   ├── [id]/edit.tsx              # 编辑插件
│   │   └── [id]/publish.tsx           # 发布插件
│   └── admin/
│       ├── dashboard.tsx              # 管理员仪表板
│       ├── plugins.tsx                # 插件管理
│       └── analytics.tsx              # 分析
├── hooks/
│   ├── usePluginMarketplace.ts        # 市场 Hook
│   ├── usePluginSearch.ts             # 搜索 Hook
│   ├── usePluginInstall.ts            # 安装 Hook
│   └── usePluginDeveloper.ts          # 开发者 Hook
├── services/
│   ├── pluginMarketplaceService.ts    # 市场服务
│   ├── pluginDevService.ts            # 开发服务
│   └── pluginAdminService.ts          # 管理服务
└── types/
    └── plugin.ts                      # 类型定义
```

## 页面设计

### 1. 插件市场首页

**布局：**
```
┌─────────────────────────────────────────────────┐
│              导航栏 + 搜索栏                      │
├─────────────────────────────────────────────────┤
│  分类侧边栏  │         主内容区                  │
│              │  ┌──────────────────────────┐   │
│  - 开发工具  │  │  精选插件轮播             │   │
│  - 自动化    │  └──────────────────────────┘   │
│  - 数据分析  │  ┌──────────────────────────┐   │
│  - 办公助手  │  │  趋势插件                 │   │
│  - ...       │  │  [卡片] [卡片] [卡片]    │   │
│              │  └──────────────────────────┘   │
│              │  ┌──────────────────────────┐   │
│              │  │  最新插件                 │   │
│              │  │  [卡片] [卡片] [卡片]    │   │
│              │  └──────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**功能：**
- 精选插件展示
- 趋势插件展示
- 分类导航
- 搜索栏
- 用户菜单

### 2. 插件详情页

**布局：**
```
┌─────────────────────────────────────────────────┐
│              导航栏                              │
├─────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐  │
│  │ [图标] 插件名称                           │  │
│  │ 作者: XXX  |  版本: 1.0.0  |  评分: ★★★★★ │  │
│  │ 描述: ...                                 │  │
│  │ [安装按钮] [分享按钮]                     │  │
│  └──────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│  标签页: 详情 | 评论 | 版本 | 截图             │
├─────────────────────────────────────────────────┤
│  详情内容                                       │
│  - 功能描述                                     │
│  - 权限列表                                     │
│  - 依赖列表                                     │
│  - 安全信息                                     │
│  - 统计信息                                     │
└─────────────────────────────────────────────────┘
```

**功能：**
- 插件基本信息
- 详细描述
- 功能列表
- 权限列表
- 依赖列表
- 安全信息
- 统计数据
- 评论列表
- 版本历史
- 截图展示

### 3. 搜索结果页

**布局：**
```
┌─────────────────────────────────────────────────┐
│  搜索栏: [搜索词] [搜索按钮]                     │
├─────────────────────────────────────────────────┤
│  过滤器:                                        │
│  分类: [下拉] | 排序: [下拉] | 评分: [滑块]    │
├─────────────────────────────────────────────────┤
│  结果: 找到 50 个插件                           │
│  ┌──────────────────────────────────────────┐  │
│  │ [卡片] [卡片] [卡片]                     │  │
│  │ [卡片] [卡片] [卡片]                     │  │
│  │ [卡片] [卡片] [卡片]                     │  │
│  └──────────────────────────────────────────┘  │
│  分页: < 1 2 3 4 5 >                           │
└─────────────────────────────────────────────────┘
```

**功能：**
- 搜索输入
- 过滤选项
- 排序选项
- 结果列表
- 分页控制

### 4. 开发者仪表板

**布局：**
```
┌─────────────────────────────────────────────────┐
│  开发者仪表板                                   │
├─────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐  │
│  │ 我的插件 (5)                             │  │
│  │ [插件卡片] [插件卡片] [插件卡片]         │  │
│  │ [创建新插件按钮]                         │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ 统计信息                                 │  │
│  │ 总下载: 10,000  |  总安装: 5,000         │  │
│  │ 平均评分: 4.5  |  评论数: 200            │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ 最近活动                                 │  │
│  │ - 插件 A 新增 100 次下载                 │  │
│  │ - 插件 B 获得新评论                      │  │
│  │ - 插件 C 发布新版本                      │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**功能：**
- 插件列表
- 创建插件
- 编辑插件
- 发布插件
- 统计信息
- 活动日志

## 交互流程

### 1. 安装插件流程

```
用户点击安装
    ↓
显示安装对话框
    ↓
选择版本 (可选)
    ↓
配置插件参数
    ↓
检查依赖
    ↓
确认安装
    ↓
执行安装
    ↓
显示进度条
    ↓
安装完成
    ↓
显示成功消息
```

### 2. 发布插件流程

```
开发者点击发布
    ↓
生成脚手架 (如果是新插件)
    ↓
编辑插件信息
    ↓
运行测试
    ↓
检查代码质量
    ↓
构建插件包
    ↓
上传包文件
    ↓
提交审核
    ↓
等待审核
    ↓
审核通过/拒绝
    ↓
发布到市场
```

### 3. 搜索流程

```
用户输入搜索词
    ↓
实时搜索建议
    ↓
用户选择或按回车
    ↓
执行搜索
    ↓
显示结果
    ↓
用户可以过滤/排序
    ↓
用户点击插件查看详情
```

## UI 组件

### PluginCard 组件

```tsx
interface PluginCardProps {
  plugin: PluginRecord;
  onInstall?: (pluginId: string) => void;
  onView?: (pluginId: string) => void;
}

// 显示内容:
// - 插件图标
// - 插件名称
// - 简短描述
// - 评分和评论数
// - 下载次数
// - 安装按钮
// - 更多信息按钮
```

### PluginDetail 组件

```tsx
interface PluginDetailProps {
  pluginId: string;
  onInstall?: (pluginId: string) => void;
}

// 显示内容:
// - 完整插件信息
// - 详细描述
// - 功能列表
// - 权限列表
// - 依赖列表
// - 安全信息
// - 统计数据
// - 评论列表
// - 版本历史
```

### PluginSearch 组件

```tsx
interface PluginSearchProps {
  onSearch?: (query: string) => void;
  onFilter?: (filters: SearchFilters) => void;
}

// 功能:
// - 搜索输入
// - 分类过滤
// - 排序选项
// - 评分过滤
// - 搜索建议
```

### PluginInstaller 组件

```tsx
interface PluginInstallerProps {
  pluginId: string;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

// 功能:
// - 版本选择
// - 配置输入
// - 依赖检查
// - 进度显示
// - 错误处理
```

### PluginReviews 组件

```tsx
interface PluginReviewsProps {
  pluginId: string;
  onReviewAdded?: () => void;
}

// 功能:
// - 评论列表
// - 评分分布
// - 添加评论表单
// - 有用/无用投票
// - 评论排序
```

## 状态管理

### Redux Store 结构

```typescript
{
  marketplace: {
    plugins: PluginRecord[],
    selectedPlugin: PluginRecord | null,
    searchResults: PluginRecord[],
    filters: SearchFilters,
    loading: boolean,
    error: string | null,
  },
  developer: {
    myPlugins: PluginRecord[],
    currentPlugin: PluginRecord | null,
    buildStatus: BuildStatus,
    publishStatus: PublishStatus,
  },
  admin: {
    pendingReviews: PluginRecord[],
    analytics: AnalyticsData,
  },
  user: {
    installedPlugins: string[],
    userReviews: PluginReview[],
  }
}
```

### 关键 Actions

```typescript
// 市场相关
fetchPlugins()
searchPlugins(query)
getPluginDetail(pluginId)
installPlugin(pluginId, config)
uninstallPlugin(installId)
addReview(pluginId, review)

// 开发者相关
createPlugin(manifest)
updatePlugin(pluginId, manifest)
buildPlugin(pluginId)
publishPlugin(pluginId)
getMyPlugins()

// 管理员相关
reviewPlugin(pluginId, status)
scanPlugin(pluginId)
moderateReview(reviewId, action)
```

## API 集成

### 服务层

```typescript
// pluginMarketplaceService.ts
class PluginMarketplaceService {
  async getPlugins(filters?: SearchFilters): Promise<PluginRecord[]>
  async searchPlugins(query: string): Promise<PluginRecord[]>
  async getPluginDetail(pluginId: string): Promise<PluginRecord>
  async installPlugin(pluginId: string, config?: any): Promise<InstallResponse>
  async uninstallPlugin(installId: string): Promise<void>
  async addReview(pluginId: string, review: ReviewData): Promise<PluginReview>
  async getReviews(pluginId: string): Promise<PluginReview[]>
}

// pluginDevService.ts
class PluginDevService {
  async generateScaffold(config: ScaffoldConfig): Promise<string>
  async runTests(pluginDir: string): Promise<TestResult>
  async checkQuality(pluginDir: string): Promise<QualityReport>
  async buildPlugin(pluginDir: string): Promise<BuildResult>
  async publishPlugin(pluginDir: string, category: string): Promise<PublishResult>
}
```

### Hook 使用示例

```typescript
// 使用市场 Hook
const { plugins, loading, error, search } = usePluginMarketplace();

// 使用搜索 Hook
const { results, searching } = usePluginSearch(query);

// 使用安装 Hook
const { installing, progress, install } = usePluginInstall();

// 使用开发者 Hook
const { building, publishing, build, publish } = usePluginDeveloper();
```

## 总结

X-Agent 插件市场前端提供了：

1. **用户友好的界面** - 易于浏览和搜索插件
2. **完整的安装流程** - 简化的安装和配置
3. **社区反馈系统** - 评分和评论
4. **开发者工具** - 完整的开发支持
5. **管理员面板** - 插件审核和管理
6. **响应式设计** - 支持各种设备

通过这些组件和流程，用户可以轻松发现、安装和管理插件，开发者可以轻松创建和发布插件。
