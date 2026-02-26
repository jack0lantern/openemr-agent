# AI-generated: Unit tests for FHIR client (mocked, no live OpenEMR)

import pytest

from app.services.fhir_client import FHIRAuthError, FHIRClient, FHIRRequestError


class TestFHIRClient:
    """Unit tests for FHIRClient with mocked dependencies."""

    def test_client_init_uses_settings_defaults(self):
        client = FHIRClient()
        assert client._base_url
        assert client._token_url
        assert client._client_id is not None

    def test_client_init_accepts_overrides(self):
        client = FHIRClient(
            base_url="http://test/fhir",
            token_url="http://test/token",
            client_id="test-client",
            private_key_path="/nonexistent/key.pem",
        )
        assert client._base_url == "http://test/fhir"
        assert client._client_id == "test-client"

    @pytest.mark.integration
    async def test_ensure_token_raises_when_no_client_id(self):
        """Integration: FHIR auth fails without client ID. Run with: pytest -m integration."""
        client = FHIRClient(client_id="")
        with pytest.raises(FHIRAuthError):
            await client._ensure_token()
