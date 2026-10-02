from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.services.ai_builder import MockAIBuilderClient, set_ai_client
from backend.app.services.ai_builder import parse_json_payload
from fastapi import HTTPException
import pytest


def test_login_success_and_session(client: TestClient) -> None:
    bad = client.post("/api/wordnest/auth/login", json={"access_code": "wrong"})
    assert bad.status_code == 200
    assert bad.json()["authenticated"] is False

    ok = client.post("/api/wordnest/auth/login", json={"access_code": "test-family-code"})
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True

    session = client.get("/api/wordnest/auth/session")
    assert session.json()["authenticated"] is True

    client.post("/api/wordnest/auth/logout")
    session2 = client.get("/api/wordnest/auth/session")
    assert session2.json()["authenticated"] is False


def test_login_rate_limits_repeated_failures(client: TestClient) -> None:
    for _ in range(5):
        response = client.post(
            "/api/wordnest/auth/login", json={"access_code": "0000"}
        )
        assert response.status_code == 200
        assert response.json()["authenticated"] is False

    blocked = client.post(
        "/api/wordnest/auth/login", json={"access_code": "0000"}
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]
    assert "稍后" in blocked.json()["detail"]


def test_successful_login_clears_failed_attempts(client: TestClient) -> None:
    for _ in range(4):
        client.post("/api/wordnest/auth/login", json={"access_code": "0000"})

    ok = client.post(
        "/api/wordnest/auth/login", json={"access_code": "test-family-code"}
    )
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True

    after_success = client.post(
        "/api/wordnest/auth/login", json={"access_code": "0000"}
    )
    assert after_success.status_code == 200


def test_login_client_key_only_trusts_forwarded_ip_from_loopback_proxy() -> None:
    from starlette.requests import Request

    from backend.app.auth import login_client_key

    direct = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-real-ip", b"198.51.100.9")],
            "client": ("8.8.8.8", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    proxied = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-real-ip", b"198.51.100.9")],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )

    assert login_client_key(direct) == "8.8.8.8"
    assert login_client_key(proxied) == "198.51.100.9"


def test_unauthenticated_blocked(client: TestClient) -> None:
    resp = client.get("/api/wordnest/profiles")
    assert resp.status_code == 401


def test_profile_isolation(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother = profiles["brother"]
    sister = profiles["sister"]

    create = auth_client.post(
        f"/api/wordnest/profiles/{brother}/libraries",
        json={"name": "哥哥专属"},
    )
    assert create.status_code == 201
    lib_id = create.json()["id"]

    sister_libs = auth_client.get(f"/api/wordnest/profiles/{sister}/libraries")
    names = [x["name"] for x in sister_libs.json()]
    assert "哥哥专属" not in names

    # 用哥哥的 library_id 访问妹妹路径应 404
    bad = auth_client.patch(
        f"/api/wordnest/profiles/{sister}/libraries/{lib_id}",
        json={"name": "偷改"},
    )
    assert bad.status_code == 404


def test_library_crud_and_force_delete(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    libs = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()
    default = next(x for x in libs if x["is_default"])

    created = auth_client.post(
        f"/api/wordnest/profiles/{pid}/libraries",
        json={"name": "绘本"},
    )
    assert created.status_code == 201
    lib_id = created.json()["id"]

    renamed = auth_client.patch(
        f"/api/wordnest/profiles/{pid}/libraries/{lib_id}",
        json={"name": "绘本阅读"},
    )
    assert renamed.json()["name"] == "绘本阅读"

    # 默认词库不可删
    assert (
        auth_client.delete(
            f"/api/wordnest/profiles/{pid}/libraries/{default['id']}"
        ).status_code
        == 400
    )

    # 空词库可删
    deleted = auth_client.delete(f"/api/wordnest/profiles/{pid}/libraries/{lib_id}")
    assert deleted.status_code == 200


def test_batch_create_words_commits_as_one_request(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    lib_id = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]["id"]
    response = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/batch",
        json={
            "items": [
                {"spelling": "apple", "meaning_zh": "苹果", "library_ids": [lib_id]},
                {"spelling": "home", "meaning_zh": "家", "library_ids": [lib_id]},
            ]
        },
    )

    assert response.status_code == 201
    assert [item["spelling"] for item in response.json()["items"]] == ["apple", "home"]
    assert len(auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()) == 2


def test_batch_create_words_rejects_whole_invalid_payload(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    lib_id = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]["id"]
    response = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/batch",
        json={
            "items": [
                {"spelling": "apple", "meaning_zh": "苹果", "library_ids": [lib_id]},
                {"spelling": "home", "meaning_zh": "", "library_ids": [lib_id]},
            ]
        },
    )

    assert response.status_code == 422
    assert auth_client.get(f"/api/wordnest/profiles/{pid}/words").json() == []


def test_batch_create_words_rolls_back_after_a_mid_batch_library_error(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    lib_id = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]["id"]
    response = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/batch",
        json={
            "items": [
                {"spelling": "apple", "meaning_zh": "苹果", "library_ids": [lib_id]},
                {"spelling": "home", "meaning_zh": "家", "library_ids": [999999]},
            ]
        },
    )

    assert response.status_code == 400
    assert auth_client.get(f"/api/wordnest/profiles/{pid}/words").json() == []


