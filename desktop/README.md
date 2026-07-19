# X-Agent Desktop 桌面应用

跨平台桌面应用，基于Tauri框架和Vue 3开发，提供本地Agent运行环境、文件系统访问、系统托盘和全局快捷键支持。

## 功能特性

### 核心功能
- **本地Agent运行环境** - 在本地运行和管理Agent
- **文件系统浏览** - 完整的文件管理界面
- **系统托盘集成** - 后台运行和快速访问
- **全局快捷键** - Ctrl+Shift+X快速唤醒应用
- **离线工作模式** - 支持离线使用
- **自动更新机制** - 自动检查和安装更新

### UI/UX特性
- **原生窗口体验** - 使用Tauri提供的原生窗口
- **快速启动** - <2秒启动时间
- **低资源占用** - <200MB内存占用
- **暗色/亮色主题** - 支持自动、浅色、深色三种主题
- **100%中文界面** - 完整的中文本地化

### 安全特性
- **本地数据加密** - 使用AES-256加密敏感数据
- **安全的IPC通信** - 后端通信使用HTTPS
- **权限管理** - 细粒度的文件访问权限控制
- **沙箱隔离** - 前端和后端隔离运行

## 项目结构

```
desktop/
├── src/                    # Rust源代码
│   ├── main.rs            # 主程序入口
│   ├── config.rs          # 配置管理
│   ├── state.rs           # 应用状态
│   ├── db.rs              # 数据库管理
│   ├── security.rs        # 安全模块
│   ├── ipc.rs             # IPC通信
│   ├── tray.rs            # 系统托盘
│   ├── utils.rs           # 工具函数
│   └── commands/           # Tauri命令
│       ├── mod.rs
│       ├── file.rs        # 文件操作
│       ├── agent.rs       # Agent管理
│       ├── api.rs         # API调用
│       ├── settings.rs    # 设置管理
│       └── window.rs      # 窗口控制
├── frontend/              # Vue 3前端
│   ├── src/
│   │   ├── main.ts        # 入口文件
│   │   ├── App.vue        # 主组件
│   │   ├── router/        # 路由配置
│   │   ├── views/         # 页面组件
│   │   │   ├── Home.vue
│   │   │   ├── Agents.vue
│   │   │   ├── Files.vue
│   │   │   ├── Runs.vue
│   │   │   └── Settings.vue
│   │   └── styles/        # 样式文件
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── index.html
├── Cargo.toml             # Rust依赖配置
├── tauri.conf.json        # Tauri配置
└── build.rs               # 构建脚本
```

## 开发环境设置

### 前置要求
- Rust 1.70+
- Node.js 16+
- npm 或 yarn

### 安装依赖

```bash
# 安装Rust工具链
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 安装Tauri CLI
cargo install tauri-cli

# 安装前端依赖
cd desktop/frontend
npm install
```

### 开发模式

```bash
# 在项目根目录运行
cargo tauri dev

# 或使用Tauri CLI
tauri dev
```

### 生产构建

```bash
# 构建应用
cargo tauri build

# 或使用Tauri CLI
tauri build
```

## 构建输出

构建完成后，安装包位置：

- **Windows**: `src-tauri/target/release/bundle/msi/`
- **macOS**: `src-tauri/target/release/bundle/dmg/`
- **Linux**: `src-tauri/target/release/bundle/deb/` 或 `rpm/`

## 配置文件

应用配置文件位置：`~/.xagent/config.json`

```json
{
  "backend_url": "http://localhost",
  "backend_port": 8000,
  "data_dir": "data",
  "log_level": "info",
  "theme": "auto",
  "language": "zh-CN",
  "auto_update": true,
  "offline_mode": false
}
```

## API命令

### 文件操作
- `read_file(path)` - 读取文件
- `write_file(path, content)` - 写入文件
- `list_directory(path)` - 列出目录
- `create_directory(path)` - 创建目录
- `delete_file(path)` - 删除文件
- `delete_directory(path)` - 删除目录
- `get_file_info(path)` - 获取文件信息

### Agent管理
- `start_agent(agent_id)` - 启动Agent
- `stop_agent(agent_id)` - 停止Agent
- `get_agent_status(agent_id)` - 获取Agent状态
- `list_agents()` - 列出所有Agent

### API调用
- `call_backend_api(method, path, body)` - 调用后端API
- `get_backend_status()` - 获取后端状态

### 设置管理
- `get_settings()` - 获取设置
- `update_settings(settings)` - 更新设置
- `get_theme()` - 获取主题
- `set_theme(theme)` - 设置主题

### 窗口控制
- `minimize_window()` - 最小化窗口
- `maximize_window()` - 最大化窗口
- `close_window()` - 关闭窗口
- `toggle_devtools()` - 切换开发者工具

## 全局快捷键

- **Ctrl+Shift+X** - 显示/隐藏应用窗口

## 系统托盘菜单

- 显示 - 显示应用窗口
- 隐藏 - 隐藏应用窗口
- 设置 - 打开设置页面
- 退出 - 退出应用

## 性能优化

### 启动速度
- 使用Tauri的轻量级框架
- 前端使用Vite进行快速构建
- 后端使用Rust编译优化

### 内存占用
- 启用LTO（Link Time Optimization）
- 使用strip移除调试符号
- 优化依赖包大小

### 构建大小
- 前端使用tree-shaking
- 后端使用release优化
- 总包大小约50-100MB

## 安全考虑

### 文件访问
- 所有文件操作都经过路径验证
- 防止目录遍历攻击
- 支持文件加密存储

### 通信安全
- 后端通信使用HTTPS
- IPC通信使用加密
- 敏感数据不存储在本地

### 权限管理
- 细粒度的权限控制
- 用户确认敏感操作
- 审计日志记录

## 测试

```bash
# 运行单元测试
cargo test

# 运行前端测试
cd frontend
npm run test

# 运行集成测试
cargo test --test '*'
```

## 故障排除

### 应用无法启动
1. 检查后端服务是否运行
2. 检查配置文件是否正确
3. 查看日志文件：`~/.xagent/logs/`

### 文件操作失败
1. 检查文件权限
2. 检查路径是否正确
3. 确保有足够的磁盘空间

### 性能问题
1. 检查系统资源使用
2. 减少后台运行的Agent数量
3. 清理临时文件

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

- 官方网站: https://x-agent.com
- 问题反馈: https://github.com/x-agent/desktop/issues
