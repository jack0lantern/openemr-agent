"""
Layer A: Direct tool unit tests.

Call each @tool function directly with deterministic inputs.
No LLM, no agent graph. Validates tool logic in isolation.
"""

import json

import pytest

from app.llm.agent import (
    book_appointment,
    get_appointment_availability,
    get_clinic_info,
    list_appointment_types,
    get_my_appointment_locations,
    get_patient_appointments,
    get_staff_assigned_clinic,
    list_providers,
    list_upcoming_appointments,
    lookup_patient_summary,
    search_medical_info,
    verify_insurance,
)


def _parse_tool_result(output: str) -> dict:
    """Parse JSON from tool output."""
    return json.loads(output)


# --- Tool 1: get_clinic_info ---


def test_get_clinic_info_empty_query_returns_full_clinic_and_all_providers():
    result = get_clinic_info.invoke({"query": ""})
    data = _parse_tool_result(result)
    assert "clinic" in data
    assert data["clinic"]["address"] == "123 Healthcare Ave, Suite 100"
    assert data["clinic"]["hours"] == "Mon–Fri 8am–5pm"
    assert data["clinic"]["phone"] == "555-0199"
    assert len(data["providers"]) == 3
    assert data["query_filter"] is None


def test_get_clinic_info_pediatrics_returns_only_pediatrics_provider():
    result = get_clinic_info.invoke({"query": "pediatrics"})
    data = _parse_tool_result(result)
    assert len(data["providers"]) == 1
    assert "pediatrics" in data["providers"][0]["specialty"].lower()
    assert data["providers"][0]["name"] == "Dr. Test Pediatrician"


def test_get_clinic_info_dr_name_returns_matching_provider():
    result = get_clinic_info.invoke({"query": "Dr. Test Provider"})
    data = _parse_tool_result(result)
    assert len(data["providers"]) == 1
    assert "Dr. Test Provider" in data["providers"][0]["name"]


def test_get_clinic_info_nonexistent_returns_empty_providers():
    result = get_clinic_info.invoke({"query": "nonexistent"})
    data = _parse_tool_result(result)
    assert "clinic" in data
    assert data["providers"] == []
    assert data["query_filter"] == "nonexistent"


# --- Tool 2: list_appointment_types ---


def test_list_appointment_types_returns_types_and_durations():
    result = list_appointment_types.invoke({})
    data = _parse_tool_result(result)
    assert "appointment_types" in data
    types = data["appointment_types"]
    assert len(types) > 0
    new_patient = next((t for t in types if t["type"] == "new_patient"), None)
    assert new_patient is not None
    assert new_patient["duration_minutes"] == 30
    office_visit = next((t for t in types if t["type"] == "office_visit"), None)
    assert office_visit is not None
    assert office_visit["duration_minutes"] == 15


# --- Tool 3: get_appointment_availability ---


def test_get_appointment_availability_date_with_slots_returns_matching_slots():
    result = get_appointment_availability.invoke({"date": "2026-03-02"})
    data = _parse_tool_result(result)
    assert data["date"] == "2026-03-02"
    assert len(data["slots"]) >= 3
    assert any(s["id"] == "test-slot-001" for s in data["slots"])
    assert "8:00 AM" in [s["time"] for s in data["slots"]]


def test_get_appointment_availability_date_with_no_slots_returns_empty_and_available_dates():
    result = get_appointment_availability.invoke({"date": "2026-03-01"})
    data = _parse_tool_result(result)
    assert data["date"] == "2026-03-01"
    assert data["slots"] == []
    assert "available_dates" in data
    assert len(data["available_dates"]) > 0
    assert "message" in data


def test_get_appointment_availability_with_new_patient_filters_short_slots():
    """New patient = 30 min; 20-min slots should be excluded."""
    result = get_appointment_availability.invoke({
        "date": "2026-03-02",
        "appointment_type": "new_patient",
    })
    data = _parse_tool_result(result)
    assert data["date"] == "2026-03-02"
    slots = data["slots"]
    assert all(s["duration"] >= 30 for s in slots)
    slot_ids = [s["id"] for s in slots]
    assert "test-slot-003" not in slot_ids  # 20 min - too short
    assert "test-slot-001" in slot_ids  # 30 min - fits
    assert "test-slot-002" in slot_ids  # 45 min - fits


# --- Tool 4: list_providers ---


def test_list_providers_no_specialty_returns_all():
    result = list_providers.invoke({"specialty": ""})
    data = _parse_tool_result(result)
    assert len(data["providers"]) == 3


