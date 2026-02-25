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
from typing_extensions import TypedDict

from app.config import settings
from app.data.mock_data import (
    MOCK_APPOINTMENTS,
    MOCK_AVAILABLE_SLOTS,
    MOCK_INSURANCE_PLANS,
    MOCK_MEDICAL_CONDITIONS,
    MOCK_PATIENTS,
    MOCK_PROVIDERS,
)


# --- Tools (mock data for demo; wire to OpenEMR FHIR / phpGACL in production) ---
# Tools return structured JSON. The LLM parses and formats results into human-friendly text.


def _tool_result(data: dict) -> str:
    """Serialize structured data as JSON for the LLM to parse."""
    return json.dumps(data, indent=2)


@tool
def get_clinic_info(query: str) -> str:
    """Get clinic information: hours, location, contact. Use for appointment locations and clinic info questions. Query can filter providers by specialty or name (e.g. 'pediatrics', 'Dr. Chen')."""
    q = query.lower().strip() if query else ""
    if q:
        providers = [
            p
            for p in MOCK_PROVIDERS
            if q in p["name"].lower() or q in p["specialty"].lower()
        ]
    else:
        providers = MOCK_PROVIDERS
    return _tool_result({
        "clinic": {
            "address": "123 Healthcare Ave, Suite 100",
            "hours": "Mon–Fri 8am–5pm",
            "parking": "Free parking in the lot behind the building",
            "phone": "555-0199",
        },
        "providers": [
            {
                "id": p["id"],
                "name": p["name"],
                "specialty": p["specialty"],
                "phone": p["phone"],
                "email": p["email"],
            }
            for p in providers
        ],
        "query_filter": query or None,
    })


