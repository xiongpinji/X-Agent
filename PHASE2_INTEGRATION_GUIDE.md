# Claude Code能力对齐第二阶段 - 集成指南

## 快速开始

### 1. 安装依赖

```bash
pip install python-docx PyPDF2 python-pptx openpyxl Pillow markdown PyYAML
```

### 2. 初始化系统

```python
from backend.app.core.skills import SkillRegistry, SkillLoader
from backend.app.core.file_operations import DocumentProcessor, ImageProcessor, FileConverter
from backend.app.core.execution import ExecutionManager

# 初始化技能系统
skill_registry = SkillRegistry()
skill_loader = SkillLoader(registry=skill_registry)

# 初始化文件操作
doc_processor = DocumentProcessor()
img_processor = ImageProcessor()
file_converter = FileConverter()

# 初始化代码执行
exec_manager = ExecutionManager()
```

### 3. 注册API路由

在FastAPI应用中注册新的API路由：

```python
from fastapi import FastAPI
from backend.app.api import skills, files_v2, code_execution

app = FastAPI()

# 注册路由
app.include_router(skills.router)
app.include_router(files_v2.router)
app.include_router(code_execution.router)
```

---

## 技能系统集成

### 创建自定义技能

```python
from backend.app.core.skills import Skill, SkillMetadata, SkillContext, SkillResult

class DataAnalysisSkill(Skill):
    """数据分析技能"""
    
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="data_analysis",
            version="1.0.0",
            description="Analyze data and generate insights",
            author="Your Team",
            capabilities=["analyze", "visualize", "report"],
            tags=["data", "analytics"],
        )
    
    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        try:
            data = kwargs.get("data", [])
            analysis_type = kwargs.get("type", "summary")
            
            # 执行分析逻辑
            result = await self._analyze(data, analysis_type)
            
            return SkillResult(
                success=True,
                data=result,
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )
    
    async def _analyze(self, data, analysis_type):
        # 实现分析逻辑
        if analysis_type == "summary":
            return {
                "count": len(data),
                "mean": sum(data) / len(data) if data else 0,
            }
        return {}
```

### 注册和使用技能

```python
# 注册技能
skill = DataAnalysisSkill()
registry.register(skill)

# 通过API执行
# POST /api/v1/skills/data_analysis/execute
# {
#     "params": {
#         "data": [1, 2, 3, 4, 5],
#         "type": "summary"
#     }
# }
```

---

## 文件操作集成

### 处理Word文档

```python
# 提取文本
result = await doc_processor.process(
    "document.docx",
    "extract_text"
)
print(result["data"])

# 添加内容
result = await doc_processor.process(
    "document.docx",
    "add_paragraph",
    text="New paragraph content"
)

# 添加标题
result = await doc_processor.process(
    "document.docx",
    "add_heading",
    text="Section Title",
    level=1
)
```

### 处理PDF

```python
# 提取文本
result = await doc_processor.process(
    "document.pdf",
    "extract_text"
)

# 获取页数
result = await doc_processor.process(
    "document.pdf",
    "get_page_count"
)

# 提取特定页面
result = await doc_processor.process(
    "document.pdf",
    "extract_page",
    page_num=0
)
```

### 处理Excel

```python
# 读取数据
result = await doc_processor.process(
    "data.xlsx",
    "read_data"
)
data = result["data"]

# 获取工作表名称
result = await doc_processor.process(
    "data.xlsx",
    "get_sheet_names"
)

# 写入数据
result = await doc_processor.process(
    "data.xlsx",
    "write_data",
    data=[[1, 2, 3], [4, 5, 6]],
    sheet_name="Sheet1"
)
```

### 处理图像

```python
# 调整大小
result = await img_processor.process(
    "image.jpg",
    "resize",
    width=800,
    height=600
)

# 转换格式
result = await img_processor.process(
    "image.jpg",
    "convert_format",
    target_format="png"
)

# 应用滤镜
result = await img_processor.process(
    "image.jpg",
    "apply_filter",
    filter_type="grayscale"
)

# 获取信息
result = await img_processor.process(
    "image.jpg",
    "get_info"
)
```

### 转换文件格式

```python
# CSV转JSON
result = await file_converter.convert(
    "data.csv",
    "json"
)

# JSON转CSV
result = await file_converter.convert(
    "data.json",
    "csv"
)

# Markdown转HTML
result = await file_converter.convert(
    "document.md",
    "html"
)
```

---

## 代码执行集成

### 执行Python代码

```python
# 简单执行
result = await exec_manager.execute_python(
    "print('Hello, World!')"
)

# 带上下文
result = await exec_manager.execute_python(
    "print(x + y)",
    context={"x": 10, "y": 20}
)

# 允许特定模块
result = await exec_manager.execute_python(
    "import math\nprint(math.pi)",
    allowed_imports=["math"]
)
```

### 执行Node.js代码

```python
# 简单执行
result = await exec_manager.execute_nodejs(
    "console.log('Hello, World!')"
)

# 导入模块
result = await exec_manager.execute_nodejs(
    "const fs = require('fs');\nconsole.log('ok')",
    modules=["fs"]
)
```

### 批量执行

```python
result = await exec_manager.execute(
    code,
    language="python",
    context={"data": [1, 2, 3]},
    allowed_imports=["json"]
)
```

---

## API使用示例

### 技能API