def test_list_providers_family_medicine_returns_only_family_medicine():
    result = list_providers.invoke({"specialty": "Family Medicine"})
    data = _parse_tool_result(result)
    assert len(data["providers"]) == 1
    assert "Family Medicine" in data["providers"][0]["specialty"]


def test_list_providers_dermatology_returns_empty_with_available_specialties():
    result = list_providers.invoke({"specialty": "Dermatology"})
    data = _parse_tool_result(result)
    assert data["providers"] == []
    assert "specialty_filter" in data
    assert "available_specialties" in data
    assert "Dermatology" in data["available_specialties"] or "Family Medicine" in data["available_specialties"]


# --- Tool 4: get_patient_appointments ---


def test_get_patient_appointments_with_appointments_returns_list():
    result = get_patient_appointments.invoke({"patient_id": "test-pat-001"})
    data = _parse_tool_result(result)
    assert data["patient_id"] == "test-pat-001"
    assert len(data["appointments"]) >= 1
    assert any(a["id"] == "test-apt-001" for a in data["appointments"])


def test_get_patient_appointments_no_appointments_returns_empty_with_message():
    result = get_patient_appointments.invoke({"patient_id": "test-pat-004"})
    data = _parse_tool_result(result)
    assert data["patient_id"] == "test-pat-004"
    assert data["appointments"] == []
    assert "message" in data


# --- get_my_appointment_locations ---


def test_get_my_appointment_locations_with_upcoming_returns_locations():
    result = get_my_appointment_locations.invoke({"patient_id": "test-pat-001"})
    data = _parse_tool_result(result)
    assert data["patient_id"] == "test-pat-001"
    assert len(data["locations"]) >= 1
    assert any("Main Clinic" in loc["location"] for loc in data["locations"])


def test_get_my_appointment_locations_no_upcoming_returns_empty():
    result = get_my_appointment_locations.invoke({"patient_id": "test-pat-004"})
    data = _parse_tool_result(result)
    assert data["patient_id"] == "test-pat-004"
    assert data["locations"] == []
    assert "message" in data


# --- get_staff_assigned_clinic ---


def test_get_staff_assigned_clinic_valid_staff_returns_facility():
    result = get_staff_assigned_clinic.invoke({"staff_id": "test-staff-001"})
    data = _parse_tool_result(result)
    assert data["staff_id"] == "test-staff-001"
    assert "facility" in data
    assert "Test Main Clinic" in data["facility"]["name"]
    assert "123 Healthcare" in data["facility"]["address"]
    assert "555-0199" in data["facility"]["phone"]


def test_get_staff_assigned_clinic_invalid_staff_returns_error():
    result = get_staff_assigned_clinic.invoke({"staff_id": "invalid-staff-999"})
    data = _parse_tool_result(result)
    assert data["staff_id"] == "invalid-staff-999"
    assert "error" in data


# --- Tool 5: book_appointment ---


def test_book_appointment_valid_patient_valid_slot_returns_success():
    result = book_appointment.invoke({"patient_id": "test-pat-001", "slot_id": "test-slot-001"})
    data = _parse_tool_result(result)
    assert data["success"] is True
    assert "appointment" in data
    assert data["appointment"]["patientName"] == "Test Patient Alpha"
    assert data["appointment"]["date"] == "2026-03-02"
    assert data["appointment"]["time"] == "8:00 AM"


def test_book_appointment_valid_patient_invalid_slot_returns_error():
    result = book_appointment.invoke({"patient_id": "test-pat-001", "slot_id": "invalid-slot-999"})
    data = _parse_tool_result(result)
    assert data["success"] is False
    assert "error" in data
    assert "suggestion" in data


def test_book_appointment_invalid_patient_valid_slot_returns_error():
    result = book_appointment.invoke({"patient_id": "invalid-pat-999", "slot_id": "test-slot-001"})
    data = _parse_tool_result(result)
    assert data["success"] is False
    assert "error" in data


def test_book_appointment_past_slot_returns_error(monkeypatch):
    """Only future appointments can be booked; past slots are rejected."""
    past_slots = [
        {
            "id": "past-slot-001",
            "date": "2020-01-01",
            "time": "9:00 AM",
            "providerId": "test-prov-001",
            "providerName": "Dr. Test Provider",
            "duration": 30,
            "location": "Main Clinic",
            "type": "checkup",
        }
    ]
    monkeypatch.setattr("app.services.data_service.MOCK_AVAILABLE_SLOTS", past_slots)
    result = book_appointment.invoke({"patient_id": "test-pat-001", "slot_id": "past-slot-001"})
    data = _parse_tool_result(result)
    assert data["success"] is False
    assert "past" in data["error"].lower() or "future" in data["error"].lower()
    assert "get_current_datetime" in data.get("suggestion", "").lower()


