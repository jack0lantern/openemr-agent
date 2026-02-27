"""Clinical tools: patient record lookups for staff (allergies, medications, vitals, encounters, etc.)."""

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result
from app.services.data_service import (
    get_patient_allergies as _get_patient_allergies_svc,
    get_patient_care_plans as _get_patient_care_plans_svc,
    get_patient_care_teams as _get_patient_care_teams_svc,
    get_patient_diagnostic_reports as _get_patient_diagnostic_reports_svc,
    get_patient_encounters as _get_patient_encounters_svc,
    get_patient_immunizations as _get_patient_immunizations_svc,
    get_patient_medications as _get_patient_medications_svc,
    get_patient_observations as _get_patient_observations_svc,
    get_patient_procedures as _get_patient_procedures_svc,
    get_patient_summary as _get_patient_summary_svc,
)


@tool
def lookup_patient_summary(patient_id: str) -> str:
    """Look up a patient's summary for triage context. Staff only. Use patient ID (e.g. pat-001)."""
    result = _get_patient_summary_svc(patient_id)
    return _tool_result(result)


@tool
def lookup_patient_allergies(patient_id: str) -> str:
    """Look up a patient's allergies and intolerances. Staff only. Use patient ID (e.g. pat-001)."""
    allergies = _get_patient_allergies_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "allergies": allergies,
        "message": f"Found {len(allergies)} allergy record(s)" if allergies else "No allergies on file",
    })


@tool
def lookup_patient_medications(patient_id: str) -> str:
    """Look up a patient's current medications. Staff only. Use patient ID (e.g. pat-001)."""
    meds = _get_patient_medications_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "medications": meds,
        "message": f"Found {len(meds)} medication(s)" if meds else "No medications on file",
    })


@tool
def lookup_patient_vitals(patient_id: str, category: str = "vital-signs") -> str:
    """Look up a patient's vitals or lab results. Staff only. Use patient ID (e.g. pat-001). Category: 'vital-signs', 'laboratory', 'social-history', 'survey'."""
    obs = _get_patient_observations_svc(patient_id, category=category)
    return _tool_result({
        "patient_id": patient_id,
        "category": category,
        "observations": obs,
        "message": f"Found {len(obs)} observation(s)" if obs else f"No {category} observations on file",
    })


@tool
def lookup_patient_encounters(patient_id: str) -> str:
    """Look up a patient's visit/encounter history. Staff only. Use patient ID (e.g. pat-001)."""
    encounters = _get_patient_encounters_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "encounters": encounters,
        "message": f"Found {len(encounters)} encounter(s)" if encounters else "No encounters on file",
    })


@tool
def lookup_patient_immunizations(patient_id: str) -> str:
    """Look up a patient's immunization history. Staff only. Use patient ID (e.g. pat-001)."""
    immunizations = _get_patient_immunizations_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "immunizations": immunizations,
        "message": f"Found {len(immunizations)} immunization(s)" if immunizations else "No immunizations on file",
    })


@tool
def lookup_patient_procedures(patient_id: str) -> str:
    """Look up a patient's procedure history. Staff only. Use patient ID (e.g. pat-001)."""
    procedures = _get_patient_procedures_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "procedures": procedures,
        "message": f"Found {len(procedures)} procedure(s)" if procedures else "No procedures on file",
    })


@tool
def lookup_patient_lab_reports(patient_id: str) -> str:
    """Look up a patient's diagnostic/lab reports. Staff only. Use patient ID (e.g. pat-001). Use for bloodwork review and lab results."""
    reports = _get_patient_diagnostic_reports_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "reports": reports,
        "message": f"Found {len(reports)} report(s)" if reports else "No diagnostic reports on file",
    })


@tool
def lookup_patient_care_plans(patient_id: str) -> str:
    """Look up a patient's care plans. Staff only. Use patient ID (e.g. pat-001)."""
    plans = _get_patient_care_plans_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "care_plans": plans,
        "message": f"Found {len(plans)} care plan(s)" if plans else "No care plans on file",
    })


@tool
def lookup_patient_care_team(patient_id: str) -> str:
    """Look up a patient's care team members. Staff only. Use patient ID (e.g. pat-001)."""
    teams = _get_patient_care_teams_svc(patient_id)
    return _tool_result({
        "patient_id": patient_id,
        "care_teams": teams,
        "message": f"Found {len(teams)} care team(s)" if teams else "No care teams on file",
    })
