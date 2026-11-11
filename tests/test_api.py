"""Offline tests: they replace the OpenAI call with a fake, so no API key or credit is needed.

Run with:  python -m pytest -q
"""
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app import config, db, llm, main, prompt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    object.__setattr__(config.settings, "database_path", tmp_path / "test.db")
    calls = []

    def fake_complete(messages):
        calls.append(messages)
        return f"Reply to: {messages[-1]['content']}", 12, 34

    monkeypatch.setattr(main, "complete", fake_complete)
    with TestClient(main.app) as c:
        c.calls = calls
        yield c


def test_system_prompt_has_all_four_layers_and_the_knowledge_file():
    text = prompt.system_prompt()
    for layer in ("Layer 1: Persona", "Layer 2: Custom knowledge", "Layer 3: Scope control", "Layer 4: Safety and honesty"):
        assert layer in text
    assert "Advanced Construction Management Course (CACM)" in text  # loaded from knowledge/knowledge.md
    assert "{knowledge}" not in text


def test_chat_returns_reply_latency_and_logs_messages(client):
    r = client.post("/api/chat", json={"message": "How long is CACM?"})
    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "Reply to: How long is CACM?"
    assert data["latency_ms"] == 12 and data["tokens_used"] == 34
    history = client.get(f"/api/history/{data['session_id']}").json()["messages"]
    assert [m["role"] for m in history] == ["user", "bot"]
    assert history[1]["latency_ms"] == 12 and history[1]["tokens_used"] == 34 and history[1]["created_at"]


def test_conversation_memory_is_sent_to_the_model(client):
    sid = client.post("/api/chat", json={"message": "Tell me about IDM"}).json()["session_id"]
    client.post("/api/chat", json={"session_id": sid, "message": "How long is it?"})
    sent = client.calls[-1]
    assert sent[0]["role"] == "system"
    assert [m["content"] for m in sent[1:]] == ["Tell me about IDM", "Reply to: Tell me about IDM", "How long is it?"]
    assert [m["role"] for m in sent[1:]] == ["user", "assistant", "user"]


def test_reset_starts_a_fresh_session_without_old_memory(client):
    sid = client.post("/api/chat", json={"message": "first"}).json()["session_id"]
    new_sid = client.post(f"/api/reset/{sid}").json()["session_id"]
    assert new_sid != sid
    client.post("/api/chat", json={"session_id": new_sid, "message": "second"})
    assert len(client.calls[-1]) == 2  # system prompt + new message only


@pytest.mark.parametrize("message", ["", "   "])
def test_empty_input_is_rejected(client, message):
    r = client.post("/api/chat", json={"message": message})
    assert r.status_code == 400 and "type a question" in r.json()["error"]


def test_overlong_input_is_rejected(client):
    r = client.post("/api/chat", json={"message": "x" * 1500})
    assert r.status_code == 400 and "under" in r.json()["error"]


def test_feedback_is_stored_and_validated(client):
    mid = client.post("/api/chat", json={"message": "hi"}).json()["message_id"]
    assert client.post("/api/feedback", json={"message_id": mid, "rating": 1}).json() == {"ok": True}
    assert client.post("/api/feedback", json={"message_id": mid, "rating": 5}).status_code == 400
    assert client.post("/api/feedback", json={"message_id": 99999, "rating": -1}).status_code == 404


def test_personal_data_is_masked_in_the_log(client):
    sid = client.post("/api/chat", json={"message": "Call me on 9876543210 or mail a.b@example.com, USN 1BM21CV001"}).json()["session_id"]
    stored = client.get(f"/api/history/{sid}").json()["messages"][0]["content"]
    assert "9876543210" not in stored and "example.com" not in stored and "1BM21CV001" not in stored


def test_missing_api_key_gives_a_friendly_error(client, monkeypatch):
    def no_key(_):
        raise llm.ChatError(503, "The assistant is not configured yet.")
    monkeypatch.setattr(main, "complete", no_key)
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 503 and "not configured" in r.json()["error"]


def _status_error(cls, code):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return cls("x", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize("exc, status, words", [
    (lambda: _status_error(openai.RateLimitError, 429), 429, "too many requests"),
    (lambda: openai.APITimeoutError(request=httpx.Request("POST", "https://x")), 504, "too long"),
    (lambda: openai.APIConnectionError(request=httpx.Request("POST", "https://x")), 503, "couldn't reach"),
    (lambda: _status_error(openai.AuthenticationError, 401), 503, "temporarily unavailable"),
])
def test_openai_errors_become_clear_messages(monkeypatch, exc, status, words):
    class FakeCompletions:
        def create(self, **_):
            raise exc()

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(llm, "_get_client", lambda: FakeClient())
    with pytest.raises(llm.ChatError) as info:
        llm.complete([{"role": "user", "content": "hi"}])
    assert info.value.status == status and words in info.value.user_message


def test_widget_and_chat_page_are_served(client):
    assert client.get("/").status_code == 200
    assert "Aakruti" in client.get("/widget.js").text
    assert client.get("/widget.css").status_code == 200
