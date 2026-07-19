"""
工具文档生成器 - 为每个工具生成完整的使用文档
"""
from __future__ import annotations

from typing import Any

from backend.app.core.tool_schema import ToolSchema


class ToolDocumentationGenerator:
    """工具文档生成器"""

    @staticmethod
    def generate_markdown(tool: ToolSchema) -> str:
        """生成 Markdown 文档"""
        doc = f"""# {tool.name}

**Version:** {tool.version}
**Category:** {tool.category.value}
**Risk Level:** {tool.risk_level.value}
**Status:** {tool.status.value}

## Description

{tool.description}

## Parameters

"""
        if tool.parameters:
            doc += "| Name | Type | Required | Description |\n"
            doc += "|------|------|----------|-------------|\n"
            for param in tool.parameters:
                required = "Yes" if param.required else "No"
                doc += f"| `{param.name}` | `{param.type}` | {required} | {param.description} |\n"
        else:
            doc += "No parameters required.\n"

        doc += f"""
## Returns

**Type:** `{tool.returns.type}`

{tool.returns.description}

"""

        if tool.permissions:
            doc += f"""## Permissions Required

"""
            for perm in tool.permissions:
                doc += f"- `{perm}`\n"
            doc += "\n"

        if tool.requires_approval:
            doc += "**Note:** This tool requires approval before execution.\n\n"

        if tool.examples:
            doc += "## Examples\n\n"
            for example in tool.examples:
                doc += f"### {example.name}\n\n"
                doc += f"{example.description}\n\n"
                doc += "**Input:**\n```json\n"
                doc += self._format_json(example.input)
                doc += "\n```\n\n"
                doc += "**Output:**\n```json\n"
                doc += self._format_json(example.output)
                doc += "\n```\n\n"

        if tool.dependencies:
            doc += f"""## Dependencies

"""
            for dep in tool.dependencies:
                doc += f"- {dep}\n"
            doc += "\n"

        if tool.tags:
            doc += f"""## Tags

"""
            for tag in tool.tags:
                doc += f"- `{tag}`\n"

        return doc

    @staticmethod
    def generate_json_schema(tool: ToolSchema) -> dict[str, Any]:
        """生成 JSON Schema"""
        properties = {}
        required = []

        for param in tool.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }

            if param.default is not None:
                prop["default"] = param.default

            if param.enum:
                prop["enum"] = param.enum

            if param.min_length is not None:
                prop["minLength"] = param.min_length

            if param.max_length is not None:
                prop["maxLength"] = param.max_length

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "title": tool.name,
            "description": tool.description,
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def generate_openapi_spec(tool: ToolSchema) -> dict[str, Any]:
        """生成 OpenAPI 规范"""
        return {
            "operationId": tool.name,
            "summary": tool.description,
            "tags": tool.tags or [tool.category.value],
            "parameters": [
                {
                    "name": param.name,
                    "in": "query",
                    "required": param.required,
                    "schema": {
                        "type": param.type,
                        "description": param.description,
                    },
                }
                for param in tool.parameters
            ],
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": tool.returns.type,
                                "description": tool.returns.description,
                            }
                        }
                    },
                },
                "400": {
                    "description": "Bad Request",
                },
                "403": {
                    "description": "Forbidden",
                },
                "500": {
                    "description": "Internal Server Error",
                },
            },
        }

    @staticmethod
    def generate_python_stub(tool: ToolSchema) -> str:
        """生成 Python 函数签名"""
        params = []
        for param in tool.parameters:
            param_str = f"{param.name}: {param.type}"
            if not param.required and param.default is not None:
                param_str += f" = {param.default}"
            params.append(param_str)

        params_str = ", ".join(params)
        return_type = tool.returns.type

        return f"""async def {tool.name}({params_str}) -> {return_type}:
    \"\"\"
    {tool.description}

    Args:
"""
        + "\n".join(
            [
                f"        {param.name}: {param.description}"
                for param in tool.parameters
            ]
        )
        + f"""

    Returns:
        {tool.returns.description}

    Raises:
        ToolExecutionError: If the tool execution fails
    \"\"\"
    pass
"""

    @staticmethod
    def _format_json(obj: Any, indent: int = 2) -> str:
        """格式化 JSON"""
        import json

        return json.dumps(obj, indent=indent, ensure_ascii=False)


class ToolDocumentationBuilder:
    """工具文档构建器 - 为所有工具生成完整文档"""

    def __init__(self, tools: list[ToolSchema]):
        self.tools = tools
        self.generator = ToolDocumentationGenerator()

    def build_markdown_docs(self) -> dict[str, str]:
        """构建 Markdown 文档"""
        docs = {}
        for tool in self.tools:
            docs[tool.name] = self.generator.generate_markdown(tool)
        return docs

    def build_json_schemas(self) -> dict[str, dict[str, Any]]:
        """构建 JSON Schema"""
        schemas = {}
        for tool in self.tools:
            schemas[tool.name] = self.generator.generate_json_schema(tool)
        return schemas

    def build_openapi_spec(self) -> dict[str, Any]:
        """构建 OpenAPI 规范"""
        paths = {}
        for tool in self.tools:
            paths[f"/tools/{tool.name}"] = {
                "post": self.generator.generate_openapi_spec(tool)
            }

        return {
            "openapi": "3.0.0",
            "info": {
                "title": "X-Agent Tool API",
                "version": "1.0.0",
                "description": "Unified tool protocol and registry for X-Agent",
            },
            "paths": paths,
        }

    def build_python_stubs(self) -> dict[str, str]:
        """构建 Python 函数签名"""
        stubs = {}
        for tool in self.tools:
            stubs[tool.name] = self.generator.generate_python_stub(tool)
        return stubs

    def build_reference_guide(self) -> str:
        """构建参考指南"""
        guide = """# X-Agent Tool Reference Guide

## Overview

This guide provides a comprehensive reference for all available tools in the X-Agent system.

## Table of Contents

"""
        for tool in self.tools:
            guide += f"- [{tool.name}](#{tool.name})\n"

        guide += "\n---\n\n"

        for tool in self.tools:
            guide += self.generator.generate_markdown(tool)
            guide += "\n---\n\n"

        return guide
