"""
Code generation prompts and templates for X-Agent.

This module provides system prompts and templates for generating high-quality code
across multiple programming languages with best practices, type safety, and proper
error handling.
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class CodeGenerationConfig:
    """Configuration for code generation."""
    language: str
    include_tests: bool = True
    include_docs: bool = True
    include_type_hints: bool = True
    include_error_handling: bool = True
    code_style: str = "pep8"  # pep8, google, airbnb, etc.
    max_line_length: int = 100
    min_docstring_coverage: float = 0.9


CODE_GENERATION_SYSTEM_PROMPT = """
你是一个专业的代码生成助手。生成代码时请遵循以下原则：

## 1. 代码质量
   - 遵循语言最佳实践和社区约定
   - 使用清晰、有意义的变量和函数命名（避免缩写）
   - 添加适当的注释解释复杂逻辑
   - 保持代码简洁，避免过度设计
   - 遵循DRY（Don't Repeat Yourself）原则
   - 单一职责原则（Single Responsibility Principle）

## 2. 类型安全
   - Python: 使用类型提示（type hints）标注所有函数参数和返回值
   - JavaScript/TypeScript: 使用TypeScript而非JavaScript
   - 避免使用any类型，使用具体的类型定义
   - 使用Union、Optional等类型操作符表达复杂类型

## 3. 错误处理
   - 添加适当的try-catch/try-except块
   - 验证所有输入参数的有效性
   - 提供有意义的错误消息，包含上下文信息
   - 使用自定义异常类而非通用异常
   - 记录错误日志便于调试

## 4. 测试
   - 生成可测试的代码（低耦合、高内聚）
   - 避免硬编码值，使用配置或参数
   - 使用依赖注入便于单元测试
   - 提供测试用例示例

## 5. 文档
   - 添加模块级文档字符串说明功能
   - 为所有公共函数添加文档字符串
   - 说明参数、返回值、异常和使用示例
   - 使用标准格式（Google、NumPy或Sphinx风格）

## 6. 性能
   - 避免不必要的循环和递归
   - 使用适当的数据结构（列表、字典、集合等）
   - 考虑时间和空间复杂度
   - 添加缓存或记忆化处理重复计算

## 7. 安全性
   - 验证和清理所有外部输入
   - 避免SQL注入、XSS等常见漏洞
   - 使用参数化查询而非字符串拼接
   - 不在代码中硬编码敏感信息（密钥、密码等）

## 8. 可维护性
   - 使用有意义的变量名和函数名
   - 保持函数简短（理想情况下<50行）
   - 避免深层嵌套（最多3层）
   - 使用常量而非魔法数字

## 输出格式
生成的代码应该：
1. 包含完整的实现
2. 包含适当的导入语句
3. 包含文档字符串和注释
4. 包含错误处理
5. 包含使用示例（在注释中或docstring中）
"""

CODE_REVIEW_PROMPT = """
请审查以下代码并提供改进建议：

代码：
{code}

请检查以下方面：
1. **语法错误** - 是否有语法错误或不兼容的语言特性
2. **逻辑错误** - 是否有逻辑缺陷或边界情况处理不当
3. **性能问题** - 是否有性能瓶颈或低效的算法
4. **安全问题** - 是否有安全漏洞或不安全的操作
5. **最佳实践违反** - 是否违反了语言或框架的最佳实践
6. **可读性** - 代码是否易于理解和维护
7. **测试覆盖** - 是否需要添加测试用例
8. **文档** - 是否需要改进文档或注释

对每个问题提供：
- 问题描述
- 严重程度（Critical/High/Medium/Low）
- 改进建议
- 改进后的代码示例（如适用）
"""

CODE_OPTIMIZATION_PROMPT = """
请优化以下代码以提高性能、可读性和可维护性：

代码：
{code}

优化目标：
1. 减少时间复杂度
2. 减少空间复杂度
3. 改进代码可读性
4. 增强错误处理
5. 添加类型提示
6. 改进命名和文档

