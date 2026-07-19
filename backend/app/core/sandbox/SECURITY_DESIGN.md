# X-Agent 代码执行沙箱 - 安全设计文档

## 1. 概述

X-Agent 代码执行沙箱提供安全的 Python 和 Node.js 代码执行环境，具有以下特性：

- **多语言支持**：Python 3.11+ 和 Node.js 18+
- **资源隔离**：CPU、内存、执行时间限制
- **安全验证**：代码静态分析和危险操作拦截
- **性能优化**：容器/进程池复用，<1秒启动时间
- **审计追踪**：完整的执行日志和统计

## 2. 安全架构

### 2.1 多层防御

```
┌─────────────────────────────────────────────────────────┐
│ 第1层：代码验证（静态分析）                              │
│ - 危险模式检测                                          │
│ - 模块白名单检查                                        │
│ - 语法验证                                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 第2层：执行隔离（进程/容器）                             │
│ - 独立进程执行                                          │
│ - 文件系统隔离                                          │
│ - 网络隔离                                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 第3层：资源限制（OS级别）                               │
│ - 内存限制（512MB 默认）                                │
│ - CPU 限制（50% 默认）                                  │
│ - 执行时间限制（30s 默认）                              │
│ - 输出大小限制（10MB 默认）                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 第4层：审计和监控                                       │
│ - 执行日志记录                                          │
│ - 性能指标收集                                          │
│ - 异常检测                                              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 威胁模型

#### Python 威胁

| 威胁 | 风险等级 | 防御措施 |
|------|---------|---------|
| 系统命令执行 | CRITICAL | 禁止 `os`, `subprocess`, `sys` 模块 |
| 文件系统访问 | CRITICAL | 禁止 `open()`, `file()` 函数 |
| 网络访问 | HIGH | 禁止 `socket`, `urllib` 模块 |
| 代码注入 | CRITICAL | 禁止 `eval()`, `exec()`, `compile()` |
| 反射攻击 | CRITICAL | 禁止 `__dict__`, `__class__`, `getattr()` |
| 内存耗尽 | HIGH | 内存限制 512MB |
| 无限循环 | HIGH | 执行时间限制 30s |

#### JavaScript 威胁

| 威胁 | 风险等级 | 防御措施 |
|------|---------|---------|
| 子进程执行 | CRITICAL | 禁止 `child_process` 模块 |
| 文件系统访问 | CRITICAL | 禁止 `fs` 模块 |
| 网络访问 | HIGH | 禁止 `http`, `https`, `net` 模块 |
| 代码注入 | CRITICAL | 禁止 `eval()`, `Function()` |
| 进程访问 | CRITICAL | 禁止 `process` 对象 |
| 内存耗尽 | HIGH | 内存限制 512MB |
| 无限循环 | HIGH | 执行时间限制 30s |

## 3. Python 沙箱实现

### 3.1 模块白名单

**允许的标准库模块**：
- 数学计算：`math`, `statistics`, `decimal`, `fractions`, `cmath`
- 数据结构：`collections`, `array`, `struct`
- 字符串处理：`string`, `re`, `textwrap`, `difflib`
- 数据编码：`json`, `csv`, `base64`, `hashlib`, `codecs`
- 日期时间：`datetime`, `time`, `calendar`
- 工具函数：`itertools`, `functools`, `operator`, `copy`
- 类型系统：`typing`, `dataclasses`, `enum`, `abc`

**允许的第三方库**：
- 数据科学：`numpy`, `pandas`, `scipy`, `sklearn`
- 可视化：`matplotlib`, `seaborn`, `plotly`
- Web：`requests`, `beautifulsoup4`, `lxml`

### 3.2 危险操作拦截

**CRITICAL 级别（绝对禁止）**：
```python
# 代码注入
__import__()
eval()
exec()
compile()

# 反射和内省
globals()
locals()
vars()
dir()
getattr()
setattr()
delattr()
hasattr()

# 魔法方法访问
__dict__
__class__
__bases__
__subclasses__
__code__
__globals__
```

**HIGH 级别（需要审批）**：
```python
# 系统访问
import os
import sys
import subprocess
import socket
import threading

# 文件操作
open()
file()

# 用户输入
input()
raw_input()
```

### 3.3 执行流程

```python
# 1. 代码验证
validator = PythonSecurityValidator()
violations = validator.validate(code)
if critical_violations:
    raise SecurityError()

# 2. 脚本准备
script = wrap_code_with_output_capture(code, variables)
write_to_temp_file(script)

# 3. 进程执行
process = subprocess.Popen(
    ["python", script_path],
    timeout=30,
    memory_limit=512MB,
    stdout=PIPE,
    stderr=PIPE
)

