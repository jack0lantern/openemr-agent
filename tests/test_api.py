"""
API-level tests for FastAPI endpoints.

Uses TestClient for sync requests. Auth is disabled via fixture for most tests.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


# --- API-01: Health ---


def test_api_01_health_returns_ok(client, disable_auth):
    """API-01: GET /health returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- API-02: Root ---


def test_api_02_root_returns_service_info(client, disable_auth):
    """API-02: GET / returns service info with endpoint descriptions."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "OpenEMR AI Agent" in data.get("service", "")
    assert "endpoints" in data
    assert "patient" in data["endpoints"] or "POST" in str(data["endpoints"])


# --- API-03, 04, 05, 06: Patient chat ---


def test_api_03_patient_valid_request_returns_200(client, disable_auth):
    """API-03: POST /api/chat/patient valid request returns 200 with message and token_usage."""
    response = client.post(
        "/api/chat/patient",
        json={"messages": [{"role": "user", "content": "What are your hours?"}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "token_usage" in data
    if data["token_usage"] is not None:
        tu = data["token_usage"]
        assert "input_tokens" in tu
        assert "output_tokens" in tu
        assert "total_tokens" in tu


def test_api_04_patient_missing_auth_when_required_returns_401(client, monkeypatch):
    """API-04: POST /api/chat/patient missing auth when required returns 401."""
    monkeypatch.setenv("PATIENT_AUTH_REQUIRED", "true")  # AI-generated
    response = client.post(
        "/api/chat/patient",
        json={"messages": [{"role": "user", "content": "What are your hours?"}]},
    )
    assert response.status_code == 401


def test_api_05_patient_empty_message_returns_400(client, disable_auth):
    """API-05: POST /api/chat/patient empty message content returns 400 or 422."""
    response = client.post(
        "/api/chat/patient",
        json={"messages": [{"role": "user", "content": ""}]},
    )
    # Pydantic validation rejects min_length=1, FastAPI returns 422
    assert response.status_code in (400, 422)


def test_api_06_patient_last_message_not_user_returns_400(client, disable_auth):
    """API-06: POST /api/chat/patient last message not role=user returns 400."""
    response = client.post(
        "/api/chat/patient",
        json={
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},  # last msg is assistant
            ]
        },
    )
    assert response.status_code == 400


# --- API-07, 08: Staff chat ---


def test_api_07_staff_valid_request_returns_200(client, disable_auth):
    """API-07: POST /api/chat/staff valid request returns 200 with message and token_usage."""
    response = client.post(
        "/api/chat/staff",
        json={"messages": [{"role": "user", "content": "What appointments are coming up?"}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "token_usage" in data
    if data["token_usage"] is not None:
        tu = data["token_usage"]
        assert "input_tokens" in tu
        assert "output_tokens" in tu
        assert "total_tokens" in tu


def test_api_08_staff_missing_auth_when_required_returns_401(client, monkeypatch):
    """API-08: POST /api/chat/staff missing auth when required returns 401."""
    monkeypatch.setenv("STAFF_AUTH_REQUIRED", "true")  # AI-generated
    response = client.post(
        "/api/chat/staff",
        json={"messages": [{"role": "user", "content": "What appointments are coming up?"}]},
    )
    assert response.status_code == 401


# --- API-09: Multi-turn ---


def test_api_09_patient_multi_turn_returns_coherent_response(client, disable_auth):
    """API-09: POST /api/chat/patient multi-turn conversation returns coherent response."""
    response = client.post(
        "/api/chat/patient",
        json={
            "messages": [
                {"role": "user", "content": "I'm test-pat-001"},
                {"role": "assistant", "content": "I have you as Test Patient Alpha. How can I help?"},
                {"role": "user", "content": "What are my appointments?"},
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert len(data["message"]) > 0
