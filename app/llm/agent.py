"""
LangGraph agents for Patient and Staff chat per PRD §4.1.

- Patient Agent: appointment locations, clinic info, booking/modify/cancel,
  non-diagnostic medical info. OAuth-scoped to authenticated patient.
- Staff Agent: Clinical Worker (FHIR read, patient history) + Administrative Worker
  (phpGACL, scheduling, insurance, medication drafts, bloodwork review).
"""

from functools import lru_cache
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph, add_messages
from typing_extensions import TypedDict

from app.config import settings


# --- Placeholder tools (PRD: wire to OpenEMR FHIR / phpGACL in production) ---


@tool
def get_clinic_info(query: str) -> str:
    """Get clinic information: hours, location, contact. Use for appointment locations and clinic info questions."""
    # Placeholder: In production, query OpenEMR or static config
    return (
        "Our clinic is at 123 Healthcare Ave, Suite 100. Hours: Mon–Fri 8am–5pm. "
        "Free parking in the lot behind the building. Phone: 555-0199."
    )


@tool
def get_appointment_availability(date: str) -> str:
    """Check appointment availability for a given date. Use YYYY-MM-DD format."""
    # Placeholder: In production, deterministic availability check via OpenEMR FHIR Slot
    return f"Availability for {date}: Morning slots at 9am, 10am, 11am. Afternoon at 2pm, 3pm. Call to confirm."


@tool
def get_medical_info_non_recommendation(topic: str) -> str:
    """Get general medical information (non-diagnostic, non-recommendation). Grounded in verified sources only."""
    # Placeholder: In production, use IMO Health or verified external APIs
    return (
        f"General information about '{topic}': This is for educational purposes only. "
        "Always consult your provider for personal medical advice. I cannot diagnose or recommend treatments."
    )


# Staff-only tools (Administrative Worker)
@tool
def lookup_patient_summary(patient_id: str) -> str:
    """Look up a patient's summary for triage context. Staff only."""
    # Placeholder: In production, FHIR Patient + Condition + Observation
    return f"Patient {patient_id}: Summary placeholder. In production, FHIR read with staff scope."


@tool
def verify_insurance(member_id: str) -> str:
    """Verify insurance coverage via EDI 270/271. Staff only."""
    # Placeholder: In production, clearinghouse APIs (Office Ally, ClaimMD, Ensora)
    return f"Insurance verification for member {member_id}: Placeholder. In production, EDI 270/271 request."


# --- State ---


class MessagesState(TypedDict):
    """LangGraph state with message history. add_messages appends/merges new messages."""

    messages: Annotated[list, add_messages]


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
- Booking, modifying, or canceling appointments (patient's own only)
- General health information (non-recommendation, educational only)

Rules:
- Never diagnose, recommend treatments, or give medical advice
- For urgent symptoms (chest pain, difficulty breathing, etc.), always say: "This may be an emergency. Please call 911 or go to the nearest ER immediately."
- Use tools when appropriate. Be concise and helpful.
- If you cannot help, suggest calling the front desk at 555-0199."""


def _build_patient_agent():
    """Build LangGraph patient agent with tools."""
    model = _get_model()
    tools = [get_clinic_info, get_appointment_availability, get_medical_info_non_recommendation]
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
        for tc in last.tool_calls:
            tool_fn = tools_by_name.get(tc["name"])
            obs = tool_fn.invoke(tc["args"]) if tool_fn else "Tool not found"
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        return {"messages": results}

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
- For red-flag triage, alert staff and recommend immediate clinical review."""


def _build_staff_agent():
    """Build LangGraph staff agent with Clinical + Administrative tools."""
    model = _get_model()
    tools = [
        get_clinic_info,
        get_appointment_availability,
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
        for tc in last.tool_calls:
            tool_fn = tools_by_name.get(tc["name"])
            obs = tool_fn.invoke(tc["args"]) if tool_fn else "Tool not found"
            results.append(ToolMessage(content=str(obs), tool_call_id=tc["id"]))
        return {"messages": results}

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


def invoke_patient_agent(user_input: str, history: list[tuple[str, str]] | None = None) -> str:
    """Invoke patient agent and return the final assistant message."""
    messages: list = []
    if history:
        for role, content in history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))

    agent = get_patient_agent()
    result = agent.invoke({"messages": messages})
    final = result["messages"][-1]
    return final.content if hasattr(final, "content") else str(final)


def invoke_staff_agent(user_input: str, history: list[tuple[str, str]] | None = None) -> str:
    """Invoke staff agent and return the final assistant message."""
    messages: list = []
    if history:
        for role, content in history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))

    agent = get_staff_agent()
    result = agent.invoke({"messages": messages})
    final = result["messages"][-1]
    return final.content if hasattr(final, "content") else str(final)
