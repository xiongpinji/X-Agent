# X-Agent Partner SDK for Go

X-Agent Partner API 的官方 Go SDK(单文件实现: `xagent.go`, 仅依赖标准库)。

> **分发方式说明**: 本 SDK 当前以**源码形式分发**, **未发布到 Go 模块代理 (proxy.golang.org)**。
> `go get github.com/xagent/partner-sdk-go` 目前**不可用**(该路径仅为模块标识, 仓库尚未公开托管)。

## 使用方式

### 方式一: go.mod replace(推荐)

将本仓库克隆到本地后, 在你的项目中:

```go.mod
require github.com/xagent/partner-sdk-go v0.2.0-alpha

replace github.com/xagent/partner-sdk-go => /path/to/X-Agent/sdks/go
```

### 方式二: 直接拷贝源码

将 `xagent.go` 拷贝到你的项目中(注意修改 package 名以匹配你的项目结构)。

## 示例

```go
client := xagent.NewPartnerClient(xagent.PartnerClientConfig{
    APIKey:  "xag_partner_xxx",
    BaseURL: "https://your-x-agent-instance.example.com", // 指向实际部署的后端
})
partner, err := client.GetPartner("partner_id")
```

## 本地构建验证状态

⚠️ 本目录代码未在本机验证编译(开发机无 Go 工具链)。
源码为标准库单文件实现; 如在构建中遇到问题, 请以本目录实际代码为准并提交 issue。

## License

MIT
