#!/usr/bin/env python3
"""从不响应任何请求的 stdio 假 server —— 验证握手超时 fail-closed。

读取 stdin 保持进程存活，但对 initialize 等一切请求不回包，
客户端必须按启动超时判定握手失败并清理子进程。
"""

import sys
import time

while True:
    line = sys.stdin.readline()
    if not line:
        break
    time.sleep(0.05)

sys.exit(0)
