# xagent-partner (JavaScript/TypeScript SDK)

X-Agent Partner API 的官方 JavaScript/TypeScript SDK。

> **分发方式说明**: 本 SDK 当前以**源码形式分发**, **未发布到 npm registry**。
> `npm install xagent-partner` 目前不可用, 请使用下方的本地构建方式。

## 本地构建

```bash
cd sdks/javascript
npm install      # 安装 devDependencies (typescript, @types/node)
npm run build    # tsc 编译到 dist/ (含 .d.ts 类型声明)
```

## 在项目中使用

构建后通过 file: 依赖引用:

```bash
npm install ./sdks/javascript        # 从仓库根目录
```

或打包后安装 tarball:

```bash
npm pack ./sdks/javascript           # 产出 xagent-partner-0.2.0-alpha.tgz
npm install ./xagent-partner-0.2.0-alpha.tgz
```

```typescript
import { PartnerClient } from 'xagent-partner';

const client = new PartnerClient({
  apiKey: 'xag_partner_xxx',
  baseUrl: 'https://your-x-agent-instance.example.com', // 指向实际部署的后端
});
const partner = await client.getPartner('partner_id');
```

## 要求

- Node.js >= 18(依赖全局 `fetch`)
- TypeScript 源码 `xagent-partner.ts` 也随包分发, 可直接以源码形式引入

## License

MIT