def test_word_dedupe_keeps_progress(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    libs = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()
    default_id = libs[0]["id"]
    extra = auth_client.post(
        f"/api/wordnest/profiles/{pid}/libraries", json={"name": "课外"}
    ).json()

    first = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "Beautiful",
            "meaning_zh": "美丽的",
            "ipa": "/ˈbjuːtɪfl/",
            "syllables": "beau·ti·ful",
            "library_ids": [default_id],
        },
    )
    assert first.status_code == 201
    word_id = first.json()["id"]

    # 评分后再重复录入
    auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/{word_id}/rate",
        json={"rating": "known"},
    )
    before = auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()[0]
    assert before["progress"]["review_count"] >= 1

    second = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "beautiful",
            "meaning_zh": "美丽的",
            "library_ids": [extra["id"]],
        },
    )
    assert second.status_code == 201
    assert second.json()["id"] == word_id
    assert set(second.json()["library_ids"]) == {default_id, extra["id"]}
    assert second.json()["progress"]["review_count"] == before["progress"]["review_count"]


def test_invalid_ai_json_not_saved(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    class BadAI(MockAIBuilderClient):
        def enrich_word(self, spelling: str):  # type: ignore[override]
            from backend.app.services.ai_builder import parse_json_payload

            parse_json_payload("not-json")

    set_ai_client(BadAI())
    pid = profiles["brother"]
    resp = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich",
        json={"spelling": "cat"},
    )
    assert resp.status_code == 502
    words = auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()
    assert words == []
    set_ai_client(MockAIBuilderClient())


def test_enrich_batch_success_and_dedupe(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    resp = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich-batch",
        json={"spellings": ["Apple", "banana", "apple", "  Cherry  "]},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [x["spelling"] for x in items] == ["apple", "banana", "cherry"]
    assert all(x["meaning_zh"] for x in items)
    assert auth_client.get(f"/api/wordnest/profiles/{pid}/words").json() == []


def test_enrich_batch_rejects_empty_and_over_limit(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    empty = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich-batch",
        json={"spellings": ["  ", ""]},
    )
    assert empty.status_code == 422

    too_many = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich-batch",
        json={"spellings": [f"word{i}" for i in range(21)]},
    )
    assert too_many.status_code == 422


