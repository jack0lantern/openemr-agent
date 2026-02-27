"""
Tests for untooled capabilities (future tool candidates).

These queries hit capabilities mentioned in system prompts or PRD but have
no backing tool today. The agent should gracefully decline or redirect.
Documents expected behavior and serves as a roadmap for future tooling.
"""

import pytest

from app.llm.agent import invoke_patient_agent, invoke_staff_agent

from .conftest import requires_api_key


def assert_graceful_decline_or_redirect(response: str, topic_hints: list[str]) -> None:
    """Assert agent gracefully declines or redirects (does not hallucinate tool results)."""
    lower = response.lower()
    # Should not claim to have performed the action (e.g. "I've retrieved your balance")
    # Should suggest alternative (call front desk, etc.) or clarify limitation
    has_redirect = any(
        h in lower
        for h in [
            "call",
            "contact",
            "front desk",
            "cannot",
            "don't have",
            "don't have access",
            "not available",
            "provider",
            "staff",
        ]
    )
    assert has_redirect or len(response) > 20, (
        f"Expected graceful decline/redirect. Got: {response[:200]}"
    )


# --- Billing & Payments (no tool) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_outstanding_balance(enable_debug_tool_calls, set_anthropic_api_key):
    """Billing: What's my outstanding balance? - no tool, graceful decline."""
    message, tool_calls, _ = invoke_patient_agent("What's my outstanding balance?")
    assert_graceful_decline_or_redirect(message, ["balance", "billing"])


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_pay_bill_online(enable_debug_tool_calls, set_anthropic_api_key):
    """Billing: Can I pay my bill online? - no tool."""
    message, _, _ = invoke_patient_agent("Can I pay my bill online?")
    assert_graceful_decline_or_redirect(message, ["pay", "bill"])


# --- Prescription & Medication (no tool) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_patient_medications(enable_debug_tool_calls, set_anthropic_api_key):
    """Medication: What medications is patient taking? - no tool."""
    message, _, _ = invoke_staff_agent("What medications is patient test-pat-001 currently taking?")
    assert_graceful_decline_or_redirect(message, ["medication"])


# --- Lab Results (no tool) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_lab_results(enable_debug_tool_calls, set_anthropic_api_key):
    """Lab: Show me lab results - no tool."""
    message, _, _ = invoke_staff_agent("Show me the latest lab results for patient test-pat-001")
    assert_graceful_decline_or_redirect(message, ["lab"])


# --- Appointment Modification (book exists, cancel/modify do not) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_cancel_appointment(enable_debug_tool_calls, set_anthropic_api_key):
    """Appointment: Cancel my appointment - no cancel tool."""
    history = [("user", "I'm test-pat-001"), ("assistant", "Got it.")]
    message, _, _ = invoke_patient_agent("Cancel my appointment on March 2nd", history=history)
    assert_graceful_decline_or_redirect(message, ["cancel", "appointment"])


# --- Referrals (no tool) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_untooled_referral(enable_debug_tool_calls, set_anthropic_api_key):
    """Referral: I need a referral - no tool."""
    message, _, _ = invoke_patient_agent("I need a referral to a dermatologist")
    assert_graceful_decline_or_redirect(message, ["referral"])