# 4. 结果解析
output = json.loads(process.stdout)
return ExecutionResult(
    success=output['success'],
    stdout=output['stdout'],
    stderr=output['stderr'],
    return_value=output['result']
)

# 5. 清理
cleanup_temp_files()
```

## 4. Node.js 沙箱实现

### 4.1 模块白名单

**允许的核心模块**：
- 工具函数：`util`, `assert`, `events`
- 数据处理：`buffer`, `stream`, `zlib`
- 加密：`crypto`
- 编码：`url`, `querystring`

**允许的 npm 包**：
- 工具库：`lodash`, `underscore`, `uuid`, `validator`
- 日期处理：`moment`, `date-fns`
- 数据验证：`joi`, `yup`, `zod`
- 数据处理：`cheerio`, `jsdom`

### 4.2 危险操作拦截

**CRITICAL 级别**：
```javascript
// 子进程
require('child_process')
require('cluster')
require('worker_threads')

// 文件系统
require('fs')

// 网络
require('net')
require('dgram')
require('http')
require('https')

// 代码执行
eval()
Function()

// 进程访问
process.exit()
process.kill()
process.env
```

### 4.3 执行流程

```javascript
// 1. 代码验证
validator = new JavaScriptSecurityValidator()
violations = validator.validate(code)
if (critical_violations) throw new SecurityError()

// 2. 脚本准备
script = wrapCodeWithOutputCapture(code, variables)
writeToTempFile(script)

// 3. 进程执行
process = spawn('node', [
    '--max-old-space-size=512',
    script_path
], {
    timeout: 30000,
    stdio: ['pipe', 'pipe', 'pipe']
})

// 4. 结果解析
output = JSON.parse(process.stdout)
return NodeExecutionResult(
    success: output.success,
    stdout: output.stdout,
    stderr: output.stderr,
    return_value: output.result
)

// 5. 清理
cleanupTempFiles()
```

## 5. 资源限制

### 5.1 默认配置

| 资源 | 限制 | 说明 |
|------|------|------|
| 执行时间 | 30 秒 | 防止无限循环 |
| 内存 | 512 MB | 防止内存耗尽 |
| CPU | 50% | 防止 CPU 饱和 |
| 输出大小 | 10 MB | 防止输出爆炸 |
| 文件系统 | 禁用 | 默认不允许文件访问 |
| 网络 | 禁用 | 默认不允许网络访问 |

### 5.2 自定义配置

```python
config = SandboxConfig(
    timeout_seconds=60.0,
    memory_limit_mb=1024,
    cpu_limit_percent=100.0,
    max_output_bytes=50 * 1024 * 1024,
    enable_network=False,
    enable_file_system=False
)

sandbox = PythonSandbox(config)
result = await sandbox.execute(code)
```

## 6. 性能优化

### 6.1 容器池复用

```python
# 创建可复用的沙箱池
pool = PythonSandboxPool(pool_size=5)
await pool.initialize()

# 执行代码时自动从池中获取
result = await pool.execute(code)

# 自动归还到池中
```

**性能指标**：
- 首次启动：~800ms
- 池中复用：~50ms
- 吞吐量：20+ ops/sec

### 6.2 缓存策略

```python
# 相同代码和参数的结果被缓存
cache = ToolResultCache(max_size=1000, ttl_seconds=3600)

# 缓存命中时直接返回
cached_result = cache.get(cache_key)
```

## 7. 安全验证

### 7.1 代码验证 API

```python
# 验证 Python 代码
is_safe, violations = validate_python_code(code)

# 验证 JavaScript 代码
is_safe, violations = validate_javascript_code(code)

# 检查违规
for violation in violations:
    print(f"{violation.risk_level}: {violation.message}")
    print(f"  Line {violation.line_number}: {violation.pattern}")
    print(f"  Suggestion: {violation.suggestion}")
```

### 7.2 风险等级

| 等级 | 说明 | 处理 |
|------|------|------|
| LOW | 低风险模式 | 允许执行 |
| MEDIUM | 中等风险模式 | 记录日志 |
| HIGH | 高风险模式 | 需要审批 |
| CRITICAL | 严重安全威胁 | 拒绝执行 |

## 8. 审计和监控

### 8.1 执行日志

```python
manager = await get_sandbox_manager()

# 获取执行统计
stats = manager.get_execution_stats()
print(f"Total: {stats['total_executions']}")
print(f"Success: {stats['successful_executions']}")
print(f"Failed: {stats['failed_executions']}")
print(f"Avg time: {stats['average_execution_time_ms']}ms")

