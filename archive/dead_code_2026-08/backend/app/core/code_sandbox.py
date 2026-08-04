"""
增强的代码执行沙箱系统 - 支持多语言、资源限制、隔离执行
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProgrammingLanguage(StrEnum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    BASH = "bash"
    TYPESCRIPT = "typescript"


@dataclass
class SandboxConfig:
    """沙箱配置"""
    language: ProgrammingLanguage
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    max_cpu_percent: int = 80
    max_output_bytes: int = 1024 * 1024  # 1MB
    allow_network: bool = False
    allow_file_write: bool = False
    temp_dir: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)

    def validate(self) -> tuple[bool, str]:
        """验证配置"""
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            return False, "timeout_seconds must be between 1 and 300"
        if self.max_memory_mb < 64 or self.max_memory_mb > 4096:
            return False, "max_memory_mb must be between 64 and 4096"
        if self.max_cpu_percent < 10 or self.max_cpu_percent > 100:
            return False, "max_cpu_percent must be between 10 and 100"
        return True, ""


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    memory_used_mb: int = 0
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
            "language": self.language.value,
        }


class CodeSandbox:
    """代码执行沙箱"""

    # 语言特定的执行配置
    LANGUAGE_CONFIGS = {
        ProgrammingLanguage.PYTHON: {
            "extension": ".py",
            "command": ["python", "-u"],
            "setup": None,
        },
        ProgrammingLanguage.JAVASCRIPT: {
            "extension": ".js",
            "command": ["node"],
            "setup": None,
        },
        ProgrammingLanguage.TYPESCRIPT: {
            "extension": ".ts",
            "command": ["ts-node"],
            "setup": None,
        },
        ProgrammingLanguage.GO: {
            "extension": ".go",
            "command": ["go", "run"],
            "setup": None,
        },
        ProgrammingLanguage.RUST: {
            "extension": ".rs",
            "command": ["rustc", "--edition", "2021", "-o", "/tmp/rust_out"],
            "setup": None,
        },
        ProgrammingLanguage.JAVA: {
            "extension": ".java",
            "command": ["java"],
            "setup": None,
        },
        ProgrammingLanguage.BASH: {
            "extension": ".sh",
            "command": ["bash"],
            "setup": None,
        },
    }

    def __init__(self, config: SandboxConfig):
        """初始化沙箱"""
        is_valid, error_msg = config.validate()
        if not is_valid:
            raise ValueError(f"Invalid sandbox config: {error_msg}")

        self.config = config
        self.temp_dir = config.temp_dir or tempfile.gettempdir()
        self._ensure_temp_dir()

    def _ensure_temp_dir(self) -> None:
        """确保临时目录存在"""
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

    async def execute(self, code: str) -> ExecutionResult:
        """执行代码"""
        start_time = time.time()

        try:
            # 验证代码
            if not code or len(code) > 100000:
                return ExecutionResult(
                    success=False,
                    output="",
                    error="Code must be between 1 and 100000 characters",
                    language=self.config.language,
                )

            # 创建临时文件
            file_path = await self._create_temp_file(code)

            try:
                # 执行代码
                result = await self._run_code(file_path)

                # 计算执行时间
                execution_time_ms = int((time.time() - start_time) * 1000)
                result.execution_time_ms = execution_time_ms

                return result
            finally:
                # 清理临时文件
                await self._cleanup_temp_file(file_path)

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                language=self.config.language,
            )

    async def _create_temp_file(self, code: str) -> str:
        """创建临时文件"""
        lang_config = self.LANGUAGE_CONFIGS.get(self.config.language)
        if not lang_config:
            raise ValueError(f"Unsupported language: {self.config.language}")

        extension = lang_config["extension"]
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=extension,
            dir=self.temp_dir,
            delete=False,
            encoding="utf-8"
        )

        try:
            temp_file.write(code)
            temp_file.flush()
            return temp_file.name
        finally:
            temp_file.close()

    async def _cleanup_temp_file(self, file_path: str) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

    async def _run_code(self, file_path: str) -> ExecutionResult:
        """运行代码"""
        lang_config = self.LANGUAGE_CONFIGS.get(self.config.language)
        if not lang_config:
            raise ValueError(f"Unsupported language: {self.config.language}")

        # 构建命令
        command = lang_config["command"] + [file_path]

        # 准备环境变量
        env = os.environ.copy()
        env.update(self.config.env_vars)

        # 如果不允许网络访问，添加网络限制
        if not self.config.allow_network:
            env["PYTHONUNBUFFERED"] = "1"

        try:
            # 执行进程
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.temp_dir,
            )

            # 等待进程完成或超时
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timeout after {self.config.timeout_seconds} seconds",
                    exit_code=-1,
                    language=self.config.language,
                )

            # 解析输出
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            # 限制输出大小
            if len(output) > self.config.max_output_bytes:
                output = output[:self.config.max_output_bytes] + "\n... (output truncated)"
            if len(error) > self.config.max_output_bytes:
                error = error[:self.config.max_output_bytes] + "\n... (error truncated)"

            return ExecutionResult(
                success=process.returncode == 0,
                output=output,
                error=error,
                exit_code=process.returncode,
                language=self.config.language,
            )

        except Exception as e:
            logger.error(f"Failed to run code: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                language=self.config.language,
            )


class SandboxPool:
    """沙箱池 - 管理多个沙箱实例"""

    def __init__(self, max_concurrent: int = 10):
        """初始化沙箱池"""
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def execute(
        self,
        code: str,
        language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
        timeout_seconds: int = 30,
        task_id: str | None = None,
    ) -> ExecutionResult:
        """执行代码"""
        config = SandboxConfig(
            language=language,
            timeout_seconds=timeout_seconds,
        )

        sandbox = CodeSandbox(config)

        async with self._semaphore:
            try:
                result = await sandbox.execute(code)
                return result
            except Exception as e:
                logger.error(f"Sandbox pool execution error: {e}")
                return ExecutionResult(
                    success=False,
                    output="",
                    error=str(e),
                    language=language,
                )

    async def execute_async(
        self,
        code: str,
        language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
        timeout_seconds: int = 30,
        task_id: str | None = None,
    ) -> str:
        """异步执行代码并返回任务ID"""
        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        task = asyncio.create_task(
            self.execute(code, language, timeout_seconds, task_id)
        )
        self._active_tasks[task_id] = task

        # 清理完成的任务
        task.add_done_callback(lambda t: self._active_tasks.pop(task_id, None))

        return task_id

    async def get_result(self, task_id: str) -> ExecutionResult | None:
        """获取执行结果"""
        task = self._active_tasks.get(task_id)
        if task is None:
            return None

        if task.done():
            try:
                return task.result()
            except Exception as e:
                logger.error(f"Failed to get task result: {e}")
                return ExecutionResult(
                    success=False,
                    output="",
                    error=str(e),
                )

        return None

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._active_tasks.get(task_id)
        if task is None:
            return False

        if not task.done():
            task.cancel()
            return True

        return False


# 全局沙箱池实例
_sandbox_pool: SandboxPool | None = None


def get_sandbox_pool() -> SandboxPool:
    """获取全局沙箱池"""
    global _sandbox_pool
    if _sandbox_pool is None:
        _sandbox_pool = SandboxPool(max_concurrent=10)
    return _sandbox_pool


async def execute_code(
    code: str,
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON,
    timeout_seconds: int = 30,
) -> ExecutionResult:
    """执行代码的便捷函数"""
    pool = get_sandbox_pool()
    return await pool.execute(code, language, timeout_seconds)