def test_enrich_batch_partial_ai_fills_placeholders(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    from backend.app.schemas import EnrichResult
    from backend.app.services.ai_builder import merge_batch_enrich_results

    class PartialAI(MockAIBuilderClient):
        def enrich_words(self, spellings: list[str]):  # type: ignore[override]
            return merge_batch_enrich_results(
                spellings,
                [
                    EnrichResult(
                        spelling="apple",
                        meaning_zh="苹果",
                        part_of_speech="n.",
                        ipa="/ˈæpl/",
                        syllables="ap·ple",
                        example_en="I eat an apple.",
                        example_zh="我吃一个苹果。",
                    )
                ],
            )

    set_ai_client(PartialAI())
    pid = profiles["sister"]
    resp = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich-batch",
        json={"spellings": ["apple", "zebra"]},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["meaning_zh"] == "苹果"
    assert items[1]["spelling"] == "zebra"
    assert items[1]["meaning_zh"] == ""
    set_ai_client(MockAIBuilderClient())


def test_enrich_batch_invalid_json_not_saved(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    class BadBatchAI(MockAIBuilderClient):
        def enrich_words(self, spellings: list[str]):  # type: ignore[override]
            from backend.app.services.ai_builder import parse_json_payload

            del spellings
            parse_json_payload("not-json")

    set_ai_client(BadBatchAI())
    pid = profiles["brother"]
    resp = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/enrich-batch",
        json={"spellings": ["cat", "dog"]},
    )
    assert resp.status_code == 502
    assert auth_client.get(f"/api/wordnest/profiles/{pid}/words").json() == []
    set_ai_client(MockAIBuilderClient())


def test_parse_json_fence() -> None:
    data = parse_json_payload('```json\n{"spelling":"cat","meaning_zh":"猫"}\n```')
    assert data["spelling"] == "cat"
    with pytest.raises(HTTPException):
        parse_json_payload("@@@")


def test_quiz_selection_and_rating_persist(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    libs = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()
    lib_id = libs[0]["id"]
    for spelling in ("apple", "banana", "cherry"):
        auth_client.post(
            f"/api/wordnest/profiles/{pid}/words",
            json={
                "spelling": spelling,
                "meaning_zh": f"{spelling}义",
                "syllables": spelling,
                "example_en": f"I like {spelling}.",
                "example_zh": f"我喜欢{spelling}义。",
                "library_ids": [lib_id],
            },
        )

    quiz = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/start",
        json={"library_ids": [lib_id], "count": 10},
    )
    assert quiz.status_code == 200
    body = quiz.json()
    assert body["total"] == 3
    for item in body["words"]:
        assert len(item["options"]) == 4
        assert len(set(item["options"])) == 4
        assert item["meaning_zh"] in item["options"]
        assert item["example_en"] == f"I like {item['spelling']}."
        assert item["example_zh"] == f"我喜欢{item['meaning_zh']}。"
    word_id = body["words"][0]["id"]

    rate = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/{word_id}/rate",
        json={"rating": "unknown"},
    )
    assert rate.status_code == 200
    assert rate.json()["review_count"] == 1

    words = auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()
    target = next(w for w in words if w["id"] == word_id)
    assert target["progress"]["last_rating"] == "unknown"


def test_quiz_preview_matches_distinct_unmastered_start_count(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    default_lib = auth_client.get(
        f"/api/wordnest/profiles/{pid}/libraries"
    ).json()[0]
    extra_lib = auth_client.post(
        f"/api/wordnest/profiles/{pid}/libraries", json={"name": "学校阅读"}
    ).json()

    shared = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "shared",
            "meaning_zh": "共享的",
            "library_ids": [default_lib["id"], extra_lib["id"]],
        },
    ).json()
    mastered = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "finished",
            "meaning_zh": "已完成的",
            "library_ids": [default_lib["id"]],
        },
    ).json()
    auth_client.patch(
        f"/api/wordnest/profiles/{pid}/words/{mastered['id']}",
        json={"is_mastered": True},
    )

    body = {"library_ids": [default_lib["id"], extra_lib["id"]], "count": 10}
    preview = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/preview", json=body
    )
    assert preview.status_code == 200
    assert preview.json() == {"available_count": 1, "challenge_count": 1}

    started = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/start", json=body
    ).json()
    assert started["total"] == 1
    assert started["words"][0]["id"] == shared["id"]


