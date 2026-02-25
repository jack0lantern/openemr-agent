"""
Layer B: Core golden path agent integration tests.

10–15 tests representing the most critical functionalities:
clinic info, availability, providers, appointments, booking, medical info,
staff patient summary, insurance verification, upcoming schedule.
Requires ANTHROPIC_API_KEY.

Extended tests live in test_agent_eval.py.
"""

import pytest

from app.llm.agent import invoke_patient_agent, invoke_staff_agent

from .conftest import requires_api_key


def assert_response_contains_any(response: str, keywords: list[str]) -> None:
    """Assert that the response contains at least one of the keywords (case-insensitive)."""
    lower = response.lower()
    assert any(k.lower() in lower for k in keywords), (
        f"Response did not contain any of {keywords}. Got: {response[:200]}"
    )


def assert_tool_was_called(tool_calls: list[dict] | None, tool_name: str) -> None:
    """Assert a specific tool was called in the debug tool calls."""
    assert tool_calls is not None, "Expected tool_calls to be present (enable debug_tool_calls)"
    names = [tc["name"] for tc in tool_calls]
    assert tool_name in names, f"Expected {tool_name} in tool calls, got: {names}"


def assert_tool_not_called(tool_calls: list[dict] | None, tool_name: str) -> None:
    """Assert a specific tool was NOT called."""
    if tool_calls is None:
        return
    names = [tc["name"] for tc in tool_calls]
    assert tool_name not in names, f"Did not expect {tool_name} in tool calls, got: {names}"


# --- Patient Agent: get_clinic_info ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_clinic_hours(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_patient_agent("What are your clinic hours?")
    assert_response_contains_any(message, ["hours", "8", "5", "mon", "fri"])
    assert_response_contains_any(message, ["address", "123", "healthcare", "parking", "phone"])


# --- Patient Agent: get_appointment_availability ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_availability_specific_date(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_patient_agent("What appointments are available on 2026-03-02?")
    assert_tool_was_called(tool_calls, "get_appointment_availability")
    assert_response_contains_any(message, ["8:00", "9:30", "11:00", "slot", "available", "dr."])


# --- Patient Agent: list_providers ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_who_are_doctors(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_patient_agent("Who are your doctors?")
    assert_tool_was_called(tool_calls, "list_providers")
    assert_response_contains_any(message, ["dr. test provider", "dr. test internist", "dr. test pediatrician"])


# --- Patient Agent: get_patient_appointments ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_my_appointments_with_history(enable_debug_tool_calls, set_anthropic_api_key):
    history = [
        ("user", "I'm test-pat-001"),
        ("assistant", "I understand you're Test Patient Alpha. How can I help?"),
    ]
    message, tool_calls = invoke_patient_agent("What are my upcoming appointments?", history=history)
    assert_tool_was_called(tool_calls, "get_patient_appointments")
    assert_response_contains_any(message, ["appointment", "2025-02-24", "9:00", "dr. test provider"])


# --- Patient Agent: book_appointment ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_booking_flow(enable_debug_tool_calls, set_anthropic_api_key):
    history = [
        ("user", "I'm test-pat-001"),
        ("assistant", "I have you as Test Patient Alpha."),
        ("user", "I'd like to book an appointment"),
        ("assistant", "I can help. Let me check availability for 2026-03-02."),
    ]
    message, tool_calls = invoke_patient_agent(
        "Book me with Dr. Test Provider on 2026-03-02 at 8:00 AM",
        history=history,
    )
    assert_tool_was_called(tool_calls, "book_appointment")
    assert_response_contains_any(message, ["booked", "confirmed", "8:00", "test patient alpha", "2026-03-02"])


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_booking_nonexistent_slot(enable_debug_tool_calls, set_anthropic_api_key):
    history = [("user", "I'm test-pat-001"), ("assistant", "Got it.")]
    message, tool_calls = invoke_patient_agent(
        "Book me for slot invalid-slot-999",
        history=history,
    )
    assert_tool_was_called(tool_calls, "book_appointment")
    assert_response_contains_any(message, ["not found", "invalid", "slot", "available"])


# --- Patient Agent: search_medical_info ---


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_medical_info_symptoms(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_patient_agent("What could cause headache and nausea?")
    assert_tool_was_called(tool_calls, "search_medical_info")
    assert_response_contains_any(message, ["consult", "provider", "migraine", "headache", "educational"])


@requires_api_key
@pytest.mark.timeout(60)
def test_patient_refuses_recommendation(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_patient_agent("Should I take ibuprofen for my headache?")
    assert_response_contains_any(
        message,
        ["cannot", "recommend", "consult", "provider", "doctor", "advice", "disclaimer"],
    )


# --- Staff Agent: lookup_patient_summary ---


@requires_api_key
@pytest.mark.timeout(60)
def test_staff_patient_summary(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_staff_agent("Pull up the summary for patient test-pat-001")
    assert_tool_was_called(tool_calls, "lookup_patient_summary")
    assert_response_contains_any(message, ["test patient alpha", "insurance", "dr. test provider", "test health"])


# --- Staff Agent: verify_insurance ---


@requires_api_key
@pytest.mark.timeout(60)
def test_staff_verify_insurance_member_id(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_staff_agent("Verify insurance for member TEST-MEM-001")
    assert_tool_was_called(tool_calls, "verify_insurance")
    assert_response_contains_any(message, ["test health", "ppo", "active", "copay", "25"])


@requires_api_key
@pytest.mark.timeout(60)
def test_staff_verify_insurance_patient_id(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_staff_agent("Check insurance for patient test-pat-001")
    assert_tool_was_called(tool_calls, "verify_insurance")
    assert_response_contains_any(message, ["test health", "insurance", "plan"])


@requires_api_key
@pytest.mark.timeout(60)
def test_staff_verify_insurance_invalid(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_staff_agent("Verify insurance for member FAKE-999")
    assert_tool_was_called(tool_calls, "verify_insurance")
    assert_response_contains_any(message, ["not found", "no active", "error"])


# --- Staff Agent: list_upcoming_appointments ---


@requires_api_key
@pytest.mark.timeout(60)
def test_staff_upcoming_appointments(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls = invoke_staff_agent("What appointments do we have coming up?")
    assert_tool_was_called(tool_calls, "list_upcoming_appointments")
    assert_response_contains_any(message, ["appointment", "test patient", "2025-02-24", "dr."])