请提供：
1. 优化后的代码
2. 优化说明（每个改进的原因）
3. 性能对比（如适用）
"""

PYTHON_CODE_TEMPLATE = '''"""
{module_name}

{module_description}

Example:
    >>> from {module_path} import {class_name}
    >>> obj = {class_name}()
    >>> result = obj.method()
"""

from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class {class_name}:
    """
    {class_description}

    Attributes:
        {attribute_name}: {attribute_description}
    """

    def __init__(self, {init_params}):
        """
        Initialize {class_name}.

        Args:
            {init_params_doc}

        Raises:
            ValueError: If parameters are invalid.
        """
        try:
            {init_body}
        except Exception as e:
            logger.error(f"Failed to initialize {class_name}: {{e}}")
            raise

    def method(self, {method_params}) -> {return_type}:
        """
        {method_description}

        Args:
            {method_params_doc}

        Returns:
            {return_description}

        Raises:
            {exception_description}

        Example:
            >>> obj = {class_name}()
            >>> result = obj.method({example_params})
        """
        try:
            {method_body}
        except Exception as e:
            logger.error(f"Method failed: {{e}}")
            raise
'''

TYPESCRIPT_CODE_TEMPLATE = '''/**
 * {module_name}
 *
 * {module_description}
 *
 * @example
 * ```typescript
 * import {{ {class_name} }} from './{module_path}';
 * const obj = new {class_name}();
 * const result = await obj.method();
 * ```
 */

import {{ Logger }} from 'winston';

interface {interface_name} {{
    {interface_properties}
}}

export class {class_name} {{
    private logger: Logger;

    /**
     * Initialize {class_name}
     *
     * @param {init_params}
     * @throws {{Error}} If parameters are invalid
     */
    constructor({init_params}) {{
        try {{
            {init_body}
        }} catch (error) {{
            this.logger.error(`Failed to initialize {class_name}: ${{error}}`);
            throw error;
        }}
    }}

    /**
     * {method_description}
     *
     * @param {method_params}
     * @returns {return_description}
     * @throws {{Error}} If operation fails
     *
     * @example
     * ```typescript
     * const result = await obj.method({example_params});
     * ```
     */
    async method({method_params}): Promise<{return_type}> {{
        try {{
            {method_body}
        }} catch (error) {{
            this.logger.error(`Method failed: ${{error}}`);
            throw error;
        }}
    }}
}}
'''

JAVA_CODE_TEMPLATE = '''/**
 * {module_name}
 *
 * {module_description}
 *
 * @author X-Agent
 * @version 1.0
 */

package {package_name};

import java.util.*;
import java.util.logging.Logger;

/**
 * {class_description}
 */
public class {class_name} {{
    private static final Logger LOGGER = Logger.getLogger({class_name}.class.getName());

    /**
     * Initialize {class_name}
     *
     * @param {init_params}
     * @throws IllegalArgumentException if parameters are invalid
     */
    public {class_name}({init_params}) {{
        try {{
            {init_body}
        }} catch (Exception e) {{
            LOGGER.severe("Failed to initialize " + {class_name}.class.getSimpleName() + ": " + e.getMessage());
            throw new IllegalArgumentException(e);
        }}
    }}

    /**
     * {method_description}
     *
     * @param {method_params}
     * @return {return_description}
     * @throws Exception if operation fails
     */
    public {return_type} method({method_params}) throws Exception {{
        try {{
            {method_body}
        }} catch (Exception e) {{
            LOGGER.severe("Method failed: " + e.getMessage());
            throw e;
        }}
    }}
}}
'''

# Language-specific patterns and best practices
PYTHON_PATTERNS = {
    "error_handling": """
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
finally:
    cleanup()
""",
    "async_function": """
async def fetch_data(url: str) -> Dict[str, Any]:
    \"\"\"Fetch data from URL asynchronously.\"\"\"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as response:
                response.raise_for_status()
                return await response.json()
    except asyncio.TimeoutError:
        logger.error(f"Request timeout for {url}")
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Request failed: {e}")
        raise
""",
    "context_manager": """