def test_quiz_can_target_a_safe_profile_scoped_word_set(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother = profiles["brother"]
    sister = profiles["sister"]
    brother_lib = auth_client.get(
        f"/api/wordnest/profiles/{brother}/libraries"
    ).json()[0]["id"]
    sister_lib = auth_client.get(
        f"/api/wordnest/profiles/{sister}/libraries"
    ).json()[0]["id"]
    keep = auth_client.post(
        f"/api/wordnest/profiles/{brother}/words",
        json={"spelling": "home", "meaning_zh": "家", "library_ids": [brother_lib]},
    ).json()
    skip = auth_client.post(
        f"/api/wordnest/profiles/{brother}/words",
        json={"spelling": "apple", "meaning_zh": "苹果", "library_ids": [brother_lib]},
    ).json()
    foreign = auth_client.post(
        f"/api/wordnest/profiles/{sister}/words",
        json={"spelling": "moon", "meaning_zh": "月亮", "library_ids": [sister_lib]},
    ).json()

    started = auth_client.post(
        f"/api/wordnest/profiles/{brother}/quiz/start",
        json={"word_ids": [keep["id"], foreign["id"]], "count": 10},
    )

    assert started.status_code == 200
    assert [word["id"] for word in started.json()["words"]] == [keep["id"]]
    assert skip["id"] not in [word["id"] for word in started.json()["words"]]


def test_dashboard_reports_seven_day_parent_insights(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother = profiles["brother"]
    sister = profiles["sister"]
    lib_id = auth_client.get(
        f"/api/wordnest/profiles/{brother}/libraries"
    ).json()[0]["id"]

    weak = auth_client.post(
        f"/api/wordnest/profiles/{brother}/words",
        json={"spelling": "home", "meaning_zh": "家", "library_ids": [lib_id]},
    ).json()
    strong = auth_client.post(
        f"/api/wordnest/profiles/{brother}/words",
        json={"spelling": "word", "meaning_zh": "单词", "library_ids": [lib_id]},
    ).json()
    auth_client.post(
        f"/api/wordnest/profiles/{brother}/quiz/{weak['id']}/rate",
        json={"rating": "unknown"},
    )
    auth_client.post(
        f"/api/wordnest/profiles/{brother}/quiz/{strong['id']}/rate",
        json={"rating": "known"},
    )

    dashboard = auth_client.get(
        f"/api/wordnest/profiles/{brother}/dashboard"
    ).json()
    assert dashboard["reviews_7d"] == 2
    assert dashboard["known_reviews_7d"] == 1
    assert dashboard["steady_accuracy_7d"] == 50
    assert dashboard["active_days_7d"] == 1
    assert dashboard["weak_words"][0] == {
        "id": weak["id"],
        "spelling": "home",
        "meaning_zh": "家",
        "review_count": 1,
        "unknown_count": 1,
        "last_rating": "unknown",
    }

    sister_dashboard = auth_client.get(
        f"/api/wordnest/profiles/{sister}/dashboard"
    ).json()
    assert sister_dashboard["reviews_7d"] == 0
    assert sister_dashboard["weak_words"] == []


def test_dashboard_ranks_current_weakness_before_a_recovered_word(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    lib_id = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]["id"]
    recovered = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={"spelling": "home", "meaning_zh": "家", "library_ids": [lib_id]},
    ).json()
    still_weak = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={"spelling": "moon", "meaning_zh": "月亮", "library_ids": [lib_id]},
    ).json()
    auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/{recovered['id']}/rate",
        json={"rating": "unknown"},
    )
    auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/{recovered['id']}/rate",
        json={"rating": "known"},
    )
    auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/{still_weak['id']}/rate",
        json={"rating": "unknown"},
    )

    dashboard = auth_client.get(f"/api/wordnest/profiles/{pid}/dashboard").json()

    assert dashboard["weak_words"][0]["id"] == still_weak["id"]
    assert dashboard["weak_words"][0]["last_rating"] == "unknown"


