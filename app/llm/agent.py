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
import os
from functools import lru_cache
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph, add_messages
from typing_extensions import TypedDict

from app.langsmith_client import add_cost_breakdown_to_langsmith
from app.schemas import Citation, ResponseMetadata
from app.llm.cost import compute_cost_usd
from app.llm.retry import invoke_with_retry
from app.llm.tools import (
    book_appointment,
    get_appointment_availability,
    get_clinic_info,
    list_appointment_types,
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
- Checking availability (openings, slots) — always use get_appointment_availability. For any appointment interaction (availability, booking, listing), call get_current_datetime FIRST to establish the current date/time, then use only future dates when calling get_appointment_availability or booking. When the user uses relative expressions like "tomorrow", "next Friday", "next week", or "next month", use get_current_datetime to resolve the exact date(s). When the user specifies an appointment type (e.g. "new patient visit", "follow-up", "checkup"), pass the appointment_type parameter to get_appointment_availability so only slots that fit that duration are proposed. Use list_appointment_types to see available types and their durations.
- Booking, modifying, or canceling appointments (patient's own only)
- General health information (non-recommendation, educational only)

Clinic location: When a patient asks "where is the clinic", "where do I go", "where is my appointment", or similar, use get_my_appointment_locations with the patient_id from context to pull locations from their upcoming appointments. If the result has multiple different locations, ask the user to specify which appointment they mean (e.g., by date or provider). If no upcoming appointments or no patient_id in context, use get_clinic_info for generic clinic address and hours. If no patient_id in context and the patient provides their ID, use get_patient_appointments.

Rules:
- Never diagnose, recommend treatments, or give medical advice
- For urgent symptoms (chest pain, difficulty breathing, etc.), always say: "This may be an emergency. Please call 911 or go to the nearest ER immediately."
- Use tools when appropriate. Be concise and helpful.
- If you cannot help, suggest calling the front desk at 555-0199.
- When the user mentions any relative time expression ("today", "tomorrow", "next week", "next month", "in two weeks", etc.), call get_current_datetime FIRST to resolve the real calendar date, then use the result when calling date-dependent tools.
- For appointment-related interactions (availability, booking, listing), always call get_current_datetime FIRST to ensure only future appointments can be booked.

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user.

When reporting search_medical_info results: (1) cite the source for each condition (e.g. "According to MedlinePlus..."); (2) include the url link when the tool result provides one (e.g. "Learn more: [condition name](url)"); (3) incorporate confidence naturally (e.g. "Migraine is a high-confidence match for your symptoms"); (4) always include the educational disclaimer."""


def _build_patient_agent():
    """Build LangGraph patient agent with tools."""
    model = _get_model()
    tools = [
        get_current_datetime,
        get_clinic_info,
        list_appointment_types,
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
            debug_entries.append(
                {"name": tc["name"], "args": dict(tc.get("args", {})), "output": str(obs)}
            )
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        out: dict = {"messages": results, "debug_tool_calls": debug_entries}
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

- Scheduling and appointment management — when the user specifies an appointment type (e.g. "new patient", "follow-up"), pass appointment_type to get_appointment_availability so only slots that fit that duration are proposed. Use list_appointment_types to see available types and durations.
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

Tool results are returned as JSON. Parse the JSON and format the data into clear, human-friendly text for the user. Do not dump raw JSON to the user.

When reporting search_medical_info results: (1) cite the source for each condition (e.g. "According to MedlinePlus..."); (2) include the url link when the tool result provides one (e.g. "Learn more: [condition name](url)"); (3) incorporate confidence naturally (e.g. "Migraine is a high-confidence match for your symptoms"); (4) always include the educational disclaimer."""


def _build_staff_agent():
    """Build LangGraph staff agent with Clinical + Administrative tools."""
    model = _get_model()
    tools = [
        get_current_datetime,
        get_clinic_info,
        list_appointment_types,
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
            debug_entries.append(
                {"name": tc["name"], "args": dict(tc.get("args", {})), "output": str(obs)}
            )
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        out: dict = {"messages": results, "debug_tool_calls": debug_entries}
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


# --- Usage aggregation ---


def _aggregate_usage(messages: list) -> dict | None:
    """
    Aggregate usage_metadata from all AIMessages in the result.
    Returns {"input_tokens": int, "output_tokens": int, "total_tokens": int} or None.
    """
    total_input = 0
    total_output = 0
    total_total = 0
    found = False
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        meta = getattr(msg, "usage_metadata", None) or (
            getattr(msg, "response_metadata", None) or {}
        ).get("usage")
        if not meta or not isinstance(meta, dict):
            continue
        inp = meta.get("input_tokens") if meta.get("input_tokens") is not None else meta.get("input_token_count")
        out = meta.get("output_tokens") if meta.get("output_tokens") is not None else meta.get("output_token_count")
        tot = meta.get("total_tokens") if meta.get("total_tokens") is not None else meta.get("total_token_count")
        if inp is not None:
            total_input += int(inp)
            found = True
        if out is not None:
            total_output += int(out)
            found = True
        if tot is not None:
            total_total += int(tot)
    if not found:
        return None
    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_total or total_input + total_output,
    }


def _extract_response_metadata(tool_calls_debug: list[dict] | None) -> ResponseMetadata | None:
    """
    Extract citations and confidence from search_medical_info tool outputs.
    Returns None when no medical info tool was called.
    """
    if not tool_calls_debug:
        return None
    citations: list[Citation] = []
    match_scores: list[float] = []
    source = "OpenEMR Medical Reference"
    for tc in tool_calls_debug:
        if tc.get("name") != "search_medical_info":
            continue
        try:
            data = json.loads(tc.get("output", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
        conditions = data.get("conditions") or []
        for cond in conditions:
            name = cond.get("name")
            if name:
                url = cond.get("url") if isinstance(cond.get("url"), str) else None
                citations.append(
                    Citation(title=name, source=source, tool_name="search_medical_info", url=url)
                )
            score = cond.get("match_score")
            if isinstance(score, (int, float)):
                match_scores.append(float(score))
    if not citations:
        return None
    top_score = max(match_scores) if match_scores else None
    if top_score is not None:
        if top_score >= 0.7:
            label = "High"
        elif top_score >= 0.4:
            label = "Medium"
        else:
            label = "Low"
    else:
        label = None
    return ResponseMetadata(
        citations=citations,
        confidence=top_score,
        confidence_label=label,
    )


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
) -> tuple[str, list[dict] | None, dict | None, ResponseMetadata | None]:
    """Invoke patient agent and return (message, tool_calls or None, usage or None, metadata or None)."""
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
    result = invoke_with_retry(agent.invoke, initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    all_tool_calls = result.get("debug_tool_calls") or []
    tool_calls = all_tool_calls if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None
    usage = _aggregate_usage(result["messages"])
    if usage is not None:
        cost_usd = (
            compute_cost_usd(
                usage["input_tokens"],
                usage["output_tokens"],
                model="claude-haiku-4-5",
            )
            if os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
            else None
        )
        add_cost_breakdown_to_langsmith(
            usage["input_tokens"],
            usage["output_tokens"],
            usage["total_tokens"],
            cost_usd,
            model="claude-haiku-4-5",
        )
    metadata = _extract_response_metadata(all_tool_calls)
    return message, tool_calls, usage, metadata


def invoke_staff_agent(
    user_input: str,
    history: list[tuple[str, str]] | None = None,
    staff_id: str | None = None,
) -> tuple[str, list[dict] | None, dict | None, ResponseMetadata | None]:
    """Invoke staff agent and return (message, tool_calls or None, usage or None, metadata or None)."""
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
    result = invoke_with_retry(agent.invoke, initial)
    final = result["messages"][-1]
    message = final.content if hasattr(final, "content") else str(final)
    all_tool_calls = result.get("debug_tool_calls") or []
    tool_calls = all_tool_calls if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None
    usage = _aggregate_usage(result["messages"])
    if usage is not None:
        cost_usd = (
            compute_cost_usd(
                usage["input_tokens"],
                usage["output_tokens"],
                model="claude-haiku-4-5",
            )
            if os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
            else None
        )
        add_cost_breakdown_to_langsmith(
            usage["input_tokens"],
            usage["output_tokens"],
            usage["total_tokens"],
            cost_usd,
            model="claude-haiku-4-5",
        )
    metadata = _extract_response_metadata(all_tool_calls)
    return message, tool_calls, usage, metadata
