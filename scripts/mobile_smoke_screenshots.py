#!/usr/bin/env python3
"""词芽移动端主路径截图与横向溢出门禁。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv(
    "WORDNEST_BASE_URL",
    "http://127.0.0.1:8000/projects/wordnest",
).rstrip("/")
ACCESS_CODE = os.getenv("WORDNEST_ACCESS_CODE")
PROFILE_NAME = os.getenv("WORDNEST_PROFILE_NAME", "哥哥")
SHOTS = Path(
    os.getenv(
        "WORDNEST_SMOKE_SHOTS",
        str(ROOT / "screenshots" / "mobile-smoke"),
    )
)


def assert_no_horizontal_overflow(page: Page, label: str) -> None:
    result = page.evaluate(
        """() => {
          const doc = document.documentElement;
          return {
            clientWidth: doc.clientWidth,
            scrollWidth: doc.scrollWidth,
            offenders: [...document.querySelectorAll('body *')]
              .filter((node) => {
                const rect = node.getBoundingClientRect();
                return rect.left < -1 || rect.right > doc.clientWidth + 1;
              })
              .slice(0, 6)
              .map((node) => ({
                tag: node.tagName,
                className: typeof node.className === 'string' ? node.className : '',
                text: (node.textContent || '').trim().slice(0, 40),
              })),
          };
        }"""
    )
    if result["scrollWidth"] > result["clientWidth"] + 1:
        raise AssertionError(f"{label} 横向溢出: {result}")


def capture(page: Page, name: str) -> None:
    assert_no_horizontal_overflow(page, name)
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)


def main() -> None:
    if not ACCESS_CODE:
        raise SystemExit("请通过 WORDNEST_ACCESS_CODE 提供家庭访问码")

    SHOTS.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        page.goto(f"{BASE}/login", wait_until="networkidle")
        capture(page, "01-login-390")
        page.fill("#access", ACCESS_CODE)
        page.get_by_role("button", name="进入词芽").click()
        page.wait_for_url("**/select")
        profile_button = page.get_by_role("button", name=re.compile(PROFILE_NAME))
        profile_button.wait_for(state="visible")
        capture(page, "02-select-390")

        profile_button.click()
        page.wait_for_url("**/app/*")
        page.get_by_role("heading", name="今日挑战").wait_for()
        home_url = page.url.rstrip("/")
        capture(page, "03-home-390")

        page.goto(f"{home_url}/words", wait_until="networkidle")
        page.get_by_role("heading", name="词库", exact=True).wait_for()
        capture(page, "04-words-390")

        page.goto(f"{home_url}/me", wait_until="networkidle")
        page.get_by_role("heading", name="家长看板").wait_for()
        capture(page, "05-parent-390")

        page.set_viewport_size({"width": 195, "height": 422})
        narrow_routes = [
            (home_url, "今日挑战", "06-home-195"),
            (f"{home_url}/words", "词库", "07-words-195"),
            (f"{home_url}/me", "家长看板", "08-parent-195"),
        ]
        for url, heading, name in narrow_routes:
            page.goto(url, wait_until="networkidle")
            page.get_by_role("heading", name=heading, exact=True).wait_for()
            capture(page, name)

        browser.close()

    if console_errors:
        raise AssertionError(f"浏览器 console error: {console_errors}")
    print(f"移动端冒烟通过，截图写入 {SHOTS}")


if __name__ == "__main__":
    main()