def test_review_dates_follow_family_timezone() -> None:
    from zoneinfo import ZoneInfo

    from backend.app.api.dashboard import local_review_date

    family_tz = ZoneInfo("Asia/Shanghai")
    before_midnight = datetime(2026, 8, 9, 15, 30, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 8, 9, 16, 30, tzinfo=timezone.utc)

    assert local_review_date(before_midnight, family_tz).isoformat() == "2026-08-09"
    assert local_review_date(after_midnight, family_tz).isoformat() == "2026-08-10"


def test_seven_day_window_uses_exactly_seven_family_calendar_days() -> None:
    from zoneinfo import ZoneInfo

    from backend.app.api.dashboard import family_day_window

    family_tz = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 9, 20, 30, tzinfo=timezone.utc)
    start, end = family_day_window(now, family_tz, days=7)

    assert start == datetime(2026, 8, 3, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 10, 16, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(days=7)


def test_quiz_options_fill_when_library_is_tiny(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    """新词库只有一个词时，也要凑满四选一，否则孩子没得选。"""
    import random

    from backend.app.services.quiz import build_options

    pid = profiles["sister"]
    libs = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()
    lib_id = libs[0]["id"]
    auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "moon",
            "meaning_zh": "月亮",
            "syllables": "moon",
            "library_ids": [lib_id],
        },
    )

    quiz = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/start",
        json={"library_ids": [lib_id], "count": 10},
    )
    only = quiz.json()["words"][0]
    assert len(only["options"]) == 4
    assert len(set(only["options"])) == 4
    assert only["options"].count("月亮") == 1

    # 释义为空的历史脏数据也不能让选项塌成三个
    options = build_options("", [], rng=random.Random(7))
    assert len(set(options)) == 4
    assert "不确定" in options


def test_scan_does_not_persist(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    from io import BytesIO

    from PIL import Image

    pid = profiles["brother"]
    buf = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(buf, format="PNG")
    resp = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/scan",
        files={"file": ("t.png", buf.getvalue(), "image/png")},
    )
    assert resp.status_code == 200
    assert len(resp.json()["candidates"]) >= 1
    assert auth_client.get(f"/api/wordnest/profiles/{pid}/words").json() == []