# --- Tool 6: search_medical_info ---


def test_search_medical_info_empty_query_returns_message_and_disclaimer():
    result = search_medical_info.invoke({"symptoms": ""})
    data = _parse_tool_result(result)
    assert data["conditions"] == []
    assert "disclaimer" in data
    assert "consult" in data["disclaimer"].lower() or "provider" in data["disclaimer"].lower()
    assert "message" in data


def test_search_medical_info_with_symptoms_returns_matching_conditions():
    result = search_medical_info.invoke({"symptoms": "headache nausea"})
    data = _parse_tool_result(result)
    assert "conditions" in data
    assert "disclaimer" in data
    # Migraine has both headache and nausea
    names = [c["name"] for c in data["conditions"]]
    assert "Migraine" in names
    assert all("description" in c and "common_symptoms" in c for c in data["conditions"])


def test_search_medical_info_unknown_symptoms_returns_empty_with_disclaimer():
    result = search_medical_info.invoke({"symptoms": "xyznonexistent123"})
    data = _parse_tool_result(result)
    assert data["conditions"] == []
    assert "disclaimer" in data


# --- Tool 7: lookup_patient_summary (Staff) ---


def test_lookup_patient_summary_valid_patient_returns_full_summary():
    result = lookup_patient_summary.invoke({"patient_id": "test-pat-001"})
    data = _parse_tool_result(result)
    assert "patient" in data
    assert data["patient"]["id"] == "test-pat-001"
    assert data["patient"]["name"] == "Test Patient Alpha"
    assert "insurance" in data
    assert data["insurance"] is not None
    assert "primaryCareProvider" in data or "recentAppointments" in data


def test_lookup_patient_summary_invalid_patient_returns_error():
    result = lookup_patient_summary.invoke({"patient_id": "invalid-pat-999"})
    data = _parse_tool_result(result)
    assert "error" in data


def test_lookup_patient_summary_no_insurance_returns_null_insurance():
    result = lookup_patient_summary.invoke({"patient_id": "test-pat-003"})
    data = _parse_tool_result(result)
    assert "patient" in data
    assert data["insurance"] is None


# --- Tool 8: verify_insurance (Staff) ---


def test_verify_insurance_valid_member_id_returns_plan_details():
    result = verify_insurance.invoke({"member_id": "TEST-MEM-001"})
    data = _parse_tool_result(result)
    assert "error" not in data
    assert data["memberId"] == "TEST-MEM-001"
    assert "plan" in data
    assert "copay" in data


def test_verify_insurance_patient_id_resolves_to_insurance():
    result = verify_insurance.invoke({"member_id": "test-pat-001"})
    data = _parse_tool_result(result)
    assert "error" not in data
    assert "plan" in data


def test_verify_insurance_invalid_member_id_returns_error():
    result = verify_insurance.invoke({"member_id": "FAKE-999"})
    data = _parse_tool_result(result)
    assert "error" in data


def test_verify_insurance_patient_with_no_insurance_returns_error():
    result = verify_insurance.invoke({"member_id": "test-pat-003"})
    data = _parse_tool_result(result)
    assert "error" in data


# --- Tool 9: list_upcoming_appointments (Staff) ---


def test_list_upcoming_appointments_returns_only_future_non_cancelled():
    result = list_upcoming_appointments.invoke({})
    data = _parse_tool_result(result)
    assert "appointments" in data
    # Tool uses today="2025-02-24"; excludes 2025-02-23 (past), cancelled, completed
    for apt in data["appointments"]:
        assert apt["date"] >= "2025-02-24"
    # Should include test-apt-001, test-apt-002 (future, scheduled/confirmed)
    ids = [a["id"] for a in data["appointments"]]
    assert "test-apt-001" in ids or len(ids) >= 1


def test_list_upcoming_appointments_sorted_by_date_time():
    result = list_upcoming_appointments.invoke({})
    data = _parse_tool_result(result)
    appointments = data["appointments"]
    from datetime import datetime

    def _sort_key(apt):
        try:
            t = datetime.strptime(apt["time"].strip(), "%I:%M %p")
            return (apt["date"], t.hour * 60 + t.minute)
        except (ValueError, TypeError):
            return (apt["date"], 0)

    for i in range(len(appointments) - 1):
        a, b = appointments[i], appointments[i + 1]
        assert _sort_key(a) <= _sort_key(b)
