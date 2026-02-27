"""Clinic tools: clinic info, provider directory, and location lookups for patients and staff."""

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result
from app.services.data_service import (
    get_clinic_info as _get_clinic_info_svc,
    get_my_appointment_locations as _get_my_appointment_locations_svc,
    get_providers,
    get_staff_assigned_clinic as _get_staff_assigned_clinic_svc,
)


@tool
def get_clinic_info(query: str) -> str:
    """Get clinic information: hours, location, contact. Use for appointment locations and clinic info questions. Query can filter providers by specialty or name (e.g. 'pediatrics', 'Dr. Chen')."""
    data = _get_clinic_info_svc(query or "")
    return _tool_result(data)


@tool
def list_providers(specialty: str = "") -> str:
    """List providers. Optionally filter by specialty (e.g. Family Medicine, Pediatrics, Internal Medicine)."""
    providers = get_providers(specialty)
    if not providers:
        return _tool_result({
            "providers": [],
            "specialty_filter": specialty,
            "available_specialties": ["Family Medicine", "Internal Medicine", "Pediatrics"],
            "message": f"No providers matching '{specialty}'",
        })
    return _tool_result({
        "providers": [
            {
                "id": p["id"],
                "name": p["name"],
                "specialty": p["specialty"],
                "credentials": p["credentials"],
                "npi": p["npi"],
                "phone": p["phone"],
                "email": p["email"],
                "schedule": p["schedule"],
            }
            for p in providers
        ],
    })


@tool
def get_my_appointment_locations(patient_id: str) -> str:
    """Get locations of the patient's upcoming appointments. Use when a patient asks 'where is the clinic', 'where do I go', or 'where are my appointments'—return the locations where they have upcoming visits. When multiple different locations are returned, ask the user to specify which appointment they mean (by date or provider)."""
    data = _get_my_appointment_locations_svc(patient_id)
    return _tool_result(data)


@tool
def get_staff_assigned_clinic(staff_id: str) -> str:
    """Get the clinic/facility assigned to a staff member. Use when staff asks 'where is the clinic' or 'where is my clinic'—return their assigned facility address and hours."""
    data = _get_staff_assigned_clinic_svc(staff_id)
    return _tool_result(data)
