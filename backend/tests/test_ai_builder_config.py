from __future__ import annotations

from types import SimpleNamespace

from backend.app.config import Settings
from backend.app.services.ai_builder import HttpAIBuilderClient


def test_batch_enrichment_uses_configured_gemini_model() -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '[{"spelling":"planet","meaning_zh":"行星",'
                            '"part_of_speech":"n.","ipa":"/ˈplænɪt/",'
                            '"syllables":"plan·et","example_en":"A planet moves.",'
                            '"example_zh":"行星会运行。"}]'
                        )
                    )
                )
            ]
        )

    settings = Settings(
        FAMILY_ACCESS_CODE="test-family-code",
        SESSION_SECRET="test-session-secret-32chars!!",
        AI_BUILDER_TOKEN="test-token",
        AI_ENRICH_MODEL="gemini-3-flash-preview",
    )
    client = HttpAIBuilderClient(settings)
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )

    result = client.enrich_words(["planet", "forest"])

    assert captured["model"] == "gemini-3-flash-preview"
    assert [item.spelling for item in result] == ["planet", "forest"]


def test_enrichment_defaults_to_gemini_flash() -> None:
    settings = Settings(
        FAMILY_ACCESS_CODE="test-family-code",
        SESSION_SECRET="test-session-secret-32chars!!",
        AI_BUILDER_TOKEN="test-token",
        _env_file=None,
    )

    assert settings.ai_enrich_model == "gemini-3-flash-preview"
