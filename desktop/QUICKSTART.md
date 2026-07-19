# X-Agent Desktop 快速开始指南

## 5分钟快速开始

### 1. 克隆项目

```bash
git clone https://github.com/x-agent/desktop.git
cd desktop
```

### 2. 安装依赖

```bash
# 安装Rust (如果未安装)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 安装Node.js (如果未安装)
# https://nodejs.org/

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 3. 启动开发服务器

```bash
# 在项目根目录运行
cargo tauri dev
```

应用将在几秒内启动，你会看到一个窗口打开。

### 4. 开始开发

- 修改 `frontend/src/` 中的Vue文件
- 修改 `src/` 中的Rust文件
- 保存文件后自动重新加载

## 常见任务

### 添加新页面

1. 在 `frontend/src/views/` 创建新的 `.vue` 文件
2. 在 `frontend/src/router/index.ts` 添加路由
3. 在 `App.vue` 的菜单中添加链接

### 调用后端API

```typescript
import { invoke } from '@tauri-apps/api/tauri'

// 调用Tauri命令
const result = await invoke('list_agents')

// 调用后端API
const response = await invoke('call_backend_api', {
  method: 'GET',
  path: '/api/agents'
})
```

### 添加新命令

1. 在 `src/commands/` 中创建或编辑模块
2. 定义命令函数：

```rust
#[tauri::command]
pub async fn my_command(param: String) -> Result<String, String> {
    Ok(format!("Hello, {}", param))
}
```

3. 在 `src/main.rs` 中注册命令

### 构建应用

```bash
# 生产构建
cargo tauri build

# 输出位置
# Windows: target/release/bundle/msi/
# macOS: target/release/bundle/dmg/
# Linux: target/release/bundle/deb/
```

## 项目结构速览

```
desktop/
├── src/                    # Rust后端
│   ├── main.rs            # 入口
│   ├── commands/          # Tauri命令
│   ├── config.rs          # 配置
│   └── ...
├── frontend/              # Vue 3前端
│   ├── src/
│   │   ├── views/         # 页面
│   │   ├── router/        # 路由
│   │   └── App.vue        # 主组件
│   └── package.json
├── Cargo.toml             # Rust配置
├── tauri.conf.json        # Tauri配置
└── README.md              # 文档
```

## 调试技巧

### 启用开发者工具

按 `F12` 打开开发者工具

### 查看日志

```bash
# 启用调试日志
RUST_LOG=debug cargo tauri dev

# 查看应用日志
# Windows: %APPDATA%\X-Agent\logs\
# macOS: ~/Library/Application Support/X-Agent/logs/
# Linux: ~/.config/X-Agent/logs/
```

### 热重载

- 修改Vue文件后自动重新加载
- 修改Rust文件后需要重新编译

## 常见问题

### Q: 应用无法启动
A: 检查后端服务是否运行，查看日志文件

### Q: 修改代码后没有反应
A: 
- Vue文件：应该自动重新加载
- Rust文件：需要重新启动 `cargo tauri dev`

### Q: 如何连接到后端？
A: 编辑 `~/.xagent/config.json` 修改后端地址

### Q: 如何清理构建缓存？
A: 运行 `cargo clean`

## 下一步

- 阅读 [README.md](README.md) 了解完整功能
- 查看 [DEVELOPER.md](DEVELOPER.md) 学习开发指南
- 查看 [BUILD_DEPLOY.md](BUILD_DEPLOY.md) 了解构建和部署
- 查看 [TESTING.md](TESTING.md) 了解测试

## 获取帮助

- 查看文档：[docs/](docs/)
- 提交Issue：[GitHub Issues](https://github.com/x-agent/desktop/issues)
- 讨论：[GitHub Discussions](https://github.com/x-agent/desktop/discussions)

## 许可证

MIT License
