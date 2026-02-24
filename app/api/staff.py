"""
Staff API - Administrative burden offload per PRD §2.1, §4.1.

Use cases: scheduling, insurance verification, clinical workflows, medication order drafts,
bloodwork review for triage. Administrative Worker tools for phpGACL and scheduling services.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.llm.agent import invoke_staff_agent
from app.schemas import ChatRequest, ChatResponse
from app.telemetry import get_tracer

router = APIRouter(prefix="/api/chat", tags=["staff"])
security = HTTPBearer(auto_error=False)


def _get_staff_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str | None:
    """Extract Bearer token. In production, validate against OpenEMR OAuth and ensure staff/admin scope."""
    if credentials is None:
        return None
    return credentials.credentials


def _build_history(messages: list) -> list[tuple[str, str]]:
    """Convert chat messages to (role, content) history, excluding the last user message."""
    history: list[tuple[str, str]] = []
    for m in messages[:-1]:
        history.append((m.role, m.content))
    return history


@router.post("/staff", response_model=ChatResponse)
async def staff_chat(
    body: ChatRequest,
    token: str | None = Depends(_get_staff_token),
) -> ChatResponse:
    """
    Staff-facing chat endpoint. Requires OAuth token with staff/admin scope.
    Supports: scheduling, insurance verification, medication order drafts,
    bloodwork review for triage, phpGACL and administrative tools.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization required. OAuth token with staff scope is required.",
        )

    last_message = body.messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="Invalid request: expected user message")

    user_input = last_message.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    tracer = get_tracer()
    with tracer.start_as_current_span("staff_chat.invoke_agent") as span:
        span.set_attribute("agent.type", "staff")
        span.set_attribute("message.length", len(user_input))

        try:
            if not settings.anthropic_api_key:
                return ChatResponse(
                    message=f"I'm your staff assistant. You asked: \"{user_input}\"\n\n"
                    "LLM integration requires ANTHROPIC_API_KEY. Please call IT support at "
                    f"{settings.escalation_phone} or escalate to a human staff member."
                )
            history = _build_history(body.messages)
            response = await asyncio.to_thread(
                invoke_staff_agent, user_input, history=history if history else None
            )
            return ChatResponse(message=response)
        except Exception as e:
            span.record_exception(e)
            return ChatResponse(
                message=f"Sorry, I couldn't process your request. Please call IT support at {settings.escalation_phone} or escalate to a human staff member."
            )