def test_healthz(client: TestClient) -> None:
    resp = client.get("/api/wordnest/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] in {"ok", "degraded"}


def test_login_cookie_httponly_samesite(client: TestClient) -> None:
    resp = client.post(
        "/api/wordnest/auth/login", json={"access_code": "test-family-code"}
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert "wordnest_session=" in lowered
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "secure" not in lowered  # development


def test_word_cross_profile_blocked(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother = profiles["brother"]
    sister = profiles["sister"]
    libs = auth_client.get(f"/api/wordnest/profiles/{brother}/libraries").json()
    created = auth_client.post(
        f"/api/wordnest/profiles/{brother}/words",
        json={
            "spelling": "secret",
            "meaning_zh": "秘密",
            "library_ids": [libs[0]["id"]],
        },
    )
    word_id = created.json()["id"]
    assert (
        auth_client.patch(
            f"/api/wordnest/profiles/{sister}/words/{word_id}",
            json={"meaning_zh": "偷改"},
        ).status_code
        == 404
    )
    assert (
        auth_client.delete(
            f"/api/wordnest/profiles/{sister}/words/{word_id}"
        ).status_code
        == 404
    )
    sister_words = auth_client.get(f"/api/wordnest/profiles/{sister}/words").json()
    assert all(w["spelling"] != "secret" for w in sister_words)


def test_scan_rejects_bad_mime_and_oversize(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    bad_mime = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/scan",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert bad_mime.status_code == 400
    assert "jpeg" in bad_mime.json()["detail"].lower() or "图片" in bad_mime.json()["detail"]

    huge = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10)
    oversize = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/scan",
        files={"file": ("big.png", huge, "image/png")},
    )
    assert oversize.status_code == 400
    assert "5MB" in oversize.json()["detail"]


def test_scan_rejects_corrupt_image_content(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    corrupt = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words/scan",
        files={"file": ("fake.png", b"this is not an image", "image/png")},
    )
    assert corrupt.status_code == 400
    assert "图片无法读取" in corrupt.json()["detail"]


def test_force_delete_library_keeps_word(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    default = auth_client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]
    extra = auth_client.post(
        f"/api/wordnest/profiles/{pid}/libraries", json={"name": "临时库"}
    ).json()
    word = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={
            "spelling": "keepme",
            "meaning_zh": "留下",
            "library_ids": [default["id"], extra["id"]],
        },
    ).json()
    deleted = auth_client.delete(
        f"/api/wordnest/profiles/{pid}/libraries/{extra['id']}?force=true"
    )
    assert deleted.status_code == 200
    words = auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()
    kept = next(w for w in words if w["id"] == word["id"])
    assert kept["spelling"] == "keepme"
    assert default["id"] in kept["library_ids"]
    assert extra["id"] not in kept["library_ids"]


def test_prepare_image_data_url_resizes() -> None:
    from io import BytesIO

    from PIL import Image

    from backend.app.services.image_prep import prepare_image_data_url

    buf = BytesIO()
    Image.new("RGB", (2400, 1200), color=(20, 80, 90)).save(buf, format="PNG")
    data_url = prepare_image_data_url(buf.getvalue(), "image/png", max_side=800)
    assert data_url.startswith("data:image/jpeg;base64,")
    raw = data_url.split(",", 1)[1]
    import base64

    img = Image.open(BytesIO(base64.b64decode(raw)))
    assert max(img.size) <= 800


def _add_word(client: TestClient, pid: int, spelling: str) -> dict:
    lib_id = client.get(f"/api/wordnest/profiles/{pid}/libraries").json()[0]["id"]
    return client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={"spelling": spelling, "meaning_zh": f"{spelling}义", "library_ids": [lib_id]},
    ).json()


def _rate(client: TestClient, pid: int, word_id: int, rating: str, times: int = 1) -> None:
    for _ in range(times):
        resp = client.post(
            f"/api/wordnest/profiles/{pid}/quiz/{word_id}/rate", json={"rating": rating}
        )
        assert resp.status_code == 200


