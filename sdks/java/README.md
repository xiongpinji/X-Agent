# X-Agent Partner SDK for Java

X-Agent Partner API 的官方 Java SDK(`PartnerClient.java` + `PartnerAPIException.java`, `package io.xagent.partner`)。

> **分发方式说明**: 本 SDK 当前以**源码形式分发**, **未发布到 Maven Central 或任何包仓库**。
> `pom.xml` 中的 `<dependency> io.xagent:partner-sdk </dependency>` 坐标目前**不可用**。

## 使用方式

将两个 `.java` 文件拷贝到你的项目源码树(保持 `io.xagent.partner` 包结构),
并确保 classpath 中包含以下依赖:

| 依赖 | 用途 |
|------|------|
| `com.fasterxml.jackson.core:jackson-databind` | JSON 序列化/反序列化(必需) |
| `com.fasterxml.jackson.datatype:jackson-datatype-jsr310` | `java.time.Instant` 支持(必需, 后端时间字段为 ISO-8601) |

要求 JDK 11+(使用 `java.net.http.HttpClient`)。

## 示例

```java
PartnerClient client = new PartnerClient(
    "xag_partner_xxx",
    "https://your-x-agent-instance.example.com", // 指向实际部署的后端
    Duration.ofSeconds(30),
    3
);
PartnerClient.PartnerResponse partner = client.getPartner("partner_id");
```

## 本地构建验证状态

⚠️ 本目录代码未在本机验证编译(开发机无 JDK/Maven)。
2026-07-20 针对后端 API 的兼容性修复(204 空响应体处理、列表端点裸数组反序列化、
Instant/jsr310 注册、FastAPI `detail` 错误消息提取、常量时间签名比较)为**静态审查修复**,
建议引入项目后先执行一次编译与冒烟测试。

## License

MIT
