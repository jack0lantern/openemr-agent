"""
Staff API - Administrative burden offload per PRD §2.1, §4.1.

Use cases: scheduling, insurance verification, clinical workflows, medication order drafts,
bloodwork review for triage. Administrative Worker tools for phpGACL and scheduling services.
"""

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.crud import append_messages, create_conversation, get_conversation_with_messages
from app.llm.agent import invoke_staff_agent
from app.schemas import ChatRequest, ChatResponse, ToolCallDebug
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


def _tool_calls_to_json(tool_calls: list[ToolCallDebug] | list[dict] | None) -> list[dict] | None:
    """Serialize tool calls for DB storage. Accepts ToolCallDebug models or plain dicts from the agent."""
    if not tool_calls:
        return None
    return [tc if isinstance(tc, dict) else tc.model_dump() for tc in tool_calls]


@router.post("/staff", response_model=ChatResponse)
async def staff_chat(
    body: ChatRequest,
    token: str | None = Depends(_get_staff_token),
    session: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Staff-facing chat endpoint. When staff_auth_required=True, requires OAuth token
    with staff/admin scope. When False, allows unauthenticated access.
    Supports: scheduling, insurance verification, medication order drafts,
    bloodwork review for triage, phpGACL and administrative tools.
    """
    if os.getenv("STAFF_AUTH_REQUIRED", "true").lower() == "true" and not token:  # AI-generated
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
            staff_id = body.staff_id if body.staff_id is not None else os.getenv("DEFAULT_STAFF_ID")
            user_id = staff_id or "unknown"

            if not os.getenv("ANTHROPIC_API_KEY", ""):
                return ChatResponse(
                    message=f"I'm your staff assistant. You asked: \"{user_input}\"\n\n"
                    "LLM integration requires ANTHROPIC_API_KEY. Please call IT support at "
                    f"{os.getenv('ESCALATION_PHONE', '555-0199')} or escalate to a human staff member."
                )

            history: list[tuple[str, str]]
            conversation_id: uuid.UUID | None = None

            if body.conversation_id:
                try:
                    cid = uuid.UUID(body.conversation_id)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid conversation_id")
                conv = await get_conversation_with_messages(session, cid)
                if conv is None:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                if conv.user_type != "staff" or conv.user_id != user_id:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                conversation_id = conv.id
                history = [(m.role, m.content) for m in conv.messages]
            else:
                history = _build_history(body.messages)

            message, tool_calls = await asyncio.to_thread(
                invoke_staff_agent,
                user_input,
                history=history if history else None,
                staff_id=staff_id,
            )

            if conversation_id is None:
                title = (user_input[:60] + "…") if len(user_input) > 60 else user_input
                conv = await create_conversation(session, "staff", user_id, title)
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
                conversation_id=str(conversation_id),
            )
        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            return ChatResponse(
                message=f"Sorry, I couldn't process your request. Please call IT support at {os.getenv('ESCALATION_PHONE', '555-0199')} or escalate to a human staff member."
            )
