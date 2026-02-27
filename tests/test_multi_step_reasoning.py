"""
Multi-step reasoning integration tests.

Scenarios requiring the agent to chain multiple tools or reason across turns.
Covers patient and staff agents. Requires ANTHROPIC_API_KEY.
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


def assert_tools_called(tool_calls: list[dict] | None, expected: list[str]) -> None:
    """Assert all expected tools were called (order-independent)."""
    assert tool_calls is not None, "Expected tool_calls to be present (enable debug_tool_calls)"
    names = [tc["name"] for tc in tool_calls]
    for tool_name in expected:
        assert tool_name in names, f"Expected {tool_name} in tool calls, got: {names}"


# --- Patient: chained tool calls within a single turn ---


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_specialty_availability_chain(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-01: Do you have a pediatrician available on 2026-03-02?"""
    message, tool_calls = invoke_patient_agent(
        "Do you have a pediatrician available on 2026-03-02?"
    )
    assert_tools_called(tool_calls, ["list_providers", "get_appointment_availability"])
    assert_response_contains_any(
        message, ["pediatrician", "dr. test pediatrician", "pediatrics", "11:00", "slot"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_date_inference_availability_chain(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-02: What's available for appointments next week? (relative date)."""
    message, tool_calls = invoke_patient_agent(
        "What's available for appointments next week?"
    )
    assert_tools_called(tool_calls, ["get_current_datetime", "get_appointment_availability"])
    assert_response_contains_any(
        message, ["available", "slot", "appointment", "2025", "2026", "no", "open"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_clinic_info_and_providers_chain(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-03: Who works at the clinic and what are the clinic hours?"""
    message, tool_calls = invoke_patient_agent(
        "Who works at the clinic and what are the clinic hours?"
    )
    assert_tools_called(tool_calls, ["get_clinic_info", "list_providers"])
    assert_response_contains_any(
        message, ["hours", "8", "mon", "fri", "dr. test provider", "provider"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_symptom_then_referral_to_specialist(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-04: I've had headaches and nausea — which doctor here should I see?"""
    message, tool_calls = invoke_patient_agent(
        "I've had headaches and nausea — which doctor here should I see?"
    )
    assert_tools_called(tool_calls, ["search_medical_info", "list_providers"])
    assert_response_contains_any(
        message, ["consult", "provider", "doctor", "educational", "dr."]
    )


@requires_api_key
@pytest.mark.timeout(60)
def test_ms_pat_next_appointment_location(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-05: Where do I need to go for my next appointment?"""
    message, tool_calls = invoke_patient_agent(
        "Where do I need to go for my next appointment?",
        patient_id="test-pat-001",
    )
    assert_tool_was_called(tool_calls, "get_my_appointment_locations")
    assert_response_contains_any(
        message, ["room 101", "main clinic", "location", "2025-02-24"]
    )


# --- Patient: multi-turn flows ---


@requires_api_key
@pytest.mark.timeout(60)
def test_ms_pat_identify_then_view_appointments(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-06: Patient identifies, then asks for appointments (migrated from test_agent_eval)."""
    history = [
        ("user", "I'm test-pat-001"),
        ("assistant", "Got it, you're Test Patient Alpha."),
    ]
    message, tool_calls = invoke_patient_agent("Show my appointments", history=history)
    assert_tool_was_called(tool_calls, "get_patient_appointments")
    assert_response_contains_any(
        message, ["test-apt-001", "appointment", "2025-02-24", "9:00"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_check_availability_then_book(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-07: Check availability, then book specific slot across turns."""
    msg1, _ = invoke_patient_agent(
        "What's available on 2026-03-02?",
        history=[
            ("user", "I'm test-pat-001"),
            ("assistant", "I have you as Test Patient Alpha."),
        ],
    )
    message, tool_calls = invoke_patient_agent(
        "Book me the 8:00 AM slot with Dr. Test Provider",
        history=[
            ("user", "I'm test-pat-001"),
            ("assistant", "I have you as Test Patient Alpha."),
            ("user", "What's available on 2026-03-02?"),
            ("assistant", msg1),
        ],
        patient_id="test-pat-001",
    )
    assert_tool_was_called(tool_calls, "book_appointment")
    assert_response_contains_any(
        message, ["booked", "confirmed", "8:00", "test patient alpha", "2026-03-02"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_medical_info_then_appointment(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-08: Medical info question, then request to make appointment."""
    msg1, _ = invoke_patient_agent("What could cause headache and nausea?")
    message, tool_calls = invoke_patient_agent(
        "Can I make an appointment?",
        history=[
            ("user", "What could cause headache and nausea?"),
            ("assistant", msg1),
        ],
    )
    tool_names = [tc["name"] for tc in (tool_calls or [])]
    used_scheduling = "get_appointment_availability" in tool_names or "book_appointment" in tool_names
    offers_booking = any(
        k in message.lower()
        for k in ["available", "slot", "appointment", "book", "schedule", "when", "date"]
    )
    assert used_scheduling or offers_booking, (
        f"Expected scheduling tool or booking offer. Tools: {tool_names}, message: {message[:200]}"
    )


# --- Staff: chained tool calls within a single turn ---


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_summary_and_insurance_chain(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-01: Full pre-visit overview including insurance status."""
    message, tool_calls = invoke_staff_agent(
        "Give me a full pre-visit overview for test-pat-001, including their insurance status"
    )
    assert_tools_called(tool_calls, ["lookup_patient_summary", "verify_insurance"])
    assert_response_contains_any(
        message, ["test patient alpha", "insurance", "test health", "copay", "25"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_medications_and_allergies_chain(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-02: Medications and allergies for test-pat-001."""
    message, tool_calls = invoke_staff_agent(
        "What medications is test-pat-001 on, and do they have any allergies I should know about?"
    )
    assert_tools_called(tool_calls, ["lookup_patient_medications", "lookup_patient_allergies"])
    assert_response_contains_any(
        message, ["medication", "allerg", "none", "no ", "test-pat-001", "patient"]
    )


@requires_api_key
@pytest.mark.timeout(60)
def test_ms_stf_expired_insurance_workflow(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-03: Check insurance for expired member EXP-MEM-001."""
    message, tool_calls = invoke_staff_agent(
        "Check insurance for member EXP-MEM-001"
    )
    assert_tool_was_called(tool_calls, "verify_insurance")
    assert_response_contains_any(
        message, ["expired", "inactive", "not found", "no active", "error"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_schedule_and_first_patient_chart(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-04: Show schedule, then pull chart for first patient."""
    msg1, tc1 = invoke_staff_agent("Show me today's schedule")
    assert_tool_was_called(tc1, "list_upcoming_appointments")

    message, tc2 = invoke_staff_agent(
        "Pull up the chart for the first patient",
        history=[
            ("user", "Show me today's schedule"),
            ("assistant", msg1),
        ],
    )
    tool_names = [tc["name"] for tc in (tc2 or [])]
    called_lookup = "lookup_patient_summary" in tool_names
    has_patient_info = any(
        k in message.lower()
        for k in ["test patient", "chart", "summary", "alpha", "beta", "patient"]
    )
    assert called_lookup or has_patient_info, (
        f"Expected lookup_patient_summary or patient info in response. Tools: {tool_names}, message: {message[:200]}"
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_comprehensive_pre_visit_prep(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-05: Prep for 9 AM with summary, meds, and allergies."""
    message, tool_calls = invoke_staff_agent(
        "Prep me for the 9 AM with test-pat-001 — I need their summary, meds, and allergies"
    )
    assert_tools_called(
        tool_calls,
        ["lookup_patient_summary", "lookup_patient_medications", "lookup_patient_allergies"],
    )
    assert_response_contains_any(
        message, ["test patient alpha", "summary", "medication", "allerg"]
    )


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_patient_encounters_and_care_plan(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-06: Encounter history and active care plan for test-pat-001."""
    message, tool_calls = invoke_staff_agent(
        "What's the encounter history and active care plan for test-pat-001?"
    )
    assert_tools_called(tool_calls, ["lookup_patient_encounters", "lookup_patient_care_plans"])
    assert_response_contains_any(
        message, ["encounter", "visit", "care plan", "history", "test-pat-001", "none", "no "]
    )
