"""
Shared fixtures for golden path evaluation tests.

Monkeypatches dev mock data with test-specific data and provides
settings overrides for integration and API tests.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()  # Load .env so ANTHROPIC_API_KEY is available for integration tests

# Skip integration tests if no API key (from .env or environment)
requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration tests (add to .env)",
)


@pytest.fixture(autouse=True)
def patch_mock_data(monkeypatch):
    """Replace dev mock data with test-specific data for ALL tests."""
    from tests.fixtures.mock_data import (
        TEST_APPOINTMENTS,
        TEST_AVAILABLE_SLOTS,
        TEST_INSURANCE_PLANS,
        TEST_PATIENTS,
        TEST_PROVIDERS,
    )
    monkeypatch.setattr("app.llm.agent.MOCK_PROVIDERS", TEST_PROVIDERS)
    monkeypatch.setattr("app.llm.agent.MOCK_PATIENTS", TEST_PATIENTS)
    monkeypatch.setattr("app.llm.agent.MOCK_APPOINTMENTS", TEST_APPOINTMENTS)
    monkeypatch.setattr("app.llm.agent.MOCK_AVAILABLE_SLOTS", TEST_AVAILABLE_SLOTS)
    monkeypatch.setattr("app.llm.agent.MOCK_INSURANCE_PLANS", TEST_INSURANCE_PLANS)


@pytest.fixture
def enable_debug_tool_calls(monkeypatch):
    """Enable tool call introspection for integration tests."""
    monkeypatch.setattr("app.config.settings.debug_tool_calls", True)


@pytest.fixture
def disable_auth(monkeypatch):
    """Disable auth requirements for API tests."""
    monkeypatch.setattr("app.config.settings.patient_auth_required", False)
    monkeypatch.setattr("app.config.settings.staff_auth_required", False)


@pytest.fixture
def set_anthropic_api_key(monkeypatch):
    """Set anthropic_api_key from env for integration tests."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr("app.config.settings.anthropic_api_key", key)
    return key
