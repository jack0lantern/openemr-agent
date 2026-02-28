"""Scheduling tools: appointment availability, booking, and patient/staff appointment views."""

from langchain_core.tools import tool

from app.data.appointment_type_durations import get_all_appointment_types
from app.llm.tools._utils import _tool_result
from app.services.data_service import (
    book_appointment as _book_appointment_svc,
    get_available_dates,
    get_available_slots,
    get_patient_appointments as _get_patient_appointments_svc,
    get_upcoming_appointments as _get_upcoming_appointments_svc,
)


@tool
def list_appointment_types() -> str:
    """List appointment types and their default durations (minutes). Use when the user asks what types of appointments are available, or before checking availability for a specific type. Durations are from OpenEMR defaults."""
    types = get_all_appointment_types()
    return _tool_result({
        "appointment_types": [
            {"type": t["type"], "label": t["label"], "duration_minutes": t["duration_minutes"]}
            for t in types
        ],
    })


@tool
def get_appointment_availability(date: str, appointment_type: str | None = None) -> str:
    """Check appointment availability for a given date. Use for queries about openings, available slots, or 'do you have anything on X'. Call get_current_datetime FIRST to establish the current date, then pass only future dates in YYYY-MM-DD format. Infer the date from natural language (e.g. 'next Friday', 'tomorrow') using get_current_datetime's relative_ranges. When the user specifies an appointment type (e.g. 'new patient', 'follow-up', 'checkup'), pass appointment_type so only slots that fit that duration are returned. Use list_appointment_types to see valid types and durations."""
    slots = get_available_slots(date, appointment_type=appointment_type)
    available_dates = sorted({s["date"] for s in slots}) if slots else get_available_dates()
    if not slots:
        return _tool_result({
            "date": date,
            "slots": [],
            "available_dates": available_dates,
            "message": f"No slots for {date}. Try: {', '.join(available_dates)}" if available_dates else f"No slots for {date}.",
        })
    return _tool_result({
        "date": date,
        "slots": [
            {
                "id": s["id"],
                "time": s["time"],
                "providerName": s["providerName"],
                "type": s["type"],
                "duration": s["duration"],
                "location": s["location"],
            }
            for s in slots
        ],
    })


@tool
def get_patient_appointments(patient_id: str) -> str:
    """Get appointments for a patient by ID (e.g. pat-001, pat-002). Use for patient's own appointments or staff lookups."""
    apts = _get_patient_appointments_svc(patient_id)
    if not apts:
        return _tool_result({
            "patient_id": patient_id,
            "appointments": [],
            "message": f"No appointments found for patient {patient_id}",
        })
    return _tool_result({
        "patient_id": patient_id,
        "appointments": [
            {
                "id": a["id"],
                "date": a["date"],
                "time": a["time"],
                "providerName": a["providerName"],
                "type": a["type"],
                "status": a["status"],
                "location": a["location"],
                "notes": a.get("notes"),
            }
            for a in apts
        ],
    })


@tool
def list_upcoming_appointments() -> str:
    """List upcoming appointments across all patients. Staff only."""
    upcoming = _get_upcoming_appointments_svc()
    return _tool_result({
        "appointments": [
            {
                "id": a["id"],
                "date": a["date"],
                "time": a["time"],
                "patientName": a["patientName"],
                "providerName": a["providerName"],
                "type": a["type"],
                "location": a["location"],
            }
            for a in upcoming
        ],
    })


@tool
def book_appointment(patient_id: str, slot_id: str) -> str:
    """Book an appointment for a patient using an available slot ID (e.g. slot-001). Call get_current_datetime FIRST to ensure the slot is in the future. Returns confirmation."""
    result = _book_appointment_svc(patient_id, slot_id)
    return _tool_result(result)
