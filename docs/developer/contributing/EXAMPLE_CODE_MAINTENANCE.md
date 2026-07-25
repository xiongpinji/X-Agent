# 示例代码维护流程

**版本**: 1.0  
**更新时间**: 2026-05-27  
**文档状态**: Published

---

## 目标

确保所有示例代码与最新API保持同步，提高代码示例的质量和可维护性，建立自动化的示例代码检查和更新流程。

---

## 流程概述

```
API变更
   ↓
检测变更
   ↓
识别受影响的示例
   ↓
更新示例代码
   ↓
验证示例
   ↓
更新文档
   ↓
发布更新
```

---

## 1. 代码审查

### 1.1 每次API变更后的审查

当API发生变更时，需要审查所有相关的示例代码。

**审查清单**：
- [ ] 检查API端点是否变更
- [ ] 检查请求参数是否变更
- [ ] 检查响应格式是否变更
- [ ] 检查错误码是否变更
- [ ] 检查认证方式是否变更
- [ ] 检查速率限制是否变更

**审查流程**：
```bash
# 1. 获取API变更日志
git log --oneline docs/API_REFERENCE.md | head -20

# 2. 比较变更
git diff HEAD~1 docs/API_REFERENCE.md

# 3. 识别受影响的示例
grep -r "endpoint_name" docs/EXAMPLES.md
grep -r "endpoint_name" docs/tutorials/

# 4. 标记需要更新的示例
# 在示例代码中添加注释：# TODO: Update for API v2.0
```

### 1.2 自动化工具检测

使用自动化工具检测过时代码。

**检测脚本** (`scripts/check_examples.py`):
```python
#!/usr/bin/env python3
"""检查示例代码是否与API同步"""

import re
import json
from pathlib import Path
from typing import List, Dict

class ExampleChecker:
    def __init__(self, api_spec_path: str, examples_dir: str):
        self.api_spec = self.load_api_spec(api_spec_path)
        self.examples_dir = Path(examples_dir)
    
    def load_api_spec(self, path: str) -> Dict:
        """加载API规范"""
        with open(path) as f:
            return json.load(f)
    
    def check_all_examples(self) -> List[Dict]:
        """检查所有示例"""
        issues = []
        
        for example_file in self.examples_dir.glob("**/*.md"):
            issues.extend(self.check_example_file(example_file))
        
        return issues
    
    def check_example_file(self, file_path: Path) -> List[Dict]:
        """检查单个示例文件"""
        issues = []
        content = file_path.read_text()
        
        # 提取代码块
        code_blocks = re.findall(r'```(?:python|bash|json)\n(.*?)\n```', content, re.DOTALL)
        
        for i, code_block in enumerate(code_blocks):
            # 检查API端点
            endpoints = re.findall(r'/api/v\d+/(\w+)', code_block)
            for endpoint in endpoints:
                if not self.endpoint_exists(endpoint):
                    issues.append({
                        'file': str(file_path),
                        'block': i,
                        'issue': f'Endpoint {endpoint} not found in API spec',
                        'severity': 'error'
                    })
            
            # 检查参数
            params = re.findall(r'"(\w+)":\s*', code_block)
            for param in params:
                if not self.param_valid(endpoint, param):
                    issues.append({
                        'file': str(file_path),
                        'block': i,
                        'issue': f'Parameter {param} not valid for {endpoint}',
                        'severity': 'warning'
                    })
        
        return issues
    
    def endpoint_exists(self, endpoint: str) -> bool:
        """检查端点是否存在"""
        for path in self.api_spec.get('paths', {}).keys():
            if endpoint in path:
                return True
        return False
    
    def param_valid(self, endpoint: str, param: str) -> bool:
        """检查参数是否有效"""
        # 实现参数验证逻辑
        return True

if __name__ == '__main__':
    checker = ExampleChecker(
        'docs/openapi.json',
        'docs/EXAMPLES.md'
    )
    
    issues = checker.check_all_examples()
    
    for issue in issues:
        print(f"[{issue['severity'].upper()}] {issue['file']}: {issue['issue']}")
    
    if any(i['severity'] == 'error' for i in issues):
        exit(1)
```

---

## 2. 更新清单

### 2.1 文档中的示例

**位置**：
- `docs/EXAMPLES.md` - 代码示例集合
- `docs/API_REFERENCE.md` - API参考中的示例
- `docs/API_INTEGRATION_GUIDE.md` - 集成指南中的示例
- `docs/tutorials/` - 教程中的示例

**更新检查**：
- [ ] 快速开始示例
- [ ] API参考示例
- [ ] 教程代码
- [ ] 集成示例
- [ ] 错误处理示例
- [ ] 认证示例

### 2.2 代码仓库中的示例