```bash
# 列出所有技能
curl -X GET http://localhost:8000/api/v1/skills

# 获取技能详情
curl -X GET http://localhost:8000/api/v1/skills/data_analysis

# 执行技能
curl -X POST http://localhost:8000/api/v1/skills/data_analysis/execute \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "data": [1, 2, 3, 4, 5],
      "type": "summary"
    }
  }'

# 按能力搜索
curl -X GET "http://localhost:8000/api/v1/skills/search/by-capability?capability=analyze"

# 按标签搜索
curl -X GET "http://localhost:8000/api/v1/skills/search/by-tag?tag=data"
```

### 文件操作API

```bash
# 处理文件
curl -X POST http://localhost:8000/api/v1/files/process \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "document.docx",
    "operation": "extract_text"
  }'

# 处理图像
curl -X POST http://localhost:8000/api/v1/files/image/process \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "image.jpg",
    "operation": "resize",
    "params": {
      "width": 800,
      "height": 600
    }
  }'

# 转换文件
curl -X POST http://localhost:8000/api/v1/files/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "data.csv",
    "output_format": "json"
  }'
```

### 代码执行API

```bash
# 执行Python代码
curl -X POST http://localhost:8000/api/v1/execution/python \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(1 + 1)",
    "context": {}
  }'

# 执行Node.js代码
curl -X POST http://localhost:8000/api/v1/execution/nodejs \
  -H "Content-Type: application/json" \
  -d '{
    "code": "console.log(1 + 1)"
  }'

# 获取执行结果
curl -X GET http://localhost:8000/api/v1/execution/{execution_id}

# 列出执行历史
curl -X GET http://localhost:8000/api/v1/execution?limit=10
```

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/test_skills.py tests/test_file_operations.py tests/test_code_execution.py

# 运行特定测试
pytest tests/test_skills.py::TestSkillRegistry::test_register_skill

# 生成覆盖率报告
pytest --cov=backend.app.core tests/
```

### 测试覆盖

- 技能系统: 90%+
- 文件操作: 85%+
- 代码执行: 88%+

---

## 故障排除

### 问题: 技能加载失败

**原因**: 技能目录不存在或模块导入错误

**解决方案**:
```python
# 检查技能目录
import os
skills_dir = "backend/app/core/skills"
if os.path.exists(skills_dir):
    print("Skills directory exists")
else:
    print("Skills directory not found")

# 检查模块导入
try:
    from backend.app.core.skills import SkillLoader
    print("Import successful")
except ImportError as e:
    print(f"Import error: {e}")
```

### 问题: 文件处理失败

**原因**: 缺少依赖库或文件格式不支持

**解决方案**:
```bash
# 安装缺失的依赖
pip install python-docx PyPDF2 python-pptx openpyxl Pillow

# 检查文件格式
file_path = "document.docx"
if file_path.endswith(".docx"):
    print("DOCX format supported")
```

### 问题: 代码执行超时

**原因**: 代码执行时间过长

**解决方案**:
```python
# 增加超时时间
exec_manager = ExecutionManager(timeout=60)

# 或在执行时指定
result = await exec_manager.execute_python(
    code,
    timeout=60
)
```

---

## 性能优化

### 1. 缓存技能元数据

```python
# 缓存已加载的技能
loaded_skills = {}

async def get_skill_cached(skill_name):
    if skill_name not in loaded_skills:
        loaded_skills[skill_name] = await skill_loader.load_skill(skill_name)
    return loaded_skills[skill_name]
```

### 2. 批量处理

```python
# 批量处理文件
result = await doc_processor.batch_process(
    files=[
        {"path": "file1.docx", "operation": "extract_text"},
        {"path": "file2.docx", "operation": "extract_text"},
    ]
)
```

### 3. 异步执行

```python
import asyncio

# 并发执行多个任务
tasks = [
    exec_manager.execute_python("print(1)"),
    exec_manager.execute_python("print(2)"),
    exec_manager.execute_python("print(3)"),
]
results = await asyncio.gather(*tasks)
```

---

## 安全最佳实践

### 1. 验证输入

```python
# 验证文件路径
from pathlib import Path

def validate_file_path(file_path):
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    return path
```

### 2. 限制代码执行

```python
# 只允许特定模块
allowed_imports = ["math", "json", "datetime"]

result = await exec_manager.execute_python(
    code,
    allowed_imports=allowed_imports
)
```

### 3. 权限检查

```python
# 在API中检查权限
from backend.app.dependencies import enforce_scope

@router.post("/execute")
async def execute_code(request: dict, principal: Principal):
    enforce_scope(principal, "execution:python")
    # 执行代码
```

---

## 监控和日志

### 启用日志

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 记录技能执行
logger.info(f"Executing skill: {skill_name}")

# 记录文件操作
logger.info(f"Processing file: {file_path}")

# 记录代码执行
logger.info(f"Executing {language} code")
```

### 监控执行

```python
# 获取执行统计
executions = exec_manager.list_executions(limit=100)
successful = sum(1 for e in executions if e["result"]["success"])
failed = len(executions) - successful

print(f"Success rate: {successful}/{len(executions)}")
```

---

## 下一步

1. **开发高级技能**: 数据分析、机器学习、自然语言处理
2. **工作流编排**: 支持技能链式执行
3. **分布式执行**: 支持分布式代码执行
4. **性能优化**: 缓存、并发、资源池
5. **监控告警**: 完整的监控和告警系统

---

**文档版本**: 1.0  
**最后更新**: 2026-05-26
