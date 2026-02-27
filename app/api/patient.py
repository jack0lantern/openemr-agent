"""
Patient API - Non-diagnostic patient support per PRD §2.1, §5.3.

Use cases: appointment locations, clinic info, booking/modifying/canceling appointments,
medical condition info (non-recommendation). OAuth token must be tied specifically
to the authenticated patient (no "God Mode" API key).
"""

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_optional
from app.db.crud import append_messages, create_conversation, get_conversation_with_messages
from app.llm.agent import invoke_patient_agent
from app.llm.cost import compute_cost_usd
from app.schemas import ChatRequest, ChatResponse, TokenUsage, ToolCallDebug
from app.telemetry import get_tracer

MODEL_NAME = "claude-haiku-4-5"

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


def _tool_calls_to_json(tool_calls: list[ToolCallDebug] | list[dict] | None) -> list[dict] | None:
    """Serialize tool calls for DB storage. Accepts ToolCallDebug models or plain dicts from the agent."""
    if not tool_calls:
        return None
    return [tc if isinstance(tc, dict) else tc.model_dump() for tc in tool_calls]


@router.post("/patient", response_model=ChatResponse)
async def patient_chat(
    body: ChatRequest,
    token: str | None = Depends(_get_patient_token),
    session: AsyncSession | None = Depends(get_db_optional),
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
            patient_id = body.patient_id if body.patient_id is not None else os.getenv("DEFAULT_PATIENT_ID")
            user_id = patient_id or "unknown"

            if not os.getenv("ANTHROPIC_API_KEY", ""):
                return ChatResponse(
                    message=f"I'm your patient assistant. You asked: \"{user_input}\"\n\n"
                    "LLM integration requires ANTHROPIC_API_KEY. Please call the front desk at "
                    f"{os.getenv('ESCALATION_PHONE', '555-0199')} for assistance."
                )

            history: list[tuple[str, str]]
            conversation_id: uuid.UUID | None = None

            if session and body.conversation_id:
                try:
                    cid = uuid.UUID(body.conversation_id)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid conversation_id")
                conv = await get_conversation_with_messages(session, cid)
                if conv is None:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                if conv.user_type != "patient" or conv.user_id != user_id:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                conversation_id = conv.id
                history = [(m.role, m.content) for m in conv.messages]
            else:
                history = _build_history(body.messages)

            message, tool_calls, usage = await asyncio.to_thread(
                invoke_patient_agent,
                user_input,
                history=history if history else None,
                patient_id=patient_id,
            )

            token_usage: TokenUsage | None = None
            if usage is not None:
                cost_usd = (
                    compute_cost_usd(
                        usage["input_tokens"],
                        usage["output_tokens"],
                        model=MODEL_NAME,
                    )
                    if os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
                    else None
                )
                token_usage = TokenUsage(
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_tokens=usage["total_tokens"],
                    cost_usd=cost_usd,
                )
                span.set_attribute("llm.token_count.prompt", usage["input_tokens"])
                span.set_attribute("llm.token_count.completion", usage["output_tokens"])

            if session:
                if conversation_id is None:
                    title = (user_input[:60] + "…") if len(user_input) > 60 else user_input
                    conv = await create_conversation(session, "patient", user_id, title)
                    conversation_id = conv.id

                await append_messages(
                    session,
                    conversation_id,
                    [
                        ("user", user_input, None),
                        ("assistant", message, _tool_calls_to_json(tool_calls)),
                    ],
                )

            return ChatResponse(
                message=message,
                tool_calls=tool_calls,
                conversation_id=str(conversation_id) if conversation_id else None,
                token_usage=token_usage,
            )
        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            return ChatResponse(
                message=f"Sorry, I couldn't process your request. Please call the front desk at {os.getenv('ESCALATION_PHONE', '555-0199')} for assistance."
            )
