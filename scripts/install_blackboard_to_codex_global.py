#!/usr/bin/env python3
"""install_blackboard_to_codex_global.py
把 blackboard MCP server 写进 Codex 全局配置 ~/.codex/config.toml。

背景:Codex 运行时会持续回写 config.toml,运行中修改会被覆盖。
所以本脚本在写入前检测 Codex 进程,只有全部关闭时才写,写完立即校验。

用法:
    python scripts/install_blackboard_to_codex_global.py          # 实际写入
    python scripts/install_blackboard_to_codex_global.py --check  # 只检测不写
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

GLOBAL_CFG = Path.home() / ".codex" / "config.toml"

# 用全英文路径:系统 Python + launcher。项目在中文路径下,config.toml 对中文
# 路径有 UTF-8/GBK 编码损坏问题,故经 launcher 间接启动真实 server。
# launcher: C:\Users\canqu\codex_blackboard.py (启动 <repo>/scripts/mcp_blackboard_server.py)
SYSTEM_PY = r"C:\Users\canqu\AppData\Local\Microsoft\WindowsApps\python.exe"
LAUNCHER = r"C:\Users\canqu\codex_blackboard.py"

# 用 TOML 单引号 literal string:反斜杠不转义,避免 \U 被 TOML 当 hex 转义报错
BLACKBOARD_SEGMENT = (
    "\n[mcp_servers.blackboard]\n"
    "command = '" + SYSTEM_PY + "'\n"
    "args = ['" + LAUNCHER + "']\n"
)


def codex_running() -> list[str]:
    """返回正在运行的 Codex 进程列表(PID + 名字)。"""
    import subprocess
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Where-Object { $_.ProcessName -match 'Codex' } "
             "| Select-Object Id,ProcessName | Format-Table -AutoSize -HideTableHeaders"],
            text=True, encoding="utf-8", errors="replace", timeout=20,
        ).strip()
    except Exception:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检测,不写入")
    args = ap.parse_args()

    procs = codex_running()
    if procs:
        print(f"❌ 检测到 {len(procs)} 个 Codex 进程在运行:")
        for p in procs:
            print(f"   {p}")
        print("\n请先完全关闭所有 Codex 窗口(包括托盘),再跑本脚本。")
        return 1

    print("✅ 未检测到 Codex 进程在运行,可以安全写入。")

    if not GLOBAL_CFG.exists():
        print(f"❌ 全局配置不存在: {GLOBAL_CFG}")
        return 2

    txt = GLOBAL_CFG.read_text(encoding="utf-8")

    # 校验现有 blackboard 段是否已是全英文路径(正确)
    already_correct = (
        "[mcp_servers.blackboard]" in txt
        and LAUNCHER in txt
        and SYSTEM_PY in txt
    )
    if already_correct:
        print("✅ blackboard 段已存在且为全英文路径,无需修改。")
        return _validate(txt)

    if "[mcp_servers.blackboard]" in txt:
        # 存在旧段(可能是中文路径损坏段),先删掉
        print("⚠️  检测到旧的 blackboard 段(可能路径损坏),将替换。")
        txt = _strip_section(txt, "mcp_servers.blackboard")

    if args.check:
        print("--check 模式:不写入。blackboard 段需写入/替换。")
        return 3

    # 追加(确保前面有换行分隔)
    if not txt.endswith("\n"):
        txt += "\n"
    txt += BLACKBOARD_SEGMENT
    GLOBAL_CFG.write_text(txt, encoding="utf-8")
    print(f"✅ 已写入 blackboard 段(全英文路径)到 {GLOBAL_CFG}")

    return _validate(GLOBAL_CFG.read_text(encoding="utf-8"))


def _strip_section(txt: str, section: str) -> str:
    """从 TOML 文本里删除 [section] 及其后续同级键,直到下一个 [...] 段或文件尾。"""
    import re
    # 匹配 [section] 到下一个 [ 开头的段(或文件尾)
    pattern = re.compile(
        r"^\[" + re.escape(section) + r"\].*?(?=^\[|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    return pattern.sub("", txt).rstrip() + "\n"


def _validate(txt: str) -> int:
    try:
        import tomllib
        d = tomllib.loads(txt)
        servers = list(d.get("mcp_servers", {}).keys())
        print(f"✅ TOML 校验通过。mcp_servers = {servers}")
        if "blackboard" in servers:
            print("✅ blackboard 已在全局配置中。现在可以重启 Codex 了。")
            return 0
        print("❌ blackboard 未出现在配置中。")
        return 4
    except Exception as e:
        print(f"❌ TOML 校验失败: {e}")
        return 5


if __name__ == "__main__":
    sys.exit(main())
