"""
Extended agent evaluation tests.

Additional integration tests beyond the core golden path.
Covers edge cases, redundant tool paths, and detailed validation.
Requires ANTHROPIC_API_KEY.
"""

import json

import pytest

from app.data.mock_data import MOCK_MEDICAL_CONDITIONS
from app.llm.agent import invoke_patient_agent, invoke_staff_agent

from .conftest import requires_api_key


def _get_tool_output(tool_calls: list[dict] | None, tool_name: str) -> str | None:
    if not tool_calls:
        return None
    for tc in tool_calls:
        if tc.get("name") == tool_name:
            return tc.get("output")
    return None


def assert_response_contains_any(response: str, keywords: list[str]) -> None:
    lower = response.lower()
    assert any(k.lower() in lower for k in keywords), (
        f"Response did not contain any of {keywords}. Got: {response[:200]}"
    )


def assert_tool_was_called(tool_calls: list[dict] | None, tool_name: str) -> None:
    assert tool_calls is not None
    names = [tc["name"] for tc in tool_calls]
    assert tool_name in names, f"Expected {tool_name} in tool calls, got: {names}"


# --- Clinic info (additional paths) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_patient_pediatricians(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_patient_agent("Do you have any pediatricians?")
    assert_tool_was_called(tool_calls, "list_providers")
    assert_response_contains_any(message, ["pediatric", "dr. test pediatrician", "pediatrics"])


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_patient_clinic_location(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_patient_agent("Where is the clinic located?")
    assert_response_contains_any(message, ["address", "123", "healthcare", "parking"])


# --- Availability (date inference) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_patient_availability_next_friday(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_patient_agent("Any openings next Friday?")
    assert_tool_was_called(tool_calls, "get_appointment_availability")


# --- Providers (specialty filter) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_patient_internal_medicine_doctor(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_patient_agent("I need an internal medicine doctor")
    assert_tool_was_called(tool_calls, "list_providers")
    assert_response_contains_any(message, ["internal medicine", "dr. test internist"])


# --- Medical info (grounded response validation) ---


@requires_api_key
@pytest.mark.timeout(90)
def test_eval_patient_fluid_overload_edema_source_verification(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """User asks about fluid overload and edema; verify agent response is grounded in source."""
    query = "What could cause edema?"
    message, tool_calls, _, _ = invoke_patient_agent(query)

    assert_tool_was_called(tool_calls, "search_medical_info")
    output = _get_tool_output(tool_calls, "search_medical_info")
    assert output is not None, "search_medical_info should return output"

    data = json.loads(output)
    conditions = data.get("conditions", [])
    assert len(conditions) > 0, "Expected at least one matching condition for fluid overload/edema"

    # Build source text from tool output (what the agent had access to)
    source_text_parts: list[str] = []
    for cond in conditions:
        source_text_parts.append(cond.get("name", ""))
        source_text_parts.append(cond.get("description", ""))
        source_text_parts.extend(cond.get("common_symptoms", []))
    source_text = " ".join(source_text_parts).lower()

    # Key facts that must appear in both source and agent response
    key_facts = ["fluid", "edema", "swelling"]
    for fact in key_facts:
        assert fact in source_text, (
            f"Source (tool output) must contain '{fact}'. Got conditions: {[c.get('name') for c in conditions]}"
        )

    # Agent response must reflect information from the source
    message_lower = message.lower()
    assert any(fact in message_lower for fact in key_facts), (
        f"Agent response must mention fluid overload/edema info from source. Got: {message[:300]}"
    )
    assert_response_contains_any(message, ["consult", "provider", "educational"])


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_patient_medical_info_response_matches_mock_database(
    enable_debug_tool_calls, set_anthropic_api_key
):
    """Verify the agent's medical info response is grounded in the mock database."""
    query = "What could cause headache and nausea?"
    message, tool_calls, _, _ = invoke_patient_agent(query)

    assert_tool_was_called(tool_calls, "search_medical_info")
    output = _get_tool_output(tool_calls, "search_medical_info")
    assert output is not None

    data = json.loads(output)
    conditions = data.get("conditions", [])
    mock_by_name = {c["name"]: c for c in MOCK_MEDICAL_CONDITIONS}

    for cond in conditions:
        name = cond.get("name")
        assert name in mock_by_name, f"Condition '{name}' not in MOCK_MEDICAL_CONDITIONS"
        expected = mock_by_name[name]
        assert cond.get("description") == expected["description"]
        assert cond.get("common_symptoms") == expected["common_symptoms"]

    condition_names = [c["name"] for c in conditions]
    assert any(name.lower() in message.lower() for name in condition_names)
    assert_response_contains_any(message, ["consult", "provider", "educational"])


# --- Staff patient summary (edge case: no insurance) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_staff_chart_no_insurance(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_staff_agent("Show me the chart for test-pat-003")
    assert_tool_was_called(tool_calls, "lookup_patient_summary")
    assert_response_contains_any(message, ["test patient no insurance", "no insurance", "insurance"])


# --- Staff schedule (alternate phrasing) ---


@requires_api_key
@pytest.mark.timeout(60)
def test_eval_staff_todays_schedule(enable_debug_tool_calls, set_anthropic_api_key):
    message, tool_calls, _, _ = invoke_staff_agent("Show me today's schedule")
    assert_tool_was_called(tool_calls, "list_upcoming_appointments")
