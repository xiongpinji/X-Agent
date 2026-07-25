# X-Agent 代码能力使用示例和最佳实践

## 目录

1. [快速开始](#快速开始)
2. [代码理解示例](#代码理解示例)
3. [代码生成示例](#代码生成示例)
4. [上下文感知示例](#上下文感知示例)
5. [代码补全示例](#代码补全示例)
6. [代码重构示例](#代码重构示例)
7. [最佳实践](#最佳实践)
8. [常见问题](#常见问题)

---

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/test_code_capabilities.py -v
```

### 基本使用

```python
from backend.app.core.code_understanding import CodeUnderstandingEngine
from backend.app.core.code_generation import CodeGenerationEngine
from backend.app.core.context_aware import ContextAwareEngine
from backend.app.core.code_completion import CodeCompletionEngine
from backend.app.core.code_refactoring import CodeRefactoringEngine

# 初始化所有引擎
understanding_engine = CodeUnderstandingEngine()
generation_engine = CodeGenerationEngine()
context_engine = ContextAwareEngine()
completion_engine = CodeCompletionEngine()
refactoring_engine = CodeRefactoringEngine()

# 分析项目
project_context = context_engine.analyze_project("/path/to/project")
print(f"Project Language: {project_context.project_structure.language}")
print(f"Architecture: {project_context.architecture_pattern.name}")
```

---

## 代码理解示例

### 示例1: 分析单个文件

```python
from backend.app.core.code_understanding import CodeUnderstandingEngine

engine = CodeUnderstandingEngine()

# 分析Python文件
analysis = engine.analyze_file("src/utils.py")

# 查看符号
print("Symbols found:")
for symbol in analysis.symbols:
    print(f"  - {symbol.name} ({symbol.kind})")
    if symbol.docstring:
        print(f"    Doc: {symbol.docstring[:50]}...")

# 查看依赖
print("\nDependencies:")
for dep in analysis.dependencies:
    print(f"  - {dep.source} -> {dep.target} ({dep.kind})")

# 查看指标
print(f"\nMetrics:")
print(f"  - Lines of Code: {analysis.metrics.lines_of_code}")
print(f"  - Cyclomatic Complexity: {analysis.metrics.cyclomatic_complexity}")
print(f"  - Comment Ratio: {analysis.metrics.comment_ratio:.2%}")
```

### 示例2: 分析整个项目

```python
# 分析整个项目
analyses = engine.analyze_project("src", extensions=[".py", ".js"])

print(f"Analyzed {len(analyses)} files")

# 构建依赖图
dependency_graph = engine.build_dependency_graph()

# 查找高复杂度的文件
high_complexity_files = []
for file_path, analysis in analyses.items():
    if analysis.metrics.cyclomatic_complexity > 10:
        high_complexity_files.append((file_path, analysis.metrics.cyclomatic_complexity))

print("\nHigh Complexity Files:")
for file_path, complexity in sorted(high_complexity_files, key=lambda x: -x[1]):
    print(f"  - {file_path}: {complexity}")
```

### 示例3: 查找代码影响

```python
# 分析修改某个文件的影响
impact = engine.find_impact("src/core/utils.py")

print(f"Impacted files: {len(impact['impacted_files'])}")
for file_path in impact['impacted_files']:
    print(f"  - {file_path}")

print(f"\nExported symbols: {impact['exported_symbols']}")
```

### 示例4: 获取重构建议

```python
# 获取重构建议
suggestions = engine.suggest_refactoring("src/main.py")

print("Refactoring suggestions:")
for suggestion in suggestions:
    print(f"  - {suggestion['type']}: {suggestion['suggestion']}")
    print(f"    Complexity: {suggestion['complexity']}")
```

---

## 代码生成示例

### 示例1: 生成函数

```python
from backend.app.core.code_generation import (
    CodeGenerationEngine, GenerationRequest, GenerationContext, CodeStyle
)

engine = CodeGenerationEngine()

# 创建生成上下文
context = GenerationContext(
    project_root="/project",
    file_path="/project/utils.py",
    language="python",
    style=CodeStyle.PEP8,
    imports=["os", "sys", "json"],
    dependencies=["requests"],
)

# 创建生成请求
request = GenerationRequest(
    description="Create a function to fetch JSON data from an API endpoint",
    context=context,
    temperature=0.7,
    max_tokens=1024,
    constraints=[
        "Include error handling",
        "Add type hints",
        "Include docstring",
    ],
)

# 生成代码
result = engine.generate_code(request)

print("Generated Code:")
print(result.code)
print(f"\nConfidence: {result.confidence:.2%}")
print(f"Imports needed: {result.imports_needed}")
print(f"Dependencies: {result.dependencies_needed}")
```

### 示例2: 分析项目风格

```python
# 分析项目风格
style = engine.analyze_project_style("/project", "python", sample_size=10)

print("Project Style Conventions:")
print(f"  - Indentation: {style['indentation']}")
print(f"  - Naming: {style['naming_convention']}")
print(f"  - Line Length: {style['line_length']}")
print(f"  - Import Style: {style['import_style']}")
print(f"  - Comment Style: {style['comment_style']}")
print(f"  - Bracket Style: {style['bracket_style']}")
```

### 示例3: 生成测试代码

```python
# 生成测试代码
test_request = GenerationRequest(
    description="Generate unit tests for the fetch_data function",
    context=GenerationContext(
        project_root="/project",
        file_path="/project/tests/test_utils.py",
        language="python",
        test_framework="pytest",
    ),
)

test_result = engine.generate_code(test_request)
print("Generated Tests:")
print(test_result.code)
```

---

## 上下文感知示例

### 示例1: 分析项目结构

```python
from backend.app.core.context_aware import (
    ContextAwareEngine, ProjectStructureAnalyzer
)

engine = ContextAwareEngine()

# 分析项目
context = engine.analyze_project("/project")

# 查看项目结构
structure = context.project_structure
print(f"Project: {structure.name}")
print(f"Language: {structure.language}")
print(f"Framework: {structure.framework}")
print(f"Package Manager: {structure.package_manager}")
print(f"Test Framework: {structure.test_framework}")

print("\nDirectories:")
for dir_name, purpose in structure.directories.items():
    print(f"  - {dir_name}: {purpose}")

print("\nKey Files:")
for file_name in structure.key_files:
    print(f"  - {file_name}")
```

### 示例2: 检测架构模式

```python
# 检测架构模式
if context.architecture_pattern:
    pattern = context.architecture_pattern
    print(f"Architecture: {pattern.name}")
    print(f"Confidence: {pattern.confidence:.2%}")
    print(f"Layers: {pattern.layers}")
    print(f"Components: {pattern.components}")
```

### 示例3: 学习项目约定

```python
# 查看项目约定
print("Project Conventions:")
for convention in context.conventions:
    print(f"\n{convention.name}:")
    print(f"  Category: {convention.category}")
    print(f"  Pattern: {convention.pattern}")
    print(f"  Level: {convention.enforcement_level}")
    if convention.examples:
        print(f"  Examples: {convention.examples[:2]}")
```

### 示例4: 建议文件位置

```python
# 建议新文件的位置
location = engine.suggest_file_location("/project", "service", "user_service.py")
print(f"Suggested location: {location}")

# 建议测试文件位置
test_location = engine.suggest_file_location("/project", "test", "test_user_service.py")
print(f"Test location: {test_location}")
```

---

## 代码补全示例

### 示例1: 基本补全

```python
from backend.app.core.code_completion import (
    CodeCompletionEngine, CompletionContext, CompletionTrigger
)

engine = CodeCompletionEngine()

# 创建补全上下文
context = CompletionContext(
    file_path="main.py",
    language="python",
    line=10,
    column=15,
    line_text="result = my_",
    file_content=open("main.py").read(),
    trigger=CompletionTrigger.MANUAL,
    prefix="my_",
    available_symbols=["my_function", "my_class", "my_variable"],
)

# 获取补全建议
result = engine.complete(context, limit=10)

print("Completion suggestions:")
for i, item in enumerate(result.items, 1):
    print(f"{i}. {item.label} ({item.kind})")
    if item.detail:
        print(f"   {item.detail}")
    print(f"   Score: {item.score:.2%}")
```

### 示例2: 导入补全

```python
# 导入补全
import_context = CompletionContext(
    file_path="main.py",
    language="python",
    line=1,
    column=7,
    line_text="import ",
    file_content="import ",
    trigger=CompletionTrigger.IMPORT,
    prefix="",
)

import_result = engine.complete(import_context)

print("Import suggestions:")
for item in import_result.items[:5]:
    print(f"  - {item.label}")
```

### 示例3: 成员补全

```python
# 成员补全 (obj.member)
member_context = CompletionContext(
    file_path="main.py",
    language="python",
    line=5,
    column=10,
    line_text="my_list.",
    file_content="my_list = []\nmy_list.",
    trigger=CompletionTrigger.DOT,
    prefix="",
)

member_result = engine.complete(member_context)

print("Member suggestions:")
for item in member_result.items[:10]:
    print(f"  - {item.label}: {item.detail}")
```

### 示例4: 代码片段补全

```python
# 获取代码片段
snippets = engine.snippet_provider.get_snippets("python")

print("Available snippets:")
for name, snippet in snippets.items():
    print(f"\n{name}:")
    print(f"  {snippet.documentation}")
    print(f"  Template: {snippet.insert_text[:50]}...")
```

---

## 代码重构示例

### 示例1: 检测重构机会

```python
from backend.app.core.code_refactoring import CodeRefactoringEngine

engine = CodeRefactoringEngine()

code = open("main.py").read()

# 检测重构机会
opportunities = engine.detect_opportunities("main.py", code, "python")

print(f"Found {len(opportunities)} refactoring opportunities:\n")

for opp in opportunities:
    print(f"Type: {opp.type}")
    print(f"Description: {opp.description}")
    print(f"Severity: {opp.severity}")
    print(f"Confidence: {opp.confidence:.2%}")
    if opp.suggested_changes:
        print(f"Suggestion: {opp.suggested_changes}")
    print()
```

### 示例2: 规划重构

```python
# 规划重构
if opportunities:
    opp = opportunities[0]
    plan = engine.plan_refactoring(opp, code, "python")

    print(f"Refactoring Plan:")
    print(f"  Type: {plan.refactoring_type}")
    print(f"  Changes: {len(plan.changes)}")
    print(f"  Affected Files: {plan.affected_files}")
    print(f"  Risk Level: {plan.risk_level}")
    print(f"  Estimated Time: {plan.estimated_time}s")

    # 查看具体变更
    for change in plan.changes:
        print(f"\n  Change in {change.file_path}:")
        print(f"    Lines: {change.start_line}-{change.end_line}")
        print(f"    Description: {change.description}")
```

### 示例3: 验证和应用重构

```python
# 验证重构
is_valid, errors = engine.validate_refactoring(plan, code)

if is_valid:
    print("✓ Refactoring plan is valid")
    
    # 应用重构
    result = engine.apply_refactoring(plan, code)
    
    print(f"Refactoring Result:")
    print(f"  Status: {result.status}")
    print(f"  Changes Applied: {result.changes_applied}")
    print(f"  Tests Passed: {result.tests_passed}")
    print(f"  Tests Failed: {result.tests_failed}")
    print(f"  Execution Time: {result.execution_time:.2f}s")
else:
    print("✗ Refactoring plan has errors:")
    for error in errors:
        print(f"  - {error}")
```

### 示例4: 获取重构建议

```python
# 获取排序后的重构建议
suggestions = engine.suggest_refactorings("main.py", code, "python", limit=5)

print("Top 5 Refactoring Suggestions:")
for i, suggestion in enumerate(suggestions, 1):
    print(f"\n{i}. {suggestion.type}")
    print(f"   {suggestion.description}")
    print(f"   Severity: {suggestion.severity}")
    print(f"   Complexity: {suggestion.complexity}/10")
```

---

## 最佳实践

### 1. 代码理解最佳实践

```python
# ✅ 好的做法
def analyze_codebase(project_root):
    engine = CodeUnderstandingEngine()
    
    # 分析整个项目
    analyses = engine.analyze_project(project_root)
    
    # 构建依赖图
    dependency_graph = engine.build_dependency_graph()
    
    # 缓存结果以供后续使用
    return analyses, dependency_graph

# ❌ 不好的做法
def analyze_single_file(file_path):
    engine = CodeUnderstandingEngine()
    
    # 每次都创建新引擎（低效）
    analysis = engine.analyze_file(file_path)
    return analysis
```

### 2. 代码生成最佳实践

```python
# ✅ 好的做法
def generate_code_with_context(description, project_root):
    engine = CodeGenerationEngine()
    context_engine = ContextAwareEngine()
    
    # 先分析项目上下文
    project_context = context_engine.analyze_project(project_root)
    
    # 创建包含完整上下文的请求
    context = GenerationContext(
        project_root=project_root,
        file_path="new_file.py",
        language=project_context.project_structure.language,
        style=CodeStyle.PEP8,
        conventions=project_context.conventions,
    )
    
    request = GenerationRequest(
        description=description,
        context=context,
        constraints=["Follow project conventions", "Include tests"],
    )
    
    return engine.generate_code(request)

# ❌ 不好的做法
def generate_code_minimal(description):
    engine = CodeGenerationEngine()
    
    # 没有上下文信息
    context = GenerationContext(
        project_root="/",
        file_path="file.py",
        language="python",
    )
    
    request = GenerationRequest(description=description, context=context)
    return engine.generate_code(request)
```

### 3. 代码补全最佳实践

```python
# ✅ 好的做法
def get_smart_completions(file_path, line, column):
    engine = CodeCompletionEngine()
    
    # 读取完整的文件内容
    with open(file_path) as f:
        file_content = f.read()
    
    lines = file_content.split("\n")
    line_text = lines[line - 1] if line <= len(lines) else ""
    
    # 提取前缀
    prefix = line_text[:column].split()[-1] if column > 0 else ""
    
    # 检测触发器
    if line_text.rstrip().endswith("."):
        trigger = CompletionTrigger.DOT
    elif "import" in line_text:
        trigger = CompletionTrigger.IMPORT
    else:
        trigger = CompletionTrigger.MANUAL
    
    context = CompletionContext(
        file_path=file_path,
        language="python",
        line=line,
        column=column,
        line_text=line_text,
        file_content=file_content,
        trigger=trigger,
        prefix=prefix,
    )
    
    return engine.complete(context, limit=20)

# ❌ 不好的做法
def get_completions_minimal(file_path):
    engine = CodeCompletionEngine()
    
    # 缺少关键信息
    context = CompletionContext(
        file_path=file_path,
        language="python",
        line=1,
        column=0,
        line_text="",
        file_content="",
    )
    
    return engine.complete(context)
```

### 4. 代码重构最佳实践

```python
# ✅ 好的做法
def safe_refactor(file_path, code):
    engine = CodeRefactoringEngine()
    
    # 1. 检测机会
    opportunities = engine.detect_opportunities(file_path, code, "python")
    
    if not opportunities:
        return None
    
    # 2. 选择最安全的重构
    safe_opp = min(opportunities, key=lambda x: x.complexity)
    
    # 3. 规划重构
    plan = engine.plan_refactoring(safe_opp, code, "python")
    
    # 4. 验证计划
    is_valid, errors = engine.validate_refactoring(plan, code)
    
    if not is_valid:
        print(f"Validation failed: {errors}")
        return None
    
    # 5. 应用重构
    result = engine.apply_refactoring(plan, code)
    
    # 6. 检查结果
    if result.status == RefactoringStatus.APPLIED:
        return result
    else:
        print(f"Refactoring failed: {result.errors}")
        return None

# ❌ 不好的做法
def unsafe_refactor(file_path, code):
    engine = CodeRefactoringEngine()
    
    # 直接应用最复杂的重构，不验证
    opportunities = engine.detect_opportunities(file_path, code, "python")
    plan = engine.plan_refactoring(opportunities[0], code, "python")
    
    # 不验证就应用
    return engine.apply_refactoring(plan, code)
```

---

## 常见问题

### Q1: 如何提高代码理解的准确率？

**A**: 
1. 确保代码语法正确
2. 提供完整的项目上下文
3. 使用正确的语言标识
4. 定期更新分析结果

```python
# 提高准确率的方法
analysis = engine.analyze_file(file_path)

# 验证符号
for symbol in analysis.symbols:
    if symbol.complexity > 10:
        # 重新分析复杂符号
        pass
```

### Q2: 生成的代码不符合项目风格怎么办？

**A**:
1. 分析项目风格
2. 在生成请求中指定风格
3. 提供代码示例

```python
# 确保风格一致
style = engine.analyze_project_style(project_root, "python")

context = GenerationContext(
    project_root=project_root,
    file_path=file_path,
    language="python",
    style=CodeStyle.PEP8,
    conventions=project_context.conventions,
)
```

### Q3: 补全建议不相关怎么办？

**A**:
1. 提供更多的上下文
2. 检查可用符号列表
3. 调整补全触发器

```python
# 改进补全质量
context = CompletionContext(
    file_path=file_path,
    language="python",
    line=line,
    column=column,
    line_text=line_text,
    file_content=file_content,  # 提供完整内容
    trigger=trigger,  # 正确的触发器
    prefix=prefix,
    available_symbols=extract_symbols(file_content),  # 提供符号列表
)
```

### Q4: 重构失败了怎么办？

**A**:
1. 检查验证错误
2. 选择更简单的重构
3. 查看回滚计划

```python
# 安全的重构流程
is_valid, errors = engine.validate_refactoring(plan, code)

if not is_valid:
    print(f"Errors: {errors}")
    
    # 尝试更简单的重构
    simpler_opp = find_simpler_opportunity(opportunities)
    plan = engine.plan_refactoring(simpler_opp, code, "python")
```

### Q5: 如何处理大型项目？

**A**:
1. 分批分析
2. 使用缓存
3. 限制分析范围

```python
# 处理大型项目
def analyze_large_project(project_root):
    engine = CodeUnderstandingEngine()
    
    # 分批分析
    batch_size = 100
    all_analyses = {}
    
    for batch in get_file_batches(project_root, batch_size):
        for file_path in batch:
            analysis = engine.analyze_file(file_path)
            all_analyses[file_path] = analysis
        
        # 定期保存缓存
        save_cache(all_analyses)
    
    return all_analyses
```

---

## 总结

X-Agent的代码能力模块提供了强大的代码理解、生成、补全和重构功能。通过遵循最佳实践，可以充分利用这些功能来提高开发效率和代码质量。

更多信息请参考：
- [代码能力指南](./CODE_CAPABILITIES_GUIDE.md)
- [对比报告](./CODE_CAPABILITIES_COMPARISON.md)
- [测试用例](../tests/test_code_capabilities.py)
