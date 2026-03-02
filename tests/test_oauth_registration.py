"""Unit tests for oauth_registration."""

import os

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.oauth_registration import (
    register_agent,
    get_all_supported_scopes_sync,
    _default_redirect_uri,
    _exclude_unimplemented_scopes,
    UNIMPLEMENTED_SCOPE_PATTERNS,
)


class TestOAuthRegistration:
    def test_exclude_unimplemented_scopes_keeps_patient_and_appointment(self):
        """Patient.read and Appointment.read are implemented in OpenEMR; only Slot/Schedule are filtered."""
        scopes = [
            "patient/Patient.read",
            "patient/Slot.read",
            "system/Schedule.rs",
            "user/Appointment.read",
        ]
        result = _exclude_unimplemented_scopes(scopes)
        assert "patient/Patient.read" in result
        assert "user/Appointment.read" in result
        assert "patient/Slot.read" not in result
        assert "system/Schedule.rs" not in result

    def test_default_redirect_uri_blank_when_no_env(self):
        """Redirect URI defaults to blank unless OAUTH_REDIRECT_URI or OAUTH_REDIRECT_BASE is set."""
        with patch.dict("os.environ", {"OAUTH_REDIRECT_URI": "", "OAUTH_REDIRECT_BASE": ""}):
            assert _default_redirect_uri() == ""

    def test_default_redirect_uri_from_oauth_redirect_uri(self):
        """When OAUTH_REDIRECT_URI is set, use it."""
        with patch.dict("os.environ", {"OAUTH_REDIRECT_URI": "https://app.example.com/callback"}):
            assert _default_redirect_uri() == "https://app.example.com/callback"

    def test_default_redirect_uri_from_oauth_redirect_base(self):
        """When OAUTH_REDIRECT_BASE is set (and not OAUTH_REDIRECT_URI), derive /oauth/callback."""
        with patch.dict("os.environ", {"OAUTH_REDIRECT_BASE": "http://localhost:8000", "OAUTH_REDIRECT_URI": ""}):
            assert _default_redirect_uri() == "http://localhost:8000/oauth/callback"

    def test_register_agent_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "client_id": "test-client-123",
            "client_secret": "secret",
            "registration_client_uri": "https://example.com/client/abc",
        }
        with patch("app.services.oauth_registration.httpx.Client") as mock_client:
            mock_post = mock_client.return_value.__enter__.return_value.post
            mock_post.return_value = mock_resp
            result = register_agent(
                "https://example.com/oauth2/default/registration",
                {"keys": [{"kty": "RSA", "kid": "ai-agent-key"}]},
                "http://localhost:8000/oauth/callback",
                "openid api:fhir",
            )
        assert result["client_id"] == "test-client-123"
        assert result["registration_client_uri"] == "https://example.com/client/abc"

    def test_register_agent_with_empty_redirect_uri_sends_empty_array(self):
        """When redirect_uri is blank, registration sends redirect_uris: []."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"client_id": "test", "client_secret": "x"}
        with patch("app.services.oauth_registration.httpx.Client") as mock_client:
            mock_post = mock_client.return_value.__enter__.return_value.post
            mock_post.return_value = mock_resp
            register_agent(
                "https://example.com/reg",
                {"keys": []},
                "",
                "openid",
            )
        call_args = mock_post.call_args
        assert call_args[1]["json"]["redirect_uris"] == []

    def test_register_agent_raises_on_4xx(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "invalid_client_metadata"
        with patch("app.services.oauth_registration.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Registration failed"):
                register_agent(
                    "https://example.com/reg",
                    {"keys": []},
                    "http://localhost/callback",
                    "openid",
                )

    def test_get_all_supported_scopes_sync_uses_fallback_on_failure(self):
        with patch("app.services.oauth_registration.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = Exception("Network error")
            scope_str = get_all_supported_scopes_sync("http://localhost:8300/oauth2/default")
        assert "openid" in scope_str
        assert "api:fhir" in scope_str
        assert "patient/Patient.read" in scope_str
        assert "user/Appointment.read" in scope_str
        assert "/Slot" not in scope_str
        assert "/Schedule" not in scope_str

    def test_get_all_supported_scopes_sync_includes_core_scopes_when_discovery_succeeds(self):
        """Core scopes (Patient.read, Appointment.read) are always included for autoregistration."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "scopes_supported": "openid fhirUser api:fhir",  # minimal set without Patient/Appointment
        }
        with patch("app.services.oauth_registration.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            scope_str = get_all_supported_scopes_sync("http://localhost:8300/oauth2/default")
        assert "patient/Patient.read" in scope_str
        assert "user/Appointment.read" in scope_str
        assert "system/Patient.read" in scope_str
        assert "system/Appointment.read" in scope_str
