# Native Messaging Host 安装说明

扩展通过 Chrome Native Messaging 与本地 X-Agent 桌面端通信
（`mcp-client.js` 中 `chrome.runtime.connectNative('com.xagent.extension')`）。
浏览器不会读取扩展目录里的 json 文件——必须把一个**填好真实值**的
host manifest 注册到操作系统的约定位置。

## 1. 准备 host manifest

复制模板并按本机实际情况修改：

```bash
cp native-messaging-host.json.example native-messaging-host.json
```

模板字段说明：

| 字段 | 必须替换 | 说明 |
| --- | --- | --- |
| `name` | 否 | 固定为 `com.xagent.extension`，与 `mcp-client.js` 中的 `connectNative` 参数一致，不要改。 |
| `path` | **是** | 占位符 `/path/to/x-agent-native-host` 必须替换为 native host 可执行文件的**绝对路径**。Windows 上指向 `.bat` / `.exe`（如 `C:\\X-Agent\\native-host\\run.bat`，注意 JSON 中反斜杠需转义）；macOS / Linux 指向可执行脚本（如 `/usr/local/bin/x-agent-native-host`）。 |
| `type` | 否 | 固定 `stdio`。 |
| `allowed_origins` | **是** | 把 `chrome-extension://YOUR_EXTENSION_ID/` 替换为扩展真实 ID。加载未打包扩展后，在 `chrome://extensions` 页面可以看到 32 位字母的扩展 ID。 |

> 占位符文件（`path` 含 `/path/to/` 或 origin 含 `YOUR_EXTENSION_ID`）直接注册会导致
> 连接失败：`connectNative` 触发 `onDisconnect`，扩展端表现为 MCP 无法连接。

## 2. 注册到操作系统

### Windows

在注册表创建键：

```
HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.xagent.extension
```

把默认值 `(Default)` 设为 host manifest 的绝对路径，例如：

```bat
reg add "HKCU\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.xagent.extension" /ve /t REG_SZ /d "C:\X-Agent\native-messaging-host.json" /f
```

### macOS

```bash
mkdir -p ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts
cp native-messaging-host.json ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.xagent.extension.json
```

### Linux

```bash
mkdir -p ~/.config/google-chrome/NativeMessagingHosts
cp native-messaging-host.json ~/.config/google-chrome/NativeMessagingHosts/com.xagent.extension.json
```

注意：注册用的文件名必须是 `<name>.json`，即 `com.xagent.extension.json`。

## 3. 验证

1. 确认 native host 可执行文件真实存在且有执行权限（先单独运行一次确认能启动）。
2. 重启 Chrome，打开扩展 popup，观察是否连接成功。
3. 排错见 `TROUBLESHOOTING.md`（其中给出了各平台注册位置的查询命令）。

## 当前状态说明

- 本仓库**不附带** native host 可执行文件的实现；`path` 指向的程序由
  X-Agent 桌面端安装包提供。在桌面端落地前，扩展的 MCP 连接会按
  `mcp-client.js` 的重连/降级逻辑失败并记录日志，属预期行为。
