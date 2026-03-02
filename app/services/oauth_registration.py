"""
OAuth2 dynamic client registration for OpenEMR.
Fetches scopes from discovery, filters unimplemented resources, and registers the agent.
"""

import logging
from typing import Any

import httpx

from app.config import openemr_oauth_base, openemr_registration_url
from app.services.key_manager import JWK_KID, private_key_to_jwks

logger = logging.getLogger(__name__)

# Scopes referencing FHIR resources without REST controllers in OpenEMR.
# Exclude to avoid registration errors or token requests for non-existent endpoints.
UNIMPLEMENTED_SCOPE_PATTERNS = ("/Slot", "/Schedule")

# Core scopes always included in registration. Patient and Appointment are implemented
# in OpenEMR FHIR routes; ensure they are requested even if discovery returns a minimal set.
_CORE_SCOPES = (
    "patient/Patient.read user/Patient.read system/Patient.read "
    "patient/Appointment.read user/Appointment.read system/Appointment.read"
).split()

# Fallback scope list when discovery fails. Mirrors OpenEMR ServerScopeListEntity
# (OIDC + SMART + FHIR V1/V2 + api scopes), excluding Slot and Schedule.
_FALLBACK_SCOPES = (
    "openid fhirUser online_access offline_access launch launch/patient "
    "api:oemr api:fhir api:port "
    "patient/AllergyIntolerance.read user/AllergyIntolerance.read system/AllergyIntolerance.read "
    "patient/Appointment.read user/Appointment.read system/Appointment.read "
    "patient/CarePlan.read user/CarePlan.read system/CarePlan.read "
    "patient/CareTeam.read user/CareTeam.read system/CareTeam.read "
    "patient/Condition.read user/Condition.read system/Condition.read "
    "patient/Coverage.read user/Coverage.read system/Coverage.read "
    "patient/Device.read user/Device.read system/Device.read "
    "patient/DiagnosticReport.read user/DiagnosticReport.read system/DiagnosticReport.read "
    "patient/DocumentReference.read user/DocumentReference.read system/DocumentReference.read "
    "patient/Binary.read user/Binary.read system/Binary.read "
    "patient/Encounter.read user/Encounter.read system/Encounter.read "
    "patient/Goal.read user/Goal.read system/Goal.read "
    "patient/Group.read user/Group.read system/Group.read "
    "patient/Immunization.read user/Immunization.read system/Immunization.read "
    "patient/Location.read user/Location.read system/Location.read "
    "patient/Medication.read user/Medication.read system/Medication.read "
    "patient/MedicationRequest.read user/MedicationRequest.read system/MedicationRequest.read "
    "patient/Observation.read user/Observation.read system/Observation.read "
    "patient/Organization.read user/Organization.read system/Organization.read "
    "patient/Patient.read user/Patient.read system/Patient.read "
    "patient/Person.read user/Person.read system/Person.read "
    "patient/Practitioner.read user/Practitioner.read system/Practitioner.read "
    "patient/PractitionerRole.read user/PractitionerRole.read system/PractitionerRole.read "
    "patient/Procedure.read user/Procedure.read system/Procedure.read "
    "patient/Provenance.read user/Provenance.read system/Provenance.read "
    "patient/ValueSet.read user/ValueSet.read system/ValueSet.read "
    "patient/OperationDefinition.read user/OperationDefinition.read system/OperationDefinition.read "
    "patient/DocumentReference.$docref user/DocumentReference.$docref system/DocumentReference.$docref "
    "system/Patient.$export system/Group.$export system/*.$bulkdata-status system/*.$export"
)


def _exclude_unimplemented_scopes(scopes: list[str]) -> list[str]:
    """Filter out scopes for unimplemented FHIR resources."""
    return [
        s
        for s in scopes
        if not any(pattern in s for pattern in UNIMPLEMENTED_SCOPE_PATTERNS)
    ]


