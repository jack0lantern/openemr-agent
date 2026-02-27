"""
Multi-step reasoning integration tests.

Scenarios requiring the agent to chain multiple tools or reason across turns.
Covers patient and staff agents. Requires ANTHROPIC_API_KEY.

Uses batch_invoke to run independent scenarios in parallel, reducing total test time.
"""

import pytest

from app.llm.agent import invoke_patient_agent, invoke_staff_agent
from tests.agent_batch import batch_invoke_patient_agent, batch_invoke_staff_agent

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


# --- Patient: batched chained tool calls (single turn) ---


@requires_api_key
@pytest.mark.timeout(120)
def test_batch_ms_patient_chains(enable_debug_tool_calls, set_anthropic_api_key):
    """Batch: PAT-MS-01 through PAT-MS-06 (6 parallel patient agent calls)."""
    requests = [
        ("Do you have a pediatrician available on 2026-03-02?", None),
        ("What's available for appointments next week?", None),
        ("Who works at the clinic and what are the clinic hours?", None),
        ("I've had headaches and nausea — which doctor here should I see?", None),
        (
            "Where do I need to go for my next appointment?",
            None,
            {"patient_id": "test-pat-001"},
        ),
        (
            "Show my appointments",
            [
                ("user", "I'm test-pat-001"),
                ("assistant", "Got it, you're Test Patient Alpha."),
            ],
        ),
    ]
    results = batch_invoke_patient_agent(requests)
    assert len(results) == 6

    # PAT-MS-01: specialty + availability chain
    msg0, tc0 = results[0]
    assert_tools_called(tc0, ["list_providers", "get_appointment_availability"])
    assert_response_contains_any(
        msg0, ["pediatrician", "dr. test pediatrician", "pediatrics", "11:00", "slot"]
    )

    # PAT-MS-02: date inference + availability chain
    msg1, tc1 = results[1]
    assert_tools_called(tc1, ["get_current_datetime", "get_appointment_availability"])
    assert_response_contains_any(
        msg1, ["available", "slot", "appointment", "2025", "2026", "no", "open"]
    )

    # PAT-MS-03: clinic info + providers chain
    msg2, tc2 = results[2]
    assert_tools_called(tc2, ["get_clinic_info", "list_providers"])
    assert_response_contains_any(
        msg2, ["hours", "8", "mon", "fri", "dr. test provider", "provider"]
    )

    # PAT-MS-04: symptom + referral chain
    msg3, tc3 = results[3]
    assert_tools_called(tc3, ["search_medical_info", "list_providers"])
    assert_response_contains_any(
        msg3, ["consult", "provider", "doctor", "educational", "dr."]
    )

    # PAT-MS-05: next appointment location
    msg4, tc4 = results[4]
    assert_tool_was_called(tc4, "get_my_appointment_locations")
    assert_response_contains_any(
        msg4, ["room 101", "main clinic", "location", "2025-02-24"]
    )

    # PAT-MS-06: identify then view appointments
    msg5, tc5 = results[5]
    assert_tool_was_called(tc5, "get_patient_appointments")
    assert_response_contains_any(
        msg5, ["test-apt-001", "appointment", "2025-02-24", "9:00"]
    )


# --- Patient: multi-turn flows (sequential, cannot batch) ---


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_pat_check_availability_then_book(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """PAT-MS-07: Check availability, then book specific slot across turns."""
    msg1, _, _ = invoke_patient_agent(
        "What's available on 2026-03-02?",
        history=[
            ("user", "I'm test-pat-001"),
            ("assistant", "I have you as Test Patient Alpha."),
        ],
    )
    message, tool_calls, _ = invoke_patient_agent(
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
    msg1, _, _ = invoke_patient_agent("What could cause headache and nausea?")
    message, tool_calls, _ = invoke_patient_agent(
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


# --- Staff: batched chained tool calls ---


@requires_api_key
@pytest.mark.timeout(120)
def test_batch_ms_staff_chains(enable_debug_tool_calls, set_anthropic_api_key):
    """Batch: STF-MS-01, 02, 03, 05, 06 (5 parallel staff agent calls)."""
    requests = [
        (
            "Give me a full pre-visit overview for test-pat-001, including their insurance status",
            None,
        ),
        (
            "What medications is test-pat-001 on, and do they have any allergies I should know about?",
            None,
        ),
        ("Check insurance for member EXP-MEM-001", None),
        (
            "Prep me for the 9 AM with test-pat-001 — I need their summary, meds, and allergies",
            None,
        ),
        (
            "What's the encounter history and active care plan for test-pat-001?",
            None,
        ),
    ]
    results = batch_invoke_staff_agent(requests)
    assert len(results) == 5

    # STF-MS-01: summary + insurance chain
    msg0, tc0 = results[0]
    assert_tools_called(tc0, ["lookup_patient_summary", "verify_insurance"])
    assert_response_contains_any(
        msg0, ["test patient alpha", "insurance", "test health", "copay", "25"]
    )

    # STF-MS-02: medications + allergies chain
    msg1, tc1 = results[1]
    assert_tools_called(tc1, ["lookup_patient_medications", "lookup_patient_allergies"])
    assert_response_contains_any(
        msg1, ["medication", "allerg", "none", "no ", "test-pat-001", "patient"]
    )

    # STF-MS-03: expired insurance workflow
    msg2, tc2 = results[2]
    assert_tool_was_called(tc2, "verify_insurance")
    assert_response_contains_any(
        msg2, ["expired", "inactive", "not found", "no active", "error"]
    )

    # STF-MS-05: comprehensive pre-visit prep
    msg3, tc3 = results[3]
    assert_tools_called(
        tc3,
        ["lookup_patient_summary", "lookup_patient_medications", "lookup_patient_allergies"],
    )
    assert_response_contains_any(
        msg3, ["test patient alpha", "summary", "medication", "allerg"]
    )

    # STF-MS-06: encounters + care plan chain
    msg4, tc4 = results[4]
    assert_tools_called(tc4, ["lookup_patient_encounters", "lookup_patient_care_plans"])
    assert_response_contains_any(
        msg4, ["encounter", "visit", "care plan", "history", "test-pat-001", "none", "no "]
    )


# --- Staff: multi-turn flow (sequential, cannot batch) ---


@requires_api_key
@pytest.mark.timeout(90)
def test_ms_stf_schedule_and_first_patient_chart(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """STF-MS-04: Show schedule, then pull chart for first patient."""
    msg1, tc1, _ = invoke_staff_agent("Show me today's schedule")
    assert_tool_was_called(tc1, "list_upcoming_appointments")

    message, tc2, _ = invoke_staff_agent(
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
