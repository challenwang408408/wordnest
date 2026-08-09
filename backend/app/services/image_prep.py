"""内存中压缩/缩放上传图片，供 OCR 使用；不落盘。"""

from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError


class InvalidImageError(ValueError):
    """上传内容无法解码为受支持的图片。"""


def prepare_image_data_url(
    raw: bytes,
    mime: str,
    *,
    max_side: int = 1600,
    max_bytes: int = 5 * 1024 * 1024,
) -> str:
    """缩放并重新编码图片，返回 data URL。无法解码时拒绝伪装的图片内容。"""
    try:
        with Image.open(BytesIO(raw)) as img:
            img.load()
            working = img.convert("RGB") if img.mode not in {"RGB", "L"} else img.copy()
            if working.mode == "L":
                working = working.convert("RGB")
            w, h = working.size
            longest = max(w, h)
            if longest > max_side:
                scale = max_side / longest
                working = working.resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS,
                )
            out = BytesIO()
            # jpeg 体积更稳；原 gif/webp/png 也转 jpeg 以便控制大小
            working.save(out, format="JPEG", quality=85, optimize=True)
            payload = out.getvalue()
            if len(payload) > max_bytes:
                out = BytesIO()
                working.save(out, format="JPEG", quality=70, optimize=True)
                payload = out.getvalue()
            b64 = base64.b64encode(payload).decode("ascii")
            return f"data:image/jpeg;base64,{b64}"
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("上传内容不是可读取的图片") from exc
