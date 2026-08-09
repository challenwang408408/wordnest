from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status
from openai import OpenAI
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.schemas import EnrichResult, ScanCandidate, ScanResult

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

ENRICH_SYSTEM = """你是小学英语学习助手。根据用户给出的英语单词，返回严格 JSON（不要 Markdown），字段：
spelling（标准小写拼写，专有名词可保留大小写）,
meaning_zh（一个核心中文释义）,
part_of_speech（词性，如 n./v./adj.）,
ipa（美式 IPA，可带斜杠）,
syllables（美式自然拼读音节，用 · 分隔，如 beau·ti·ful）,
example_en（一句简短英文例句）,
example_zh（对应中文翻译）。
只返回 JSON 对象。"""

ENRICH_BATCH_SYSTEM = """你是小学英语学习助手。根据用户给出的多个英语单词，返回严格 JSON 数组（不要 Markdown）。
数组每个元素字段：
spelling（标准小写拼写，专有名词可保留大小写）,
meaning_zh（一个核心中文释义）,
part_of_speech（词性，如 n./v./adj.）,
ipa（美式 IPA，可带斜杠）,
syllables（美式自然拼读音节，用 · 分隔，如 beau·ti·ful）,
example_en（一句简短英文例句）,
example_zh（对应中文翻译）。
每个输入词都要有一条结果；顺序尽量与输入一致。只返回 JSON 数组。"""

SCAN_SYSTEM = """你是小学英语阅读助手。从图片中提取适合小学生学习的英语单词。
返回严格 JSON（不要 Markdown）：{"candidates":[{"spelling":"...","meaning_zh":"可选中文"}]}。
只提取清晰可见的英语单词，去重，最多 20 个。不要编造图片里没有的词。"""


class AIBuilderClient(Protocol):
    def enrich_word(self, spelling: str) -> EnrichResult: ...

    def enrich_words(self, spellings: list[str]) -> list[EnrichResult]: ...

    def scan_image(self, data_url: str, mime: str) -> ScanResult: ...


def _placeholder_enrich(spelling: str) -> EnrichResult:
    return EnrichResult(
        spelling=spelling.strip(),
        meaning_zh="",
        part_of_speech="",
        ipa="",
        syllables="",
        example_en="",
        example_zh="",
    )


def merge_batch_enrich_results(
    spellings: list[str], items: list[EnrichResult]
) -> list[EnrichResult]:
    """按输入顺序对齐结果；AI 漏掉的词用可编辑空草稿补上。"""
    by_key: dict[str, EnrichResult] = {}
    for item in items:
        key = item.spelling.strip().lower()
        if key and key not in by_key:
            by_key[key] = item
    merged: list[EnrichResult] = []
    for spelling in spellings:
        key = spelling.strip().lower()
        found = by_key.get(key)
        if found is not None:
            merged.append(found)
        else:
            merged.append(_placeholder_enrich(spelling))
    return merged


def strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = FENCE_RE.sub("", cleaned).strip()
    return cleaned


def parse_json_payload(text: str) -> Any:
    cleaned = strip_markdown_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 返回的内容不是有效 JSON，请重试或手工补充",
        ) from exc


class HttpAIBuilderClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.ai_builder_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="未配置 AI_BUILDER_TOKEN，无法调用 AI 补全",
            )
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.ai_builder_token,
            base_url=settings.ai_base_url,
            timeout=settings.ai_timeout_seconds,
        )

    def enrich_word(self, spelling: str) -> EnrichResult:
        try:
            completion = self.client.chat.completions.create(
                model="grok-4.5",
                messages=[
                    {"role": "system", "content": ENRICH_SYSTEM},
                    {"role": "user", "content": spelling},
                ],
                temperature=0.3,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI 补全超时，请稍后重试",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 补全服务暂时不可用，请手工补充或稍后重试",
            ) from exc

        content = completion.choices[0].message.content or ""
        payload = parse_json_payload(content)
        try:
            return EnrichResult.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 返回字段不完整，请重试或手工补充",
            ) from exc

    def enrich_words(self, spellings: list[str]) -> list[EnrichResult]:
        if len(spellings) == 1:
            return [self.enrich_word(spellings[0])]
        try:
            completion = self.client.chat.completions.create(
                model="grok-4.5",
                messages=[
                    {"role": "system", "content": ENRICH_BATCH_SYSTEM},
                    {
                        "role": "user",
                        "content": "请补全这些单词：\n"
                        + "\n".join(f"- {s}" for s in spellings),
                    },
                ],
                temperature=0.3,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI 批量补全超时，请减少词数后重试",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 补全服务暂时不可用，请手工补充或稍后重试",
            ) from exc

        content = completion.choices[0].message.content or ""
        payload = parse_json_payload(content)
        if isinstance(payload, dict) and "items" in payload:
            payload = payload["items"]
        if not isinstance(payload, list):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 批量补全返回格式无效，请重试或手工补充",
            )
        parsed: list[EnrichResult] = []
        for item in payload:
            try:
                parsed.append(EnrichResult.model_validate(item))
            except ValidationError:
                # 单条坏数据跳过，后面用空草稿对齐
                continue
        if not parsed:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 批量补全没有可用结果，请重试或手工补充",
            )
        return merge_batch_enrich_results(spellings, parsed)

    def scan_image(self, data_url: str, mime: str) -> ScanResult:
        del mime  # 已在上游校验
        try:
            completion = self.client.chat.completions.create(
                model="kimi-k2.5",
                messages=[
                    {"role": "system", "content": SCAN_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请提取图片中适合小学生的英语单词。",
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                temperature=1.0,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="图片识别超时，请换一张更清晰的照片或手工录入",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="图片识别暂时不可用，请稍后重试或手工录入",
            ) from exc

        content = completion.choices[0].message.content or ""
        payload = parse_json_payload(content)
        try:
            if isinstance(payload, list):
                candidates = [ScanCandidate.model_validate(item) for item in payload]
                return ScanResult(candidates=candidates)
            return ScanResult.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="图片识别结果格式无效，请重试",
            ) from exc


class MockAIBuilderClient:
    def enrich_word(self, spelling: str) -> EnrichResult:
        base = spelling.strip().lower()
        return EnrichResult(
            spelling=base,
            meaning_zh=f"{base}的意思",
            part_of_speech="n.",
            ipa=f"/{base}/",
            syllables="·".join(base[i : i + 2] or base for i in range(0, len(base), 2))
            or base,
            example_en=f"I like {base}.",
            example_zh=f"我喜欢{base}。",
        )

    def enrich_words(self, spellings: list[str]) -> list[EnrichResult]:
        return [self.enrich_word(s) for s in spellings]

    def scan_image(self, data_url: str, mime: str) -> ScanResult:
        del data_url, mime
        return ScanResult(
            candidates=[
                ScanCandidate(spelling="apple", meaning_zh="苹果"),
                ScanCandidate(spelling="book", meaning_zh="书"),
            ]
        )


_ai_client: AIBuilderClient | None = None


def get_ai_client(settings: Settings) -> AIBuilderClient:
    global _ai_client
    if _ai_client is not None:
        return _ai_client
    return HttpAIBuilderClient(settings)


def set_ai_client(client: AIBuilderClient | None) -> None:
    global _ai_client
    _ai_client = client
