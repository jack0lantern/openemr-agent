"""
LangGraph agents for Patient and Staff chat per PRD §4.1.

- Patient Agent: appointment locations, clinic info, booking/modify/cancel,
  non-diagnostic medical info. OAuth-scoped to authenticated patient.
- Staff Agent: Clinical Worker (FHIR read, patient history) + Administrative Worker
  (phpGACL, scheduling, insurance, medication drafts, bloodwork review).

Tools return structured JSON; the LLM formats results into human-friendly text.
"""

import operator
import os
from functools import lru_cache
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph, add_messages
from typing_extensions import TypedDict

from app.llm.tools import (
    book_appointment,
    get_appointment_availability,
    get_clinic_info,
    get_current_datetime,
    get_my_appointment_locations,
    get_patient_appointments,
    get_staff_assigned_clinic,
    list_providers,
    list_upcoming_appointments,
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
    search_medical_info,
    verify_insurance,
)


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
        api_key=os.getenv("ANTHROPIC_API_KEY") or None,
    )


# --- Patient agent ---

PATIENT_SYSTEM_PROMPT = """You are a patient assistant for a healthcare clinic. Your role is non-diagnostic support per HIPAA and clinical safety guidelines.

You help with:
- Appointment locations, clinic hours, and contact info
- Checking availability (openings, slots) — always use get_appointment_availability. For any appointment interaction (availability, booking, listing), call get_current_datetime FIRST to establish the current date/time, then use only future dates when calling get_appointment_availability or booking. When the user uses relative expressions like "tomorrow", "next Friday", "next week", or "next month", use get_current_datetime to resolve the exact date(s).
- Booking, modifying, or canceling appointments (patient's own only)
- General health information (non-recommendation, educational only)

Clinic location: When a patient asks "where is my clinic" or "where are my appointments", use get_my_appointment_locations with the patient_id from context to show locations of their upcoming appointments. If no patient_id in context, use get_patient_appointments only when the patient provides their ID.

Rules:
- Never diagnose, recommend treatments, or give medical advice
- For urgent symptoms (chest pain, difficulty breathing, etc.), always say: "This may be an emergency. Please call 911 or go to the nearest ER immediately."
- Use tools when appropriate. Be concise and helpful.
- If you cannot help, suggest calling the front desk at 555-0199.
- When the user mentions any relative time expression ("today", "tomorrow", "next week", "next month", "in two weeks", etc.), call get_current_datetime FIRST to resolve the real calendar date, then use the result when calling date-dependent tools.
- For appointment-related interactions (availability, booking, listing), always call get_current_datetime FIRST to ensure only future appointments can be booked.

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user."""


def _build_patient_agent():
    """Build LangGraph patient agent with tools."""
    model = _get_model()
    tools = [
        get_current_datetime,
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
            if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true":
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
- Clinical data review: allergies, medications, vitals, lab results, immunizations, procedures, encounters
- Care plans and care team lookups
- Bloodwork and diagnostic report review for triage
- Medication order drafts (staged for provider sign-off)

Clinic location: When staff asks "where is the clinic" or "where is my clinic", use get_staff_assigned_clinic with the staff_id from context to show their assigned facility. If no staff_id in context, use get_clinic_info for generic clinic info.

Rules:
- Clinical recommendations must be drafts requiring clinician approval
- Use tools for patient lookups, insurance verification, and clinical data review
- Be concise. Escalate to human when uncertain.
- For red-flag triage, alert staff and recommend immediate clinical review.
- When the user mentions any relative time expression ("today", "tomorrow", "next week", "next month", "in two weeks", etc.), call get_current_datetime FIRST to resolve the real calendar date, then use the result when calling date-dependent tools.
- For appointment-related interactions (availability, booking, listing), always call get_current_datetime FIRST to ensure only future appointments can be booked.

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user."""


def _build_staff_agent():
    """Build LangGraph staff agent with Clinical + Administrative tools."""
    model = _get_model()
    tools = [
        get_current_datetime,
        get_clinic_info,
        get_appointment_availability,
        get_staff_assigned_clinic,
        list_providers,
        get_patient_appointments,
        list_upcoming_appointments,
        book_appointment,
        search_medical_info,
        lookup_patient_summary,
        lookup_patient_allergies,
        lookup_patient_medications,
        lookup_patient_vitals,
        lookup_patient_encounters,
        lookup_patient_immunizations,
        lookup_patient_procedures,
        lookup_patient_lab_reports,
        lookup_patient_care_plans,
        lookup_patient_care_team,
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
            if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true":
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
    tool_calls = result.get("debug_tool_calls") if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None
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
    tool_calls = result.get("debug_tool_calls") if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None
    return message, tool_calls
