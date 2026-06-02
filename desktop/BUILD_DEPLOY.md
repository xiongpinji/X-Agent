# X-Agent Desktop 构建和部署指南

## 系统要求

### Windows
- Windows 7 或更高版本
- .NET Framework 4.5+
- Visual C++ Redistributable

### macOS
- macOS 10.13 或更高版本
- Xcode Command Line Tools

### Linux
- Ubuntu 18.04 或更高版本
- GTK 3.0+
- libssl-dev

## 开发环境设置

### 1. 安装Rust

```bash
# Windows/macOS/Linux
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 验证安装
rustc --version
cargo --version
```

### 2. 安装Node.js

```bash
# 使用nvm (推荐)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# 或直接下载
# https://nodejs.org/
```

### 3. 安装Tauri CLI

```bash
cargo install tauri-cli
```

### 4. 安装平台特定工具

#### Windows
```bash
# 安装Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/
```

#### macOS
```bash
xcode-select --install
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get install libssl-dev libgtk-3-dev libayatana-appindicator3-dev

# Fedora
sudo dnf install openssl-devel gtk3-devel libappindicator-gtk3-devel
```

## 构建流程

### 开发构建

```bash
# 进入项目目录
cd desktop

# 安装前端依赖
cd frontend
npm install
cd ..

# 开发模式运行
cargo tauri dev
```

### 生产构建

```bash
# 构建应用
cargo tauri build

# 或指定目标平台
cargo tauri build --target x86_64-pc-windows-msvc
cargo tauri build --target x86_64-apple-darwin
cargo tauri build --target x86_64-unknown-linux-gnu
```

### 构建输出

构建完成后，安装包位置：

```
target/release/bundle/
├── msi/                    # Windows MSI安装程序
├── nsis/                   # Windows NSIS安装程序
├── dmg/                    # macOS DMG安装程序
├── app/                    # macOS APP包
├── deb/                    # Linux DEB包
└── rpm/                    # Linux RPM包
```

## 代码签名

### Windows代码签名

```bash
# 使用signtool (Visual Studio提供)
signtool sign /f certificate.pfx /p password /t http://timestamp.server.com /d "X-Agent Desktop" app.exe
```

### macOS代码签名

```bash
# 配置Tauri
# tauri.conf.json
{
  "tauri": {
    "bundle": {
      "macOS": {
        "signingIdentity": "Developer ID Application: Your Name (XXXXXXXXXX)"
      }
    }
  }
}

# 构建时自动签名
cargo tauri build
```

### Linux签名

```bash
# 使用GPG签名
gpg --detach-sign --armor app.deb
```

## 自动更新配置

### 1. 配置更新服务器

编辑 `tauri.conf.json`:

```json
{
  "tauri": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://updates.example.com/releases/{{target}}/{{current_version}}"
      ],
      "dialog": true,
      "pubkey": "YOUR_PUBLIC_KEY"
    }
  }
}
```

### 2. 生成签名密钥

```bash
# 生成密钥对
cargo tauri signer generate -w ~/.tauri/key.txt

# 获取公钥
cat ~/.tauri/key.txt | grep "public key"
```

### 3. 签名发布

```bash
# 签名应用
cargo tauri signer sign path/to/app.tar.gz ~/.tauri/key.txt
```

## 持续集成/持续部署 (CI/CD)

### GitHub Actions配置

创建 `.github/workflows/build.yml`:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Setup Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies (Linux)
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y libssl-dev libgtk-3-dev libayatana-appindicator3-dev

      - name: Build
        run: |
          cd desktop
          cargo tauri build

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: ${{ matrix.os }}-build
          path: desktop/target/release/bundle/
```

## 发布流程

### 1. 准备发布

```bash
# 更新版本号
# 编辑 Cargo.toml 和 tauri.conf.json

# 更新CHANGELOG
# 编辑 CHANGELOG.md

# 提交更改
git add .
git commit -m "chore: bump version to 0.2.0"
```

### 2. 创建标签

```bash
# 创建版本标签
git tag -a v0.2.0 -m "Release version 0.2.0"

# 推送标签
git push origin v0.2.0
```

### 3. 构建发布

```bash
# 构建所有平台
cargo tauri build

# 签名应用
cargo tauri signer sign path/to/app.tar.gz ~/.tauri/key.txt
```

### 4. 上传到发布服务器

```bash
# 上传到GitHub Releases
gh release create v0.2.0 \
  target/release/bundle/msi/*.msi \
  target/release/bundle/dmg/*.dmg \
  target/release/bundle/deb/*.deb

# 或上传到自定义服务器
scp target/release/bundle/*/* user@server:/releases/
```

## 性能优化

### 构建优化

```toml
[profile.release]
opt-level = "z"        # 优化大小
lto = true             # 启用Link Time Optimization
codegen-units = 1      # 单个编译单元
strip = true           # 移除调试符号
panic = "abort"        # 使用abort而不是unwind
```

### 前端优化

```bash
# 启用gzip压缩
npm run build -- --minify terser

# 分析包大小
npm run build -- --analyze
```

### 运行时优化

- 启用离线模式缓存
- 实现增量更新
- 使用CDN加载资源

## 故障排除

### 构建失败

```bash
# 清理构建缓存
cargo clean

# 更新依赖
cargo update

# 重新构建
cargo tauri build
```

### 签名问题

```bash
# 验证签名
signtool verify /pa app.exe

# 重新签名
signtool sign /f certificate.pfx /p password app.exe
```

### 更新问题

```bash
# 检查更新配置
cat tauri.conf.json | grep -A 5 updater

# 验证签名密钥
cat ~/.tauri/key.txt
```

## 监控和日志

### 应用日志

日志文件位置：
- Windows: `%APPDATA%\X-Agent\logs\`
- macOS: `~/Library/Application Support/X-Agent/logs/`
- Linux: `~/.config/X-Agent/logs/`

### 启用调试日志

```bash
# 设置日志级别
RUST_LOG=debug cargo tauri dev

# 或在配置文件中设置
# config.json
{
  "log_level": "debug"
}
```

### 性能监控

```bash
# 使用Tauri的性能分析
cargo tauri dev --profile profiling
```

## 安全检查清单

- [ ] 代码已审查
- [ ] 依赖已更新
- [ ] 安全漏洞已修复
- [ ] 应用已签名
- [ ] 更新服务器已配置
- [ ] 备份已创建
- [ ] 文档已更新

## 发布后检查

- [ ] 应用可正常启动
- [ ] 所有功能正常工作
- [ ] 性能符合预期
- [ ] 没有崩溃或错误
- [ ] 更新机制正常工作
- [ ] 用户反馈已收集

## 回滚流程

如果发现严重问题：

```bash
# 撤销标签
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0

# 恢复到上一个版本
git revert HEAD

# 重新发布
git tag -a v0.2.1 -m "Hotfix release"
git push origin v0.2.1
```

## 许可证

MIT License
