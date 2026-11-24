import json
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="needs the `api` extra")

import httpx
from fastapi.testclient import TestClient

from vi_pii_guard.api.app import create_app
from vi_pii_guard.api.settings import Settings


def make_client(handler: Any = None, **settings: Any) -> TestClient:
    transport = httpx.MockTransport(handler) if handler else None
    app = create_app(Settings(_env_file=None, **settings), transport=transport)
    return TestClient(app)


def test_health_detect_redact_restore() -> None:
    with make_client() as client:
        assert client.get("/healthz").json()["status"] == "ok"

        spans = client.post("/v1/detect", json={"text": "SĐT 0912345678"}).json()["spans"]
        assert spans[0]["entity_type"] == "PHONE"

        redacted = client.post("/v1/redact", json={"text": "Họ tên: Lê Văn Nam"}).json()
        assert redacted["text"] == "Họ tên: [PERSON_1]"
        assert "Lê Văn Nam" not in json.dumps(redacted, ensure_ascii=False)

        restored = client.post(
            "/v1/restore", json={"text": "Chào [PERSON_1]", "session_id": redacted["session_id"]}
        ).json()
        assert restored["text"] == "Chào Lê Văn Nam"

        assert client.delete(f"/v1/sessions/{redacted['session_id']}").status_code == 204


def test_proxy_redacts_upstream_and_restores_answer() -> None:
    seen: dict[str, Any] = {}

    def upstream(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        user_text = seen["body"]["messages"][-1]["content"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": f"Đã ghi nhận: {user_text}"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with make_client(
        upstream, upstream_base_url="https://llm.test/v1", upstream_api_key="sk-test"
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "any",
                "messages": [
                    {"role": "system", "content": "Bạn là trợ lý."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Tôi tên là Phạm Thu Hà, SĐT 0912345678"}
                        ],
                    },
                    {"role": "user", "content": "Gọi lại 0912345678 giúp tôi"},
                ],
            },
        )

    assert response.status_code == 200
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    sent = json.dumps(seen["body"], ensure_ascii=False)
    assert "0912345678" not in sent
    assert "Phạm Thu Hà" not in sent
    assert "[PHONE_1]" in sent
    assert "[PERSON_1]" in sent
    assert (
        response.json()["choices"][0]["message"]["content"]
        == "Đã ghi nhận: Gọi lại 0912345678 giúp tôi"
    )
    assert response.headers["x-pii-redacted"] == "3"
    assert response.headers["x-pii-session"]


def test_proxy_forwards_client_auth_when_no_key_configured() -> None:
    seen: dict[str, Any] = {}

    def upstream(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": []})

    with make_client(upstream) as client:
        client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": "Bearer client-key"},
        )
    assert seen["auth"] == "Bearer client-key"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"messages": "nope"}, "invalid_messages"),
        ({"messages": [], "stream": True}, "stream_not_supported"),
    ],
)
def test_proxy_rejects_bad_requests(payload: dict[str, Any], code: str) -> None:
    with make_client() as client:
        response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_proxy_passes_upstream_errors_through() -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with make_client(upstream) as client:
        response = client.post("/v1/chat/completions", json={"messages": []})
    assert response.status_code == 429


def test_proxy_reports_unreachable_upstream() -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with make_client(upstream) as client:
        response = client.post("/v1/chat/completions", json={"messages": []})
    assert response.status_code == 502
