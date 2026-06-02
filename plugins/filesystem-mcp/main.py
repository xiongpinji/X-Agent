"""File System MCP Plugin - Read, write, search, and manage files"""

import logging
import os
from pathlib import Path
from typing import Any, List
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


class FileSystemPlugin:
    """File System MCP Plugin Server"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize File System plugin"""
        self.config = config or {}
        self.allowed_paths = self.config.get("allowed_paths", [])
        self.max_file_size_mb = self.config.get("max_file_size_mb", 100)
        self.enable_write = self.config.get("enable_write", True)

        if not self.allowed_paths:
            raise ValueError("allowed_paths is required")

        # Convert to Path objects
        self.allowed_paths = [Path(p).resolve() for p in self.allowed_paths]

        logger.info(f"FileSystemPlugin initialized with {len(self.allowed_paths)} allowed paths")

    def _is_path_allowed(self, file_path: str) -> bool:
        """Check if path is allowed"""
        try:
            path = Path(file_path).resolve()

            # Check if path is within allowed paths
            for allowed_path in self.allowed_paths:
                try:
                    path.relative_to(allowed_path)
                    return True
                except ValueError:
                    continue

            return False
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False

    async def read_file(self, path: str, encoding: str = "utf-8") -> dict[str, Any]:
        """Read file content"""
        try:
            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            file_path = Path(path)

            if not file_path.exists():
                return {
                    "status": "error",
                    "message": f"File not found: {path}"
                }

            if not file_path.is_file():
                return {
                    "status": "error",
                    "message": f"Not a file: {path}"
                }

            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                return {
                    "status": "error",
                    "message": f"File too large: {file_size_mb:.2f}MB (max: {self.max_file_size_mb}MB)"
                }

            # Read file
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "content": content,
                    "size": len(content),
                    "encoding": encoding
                }
            }
        except Exception as e:
            logger.error(f"Read file error: {e}")
            return {
                "status": "error",
                "message": f"Read file error: {str(e)}"
            }

    async def write_file(self, path: str, content: str, append: bool = False) -> dict[str, Any]:
        """Write content to file"""
        try:
            if not self.enable_write:
                return {
                    "status": "error",
                    "message": "Write operations are disabled"
                }

            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            file_path = Path(path)

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "size": len(content),
                    "mode": "append" if append else "write"
                }
            }
        except Exception as e:
            logger.error(f"Write file error: {e}")
            return {
                "status": "error",
                "message": f"Write file error: {str(e)}"
            }

    async def list_files(self, path: str, recursive: bool = False) -> dict[str, Any]:
        """List files in directory"""
        try:
            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            dir_path = Path(path)

            if not dir_path.exists():
                return {
                    "status": "error",
                    "message": f"Directory not found: {path}"
                }

            if not dir_path.is_dir():
                return {
                    "status": "error",
                    "message": f"Not a directory: {path}"
                }

            # List files
            files = []
            if recursive:
                items = dir_path.rglob("*")
            else:
                items = dir_path.iterdir()

            for item in items:
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Error listing {item}: {e}")

            return {
                "status": "success",
                "data": sorted(files, key=lambda x: x["name"]),
                "count": len(files)
            }
        except Exception as e:
            logger.error(f"List files error: {e}")
            return {
                "status": "error",
                "message": f"List files error: {str(e)}"
            }

    async def search_files(self, path: str, pattern: str, recursive: bool = True) -> dict[str, Any]:
        """Search files by pattern"""
        try:
            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            dir_path = Path(path)

            if not dir_path.exists():
                return {
                    "status": "error",
                    "message": f"Directory not found: {path}"
                }

            if not dir_path.is_dir():
                return {
                    "status": "error",
                    "message": f"Not a directory: {path}"
                }

            # Search files
            files = []
            if recursive:
                items = dir_path.rglob(pattern)
            else:
                items = dir_path.glob(pattern)

            for item in items:
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
                    })
                except Exception as e:
                    logger.warning(f"Error searching {item}: {e}")

            return {
                "status": "success",
                "data": sorted(files, key=lambda x: x["name"]),
                "count": len(files)
            }
        except Exception as e:
            logger.error(f"Search files error: {e}")
            return {
                "status": "error",
                "message": f"Search files error: {str(e)}"
            }

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file"""
        try:
            if not self.enable_write:
                return {
                    "status": "error",
                    "message": "Write operations are disabled"
                }

            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            file_path = Path(path)

            if not file_path.exists():
                return {
                    "status": "error",
                    "message": f"File not found: {path}"
                }

            if not file_path.is_file():
                return {
                    "status": "error",
                    "message": f"Not a file: {path}"
                }

            # Delete file
            file_path.unlink()

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "message": "File deleted"
                }
            }
        except Exception as e:
            logger.error(f"Delete file error: {e}")
            return {
                "status": "error",
                "message": f"Delete file error: {str(e)}"
            }

    async def get_file_info(self, path: str) -> dict[str, Any]:
        """Get file information"""
        try:
            if not self._is_path_allowed(path):
                return {
                    "status": "error",
                    "message": f"Path not allowed: {path}"
                }

            file_path = Path(path)

            if not file_path.exists():
                return {
                    "status": "error",
                    "message": f"File not found: {path}"
                }

            stat = file_path.stat()

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "name": file_path.name,
                    "type": "directory" if file_path.is_dir() else "file",
                    "size": stat.st_size,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "created": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "accessed": datetime.fromtimestamp(stat.st_atime, UTC).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:]
                }
            }
        except Exception as e:
            logger.error(f"Get file info error: {e}")
            return {
                "status": "error",
                "message": f"Get file info error: {str(e)}"
            }

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Handle tool calls"""
        try:
            if tool_name == "read_file":
                return await self.read_file(**args)
            elif tool_name == "write_file":
                return await self.write_file(**args)
            elif tool_name == "list_files":
                return await self.list_files(**args)
            elif tool_name == "search_files":
                return await self.search_files(**args)
            elif tool_name == "delete_file":
                return await self.delete_file(**args)
            elif tool_name == "get_file_info":
                return await self.get_file_info(**args)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "status": "error",
                "message": f"Tool execution error: {str(e)}"
            }


# Entry point for MCP server
if __name__ == "__main__":
    import asyncio

    # Example usage
    config = {
        "allowed_paths": ["/home/user/documents", "/tmp"]
    }

    plugin = FileSystemPlugin(config)

    # Test
    result = asyncio.run(plugin.list_files("/home/user/documents"))
    print(result)
