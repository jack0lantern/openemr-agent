"""
LangChain tools for the OpenEMR agent, organized by domain.

Modules
-------
datetime_tools     – current date/time and relative date calculations
scheduling_tools   – appointment availability, booking, and patient/staff views
clinic_tools       – clinic info, provider directory, location lookups
medical_info_tools – educational symptom/condition search (non-diagnostic)
clinical_tools     – patient record lookups for staff (allergies, meds, vitals, …)
insurance_tools    – insurance coverage verification (EDI 270/271)
"""

from app.llm.tools.clinic_tools import (
    get_clinic_info,
    get_my_appointment_locations,
    get_staff_assigned_clinic,
    list_providers,
)
from app.llm.tools.clinical_tools import (
    lookup_patient_allergies,
    lookup_patient_care_plans,
    lookup_patient_care_team,
    lookup_patient_encounters,
    lookup_patient_immunizations,
    lookup_patient_lab_reports,
    lookup_patient_medications,
    lookup_patient_procedures,
    lookup_patient_summary,
    lookup_patient_vitals,
)
from app.llm.tools.datetime_tools import get_current_datetime
from app.llm.tools.insurance_tools import verify_insurance
from app.llm.tools.medical_info_tools import search_medical_info
from app.llm.tools.scheduling_tools import (
    book_appointment,
    get_appointment_availability,
    get_patient_appointments,
    list_appointment_types,
    list_upcoming_appointments,
)

__all__ = [
    # datetime
    "get_current_datetime",
    # scheduling
    "get_appointment_availability",
    "list_appointment_types",
    "get_patient_appointments",
    "list_upcoming_appointments",
    "book_appointment",
    # clinic
    "get_clinic_info",
    "list_providers",
    "get_my_appointment_locations",
    "get_staff_assigned_clinic",
    # medical info
    "search_medical_info",
    # clinical (staff)
    "lookup_patient_summary",
    "lookup_patient_allergies",
    "lookup_patient_medications",
    "lookup_patient_vitals",
    "lookup_patient_encounters",
    "lookup_patient_immunizations",
    "lookup_patient_procedures",
    "lookup_patient_lab_reports",
    "lookup_patient_care_plans",
    "lookup_patient_care_team",
    # insurance (staff)
    "verify_insurance",
]
