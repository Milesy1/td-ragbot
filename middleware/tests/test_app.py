"""HTTP and WebSocket tests for the TD agent middleware."""

from __future__ import annotations

import os

os.environ["PAIRING_TOKEN"] = "test-token"

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import app, manager
from schemas import ALLOWED_ACTIONS


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_register_wrong_token_closes_connection() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"action": "register", "token": "wrong-token", "session": "td"})
        closed = False
        try:
            first = ws.receive_json()
            assert first.get("ok") is False
            try:
                ws.receive_json()
            except WebSocketDisconnect:
                closed = True
        except WebSocketDisconnect:
            closed = True
        assert closed
    assert manager.get("td") is None


def test_register_correct_token_listed_in_sessions() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {"action": "register", "token": "test-token", "session": "studio"}
        )
        ack = ws.receive_json()
        assert ack["ok"] is True
        assert ack["session_id"] == "studio"

        listed = client.get("/sessions")
        assert listed.status_code == 200
        rows = listed.json()["sessions"]
        match = next(row for row in rows if row["session"] == "studio")
        assert match["last_command"] is None
        assert "connected_at" in match
        assert match["duration_seconds"] >= 0
    assert manager.get("studio") is None


def test_cmd_disconnected_returns_503(cmd_headers: dict[str, str]) -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers=cmd_headers,
        json={"action": "list_ops", "path": "/project1"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert "error" in body


def test_cmd_named_missing_session_returns_503(cmd_headers: dict[str, str]) -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers=cmd_headers,
        json={
            "action": "list_ops",
            "path": "/project1",
            "session": "does-not-exist",
        },
    )
    assert response.status_code == 503
    assert response.json()["ok"] is False


def test_off_allowlist_post_cmd_returns_422(cmd_headers: dict[str, str]) -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers=cmd_headers,
        json={"action": "write_script", "path": "/project1", "code": "print(1)"},
    )
    assert response.status_code == 422
    assert "write_script" not in ALLOWED_ACTIONS


def test_exec_post_cmd_returns_422(cmd_headers: dict[str, str]) -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers=cmd_headers,
        json={"action": "exec", "code": "1 + 1"},
    )
    assert response.status_code == 422


def test_cmd_missing_pairing_token_returns_401() -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        json={"action": "list_ops", "path": "/project1"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid pairing token"}


def test_cmd_wrong_pairing_token_returns_401() -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers={"X-Pairing-Token": "wrong-token"},
        json={"action": "list_ops", "path": "/project1"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid pairing token"}


def test_cmd_correct_pairing_token_passes_through(cmd_headers: dict[str, str]) -> None:
    client = TestClient(app)
    response = client.post(
        "/cmd",
        headers=cmd_headers,
        json={"action": "list_ops", "path": "/project1"},
    )
    assert response.status_code != 401
    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert "error" in body


def test_sessions_empty_when_none_connected() -> None:
    client = TestClient(app)
    response = client.get("/sessions")
    assert response.status_code == 200
    assert response.json()["sessions"] == []
