"""
Test-only batch invocation helpers for parallel agent execution.

Runs multiple agent invocations in parallel via LangGraph's batch() to reduce
golden path test suite wall time. Not used in production.
"""

import os  # AI-generated

from langchain_core.messages import AIMessage, HumanMessage

from app.llm.agent import get_patient_agent, get_staff_agent
from app.llm.retry import invoke_with_retry


def _messages_from_request(
    user_input: str, history: list[tuple[str, str]] | None
) -> list:
    """Build message list from user_input and optional history."""
    messages: list = []
    if history:
        for role, content in history:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))
    return messages


def batch_invoke_patient_agent(
    requests: list[
        tuple[str, list[tuple[str, str]] | None]
        | tuple[str, list[tuple[str, str]] | None, dict]
    ],
) -> list[tuple[str, list[dict] | None]]:
    """Run multiple patient agent invocations in parallel via batch.

    Each request is (user_input, history) or (user_input, history, {"patient_id": "..."}).
    """
    agent = get_patient_agent()
    initials = []
    for item in requests:
        user_input = item[0]
        history = item[1]
        extra = item[2] if len(item) >= 3 and item[2] else {}
        initial: dict = {
            "messages": _messages_from_request(user_input, history),
            "debug_tool_calls": [],
        }
        if extra.get("patient_id"):
            initial["patient_id"] = extra["patient_id"]
        initials.append(initial)
    results = invoke_with_retry(agent.batch, initials)
    outputs = []
    for result in results:
        final = result["messages"][-1]
        message = final.content if hasattr(final, "content") else str(final)
        tool_calls = result.get("debug_tool_calls") if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None  # AI-generated
        outputs.append((message, tool_calls))
    return outputs


def batch_invoke_staff_agent(
    requests: list[
        tuple[str, list[tuple[str, str]] | None]
        | tuple[str, list[tuple[str, str]] | None, dict]
    ],
) -> list[tuple[str, list[dict] | None]]:
    """Run multiple staff agent invocations in parallel via batch.

    Each request is (user_input, history) or (user_input, history, {"staff_id": "..."}).
    """
    agent = get_staff_agent()
    initials = []
    for item in requests:
        user_input = item[0]
        history = item[1]
        extra = item[2] if len(item) >= 3 and item[2] else {}
        initial: dict = {
            "messages": _messages_from_request(user_input, history),
            "debug_tool_calls": [],
        }
        if extra.get("staff_id"):
            initial["staff_id"] = extra["staff_id"]
        initials.append(initial)
    results = invoke_with_retry(agent.batch, initials)
    outputs = []
    for result in results:
        final = result["messages"][-1]
        message = final.content if hasattr(final, "content") else str(final)
        tool_calls = result.get("debug_tool_calls") if os.getenv("DEBUG_TOOL_CALLS", "false").lower() == "true" else None  # AI-generated
        outputs.append((message, tool_calls))
    return outputs