# 获取执行历史
history = manager.get_execution_history(limit=100)
for record in history:
    print(f"{record['timestamp']}: {record['language']} - {record['success']}")
```

### 8.2 性能指标

```python
# 运行基准测试
benchmark = SandboxBenchmark()
results = await benchmark.run_all_benchmarks(iterations=10)

# 打印结果
benchmark.print_results()
```

## 9. 集成指南

### 9.1 基本使用

```python
from backend.app.core.sandbox import execute_code, ExecutionLanguage

# 执行 Python 代码
result = await execute_code(
    code="result = 1 + 2\n_result = result",
    language=ExecutionLanguage.PYTHON
)

# 执行 JavaScript 代码
result = await execute_code(
    code="const result = 1 + 2;\n_result = result;",
    language=ExecutionLanguage.NODEJS
)
```

### 9.2 工具集成

```python
from backend.app.core.sandbox import CodeExecutionTool

tool = CodeExecutionTool()

# 执行 Python
result = await tool.execute_python(
    code="result = sum([1, 2, 3, 4, 5])\n_result = result",
    variables={"data": [1, 2, 3]}
)

# 验证代码
validation = await tool.validate_code(code, language="python")
```

### 9.3 MCP 工具注册

```python
# 在 MCP 适配器中注册
adapter.register_tool(
    "execute_python",
    tool.execute_python,
    {
        "code": {"type": "string", "description": "Python code to execute"},
        "variables": {"type": "object", "description": "Variables to inject"}
    }
)

adapter.register_tool(
    "execute_javascript",
    tool.execute_javascript,
    {
        "code": {"type": "string", "description": "JavaScript code to execute"},
        "variables": {"type": "object", "description": "Variables to inject"}
    }
)
```

## 10. 安全最佳实践

### 10.1 代码审查清单

- [ ] 检查是否有 CRITICAL 级别违规
- [ ] 检查是否有未授权的模块导入
- [ ] 检查是否有文件系统访问
- [ ] 检查是否有网络访问
- [ ] 检查是否有无限循环风险
- [ ] 检查是否有内存泄漏风险
- [ ] 检查输出大小是否合理

### 10.2 部署建议

1. **生产环境**：
   - 启用审计追踪
   - 启用代码验证
   - 设置严格的资源限制
   - 定期审查执行日志

2. **开发环境**：
   - 可以放宽某些限制
   - 启用详细日志
   - 运行性能基准测试

3. **监控告警**：
   - 执行失败率 > 5%
   - 平均执行时间 > 5s
   - 内存使用 > 400MB
   - 输出大小 > 5MB

## 11. 故障排查

### 11.1 常见问题

**Q: 代码执行超时**
- A: 检查代码是否有无限循环，增加 timeout_seconds 配置

**Q: 内存不足**
- A: 减少数据集大小，增加 memory_limit_mb 配置

**Q: 模块不在白名单**
- A: 检查模块是否安全，联系管理员添加到白名单

**Q: 代码被拒绝执行**
- A: 运行 validate_code() 检查违规，修改代码后重试

### 11.2 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 验证代码
is_safe, violations = validate_python_code(code)
for v in violations:
    print(f"Line {v.line_number}: {v.message}")

# 获取执行统计
stats = await tool.get_execution_stats()
print(stats)
```

## 12. 性能基准

### 12.1 启动时间

| 场景 | 时间 |
|------|------|
| 首次启动 | ~800ms |
| 池中复用 | ~50ms |
| 代码验证 | ~5ms |

### 12.2 吞吐量

| 操作 | 吞吐量 |
|------|--------|
| Python 简单运算 | 20 ops/sec |
| Python 复杂计算 | 5 ops/sec |
| JavaScript 简单运算 | 18 ops/sec |
| JavaScript 复杂计算 | 4 ops/sec |

### 12.3 资源使用

| 资源 | 使用量 |
|------|--------|
| 单个进程内存 | ~50MB |
| 池内存（5个） | ~250MB |
| 临时文件 | ~1MB/执行 |

## 13. 合规性

### 13.1 安全标准

- ✓ OWASP Top 10 防护
- ✓ CWE-94（代码注入）防护
- ✓ CWE-95（不当中立化）防护
- ✓ CWE-78（OS 命令注入）防护

### 13.2 审计要求

- 所有执行都被记录
- 执行历史保留 1000 条
- 违规代码被拒绝
- 性能指标被收集

## 14. 未来改进

- [ ] Docker 容器隔离（Linux）
- [ ] Seccomp 系统调用过滤
- [ ] 更多语言支持（Go, Rust, Java）
- [ ] 分布式执行
- [ ] 实时性能监控仪表板
- [ ] 自适应资源限制
