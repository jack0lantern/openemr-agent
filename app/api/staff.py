"""
Staff API - Administrative burden offload per PRD §2.1, §4.1.

Use cases: scheduling, insurance verification, clinical workflows, medication order drafts,
bloodwork review for triage. Administrative Worker tools for phpGACL and scheduling services.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["staff"])
security = HTTPBearer(auto_error=False)


def _get_staff_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str | None:
    """Extract Bearer token. In production, validate against OpenEMR OAuth and ensure staff/admin scope."""
    if credentials is None:
        return None
    return credentials.credentials


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

    # Placeholder: In production, validate token with OpenEMR, verify staff role via phpGACL,
    # and invoke LangGraph orchestrator with Clinical + Administrative workers
    user_input = last_message.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    # Degrade gracefully per PRD §5.2: on failure, include escalation number
    try:
        # TODO: Wire to LangGraph orchestrator with:
        # - Clinical Worker: FHIR read, patient history summary
        # - Administrative Worker: phpGACL, scheduling, insurance (EDI 270/271),
        #   medication order drafts (staged for provider sign-off), bloodwork review
        response = (
            f"I'm your staff assistant. You asked: \"{user_input}\"\n\n"
            "I can help with scheduling, insurance verification, medication order drafts, "
            "bloodwork review for triage, and other administrative tasks. "
            "Full agent integration with OpenEMR is coming soon."
        )
        return ChatResponse(message=response)
    except Exception:
        return ChatResponse(
            message=f"Sorry, I couldn't process your request. Please call IT support at {settings.escalation_phone} or escalate to a human staff member."
        )
