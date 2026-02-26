"""
LangGraph agents for Patient and Staff chat per PRD §4.1.

- Patient Agent: appointment locations, clinic info, booking/modify/cancel,
  non-diagnostic medical info. OAuth-scoped to authenticated patient.
- Staff Agent: Clinical Worker (FHIR read, patient history) + Administrative Worker
  (phpGACL, scheduling, insurance, medication drafts, bloodwork review).

Tools return structured JSON; the LLM formats results into human-friendly text.
"""

import json
import operator
from functools import lru_cache
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph, add_messages
from typing_extensions import NotRequired, TypedDict

from app.config import settings
from app.services.data_service import (
    book_appointment as _book_appointment_svc,
    get_available_dates,
    get_available_slots,
    get_clinic_info as _get_clinic_info_svc,
    get_my_appointment_locations as _get_my_appointment_locations_svc,
    get_patient_appointments as _get_patient_appointments_svc,
    get_patient_summary as _get_patient_summary_svc,
    get_providers,
    get_staff_assigned_clinic as _get_staff_assigned_clinic_svc,
    get_upcoming_appointments as _get_upcoming_appointments_svc,
    search_conditions as _search_conditions_svc,
    verify_insurance as _verify_insurance_svc,
)


# --- Tools (mock data for demo; wire to OpenEMR FHIR / phpGACL in production) ---
# Tools return structured JSON. The LLM parses and formats results into human-friendly text.


def _tool_result(data: dict) -> str:
    """Serialize structured data as JSON for the LLM to parse."""
    return json.dumps(data, indent=2)


@tool
def get_clinic_info(query: str) -> str:
    """Get clinic information: hours, location, contact. Use for appointment locations and clinic info questions. Query can filter providers by specialty or name (e.g. 'pediatrics', 'Dr. Chen')."""
    data = _get_clinic_info_svc(query or "")
    return _tool_result(data)


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


# AI-generated: clinic location tools for patient (appointment locations) and staff (assigned facility)
@tool
def get_my_appointment_locations(patient_id: str) -> str:
    """Get locations of the patient's upcoming appointments. Use when a patient asks 'where is my clinic' or 'where are my appointments'—return the locations where they have upcoming visits."""
    data = _get_my_appointment_locations_svc(patient_id)
    return _tool_result(data)


@tool
def get_staff_assigned_clinic(staff_id: str) -> str:
    """Get the clinic/facility assigned to a staff member. Use when staff asks 'where is the clinic' or 'where is my clinic'—return their assigned facility address and hours."""
    data = _get_staff_assigned_clinic_svc(staff_id)
    return _tool_result(data)
# End AI-generated code


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


@tool
def search_medical_info(symptoms: str) -> str:
    """Search for possible conditions associated with given symptoms. Returns educational information only—never diagnoses or recommends treatments. Use when a patient asks about symptoms, 'what could cause X', or 'conditions related to Y'. Input: symptom keywords (e.g. 'headache nausea', 'cough fever', 'stomach pain')."""
    query = (symptoms or "").lower().strip()
    if not query:
        return _tool_result({
            "conditions": [],
            "query": symptoms,
            "disclaimer": "This is educational information only. It does not constitute medical advice, diagnosis, or treatment. Always consult your healthcare provider for personal medical guidance.",
            "message": "Please provide symptom keywords to search (e.g. headache, cough, stomach pain).",
        })
    matches = _search_conditions_svc(symptoms)
    return _tool_result({
        "conditions": matches,
        "query": symptoms,
        "disclaimer": "This is educational information only. It does not constitute medical advice, diagnosis, or treatment. Always consult your healthcare provider for personal medical guidance.",
        "message": f"Found {len(matches)} possible condition(s) associated with '{symptoms}'." if matches else f"No matching conditions found for '{symptoms}'. Consider rephrasing or consulting your provider.",
    })


# Staff-only tools (Administrative Worker)
@tool
def lookup_patient_summary(patient_id: str) -> str:
    """Look up a patient's summary for triage context. Staff only. Use patient ID (e.g. pat-001)."""
    result = _get_patient_summary_svc(patient_id)
    if "error" in result:
        return _tool_result(result)
    return _tool_result(result)


@tool
def verify_insurance(member_id: str) -> str:
    """Verify insurance coverage. Staff only. Use member ID (e.g. MEM-987654321, AET-MEM-555123, UHC-MEM-777888) or patient ID (e.g. pat-001, test-pat-001)."""
    result = _verify_insurance_svc(member_id)
    return _tool_result(result)


# --- State ---


class MessagesState(TypedDict, total=False):
    """LangGraph state with message history. add_messages appends/merges new messages."""

    messages: Annotated[list, add_messages]
    debug_tool_calls: Annotated[list, operator.add]
    patient_id: str
    staff_id: str


# --- Model setup ---


def _get_model():
    """Claude Sonnet per PRD §4.2. Requires ANTHROPIC_API_KEY."""
    return ChatAnthropic(
        model="claude-haiku-4-5",
        temperature=0,
        api_key=settings.anthropic_api_key or None,
    )


# --- Patient agent ---

PATIENT_SYSTEM_PROMPT = """You are a patient assistant for a healthcare clinic. Your role is non-diagnostic support per HIPAA and clinical safety guidelines.

You help with:
- Appointment locations, clinic hours, and contact info
- Checking availability (openings, slots) — always use get_appointment_availability; infer dates from phrases like "next Friday" or "tomorrow"
- Booking, modifying, or canceling appointments (patient's own only)
- General health information (non-recommendation, educational only)

Clinic location: When a patient asks "where is my clinic" or "where are my appointments", use get_my_appointment_locations with the patient_id from context to show locations of their upcoming appointments. If no patient_id in context, use get_patient_appointments only when the patient provides their ID.

Rules:
- Never diagnose, recommend treatments, or give medical advice
- For urgent symptoms (chest pain, difficulty breathing, etc.), always say: "This may be an emergency. Please call 911 or go to the nearest ER immediately."
- Use tools when appropriate. Be concise and helpful.
- If you cannot help, suggest calling the front desk at 555-0199.

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user."""


