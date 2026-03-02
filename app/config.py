"""
App configuration. Auth flags respect PATIENT_AUTH_REQUIRED and STAFF_AUTH_REQUIRED env vars.
Read at access time so tests can monkeypatch env before importing/running.
"""

import os


def openemr_token_url() -> str:
    """OAuth2 token endpoint URL."""
    return os.getenv("OPENEMR_TOKEN_URL", "http://openemr/oauth2/default/token")


def openemr_oauth_base() -> str:
    """OAuth2 base URL (token URL with /token suffix removed)."""
    url = openemr_token_url().rstrip("/")
    if url.endswith("/token"):
        return url[: -len("/token")]
    return url


def openemr_registration_url() -> str:
    """OAuth2 dynamic client registration endpoint. Derived from token URL."""
    return f"{openemr_oauth_base()}/registration"


def openemr_discovery_url() -> str:
    """OIDC discovery endpoint. Derived from token URL."""
    return f"{openemr_oauth_base()}/.well-known/openid-configuration"


def external_data_cache_ttl_minutes() -> int:
    """TTL in minutes for MedlinePlus/RxNav response cache. Default 720 (12h)."""
    return int(os.getenv("EXTERNAL_DATA_CACHE_TTL_MINUTES", "720"))


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in ("true", "1", "yes")


def patient_auth_required() -> bool:
    """When true, require and validate OAuth tokens for the patient API."""
    return _env_bool("PATIENT_AUTH_REQUIRED", False)


def staff_auth_required() -> bool:
    """When true, require and validate OAuth tokens for the staff API."""
    return _env_bool("STAFF_AUTH_REQUIRED", False)
