#!/usr/bin/env python3
"""本地 390x844 关键图与主路径冒烟（不提交）。"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
BASE = "http://127.0.0.1:8000"


def main() -> None:
    SHOTS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.screenshot(path=str(SHOTS / "01_login.png"))

        page.fill("#access", "local-family-code")
        page.click('button[type="submit"]')
        page.wait_for_url("**/select")
        page.screenshot(path=str(SHOTS / "02_select.png"))

        page.get_by_role("button", name="哥哥").click()
        page.wait_for_url("**/app/**")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "03_home.png"))

        page.get_by_role("link", name="录单词").click()
        page.wait_for_url("**/add")
        page.fill("#spellings", "happy")
        page.click('button[type="submit"]')
        page.wait_for_selector("text=保存勾选的", timeout=60000)
        page.screenshot(path=str(SHOTS / "04_add_word.png"))
        page.get_by_role("button", name=re.compile(r"保存勾选的")).click()
        page.wait_for_url("**/words")
        page.screenshot(path=str(SHOTS / "05_words.png"))

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)
        overflow = page.evaluate(
            """() => {
              const doc = document.documentElement;
              return doc.scrollWidth > doc.clientWidth + 1;
            }"""
        )
        print("horizontal_overflow=", overflow)
        print("screenshots written to", SHOTS)
        browser.close()


if __name__ == "__main__":
    main()
