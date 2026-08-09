#!/usr/bin/env python3
"""真实 AI Builders smoke：需显式设置 RUN_AI_SMOKE=1 与 AI_BUILDER_TOKEN。"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _make_ocr_sample() -> Path:
    from PIL import Image, ImageDraw

    fixtures = ROOT / "scripts" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    out = fixtures / "ocr_sample.png"
    img = Image.new("RGB", (640, 360), (250, 252, 250))
    draw = ImageDraw.Draw(img)
    draw.text((40, 80), "apple banana book", fill=(23, 53, 63))
    draw.text((40, 160), "beautiful happy", fill=(49, 92, 107))
    img.save(out)
    return out


def main() -> int:
    _load_dotenv()
    if os.getenv("RUN_AI_SMOKE") != "1":
        print("跳过：请设置 RUN_AI_SMOKE=1 才会调用真实 AI。")
        return 0
    if not os.getenv("AI_BUILDER_TOKEN"):
        print("失败：缺少 AI_BUILDER_TOKEN", file=sys.stderr)
        return 1

    os.environ.setdefault("FAMILY_ACCESS_CODE", "smoke-family-code")
    os.environ.setdefault("SESSION_SECRET", "smoke-session-secret-32chars!!")
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("DATA_DIR", str(ROOT / "data" / "smoke"))

    from backend.app.config import get_settings
    from backend.app.services.ai_builder import HttpAIBuilderClient

    get_settings.cache_clear()
    settings = get_settings()
    client = HttpAIBuilderClient(settings)

    enrich = client.enrich_word("beautiful")
    print("enrich:", enrich.model_dump())
    assert enrich.spelling
    assert enrich.meaning_zh
    assert enrich.syllables

    sample = _make_ocr_sample()
    raw = sample.read_bytes()
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    scan = client.scan_image(data_url, "image/png")
    print("scan candidates:", [c.model_dump() for c in scan.candidates])
    assert len(scan.candidates) >= 1
    print("AI smoke 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
