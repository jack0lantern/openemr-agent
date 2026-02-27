"""Scheduling tools: appointment availability, booking, and patient/staff appointment views."""

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result
from app.services.data_service import (
    book_appointment as _book_appointment_svc,
    get_available_dates,
    get_available_slots,
    get_patient_appointments as _get_patient_appointments_svc,
    get_upcoming_appointments as _get_upcoming_appointments_svc,
)


@tool
def get_appointment_availability(date: str) -> str:
    """Check appointment availability for a given date. Use for queries about openings, available slots, or 'do you have anything on X'. Infer the date from natural language (e.g. 'next Friday', 'tomorrow') and pass YYYY-MM-DD format (e.g. 2025-02-25)."""
    slots = get_available_slots(date)
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
    """Book an appointment for a patient using an available slot ID (e.g. slot-001). Returns confirmation."""
    result = _book_appointment_svc(patient_id, slot_id)
    return _tool_result(result)
