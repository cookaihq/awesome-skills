"""Open a visible Chromium at xiaohongshu.com so the user can scan the QR code.

Polls until a non-empty `web_session` cookie appears, then prints the full cookie
string (k=v; k=v) to stdout. MUST run inside the XHS .venv (playwright installed
there). stderr carries human prompts; stdout carries ONLY the cookie string.
"""
from __future__ import annotations

import argparse
import sys
import time

LOGIN_URL = "https://www.xiaohongshu.com/explore"


def _mask(s: str) -> str:
    return "****" if len(s) <= 8 else f"{s[:4]}****{s[-4:]}"


def main() -> int:
    ap = argparse.ArgumentParser(description="XHS QR login -> cookie string")
    ap.add_argument("--timeout", type=int, default=180, help="seconds to wait for login")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "未安装 playwright。请在 XHS venv 执行：pip install playwright "
            "&& python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    web_session = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        print(
            "已打开浏览器，请用小红书 App 扫码登录（无需也不要输入账号密码）……",
            file=sys.stderr,
        )

        deadline = time.time() + args.timeout
        cookie_str = ""
        while time.time() < deadline:
            cookies = context.cookies()
            web_session = next(
                (c for c in cookies if c.get("name") == "web_session"), None
            )
            if web_session and web_session.get("value"):
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies if c.get("value")
                )
                break
            time.sleep(2)
        browser.close()

    if not cookie_str:
        print("登录超时，未获取到 web_session", file=sys.stderr)
        return 1

    print(cookie_str, flush=True)
    print(f"✓ 已获取 Cookie（web_session={_mask(web_session['value'])}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
