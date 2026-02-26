"""
Patient API - Non-diagnostic patient support per PRD §2.1, §5.3.

Use cases: appointment locations, clinic info, booking/modifying/canceling appointments,
medical condition info (non-recommendation). OAuth token must be tied specifically
to the authenticated patient (no "God Mode" API key).
"""

import asyncio
import os  # AI-generated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.llm.agent import invoke_patient_agent
from app.schemas import ChatRequest, ChatResponse
from app.telemetry import get_tracer

router = APIRouter(prefix="/api/chat", tags=["patient"])
security = HTTPBearer(auto_error=False)


def _get_patient_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str | None:
    """Extract Bearer token. In production, validate against OpenEMR OAuth and ensure patient scope."""
    if credentials is None:
        return None
    return credentials.credentials


def _build_history(messages: list) -> list[tuple[str, str]]:
    """Convert chat messages to (role, content) history, excluding the last user message."""
    history: list[tuple[str, str]] = []
    for m in messages[:-1]:
        history.append((m.role, m.content))
    return history


@router.post("/patient", response_model=ChatResponse)
async def patient_chat(
    body: ChatRequest,
    token: str | None = Depends(_get_patient_token),
) -> ChatResponse:
    """
    Patient-facing chat endpoint. When patient_auth_required=True, requires OAuth token
    tied to the authenticated patient. When False, allows unauthenticated access.
    Supports: appointment info, clinic info, booking/modify/cancel, non-diagnostic medical info.
    """
    if os.getenv("PATIENT_AUTH_REQUIRED", "true").lower() == "true" and not token:  # AI-generated
        raise HTTPException(
            status_code=401,
            detail="Authorization required. OAuth token tied to the authenticated patient is required.",
        )

    last_message = body.messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="Invalid request: expected user message")

    user_input = last_message.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    tracer = get_tracer()
    with tracer.start_as_current_span("patient_chat.invoke_agent") as span:
        span.set_attribute("agent.type", "patient")
        span.set_attribute("message.length", len(user_input))

        try:
            if not os.getenv("ANTHROPIC_API_KEY", ""):  # AI-generated
                return ChatResponse(
                    message=f"I'm your patient assistant. You asked: \"{user_input}\"\n\n"
                    "LLM integration requires ANTHROPIC_API_KEY. Please call the front desk at "
                    f"{os.getenv('ESCALATION_PHONE', '555-0199')} for assistance."  # AI-generated
                )
            history = _build_history(body.messages)
            patient_id = body.patient_id if body.patient_id is not None else os.getenv("DEFAULT_PATIENT_ID")  # AI-generated
            message, tool_calls = await asyncio.to_thread(
                invoke_patient_agent,
                user_input,
                history=history if history else None,
                patient_id=patient_id,
            )
            return ChatResponse(message=message, tool_calls=tool_calls)
        except Exception as e:
            span.record_exception(e)
            return ChatResponse(
                message=f"Sorry, I couldn't process your request. Please call the front desk at {os.getenv('ESCALATION_PHONE', '555-0199')} for assistance."  # AI-generated
            )
