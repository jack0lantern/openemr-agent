"""Medical information tools: educational symptom/condition search (non-diagnostic)."""

from langchain_core.tools import tool

from app.llm.tools._utils import _tool_result
from app.services.data_service import search_conditions as _search_conditions_svc
from app.services.data_service import search_pharmaceuticals as _search_pharmaceuticals_svc

_DISCLAIMER = (
    "This is educational information only. It does not constitute medical advice, "
    "diagnosis, or treatment. Always consult your healthcare provider for personal medical guidance."
)


@tool
def search_medical_info(symptoms: str) -> str:
    """Search for possible conditions associated with given symptoms. Returns educational information only—never diagnoses or recommends treatments. Use when a patient asks about symptoms, 'what could cause X', or 'conditions related to Y'. Input: symptom keywords (e.g. 'headache nausea', 'cough fever', 'stomach pain')."""
    query = (symptoms or "").lower().strip()
    if not query:
        return _tool_result({
            "conditions": [],
            "query": symptoms,
            "disclaimer": _DISCLAIMER,
            "message": "Please provide symptom keywords to search (e.g. headache, cough, stomach pain).",
        })
    matches = _search_conditions_svc(symptoms)
    return _tool_result({
        "conditions": matches,
        "query": symptoms,
        "disclaimer": _DISCLAIMER,
        "message": (
            f"Found {len(matches)} possible condition(s) associated with '{symptoms}'."
            if matches
            else f"No matching conditions found for '{symptoms}'. Consider rephrasing or consulting your provider."
        ),
    })


@tool
def search_pharmaceutical_info(query: str) -> str:
    """Search for educational information about pharmaceuticals/medications, including drug interactions. Returns non-diagnostic educational info only. Use when a patient asks about a drug, 'what is X used for', 'side effects of Y', or 'what meds interact with X'. Input: drug name or use keywords (e.g. 'lisinopril', 'warfarin', 'blood pressure', 'warfarin what meds interact')."""
    q = (query or "").lower().strip()
    if not q:
        return _tool_result({
            "medications": [],
            "query": query,
            "disclaimer": _DISCLAIMER,
            "message": "Please provide a medication name or use to search (e.g. lisinopril, blood pressure).",
        })
    matches = _search_pharmaceuticals_svc(query)
    return _tool_result({
        "medications": matches,
        "query": query,
        "disclaimer": _DISCLAIMER,
        "message": (
            f"Found {len(matches)} medication(s) matching '{query}'."
            if matches
            else f"No matching medications found for '{query}'. Consider checking the spelling or consulting your provider."
        ),
    })
