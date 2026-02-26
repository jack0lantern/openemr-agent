# AI-generated: OpenEMR FHIR R4 client with OAuth2 JWT authentication
# Handles token acquisition, caching, and FHIR resource queries

import logging
import time
import uuid
from pathlib import Path

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

# Default FHIR scopes for client credentials (system-level read + write for booking)
_FHIR_SCOPES = (
    "api:fhir openid "
    "system/Patient.read system/Practitioner.read system/Appointment.read "
    "system/Appointment.write system/Slot.read system/Schedule.read "
    "system/Coverage.read system/Condition.read system/Location.read "
    "system/Organization.read"
)


class FHIRAuthError(Exception):
    """Raised when OAuth2 token acquisition fails."""

    pass


class FHIRRequestError(Exception):
    """Raised when a FHIR API request fails."""

    pass


class FHIRClient:
    """
    Async FHIR R4 client with OAuth2 JWT (client_credentials) authentication.
    Caches access token until near-expiry (refresh 30s before expiry).
    """

    def __init__(
        self,
        base_url: str | None = None,
        token_url: str | None = None,
        client_id: str | None = None,
        private_key_path: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.openemr_fhir_url).rstrip("/")
        self._token_url = token_url or settings.openemr_token_url
        self._client_id = client_id or settings.openemr_client_id
        self._private_key_path = Path(private_key_path or settings.private_key_path)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _ensure_token(self) -> str:
        """Get valid access token, refreshing if near expiry."""
        now = time.time()
        if self._access_token and self._token_expires_at > now + 30:
            return self._access_token

        if not self._client_id:
            raise FHIRAuthError("OPENEMR_CLIENT_ID is not configured")
        if not self._private_key_path.exists():
            raise FHIRAuthError(
                f"Private key not found at {self._private_key_path}. "
                "Configure PRIVATE_KEY_PATH for JWT signing."
            )

        private_key = self._private_key_path.read_text()
        iat = int(now)
        exp = iat + 300  # 5 minutes max per OpenEMR
        payload = {
            "iss": self._client_id,
            "sub": self._client_id,
            "aud": self._token_url,
            "exp": exp,
            "jti": str(uuid.uuid4()),
            "iat": iat,
        }
        try:
            assertion = jwt.encode(
                payload,
                private_key,
                algorithm="RS384",
                headers={"kid": "ai-agent-key"},
            )
        except Exception as e:
            logger.exception("JWT signing failed")
            raise FHIRAuthError(f"JWT signing failed: {e}") from e

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                    "scope": _FHIR_SCOPES,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            logger.error(
                "Token request failed: status=%s body=%s",
                resp.status_code,
                resp.text[:500],
            )
            raise FHIRAuthError(
                f"Token request failed: {resp.status_code} - {resp.text[:200]}"
            )

        data = resp.json()
        self._access_token = data.get("access_token")
        expires_in = data.get("expires_in", 60)
        self._token_expires_at = now + expires_in

        if not self._access_token:
            raise FHIRAuthError("Token response missing access_token")

        return self._access_token

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Make authenticated FHIR request. path is relative to base (e.g. Practitioner)."""
        token = await self._ensure_token()
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
        }
        if json_body:
            headers["Content-Type"] = "application/fhir+json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, params=params or {}, headers=headers)
            elif method == "POST":
                resp = await client.post(url, json=json_body, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

        if resp.status_code >= 400:
            logger.error(
                "FHIR request failed: %s %s status=%s body=%s",
                method,
                path,
                resp.status_code,
                resp.text[:500],
            )
            raise FHIRRequestError(
                f"FHIR {method} {path}: {resp.status_code} - {resp.text[:200]}"
            )

        return resp.json()

    async def get_practitioners(self, specialty: str | None = None) -> dict:
        """GET /fhir/Practitioner. Optional specialty filter."""
        params: dict = {}
        if specialty:
            params["specialty"] = specialty
        return await self._request("GET", "Practitioner", params=params if params else None)

    async def get_patients(self) -> dict:
        """GET /fhir/Patient."""
        return await self._request("GET", "Patient")

    async def get_patient(self, patient_id: str) -> dict:
        """GET /fhir/Patient/{id}."""
        return await self._request("GET", f"Patient/{patient_id}")

    async def get_appointments(
        self,
        patient_id: str | None = None,
        date_ge: str | None = None,
        status: str | None = None,
    ) -> dict:
        """GET /fhir/Appointment with optional filters."""
        params: dict = {}
        if patient_id:
            params["patient"] = f"Patient/{patient_id}"
        if date_ge:
            params["date"] = f"ge{date_ge}"
        if status:
            params["status"] = status
        return await self._request("GET", "Appointment", params=params if params else None)

    async def get_slots(
        self,
        start: str | None = None,
        start_ge: str | None = None,
        status: str = "free",
    ) -> dict:
        """GET /fhir/Slot. start/start_ge in FHIR dateTime format."""
        params: dict = {"status": status}
        if start:
            params["start"] = start
        if start_ge:
            params["start"] = f"ge{start_ge}"
        return await self._request("GET", "Slot", params=params if params else None)

    async def get_schedules(self) -> dict:
        """GET /fhir/Schedule."""
        return await self._request("GET", "Schedule")

    async def get_coverages(self, identifier: str | None = None) -> dict:
        """GET /fhir/Coverage. Optional identifier (member ID) filter."""
        params: dict = {}
        if identifier:
            params["identifier"] = identifier
        return await self._request("GET", "Coverage", params=params if params else None)

    async def get_conditions(
        self,
        patient_id: str | None = None,
        code_text: str | None = None,
    ) -> dict:
        """GET /fhir/Condition. Optional patient and code:text filters."""
        params: dict = {}
        if patient_id:
            params["patient"] = f"Patient/{patient_id}"
        if code_text:
            params["code"] = code_text
        return await self._request("GET", "Condition", params=params if params else None)

    async def get_locations(self) -> dict:
        """GET /fhir/Location."""
        return await self._request("GET", "Location")

    async def get_organizations(self) -> dict:
        """GET /fhir/Organization. Returns facility/clinic resources."""
        return await self._request("GET", "Organization")

    async def create_appointment(self, appointment: dict) -> dict:
        """POST /fhir/Appointment to book an appointment."""
        return await self._request("POST", "Appointment", json_body=appointment)


# Singleton for reuse
_client: FHIRClient | None = None


def get_fhir_client() -> FHIRClient:
    """Get or create the shared FHIR client instance."""
    global _client
    if _client is None:
        _client = FHIRClient()
    return _client
# End AI-generated code