async def get_all_supported_scopes(oauth_base_url: str | None = None) -> str:
    """
    Fetch scopes from OIDC discovery, filter unimplemented, return space-joined list.
    Falls back to static list if discovery fails.
    """
    base = oauth_base_url or openemr_oauth_base()
    url = f"{base.rstrip('/')}/.well-known/openid-configuration"
    logger.info("get_all_supported_scopes: fetching discovery from %s", url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        logger.info("get_all_supported_scopes: discovery fetch succeeded")
    except Exception as e:
        logger.warning("get_all_supported_scopes: discovery fetch failed, using fallback scopes: %s", e)
        return " ".join(_exclude_unimplemented_scopes(_FALLBACK_SCOPES.split()))

    raw = data.get("scopes_supported")
    if not raw:
        logger.warning("get_all_supported_scopes: discovery returned empty scopes_supported, using fallback")
        return " ".join(_exclude_unimplemented_scopes(_FALLBACK_SCOPES.split()))

    if isinstance(raw, str):
        scopes = raw.split()
    elif isinstance(raw, list):
        scopes = [s for s in raw if isinstance(s, str)]
    else:
        scopes = []

    filtered = _exclude_unimplemented_scopes(scopes)
    merged = set(filtered) | set(_CORE_SCOPES)
    result = " ".join(sorted(merged)) if merged else _FALLBACK_SCOPES
    logger.info(
        "get_all_supported_scopes: returning %d scopes (%d after filtering, %d with core)",
        len(scopes),
        len(filtered),
        len(merged),
    )
    return result


def get_all_supported_scopes_sync(oauth_base_url: str | None = None) -> str:
    """Synchronous version for use in scripts."""
    import asyncio

    return asyncio.run(get_all_supported_scopes(oauth_base_url))


def register_agent(
    registration_url: str,
    jwks: dict,
    redirect_uri: str,
    scope: str,
    client_name: str = "OpenEMR AI Agent",
) -> dict[str, Any]:
    """
    POST to OpenEMR dynamic client registration endpoint.
    Returns parsed JSON with client_id, client_secret, registration_client_uri, etc.
    """
    redirect_uris = [redirect_uri] if redirect_uri else []
    body = {
        "application_type": "private",
        "token_endpoint_auth_method": "private_key_jwt",
        "jwks": jwks,
        "redirect_uris": redirect_uris,
        "client_name": client_name,
        "scope": scope,
        "contacts": ["ai-agent@openemr.local"],
    }

    logger.info("register_agent: POSTing to %s", registration_url)
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            registration_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        msg = f"Registration failed: {resp.status_code} - {resp.text[:500]}"
        logger.error("register_agent: %s", msg)
        raise RuntimeError(msg)

    result = resp.json()
    logger.info("register_agent: success, client_id=%s", result.get("client_id", "(none)"))
    return result


def register_agent_with_keys(
    private_key_path: str,
    registration_url: str | None = None,
    redirect_uri: str | None = None,
    oauth_base_url: str | None = None,
) -> dict[str, Any]:
    """
    Full registration flow: load keys, fetch scopes, register.
    For use in scripts; uses sync HTTP.
    """
    from pathlib import Path

    reg_url = registration_url or openemr_registration_url()
    redirect = _default_redirect_uri() if redirect_uri is None else redirect_uri
    key_path = Path(private_key_path)

    if not key_path.exists():
        raise FileNotFoundError(f"Private key not found: {key_path}")

    jwks = private_key_to_jwks(key_path, kid=JWK_KID)
    scope = get_all_supported_scopes_sync(oauth_base_url)
    return register_agent(reg_url, jwks, redirect, scope)


def _default_redirect_uri() -> str:
    """Redirect URI for OAuth client registration. Blank unless env vars are set."""
    import os

    uri = os.getenv("OAUTH_REDIRECT_URI")
    if uri:
        return uri.rstrip("/")
    base = os.getenv("OAUTH_REDIRECT_BASE")
    if base:
        return f"{base.rstrip('/')}/oauth/callback"
    return ""
