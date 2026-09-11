from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.services.ai_builder import (
    HttpAIBuilderClient,
    VOICE_WORD_PROMPT,
    normalize_voice_words,
)


def test_normalize_voice_words_keeps_order_and_supported_punctuation() -> None:
    transcript = "Apple, banana, APPLE, can't, mother-in-law。中文"
    assert normalize_voice_words(transcript) == [
        "apple",
        "banana",
        "can't",
        "mother-in-law",
    ]


def test_voice_transcription_requires_login(client: TestClient) -> None:
    response = client.post(
        "/api/wordnest/profiles/1/words/transcribe-voice",
        files={"file": ("recording.webm", b"audio", "audio/webm")},
    )
    assert response.status_code == 401


def test_voice_transcription_returns_words_without_persisting(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    profile_id = profiles["brother"]
    response = auth_client.post(
        f"/api/wordnest/profiles/{profile_id}/words/transcribe-voice",
        files={"file": ("recording.webm", b"audio", "audio/webm;codecs=opus")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "words": ["apple", "banana"],
        "text": "apple, banana",
        "request_id": "mock-voice-request",
    }
    assert auth_client.get(
        f"/api/wordnest/profiles/{profile_id}/words"
    ).json() == []


def test_voice_transcription_accepts_raw_audio_bytes_from_mobile_webview(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    profile_id = profiles["brother"]
    response = auth_client.post(
        f"/api/wordnest/profiles/{profile_id}/words/transcribe-voice",
        content=b"recorded-audio",
        headers={"content-type": "audio/mp4"},
    )

    assert response.status_code == 200
    assert response.json()["words"] == ["apple", "banana"]


def test_voice_transcription_rejects_invalid_or_large_upload(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    profile_id = profiles["brother"]
    bad_mime = auth_client.post(
        f"/api/wordnest/profiles/{profile_id}/words/transcribe-voice",
        files={"file": ("recording.txt", b"audio", "text/plain")},
    )
    assert bad_mime.status_code == 400
    assert "录音" in bad_mime.json()["detail"]

    empty = auth_client.post(
        f"/api/wordnest/profiles/{profile_id}/words/transcribe-voice",
        files={"file": ("recording.webm", b"", "audio/webm")},
    )
    assert empty.status_code == 400
    assert "空" in empty.json()["detail"]

    oversized = auth_client.post(
        f"/api/wordnest/profiles/{profile_id}/words/transcribe-voice",
        files={
            "file": (
                "recording.webm",
                b"0" * (8 * 1024 * 1024 + 1),
                "audio/webm",
            )
        },
    )
    assert oversized.status_code == 400
    assert "8MB" in oversized.json()["detail"]


def test_http_voice_client_sends_english_prompt_and_normalizes(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs) -> httpx.Response:
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={
                "request_id": "req_voice_123",
                "text": "Apple, banana, apple, mother-in-law",
            },
        )

    monkeypatch.setattr("backend.app.services.ai_builder.httpx.post", fake_post)
    settings = Settings(
        FAMILY_ACCESS_CODE="test-family-code",
        SESSION_SECRET="test-session-secret-32chars!!",
        AI_BUILDER_TOKEN="test-token",
    )
    client = HttpAIBuilderClient(settings)
    result = client.transcribe_words(b"audio", "audio/webm")

    assert captured["url"] == (
        "https://space.ai-builders.com/backend/v1/audio/transcriptions"
    )
    assert captured["data"] == {"language": "en", "prompt": VOICE_WORD_PROMPT}
    assert captured["headers"] == {"Authorization": "Bearer test-token"}
    assert result.words == ["apple", "banana", "mother-in-law"]
    assert result.text == "apple, banana, mother-in-law"
    assert result.request_id == "req_voice_123"