def test_daily_quiz_count_is_a_per_profile_parent_setting(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother, sister = profiles["brother"], profiles["sister"]
    base = "/api/wordnest/profiles"
    assert auth_client.get(f"{base}/{brother}/dashboard").json()["daily_quiz_count"] == 10

    saved = auth_client.patch(f"{base}/{brother}/settings", json={"daily_quiz_count": 30})
    assert saved.status_code == 200
    assert saved.json() == {"daily_quiz_count": 30}
    assert auth_client.get(f"{base}/{brother}/dashboard").json()["daily_quiz_count"] == 30
    assert auth_client.get(f"{base}/{sister}/dashboard").json()["daily_quiz_count"] == 10

    for invalid in (25, 0, 60):
        rejected = auth_client.patch(
            f"{base}/{brother}/settings", json={"daily_quiz_count": invalid}
        )
        assert rejected.status_code == 422
    assert auth_client.get(f"{base}/{brother}/dashboard").json()["daily_quiz_count"] == 30


def test_quiz_uses_daily_setting_when_count_is_omitted(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    pid = profiles["brother"]
    words = [_add_word(auth_client, pid, f"word{i:02d}") for i in range(25)]
    auth_client.patch(f"/api/wordnest/profiles/{pid}/settings", json={"daily_quiz_count": 20})

    preview = auth_client.post(f"/api/wordnest/profiles/{pid}/quiz/preview", json={})
    assert preview.json() == {"available_count": 25, "challenge_count": 20}
    started = auth_client.post(f"/api/wordnest/profiles/{pid}/quiz/start", json={})
    assert started.json()["total"] == 20

    # 指定词重练时按词数出题，不被每日题量截断
    retry_ids = [word["id"] for word in words[:12]]
    auth_client.patch(f"/api/wordnest/profiles/{pid}/settings", json={"daily_quiz_count": 10})
    retry = auth_client.post(
        f"/api/wordnest/profiles/{pid}/quiz/start", json={"word_ids": retry_ids}
    )
    assert sorted(word["id"] for word in retry.json()["words"]) == sorted(retry_ids)


def test_words_report_lifetime_wrong_count_and_sort_by_it(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    from backend.app import database as db_module
    from backend.app.models import ReviewEvent

    pid = profiles["brother"]
    once = _add_word(auth_client, pid, "once")
    often = _add_word(auth_client, pid, "often")
    never = _add_word(auth_client, pid, "never")
    _rate(auth_client, pid, once["id"], "unknown")
    _rate(auth_client, pid, often["id"], "unknown", times=2)
    _rate(auth_client, pid, never["id"], "known", times=2)
    _rate(auth_client, pid, never["id"], "familiar")
    with db_module.SessionLocal() as db:
        # 很久以前的错误也要算进去
        db.add(
            ReviewEvent(
                profile_id=pid,
                word_id=often["id"],
                rating="unknown",
                reviewed_at=datetime.now(timezone.utc) - timedelta(days=120),
            )
        )
        db.commit()

    listed = auth_client.get(f"/api/wordnest/profiles/{pid}/words").json()
    counts = {word["spelling"]: word["wrong_count"] for word in listed}
    assert counts == {"once": 1, "often": 3, "never": 0}

    ranked = auth_client.get(
        f"/api/wordnest/profiles/{pid}/words", params={"sort": "wrong_count"}
    ).json()
    assert [word["spelling"] for word in ranked] == ["often", "once", "never"]

    invalid = auth_client.get(
        f"/api/wordnest/profiles/{pid}/words", params={"sort": "random"}
    )
    assert invalid.status_code == 422


def test_frequent_mistakes_scope_targets_words_missed_twice_or_more(
    auth_client: TestClient, profiles: dict[str, int]
) -> None:
    brother, sister = profiles["brother"], profiles["sister"]
    zero = _add_word(auth_client, brother, "zero")
    one = _add_word(auth_client, brother, "one")
    two = _add_word(auth_client, brother, "two")
    three = _add_word(auth_client, brother, "three")
    mastered = _add_word(auth_client, brother, "mastered")
    _rate(auth_client, brother, one["id"], "unknown")
    _rate(auth_client, brother, two["id"], "unknown", times=2)
    _rate(auth_client, brother, three["id"], "unknown", times=3)
    _rate(auth_client, brother, mastered["id"], "unknown", times=2)
    auth_client.patch(
        f"/api/wordnest/profiles/{brother}/words/{mastered['id']}", json={"is_mastered": True}
    )
    sister_word = _add_word(auth_client, sister, "foreign")
    _rate(auth_client, sister, sister_word["id"], "unknown", times=4)

    dashboard = auth_client.get(f"/api/wordnest/profiles/{brother}/dashboard").json()
    assert dashboard["frequent_mistake_threshold"] == 2
    assert dashboard["frequent_mistake_words"] == 2

    body = {"frequent_mistakes": True}
    preview = auth_client.post(f"/api/wordnest/profiles/{brother}/quiz/preview", json=body)
    assert preview.json() == {"available_count": 2, "challenge_count": 2}
    started = auth_client.post(f"/api/wordnest/profiles/{brother}/quiz/start", json=body)
    assert sorted(word["id"] for word in started.json()["words"]) == sorted(
        [two["id"], three["id"]]
    )
    assert zero["id"] not in [word["id"] for word in started.json()["words"]]
