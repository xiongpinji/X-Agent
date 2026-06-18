#!/usr/bin/env python3
"""dispatch_to_codex.py —— ZCode 同步调用本机 Codex 的薄封装。

用途
----
ZCode 在会话内需要 Codex 立即执行某任务并返回结果时,用本脚本调起
`codex exec`(非交互模式),把 Codex 的最终回复落盘并打印,供 ZCode 读回。

这构成 ZCode → Codex 方向的**同步直连**通道,与 MCP 黑板的双向异步通道互补。

用法
----
    # 直接传 prompt
    python scripts/dispatch_to_codex.py "修复 sessions.py 的越权, 见 FIX_TASKS.md#P0-02"

    # 从 stdin 读 prompt(长文本友好)
    echo "请做 X" | python scripts/dispatch_to_codex.py -

    # 指定超时(秒)和工作目录
    python scripts/dispatch_to_codex.py --timeout 300 --cd "D:/repo" "prompt"

输出
----
- stdout: Codex 的最终回复全文
- 同时落盘到 audit_reports/_comm/_codex_last.txt(便于 ZCode 工具读取)
- 退出码: 0 成功; 非0 失败(stderr 含原因)

注意
----
- 不传 --sandbox,默认让 codex exec 用其配置的策略(workspace-write)。
  如需只读分析,加 --sandbox read-only。
- 不自动加 --dangerously-bypass-approvals-and-sandbox,避免误开全权限。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAST_MSG_FILE = REPO_ROOT / "audit_reports" / "_comm" / "_codex_last.txt"


def _find_codex() -> str | None:
    """探测 codex 可执行文件。Windows 上 subprocess 不自动解析 .cmd 扩展名,
    需要显式找到 codex.cmd 或用 shell=True。"""
    # 优先用 shutil.which(会考虑 PATHEXT)
    for name in ("codex", "codex.cmd", "codex.exe"):
        found = shutil.which(name)
        if found:
            return found
    # 常见 npm 全局路径兜底
    npm_global = Path(os.environ.get("APPDATA", "")) / "npm"
    for cand in (npm_global / "codex.cmd", npm_global / "codex"):
        if cand.exists():
            return str(cand)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="同步调用本机 codex exec")
    ap.add_argument("prompt", nargs="?", default=None, help="给 Codex 的指令;- 表示从 stdin 读")
    ap.add_argument("--timeout", type=int, default=600, help="超时秒数(默认 600)")
    ap.add_argument("--cd", default=str(REPO_ROOT), help="Codex 工作根目录(默认仓库根)")
    ap.add_argument("--sandbox", default=None, help="sandbox 策略 read-only/workspace-write/danger-full-access")
    ap.add_argument("--json", action="store_true", help="让 codex 输出 JSONL 事件流")
    ap.add_argument("--resume", default=None, metavar="SESSION_ID",
                    help="复用指定 Codex 会话 ID(用 codex exec resume)。"
                         "不传则起新会话。固定绑定见 audit_reports/_comm/SESSION_BINDINGS.json")
    ap.add_argument("--bypass-sandbox", action="store_true",
                    help="加 --dangerously-bypass-approvals-and-sandbox。"
                         "Codex 桌面版的 windows sandbox 在 resume 时常报 'spawn setup refresh',"
                         "需要 bypass 才能跑 Bash。仅在受信本机协作场景使用。")
    args = ap.parse_args()

    # 解析 prompt
    if args.prompt is None or args.prompt == "-":
        prompt = sys.stdin.read().strip()
    else:
        prompt = args.prompt
    if not prompt:
        sys.stderr.write("error: empty prompt\n")
        return 2

    # 组装 codex 命令
    codex_bin = _find_codex()
    if not codex_bin:
        sys.stderr.write("[dispatch] codex not found on PATH\n")
        return 127

    # resume 模式:codex exec resume <id> <prompt>; 不支持 -s/--sandbox/-C
    # 会话本身已绑定到原会话的 cwd,无需也无法用 -C 重新指定
    if args.resume:
        cmd = [codex_bin, "exec", "resume", "--skip-git-repo-check"]
        if args.bypass_sandbox:
            cmd += ["--dangerously-bypass-approvals-and-sandbox"]
        if args.json:
            cmd += ["--json"]
        LAST_MSG_FILE.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(LAST_MSG_FILE)]
        cmd += [args.resume, prompt]
        mode = f"resume {args.resume}"
    else:
        cmd = [codex_bin, "exec", "--skip-git-repo-check"]
        cmd += ["-C", str(args.cd)]
        if args.sandbox:
            cmd += ["-s", args.sandbox]
        if args.json:
            cmd += ["--json"]
        LAST_MSG_FILE.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(LAST_MSG_FILE)]
        cmd += [prompt]
        mode = "new session"

    # Windows 下 .cmd 必须经 shell 调用;其他平台直接执行
    use_shell = sys.platform == "win32" and codex_bin.lower().endswith(".cmd")

    sys.stderr.write(f"[dispatch] running: {codex_bin} ({mode}, timeout={args.timeout}s)\n")

    # 用 Popen 而非 run:codex.cmd 在 Windows 上输出完最后消息后进程可能不干净退出,
    # 死等 wait() 会拖到超时。改为轮询 -o 落盘文件,拿到结果即主动收尾。
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=use_shell,
    )

    # 清掉上次的落盘文件,以便区分本次新输出
    if LAST_MSG_FILE.exists():
        LAST_MSG_FILE.unlink()

    import time
    deadline = time.monotonic() + args.timeout
    last_msg = ""
    while True:
        # 进程已退出
        if proc.poll() is not None:
            break
        # 检查落盘文件是否已有新内容
        if LAST_MSG_FILE.exists():
            content = LAST_MSG_FILE.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                last_msg = content
                break
        if time.monotonic() > deadline:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            sys.stderr.write(f"[dispatch] TIMEOUT after {args.timeout}s\n")
            # 即便超时,若已有落盘也一并输出
            if last_msg:
                print(last_msg)
            return 124
        time.sleep(1.0)

    # 收尾:确保进程结束,收集剩余输出
    try:
        stdout, stderr = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    rc = proc.returncode if proc.returncode is not None else 0

    if not last_msg and LAST_MSG_FILE.exists():
        last_msg = LAST_MSG_FILE.read_text(encoding="utf-8", errors="replace").strip()

    if rc != 0:
        sys.stderr.write(f"[dispatch] codex exit={rc}\n")
        if stderr:
            sys.stderr.write(stderr[-2000:] + "\n")

    # 打印结果:优先落盘文件,其次原始 stdout
    output = last_msg or (stdout or "").strip()
    if output:
        print(output)
    else:
        sys.stderr.write("[dispatch] no output from codex\n")

    return rc


if __name__ == "__main__":
    sys.exit(main())