class ResourceManager:
    def __enter__(self):
        logger.info("Acquiring resource")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Releasing resource")
        if exc_type:
            logger.error(f"Exception occurred: {exc_val}")
        return False
""",
    "decorator": """
def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(delay)
        return wrapper
    return decorator
""",
    "type_hints": """
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar

T = TypeVar('T')

def process_data(
    data: List[Dict[str, Any]],
    filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    transform_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    \"\"\"Process data with optional filtering and transformation.\"\"\"
    result = data
    if filter_fn:
        result = [item for item in result if filter_fn(item)]
    if transform_fn:
        result = [transform_fn(item) for item in result]
    return result
""",
}

TYPESCRIPT_PATTERNS = {
    "error_handling": """
try {
    const result = await riskyOperation();
    return result;
} catch (error) {
    if (error instanceof SpecificError) {
        logger.error(`Operation failed: ${error.message}`);
        throw error;
    }
    logger.error(`Unexpected error: ${error}`);
    throw new Error(`Operation failed: ${error}`);
} finally {
    cleanup();
}
""",
    "async_function": """
async function fetchData(url: string): Promise<Record<string, any>> {
    try {
        const response = await fetch(url, { timeout: 30000 });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        logger.error(`Request failed: ${error}`);
        throw error;
    }
}
""",
    "interface": """
interface User {
    id: string;
    name: string;
    email: string;
    createdAt: Date;
    metadata?: Record<string, any>;
}

interface ApiResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
    timestamp: Date;
}
""",
    "decorator": """
function retry(maxAttempts: number = 3, delay: number = 1000) {
    return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
        const originalMethod = descriptor.value;
        descriptor.value = async function (...args: any[]) {
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                try {
                    return await originalMethod.apply(this, args);
                } catch (error) {
                    if (attempt === maxAttempts - 1) throw error;
                    logger.warn(`Attempt ${attempt + 1} failed: ${error}`);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        };
        return descriptor;
    };
}
""",
}

JAVA_PATTERNS = {
    "error_handling": """
try {
    result = riskyOperation();
} catch (SpecificException e) {
    LOGGER.severe("Operation failed: " + e.getMessage());
    throw new RuntimeException(e);
} catch (Exception e) {
    LOGGER.severe("Unexpected error: " + e.getMessage());
    throw new RuntimeException(e);
} finally {
    cleanup();
}
""",
    "async_function": """
public CompletableFuture<Map<String, Object>> fetchData(String url) {
    return CompletableFuture.supplyAsync(() -> {
        try {
            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(30))
                .GET()
                .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            return parseJson(response.body());
        } catch (Exception e) {
            LOGGER.severe("Request failed: " + e.getMessage());
            throw new RuntimeException(e);
        }
    });
}
""",
}


def get_system_prompt(language: str = "python") -> str:
    """Get the system prompt for code generation."""
    return CODE_GENERATION_SYSTEM_PROMPT


def get_review_prompt(code: str) -> str:
    """Get the code review prompt."""
    return CODE_REVIEW_PROMPT.format(code=code)


def get_optimization_prompt(code: str) -> str:
    """Get the code optimization prompt."""
    return CODE_OPTIMIZATION_PROMPT.format(code=code)


def get_language_patterns(language: str) -> Dict[str, str]:
    """Get language-specific code patterns."""
    patterns_map = {
        "python": PYTHON_PATTERNS,
        "typescript": TYPESCRIPT_PATTERNS,
        "javascript": TYPESCRIPT_PATTERNS,
        "java": JAVA_PATTERNS,
    }
    return patterns_map.get(language.lower(), {})


def get_code_template(language: str) -> str:
    """Get code template for the specified language."""
    templates = {
        "python": PYTHON_CODE_TEMPLATE,
        "typescript": TYPESCRIPT_CODE_TEMPLATE,
        "javascript": TYPESCRIPT_CODE_TEMPLATE,
        "java": JAVA_CODE_TEMPLATE,
    }
    return templates.get(language.lower(), PYTHON_CODE_TEMPLATE)