def _build_patient_agent():
    """Build LangGraph patient agent with tools."""
    model = _get_model()
    tools = [
        get_clinic_info,
        get_appointment_availability,
        get_my_appointment_locations,
        list_providers,
        get_patient_appointments,
        book_appointment,
        search_medical_info,
    ]
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)

    def llm_node(state: dict) -> dict:
        prompt = PATIENT_SYSTEM_PROMPT
        pid = state.get("patient_id")
        if pid:
            prompt += f"\n\nContext: The authenticated patient ID is {pid}. Use this patient_id when calling get_my_appointment_locations or get_patient_appointments for the patient's own data."
        msgs = [SystemMessage(content=prompt)] + list(state["messages"])
        response = model_with_tools.invoke(msgs)
        return {"messages": [response]}

    def tool_node(state: dict) -> dict:
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return {"messages": []}
        results = []
        debug_entries = []
        for tc in last.tool_calls:
            tool_fn = tools_by_name.get(tc["name"])
            obs = tool_fn.invoke(tc["args"]) if tool_fn else "Tool not found"
            if settings.debug_tool_calls:
                debug_entries.append(
                    {"name": tc["name"], "args": dict(tc.get("args", {})), "output": str(obs)}
                )
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        out: dict = {"messages": results}
        if debug_entries:
            out["debug_tool_calls"] = debug_entries
        return out

    def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(MessagesState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue, ["tools", END])
    graph.add_edge("tools", "llm")
    return graph.compile()


# --- Staff agent ---

STAFF_SYSTEM_PROMPT = """You are a staff assistant for a healthcare clinic. You help administrative and clinical staff with:

- Scheduling and appointment management
- Insurance verification (EDI 270/271)
- Patient summaries for triage context
- Medication order drafts (staged for provider sign-off)
- Bloodwork review for triage

Clinic location: When staff asks "where is the clinic" or "where is my clinic", use get_staff_assigned_clinic with the staff_id from context to show their assigned facility. If no staff_id in context, use get_clinic_info for generic clinic info.

Rules:
- Clinical recommendations must be drafts requiring clinician approval
- Use tools for patient lookups, insurance verification
- Be concise. Escalate to human when uncertain.
- For red-flag triage, alert staff and recommend immediate clinical review.

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user."""


def _build_staff_agent():
    """Build LangGraph staff agent with Clinical + Administrative tools."""
    model = _get_model()
    tools = [
        get_clinic_info,
        get_appointment_availability,
        get_staff_assigned_clinic,
        list_providers,
        get_patient_appointments,
        list_upcoming_appointments,
        book_appointment,
        search_medical_info,
        lookup_patient_summary,
        verify_insurance,
    ]
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)

    def llm_node(state: dict) -> dict:
        prompt = STAFF_SYSTEM_PROMPT
        sid = state.get("staff_id")
        if sid:
            prompt += f"\n\nContext: The authenticated staff ID is {sid}. Use this staff_id when calling get_staff_assigned_clinic for 'where is the clinic'."
        msgs = [SystemMessage(content=prompt)] + list(state["messages"])
        response = model_with_tools.invoke(msgs)
        return {"messages": [response]}

    def tool_node(state: dict) -> dict:
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return {"messages": []}
        results = []
        debug_entries = []
        for tc in last.tool_calls:
            tool_fn = tools_by_name.get(tc["name"])
            obs = tool_fn.invoke(tc["args"]) if tool_fn else "Tool not found"
            if settings.debug_tool_calls:
                debug_entries.append(
                    {"name": tc["name"], "args": dict(tc.get("args", {})), "output": str(obs)}
                )
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        out: dict = {"messages": results}
        if debug_entries:
            out["debug_tool_calls"] = debug_entries
        return out

    def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(MessagesState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue, ["tools", END])
    graph.add_edge("tools", "llm")
    return graph.compile()


# --- Public API (lazy init to avoid startup cost) ---


@lru_cache(maxsize=1)
def get_patient_agent():
    return _build_patient_agent()


@lru_cache(maxsize=1)
def get_staff_agent():
    return _build_staff_agent()


def invoke_patient_agent(
    user_input: str,
    history: list[tuple[str, str]] | None = None,
    patient_id: str | None = None,
) -> tuple[str, list[dict] | None]:
    """Invoke patient agent and return (message, tool_calls or None)."""
    messages: list = []
    if history:
        for role, content in history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))

    agent = get_patient_agent()
    initial: dict = {"messages": messages, "debug_tool_calls": []}
    if patient_id:
        initial["patient_id"] = patient_id
    result = agent.invoke(initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    tool_calls = result.get("debug_tool_calls") if settings.debug_tool_calls else None
    return message, tool_calls


def invoke_staff_agent(
    user_input: str,
    history: list[tuple[str, str]] | None = None,
    staff_id: str | None = None,
) -> tuple[str, list[dict] | None]:
    """Invoke staff agent and return (message, tool_calls or None)."""
    messages: list = []
    if history:
        for role, content in history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))

    agent = get_staff_agent()
    initial: dict = {"messages": messages, "debug_tool_calls": []}
    if staff_id:
        initial["staff_id"] = staff_id
    result = agent.invoke(initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    tool_calls = result.get("debug_tool_calls") if settings.debug_tool_calls else None
    return message, tool_calls
