# X-Agent Desktop 开发者文档

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    X-Agent Desktop                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Vue 3 Frontend (TypeScript)            │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │  Home | Agents | Files | Runs | Settings  │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                         ↕ IPC                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │        Tauri Runtime (Rust Backend)             │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │  Commands | State | DB | Security | IPC   │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                         ↕ HTTP                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │      X-Agent Backend (Python FastAPI)           │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 模块设计

#### 前端模块 (Vue 3)
- **Router** - 页面路由管理
- **Views** - 页面组件
- **Components** - 可复用组件
- **Stores** - Pinia状态管理
- **Services** - API调用服务
- **Utils** - 工具函数

#### 后端模块 (Rust)
- **Commands** - Tauri命令处理
- **State** - 应用状态管理
- **Config** - 配置管理
- **DB** - SQLite数据库
- **Security** - 安全模块
- **IPC** - 进程间通信
- **Tray** - 系统托盘

## 开发指南

### 添加新命令

1. 在 `src/commands/` 中创建新模块或编辑现有模块
2. 定义命令函数，使用 `#[tauri::command]` 宏
3. 在 `src/main.rs` 中注册命令

```rust
#[tauri::command]
pub async fn my_command(
    param: String,
    state: State<'_, std::sync::Arc<crate::state::AppState>>,
) -> Result<String, String> {
    // 实现逻辑
    Ok("result".to_string())
}
```

### 添加新页面

1. 在 `frontend/src/views/` 中创建新的 `.vue` 文件
2. 在 `frontend/src/router/index.ts` 中添加路由
3. 在 `App.vue` 中添加菜单项

```typescript
// router/index.ts
{
  path: '/new-page',
  name: 'NewPage',
  component: () => import('../views/NewPage.vue')
}
```

### 调用后端API

```typescript
import { invoke } from '@tauri-apps/api/tauri'

// 调用Tauri命令
const result = await invoke('my_command', { param: 'value' })

// 调用后端API
const response = await invoke('call_backend_api', {
  method: 'GET',
  path: '/api/agents',
  body: null
})
```

### 状态管理

使用Pinia进行前端状态管理：

```typescript
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    backendConnected: false,
    agentRunning: false
  }),
  getters: {
    isReady: (state) => state.backendConnected
  },
  actions: {
    setBackendConnected(connected: boolean) {
      this.backendConnected = connected
    }
  }
})
```

## 数据库设计

### 表结构

#### agents 表
```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### runs 表
```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  status TEXT NOT NULL,
  input TEXT,
  output TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (agent_id) REFERENCES agents(id)
)
```

#### settings 表
```sql
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## 安全最佳实践

### 文件操作安全
```rust
// 验证路径，防止目录遍历
crate::security::validate_file_path(&base_dir, &file_path)?;

// 检查文件名安全性
if !crate::security::is_safe_filename(filename) {
    return Err("Invalid filename".into());
}
```

### 数据加密
```rust
use crate::security::Encryption;

let encryption = Encryption::from_password("password");
let encrypted = encryption.encrypt(plaintext)?;
let decrypted = encryption.decrypt(&encrypted)?;
```

### IPC通信安全
- 所有通信都经过验证
- 敏感数据使用加密
- 实现请求签名验证

## 性能优化

### 前端优化
- 使用代码分割和懒加载
- 启用gzip压缩
- 使用CDN加载第三方库
- 优化图片和资源

### 后端优化
- 使用异步编程
- 启用LTO编译优化
- 使用连接池
- 实现缓存机制

### 构建优化
```toml
[profile.release]
opt-level = "z"      # 优化大小
lto = true           # 启用LTO
codegen-units = 1    # 单个编译单元
strip = true         # 移除调试符号
```

## 测试策略

### 单元测试
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encryption() {
        let encryption = Encryption::from_password("test");
        let plaintext = b"Hello";
        let ciphertext = encryption.encrypt(plaintext).unwrap();
        let decrypted = encryption.decrypt(&ciphertext).unwrap();
        assert_eq!(plaintext, &decrypted[..]);
    }
}
```

### 集成测试
- 测试前后端通信
- 测试数据库操作
- 测试文件系统操作

### E2E测试
- 使用Tauri测试框架
- 测试完整的用户流程
- 测试跨平台兼容性

## 调试技巧

### 启用开发者工具
```rust
// 在开发模式下启用DevTools
#[cfg(debug_assertions)]
window.open_devtools();
```

### 日志记录
```rust
log::debug!("Debug message");
log::info!("Info message");
log::warn!("Warning message");
log::error!("Error message");
```

### 前端调试
```typescript
// 使用浏览器DevTools
console.log('Debug info')
console.error('Error info')
```

## 部署指南

### 打包应用
```bash
# 构建所有平台
cargo tauri build

# 构建特定平台
cargo tauri build --target x86_64-pc-windows-msvc
cargo tauri build --target x86_64-apple-darwin
cargo tauri build --target x86_64-unknown-linux-gnu
```

### 签名和公证
- Windows: 使用代码签名证书
- macOS: 使用Apple开发者证书
- Linux: 使用GPG密钥

### 自动更新
配置 `tauri.conf.json` 中的更新设置：
```json
{
  "updater": {
    "active": true,
    "endpoints": ["https://updates.example.com/"],
    "dialog": true,
    "pubkey": "..."
  }
}
```

## 常见问题

### Q: 如何添加新的依赖？
A: 在 `Cargo.toml` 中添加依赖，然后运行 `cargo build`

### Q: 如何调试IPC通信？
A: 启用日志记录，查看 `~/.xagent/logs/` 中的日志文件

### Q: 如何优化应用大小？
A: 启用LTO、strip调试符号、移除不必要的依赖

### Q: 如何支持新的平台？
A: 在 `tauri.conf.json` 中配置目标平台，然后构建

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 许可证

MIT License
