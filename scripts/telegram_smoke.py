"""Telegram 消息网关真机冒烟脚本。

用法（需先申请 bot token，@BotFather）：

    # 1. 完整冒烟：getMe 验 token → 网关 API 注册 → webhook/轮询路径说明
    XAGENT_TELEGRAM_BOT_TOKEN=123456:ABC... python scripts/telegram_smoke.py

    # 2. 只验 token 有效性
    python scripts/telegram_smoke.py --check-only

    # 3. 后端不在线时只做 token + webhook 设置检查
    python scripts/telegram_smoke.py --api-url http://localhost:8000 --api-key bootstrap

退出码：0 全部通过 / 1 失败（原因见输出）。不发送任何消息给真实用户
（getMe 只读；webhook 设置是幂等配置操作，需显式 --set-webhook 才执行）。
"""

from __future__ import annotations

import argparse
import os
import sys

BASE = "https://api.telegram.org"


def check_token(token: str) -> dict:
    import httpx

    resp = httpx.get(f"{BASE}/bot{token}/getMe", timeout=15)
    data = resp.json()
    if resp.status_code != 200 or not data.get("ok"):
        raise SystemExit(
            f"[FAIL] getMe 无效：HTTP {resp.status_code} {data.get('description', '')}\n"
            "       请检查 token（@BotFather /mybots → API Token）"
        )
    me = data["result"]
    print(f"[OK] token 有效：@{me.get('username')} (id={me.get('id')})")
    return me


def check_webhook(token: str, expected: str | None) -> None:
    import httpx

    resp = httpx.get(f"{BASE}/bot{token}/getWebhookInfo", timeout=15)
    info = resp.json().get("result", {})
    url = info.get("url") or ""
    pending = info.get("pending_update_count", 0)
    if not url:
        print(f"[WARN] 未设置 webhook（当前轮询模式，pending={pending}）")
        print("       网关 register+start 后由 Telegram 侧推送；或显式 --set-webhook <公网URL>")
    else:
        print(f"[OK] webhook: {url} (pending={pending}, last_error={info.get('last_error_message') or '无'})")
    if expected and url and not url.startswith(expected):
        print(f"[WARN] webhook 指向 {url}，与期望 {expected} 不一致")


def set_webhook(token: str, url: str) -> None:
    import httpx

    resp = httpx.post(f"{BASE}/bot{token}/setWebhook", json={"url": url}, timeout=15)
    data = resp.json()
    if data.get("ok"):
        print(f"[OK] webhook 已设置: {url}")
    else:
        raise SystemExit(f"[FAIL] setWebhook: {data.get('description')}")


def check_backend(api_url: str, api_key: str) -> None:
    """后端网关 API 冒烟：注册 telegram（走 webhook 体系的 400 可诊断路径）+ 状态。"""
    import httpx

    client = httpx.Client(base_url=api_url.rstrip("/"), headers={"x-api-key": api_key}, timeout=15)
    health = client.get("/health")
    if health.status_code != 200:
        raise SystemExit(f"[FAIL] 后端 /health {health.status_code}（先启动 backend）")
    print(f"[OK] 后端在线: {api_url}")

    status = client.get("/api/v1/channels/gateway/status")
    print(f"[INFO] gateway status: HTTP {status.status_code} {status.text[:200]}")
    if status.status_code == 200:
        running = status.json().get("running")
        print(f"[{'OK' if running else 'WARN'}] gateway.running={running}"
              f"{'（POST /gateway/start 启动）' if not running else ''}")
    else:
        print("[INFO] status 不可达——确认 backend 版本包含 gateway 端点（2026-09-06 批次）")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check-only", action="store_true", help="只验 token，不碰后端")
    parser.add_argument("--api-url", default=os.environ.get("XAGENT_API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("XAGENT_API_KEY", "bootstrap"))
    parser.add_argument("--set-webhook", metavar="URL", help="显式设置 webhook 到公网 URL")
    args = parser.parse_args()

    token = os.environ.get("XAGENT_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "[FAIL] 未设置 XAGENT_TELEGRAM_BOT_TOKEN\n"
            "       @BotFather → /newbot → 复制 token 后重试"
        )

    check_token(token)
    check_webhook(token, None)
    if args.set_webhook:
        set_webhook(token, args.set_webhook)
    if not args.check_only:
        check_backend(args.api_url, args.api_key)
    print("[DONE] 冒烟完成")


if __name__ == "__main__":
    sys.exit(main())