@tool
def get_appointment_availability(date: str) -> str:
    """Check appointment availability for a given date. Use for queries about openings, available slots, or 'do you have anything on X'. Infer the date from natural language (e.g. 'next Friday', 'tomorrow') and pass YYYY-MM-DD format (e.g. 2025-02-25)."""
    slots = [s for s in MOCK_AVAILABLE_SLOTS if s["date"] == date]
    available_dates = sorted({s["date"] for s in MOCK_AVAILABLE_SLOTS})
    if not slots:
        return _tool_result({
            "date": date,
            "slots": [],
            "available_dates": available_dates,
            "message": f"No slots for {date}. Try: {', '.join(available_dates)}",
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
    if specialty:
        providers = [
            p for p in MOCK_PROVIDERS if specialty.lower() in p["specialty"].lower()
        ]
    else:
        providers = MOCK_PROVIDERS
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
    apts = [a for a in MOCK_APPOINTMENTS if a["patientId"] == patient_id]
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
    today = "2025-02-24"
    upcoming = [
        a
        for a in MOCK_APPOINTMENTS
        if a["date"] >= today and a["status"] not in ("cancelled", "completed")
    ]
    upcoming.sort(key=lambda a: (a["date"], a["time"]))
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
    slot = next((s for s in MOCK_AVAILABLE_SLOTS if s["id"] == slot_id), None)
    if not slot:
        return _tool_result({
            "success": False,
            "error": f"Slot {slot_id} not found",
            "suggestion": "Use get_appointment_availability to see available slots",
        })
    patient = next((p for p in MOCK_PATIENTS if p["id"] == patient_id), None)
    if not patient:
        return _tool_result({
            "success": False,
            "error": f"Patient {patient_id} not found",
        })
    return _tool_result({
        "success": True,
        "appointment": {
            "patientName": patient["name"],
            "date": slot["date"],
            "time": slot["time"],
            "providerName": slot["providerName"],
            "type": slot["type"],
            "duration": slot["duration"],
            "location": slot["location"],
        },
        "confirmation_note": "Confirmation will be sent via email",
    })


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
    # Match conditions where any common_symptom contains any query term
    query_terms = [t for t in query.split() if len(t) >= 2]
    matches = []
    for cond in MOCK_MEDICAL_CONDITIONS:
        symptom_text = " ".join(cond["common_symptoms"]).lower()
        cond_name_lower = cond["name"].lower()
        if any(
            term in symptom_text or term in cond_name_lower
            for term in query_terms
        ):
            matches.append({
                "name": cond["name"],
                "description": cond["description"],
                "common_symptoms": cond["common_symptoms"],
            })
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
    patient = next((p for p in MOCK_PATIENTS if p["id"] == patient_id), None)
    if not patient:
        return _tool_result({
            "error": f"Patient {patient_id} not found",
        })
    ins = next(
        (
            i
            for i in MOCK_INSURANCE_PLANS
            if i["id"] == patient.get("insurancePlanId")
        ),
        None,
    )
    prov = next(
        (
            p
            for p in MOCK_PROVIDERS
            if p["id"] == patient.get("primaryCareProviderId")
        ),
        None,
    )
    apts = [a for a in MOCK_APPOINTMENTS if a["patientId"] == patient_id]
    return _tool_result({
        "patient": {
            "id": patient["id"],
            "name": patient["name"],
            "dateOfBirth": patient["dateOfBirth"],
            "phone": patient["phone"],
            "email": patient["email"],
            "address": patient["address"],
            "emergencyContact": patient.get("emergencyContact"),
            "emergencyContactPhone": patient.get("emergencyContactPhone"),
        },
        "insurance": {
            "payerName": ins["payerName"],
            "planName": ins["planName"],
            "memberId": ins["memberId"],
        } if ins else None,
        "primaryCareProvider": prov["name"] if prov else None,
        "recentAppointments": [
            {"date": a["date"], "time": a["time"], "status": a["status"]}
            for a in apts[:5]
        ],
    })


@tool
def verify_insurance(member_id: str) -> str:
    """Verify insurance coverage. Staff only. Use member ID (e.g. MEM-987654321, AET-MEM-555123, UHC-MEM-777888) or patient ID (e.g. pat-001, test-pat-001)."""
    if member_id.startswith("pat-") or member_id.startswith("test-pat-"):
        patient = next((p for p in MOCK_PATIENTS if p["id"] == member_id), None)
        if not patient:
            return _tool_result({"error": f"Patient {member_id} not found"})
        plan = next(
            (
                i
                for i in MOCK_INSURANCE_PLANS
                if i["id"] == patient.get("insurancePlanId")
            ),
            None,
        )
        if not plan:
            return _tool_result({
                "error": f"Patient {member_id} has no insurance on file",
            })
    else:
        plan = next(
            (i for i in MOCK_INSURANCE_PLANS if i["memberId"] == member_id),
            None,
        )
        if not plan:
            return _tool_result({
                "error": f"No active insurance found for member ID {member_id}",
            })
    return _tool_result({
        "memberId": plan["memberId"],
        "plan": {
            "payerName": plan["payerName"],
            "planName": plan["planName"],
            "planType": plan["planType"],
            "groupNumber": plan["groupNumber"],
            "status": plan["status"],
            "effectiveDate": plan["effectiveDate"],
        },
        "copay": plan.get("copay") or {},
    })


# --- State ---


class MessagesState(TypedDict):
    """LangGraph state with message history. add_messages appends/merges new messages."""

    messages: Annotated[list, add_messages]
    debug_tool_calls: Annotated[list, operator.add]


# --- Model setup ---


def _get_model():
    """Claude Sonnet per PRD §4.2. Requires ANTHROPIC_API_KEY."""
    return ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
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
        list_providers,
        get_patient_appointments,
        book_appointment,
        search_medical_info,
    ]
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)

    def llm_node(state: dict) -> dict:
        msgs = [SystemMessage(content=PATIENT_SYSTEM_PROMPT)] + list(state["messages"])
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
        msgs = [SystemMessage(content=STAFF_SYSTEM_PROMPT)] + list(state["messages"])
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
    user_input: str, history: list[tuple[str, str]] | None = None
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
    initial = {"messages": messages, "debug_tool_calls": []}
    result = agent.invoke(initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    tool_calls = result.get("debug_tool_calls") if settings.debug_tool_calls else None
    return message, tool_calls


def invoke_staff_agent(
    user_input: str, history: list[tuple[str, str]] | None = None
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
    initial = {"messages": messages, "debug_tool_calls": []}
    result = agent.invoke(initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    tool_calls = result.get("debug_tool_calls") if settings.debug_tool_calls else None
    return message, tool_calls
