"""
Shared fixtures for golden path evaluation tests.

Monkeypatches dev mock data with test-specific data and provides
settings overrides for integration and API tests.
"""

import datetime
import os

import pytest
from dotenv import load_dotenv

load_dotenv()  # Load .env so ANTHROPIC_API_KEY is available for integration tests

# Use SQLite in-memory instead of PostgreSQL for tests (no external DB required)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def ensure_db_tables():
    """Create DB tables before tests that use the database (runs before client fixture)."""
    import asyncio

    from app.db import init_db

    asyncio.run(init_db())

# Skip integration tests if no API key (from .env or environment)
requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration tests (add to .env)",
)


@pytest.fixture(autouse=True)
def patch_today(monkeypatch):
    """Use fixed today (2025-02-24) for date-sensitive tests (list_upcoming_appointments)."""
    fake_today = datetime.date(2025, 2, 24)
    monkeypatch.setattr("app.services.data_service._today", lambda: fake_today)


@pytest.fixture(autouse=True)
def patch_mock_data(monkeypatch):
    """Replace dev mock data with test-specific data for ALL tests."""
    from tests.fixtures.mock_data import (
        TEST_APPOINTMENTS,
        TEST_AVAILABLE_SLOTS,
        TEST_FACILITIES,
        TEST_INSURANCE_PLANS,
        TEST_PATIENTS,
        TEST_PROVIDERS,
        TEST_STAFF,
    )
    # Patch data_service's imports (it imports from mock_data at load time)
    monkeypatch.setattr("app.services.data_service.MOCK_PROVIDERS", TEST_PROVIDERS)
    monkeypatch.setattr("app.services.data_service.MOCK_PATIENTS", TEST_PATIENTS)
    monkeypatch.setattr("app.services.data_service.MOCK_APPOINTMENTS", TEST_APPOINTMENTS)
    monkeypatch.setattr("app.services.data_service.MOCK_AVAILABLE_SLOTS", TEST_AVAILABLE_SLOTS)
    monkeypatch.setattr("app.services.data_service.MOCK_INSURANCE_PLANS", TEST_INSURANCE_PLANS)
    monkeypatch.setattr("app.services.data_service.MOCK_STAFF", TEST_STAFF)
    monkeypatch.setattr("app.services.data_service.MOCK_FACILITIES", TEST_FACILITIES)


@pytest.fixture(autouse=True)
def ensure_use_mock_data(monkeypatch):
    """Ensure tests use mock data (default; avoids FHIR connectivity)."""
    monkeypatch.setenv("USE_MOCK_DATA", "true")  # AI-generated


@pytest.fixture
def enable_debug_tool_calls(monkeypatch):
    """Enable tool call introspection for integration tests."""
    monkeypatch.setenv("DEBUG_TOOL_CALLS", "true")  # AI-generated


@pytest.fixture
def disable_auth(monkeypatch):
    """Disable auth requirements for API tests."""
    monkeypatch.setenv("PATIENT_AUTH_REQUIRED", "false")  # AI-generated
    monkeypatch.setenv("STAFF_AUTH_REQUIRED", "false")  # AI-generated


@pytest.fixture
def set_anthropic_api_key(monkeypatch):
    """Set anthropic_api_key from env for integration tests."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)  # AI-generated
    return key