**位置**：
- `examples/` - 独立示例脚本
- `tests/` - 测试用例（也是示例）
- `backend/app/api/` - API实现中的文档字符串示例

**更新检查**：
- [ ] 独立示例脚本
- [ ] 集成测试
- [ ] 单元测试
- [ ] API文档字符串

### 2.3 更新优先级

| 优先级 | 类型 | 更新周期 |
|--------|------|---------|
| P0 | 快速开始示例 | 立即 |
| P0 | API参考示例 | 立即 |
| P1 | 教程代码 | 1周内 |
| P1 | 集成示例 | 1周内 |
| P2 | 高级示例 | 2周内 |
| P2 | 测试用例 | 2周内 |

---

## 3. 验证流程

### 3.1 运行所有示例代码

**验证脚本** (`scripts/run_examples.py`):
```python
#!/usr/bin/env python3
"""运行所有示例代码"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

class ExampleRunner:
    def __init__(self, examples_dir: str):
        self.examples_dir = Path(examples_dir)
        self.results = []
    
    def run_all_examples(self) -> bool:
        """运行所有示例"""
        success = True
        
        for example_file in self.examples_dir.glob("**/*.py"):
            if not self.run_example(example_file):
                success = False
        
        return success
    
    def run_example(self, file_path: Path) -> bool:
        """运行单个示例"""
        print(f"Running {file_path}...")
        
        try:
            result = subprocess.run(
                [sys.executable, str(file_path)],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✓ {file_path} passed")
                self.results.append((str(file_path), 'passed', None))
                return True
            else:
                print(f"✗ {file_path} failed")
                print(f"  Error: {result.stderr}")
                self.results.append((str(file_path), 'failed', result.stderr))
                return False
        
        except subprocess.TimeoutExpired:
            print(f"✗ {file_path} timed out")
            self.results.append((str(file_path), 'timeout', None))
            return False
        
        except Exception as e:
            print(f"✗ {file_path} error: {e}")
            self.results.append((str(file_path), 'error', str(e)))
            return False
    
    def generate_report(self) -> str:
        """生成报告"""
        report = "# Example Execution Report\n\n"
        
        passed = sum(1 for _, status, _ in self.results if status == 'passed')
        failed = sum(1 for _, status, _ in self.results if status == 'failed')
        timeout = sum(1 for _, status, _ in self.results if status == 'timeout')
        error = sum(1 for _, status, _ in self.results if status == 'error')
        
        report += f"## Summary\n"
        report += f"- Passed: {passed}\n"
        report += f"- Failed: {failed}\n"
        report += f"- Timeout: {timeout}\n"
        report += f"- Error: {error}\n"
        report += f"- Total: {len(self.results)}\n\n"
        
        report += "## Details\n"
        for file_path, status, error_msg in self.results:
            report += f"- {file_path}: {status}\n"
            if error_msg:
                report += f"  Error: {error_msg}\n"
        
        return report

if __name__ == '__main__':
    runner = ExampleRunner('examples')
    success = runner.run_all_examples()
    
    print("\n" + runner.generate_report())
    
    sys.exit(0 if success else 1)
```

### 3.2 确保输出符合预期

**输出验证**：
```python
def verify_output(actual_output: str, expected_output: str) -> bool:
    """验证输出是否符合预期"""
    # 精确匹配
    if actual_output.strip() == expected_output.strip():
        return True
    
    # 模式匹配
    import re
    pattern = expected_output.replace('...', '.*')
    if re.match(pattern, actual_output.strip()):
        return True
    
    return False
```

### 3.3 更新文档中的输出示例

**示例更新**：
```markdown
### 创建Agent

**请求**：
```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DataAnalyzer",
    "model": "gpt-4"
  }'
```

**响应** (2026-05-27更新):
```json
{
  "id": "agent_001",
  "name": "DataAnalyzer",
  "model": "gpt-4",
  "created_at": "2026-05-27T10:30:00Z"
}
```
```

---

## 4. 版本标记

### 4.1 为示例添加版本标记

```python
"""
示例：创建Agent

兼容版本：v1.0+
最后更新：2026-05-27
作者：X-Agent团队

此示例展示如何创建一个新的Agent。
"""

import requests

def create_agent():
    response = requests.post(
        'http://localhost:8000/api/v1/agents',
        headers={'Authorization': 'Bearer token'},
        json={
            'name': 'DataAnalyzer',
            'model': 'gpt-4'
        }
    )
    return response.json()
```

### 4.2 标注兼容的API版本

**示例代码头部**：
```python
# API Version: v1.0+
# Last Updated: 2026-05-27
# Compatibility: Python 3.8+, requests 2.25+

# 此示例在以下API版本中测试过：
# - v1.0 (2026-05-01)
# - v1.1 (2026-05-15)
# - v1.2 (2026-05-27)
```

