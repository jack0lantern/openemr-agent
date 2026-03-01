"""
App configuration. Auth flags respect PATIENT_AUTH_REQUIRED and STAFF_AUTH_REQUIRED env vars.
Read at access time so tests can monkeypatch env before importing/running.
"""

import os


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
