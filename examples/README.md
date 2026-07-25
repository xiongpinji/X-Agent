# X-Agent 示例代码

本目录包含 4 个**真实可运行**的示例脚本，均基于仓库当前实际 API（`backend.app.*`）编写，并已逐个验证。

> 说明：2026-07-20 文档收敛（P1-21）前，本 README 引用的 8 个示例文件（`01_basic_agent.py` 等）及其中的 `Agent` 类在仓库中并不存在，已全部移除。下列示例为仓内现存且验证过的真实示例。

## 前置条件

```bash
pip install -e ".[dev]"   # 在仓库根目录执行
```

各示例的可选依赖：

| 示例 | 额外依赖 |
|------|----------|
| `llm_provider_example.py` | 无 API key 时自动跳过在线示例；可设 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`，或本地运行 Ollama |
| `browser_automation_examples.py` | `playwright install chromium`（首次使用需下载浏览器） |
| `browser_monitoring_examples.py` | 同上 |
| `sandbox_pooling_demo.py` | 无（使用本地子进程沙箱） |

## 示例清单

### 1. LLM 多提供商 — `llm_provider_example.py`

演示统一 LLM 接口（`backend.app.core.llm_providers`）：单一提供商调用、流式输出、多提供商路由（OpenAI / Anthropic / Ollama）、错误处理、成本统计。

```bash
python examples/llm_provider_example.py
```

未设置 API key 时会打印警告并跳过在线示例；未拉取模型的 Ollama 调用会被捕获并打印错误（优雅降级），脚本不会崩溃。

### 2. 浏览器自动化 — `browser_automation_examples.py`

演示增强浏览器服务（`backend.app.services.browser`）的 9 个场景：基础导航与交互、多策略智能定位、自适应等待、高级交互、页面分析与数据提取、错误恢复、浏览器池、反检测隐身模式、完整工作流。

```bash
python examples/browser_automation_examples.py
```

### 3. 浏览器监控 — `browser_monitoring_examples.py`

演示浏览器监控能力（`backend.app.services.browser.advanced_monitoring`）：网络请求监控、元素引用、控制台监控、自然语言定位、页面快照、完整工作流。文件内大部分代码以注释形式给出，便于按需启用。

```bash
python examples/browser_monitoring_examples.py
```

### 4. 沙箱池化执行 — `sandbox_pooling_demo.py`

演示优化执行管理器（`backend.app.core.execution.OptimizedExecutionManager`）：基础代码执行、并发执行、性能对比、池统计监控、错误处理（含禁用操作拦截）。

```bash
python examples/sandbox_pooling_demo.py
```

## 更多示例与教程

- 文档中的示例说明: [docs/developer/sdk/EXAMPLES.md](../docs/developer/sdk/EXAMPLES.md)
- API 使用示例: [docs/developer/api/API_EXAMPLES.md](../docs/developer/api/API_EXAMPLES.md)
- 教程: [docs/developer/tutorials/](../docs/developer/tutorials/)
- MCP 插件示例: [docs/developer/plugins/MCP_PLUGIN_EXAMPLES.md](../docs/developer/plugins/MCP_PLUGIN_EXAMPLES.md)
