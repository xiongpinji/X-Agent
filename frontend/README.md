# X-Agent Web UI

现代化的Web界面，为X-Agent提供直观的用户交互体验。

## 快速开始

### 前置要求
- Node.js 16+
- npm 或 yarn

### 安装

```bash
cd frontend
npm install
```

### 开发

```bash
npm run dev
```

访问 `http://localhost:3000`

### 构建

```bash
npm run build
```

### 预览

```bash
npm run preview
```

## 功能

- 📊 **Dashboard** - 系统状态概览和快速操作
- 💬 **Chat** - 实时对话界面，支持多个代理
- ✓ **Tasks** - 任务管理和进度跟踪
- 🔧 **Tools** - 工具配置和测试
- 🧠 **Memory** - 记忆管理和搜索
- 🌓 **主题** - 亮色/暗色主题切换
- 📱 **响应式** - 完全支持移动设备
- ⚡ **实时** - WebSocket实时通信

## 技术栈

- React 18 + TypeScript
- Vite
- TailwindCSS
- Zustand
- React Query
- Axios
- WebSocket

## 项目结构

```
src/
├── components/      # 可复用组件
├── pages/          # 页面组件
├── services/       # API和WebSocket服务
├── store/          # 状态管理
├── types/          # 类型定义
├── utils/          # 工具函数
├── App.tsx         # 主应用
├── main.tsx        # 入口
└── index.css       # 全局样式
```

## 配置

### API URL

编辑 `src/services/api.ts`:

```typescript
const apiClient = new ApiClient('http://your-api-url/api/v1')
```

### WebSocket URL

编辑 `src/services/websocket.ts`:

```typescript
const wsService = new WebSocketService('ws://your-api-url/ws')
```

## 脚本

- `npm run dev` - 启动开发服务器
- `npm run build` - 生产构建
- `npm run preview` - 预览构建结果
- `npm run lint` - 代码检查
- `npm run type-check` - TypeScript类型检查
- `npm run format` - 代码格式化

## 部署

### Docker

```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
```

### Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /var/www/x-agent-ui;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 浏览器支持

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## 许可证

MIT

## 文档

详见 [WEB_UI.md](../docs/WEB_UI.md)
