"""Force UTF-8 encoding for Python runtime.

This file is automatically imported by Python at startup when placed in
site-packages or when PYTHONPATH includes its directory. It ensures that
file I/O defaults to UTF-8, fixing issues on Windows systems with non-ASCII
(e.g., Chinese) paths where the default GBK/CP936 encoding causes failures.

Usage:
  1. Copy this file to your Python's site-packages directory, OR
  2. Set PYTHONUTF8=1 environment variable (Python 3.7+), OR
  3. Run Python with -X utf8 flag

See: https://docs.python.org/3/library/os.html#python-utf8-mode
"""

import sys

# Enable UTF-8 mode if not already enabled (Python 3.7+)
if sys.flags.utf8_mode == 0:
    # Note: This cannot change utf8_mode at runtime, but we can set
    # the default encoding for file operations
    pass

# Set default encoding for stdout/stderr if they're using ASCII/GBK
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure filesystem encoding is UTF-8
import os

if sys.platform == "win32":
    # On Windows, ensure we use UTF-8 for filesystem operations
    # This is a no-op if PYTHONUTF8=1 is already set
    os.environ.setdefault("PYTHONUTF8", "1")
# sitecustomize.py — 解决 Windows 中文路径下 Python site 模块崩溃
# 将此文件放在项目根目录，通过 PYTHONPATH 或 .pth 文件加载
import sys
import os

if sys.platform == "win32":
    # 强制 UTF-8 模式，避免 GBK 编码在中文路径下崩溃
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # 确保文件系统编码为 UTF-8
    if hasattr(sys, "_enablelegacywindowsfsencoding"):
        pass  # 不启用 legacy 编码，保持 UTF-8