---

## 5. 自动化工具

### 5.1 检查示例代码

```bash
# 检查示例代码
python scripts/check_examples.py

# 输出示例
[ERROR] docs/EXAMPLES.md: Endpoint 'agents' not found in API spec
[WARNING] docs/tutorials/01-agent-basics.md: Parameter 'model' deprecated in v1.2
```

### 5.2 运行所有示例

```bash
# 运行所有示例
python scripts/run_examples.py

# 输出示例
Running examples/create_agent.py...
✓ examples/create_agent.py passed
Running examples/list_agents.py...
✗ examples/list_agents.py failed
  Error: Connection refused
```

### 5.3 生成示例报告

```bash
# 生成示例报告
python scripts/example_report.py

# 输出示例
# Example Code Maintenance Report
# Generated: 2026-05-27

## Summary
- Total Examples: 42
- Updated: 38
- Outdated: 4
- Broken: 0

## Outdated Examples
- docs/tutorials/02-workflow-orchestration.md (last updated: 2026-04-01)
- examples/advanced_workflow.py (last updated: 2026-04-15)
```

---

## 6. 责任人和流程

### 6.1 责任分工

| 角色 | 责任 |
|------|------|
| 文档团队 | 维护文档中的示例 |
| 开发团队 | API变更时通知文档团队 |
| QA团队 | 验证示例代码 |
| 发布经理 | 协调示例更新和发布 |

### 6.2 更新流程

1. **API变更通知**
   - 开发团队在PR中标记API变更
   - 自动通知文档团队

2. **示例识别**
   - 文档团队运行检查工具
   - 识别受影响的示例

3. **示例更新**
   - 更新示例代码
   - 运行验证脚本
   - 更新输出示例

4. **审查和发布**
   - 提交PR进行审查
   - 合并到主分支
   - 发布文档更新

### 6.3 时间表

| 阶段 | 时间 | 负责人 |
|------|------|--------|
| API变更 | T+0 | 开发团队 |
| 通知 | T+1小时 | 自动化系统 |
| 识别 | T+2小时 | 文档团队 |
| 更新 | T+4小时 | 文档团队 |
| 验证 | T+6小时 | QA团队 |
| 发布 | T+8小时 | 发布经理 |

---

## 7. 质量指标

### 7.1 示例代码质量指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 示例覆盖率 | 100% | 95% |
| 示例可运行率 | 100% | 98% |
| 示例更新及时性 | <1周 | 3天 |
| 示例文档完整性 | 100% | 92% |
| 示例版本标记 | 100% | 88% |

### 7.2 监控和告警

```yaml
# 监控规则
rules:
  - name: outdated_examples
    condition: example_age > 30_days
    severity: warning
    action: notify_team
  
  - name: broken_examples
    condition: example_execution_failed
    severity: critical
    action: create_issue
  
  - name: missing_version_tag
    condition: example_without_version_tag
    severity: warning
    action: notify_team
```

---

## 8. 最佳实践

### 8.1 编写示例代码

- 保持示例简洁明了
- 包含错误处理
- 添加注释说明
- 提供完整的输出示例
- 标注API版本和兼容性

### 8.2 维护示例代码

- 定期运行验证脚本
- 及时更新过时示例
- 记录示例的最后更新时间
- 保持示例与文档同步
- 收集用户反馈

### 8.3 文档示例

- 在文档中标注示例版本
- 提供多种编程语言的示例
- 包含成功和失败的示例
- 提供完整的错误处理示例
- 链接到完整的示例代码

---

## 9. 故障排查

### 9.1 常见问题

**Q: 示例代码运行失败**
A: 检查API版本是否匹配，运行 `python scripts/check_examples.py` 诊断问题

**Q: 示例输出与文档不符**
A: 运行 `python scripts/run_examples.py` 更新输出示例

**Q: 如何快速找到过时的示例**
A: 运行 `python scripts/example_report.py` 生成报告

### 9.2 调试技巧

```bash
# 启用详细日志
python scripts/check_examples.py --verbose

# 只检查特定文件
python scripts/check_examples.py --file docs/EXAMPLES.md

# 生成详细报告
python scripts/example_report.py --format html --output report.html
```

---

## 相关文档

- [API参考](../api/API_REFERENCE.md) - 完整API端点列表
- [代码示例](../sdk/EXAMPLES.md) - 所有代码示例
- [教程](../tutorials/tutorials/GETTING_STARTED.md) - 完整教程
- [贡献指南](../CONTRIBUTING.md) - 如何贡献

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 文档团队  
**许可证**: MIT
