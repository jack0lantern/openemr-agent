"""
Patient API - Non-diagnostic patient support per PRD §2.1, §5.3.

Use cases: appointment locations, clinic info, booking/modifying/canceling appointments,
medical condition info (non-recommendation). OAuth token must be tied specifically
to the authenticated patient (no "God Mode" API key).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["patient"])
security = HTTPBearer(auto_error=False)


def _get_patient_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str | None:
    """Extract Bearer token. In production, validate against OpenEMR OAuth and ensure patient scope."""
    if credentials is None:
        return None
    return credentials.credentials


@router.post("/patient", response_model=ChatResponse)
async def patient_chat(
    body: ChatRequest,
    token: str | None = Depends(_get_patient_token),
) -> ChatResponse:
    """
    Patient-facing chat endpoint. Requires OAuth token tied to the authenticated patient.
    Supports: appointment info, clinic info, booking/modify/cancel, non-diagnostic medical info.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization required. OAuth token tied to the authenticated patient is required.",
        )

    last_message = body.messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="Invalid request: expected user message")

    # Placeholder: In production, validate token with OpenEMR, extract patient_id,
    # and invoke LangGraph agent with patient-scoped tools (appointments, clinic info, etc.)
    user_input = last_message.content.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    # Degrade gracefully per PRD §5.2: on failure, include escalation number
    try:
        # TODO: Wire to LangGraph patient agent with tools:
        # - get_clinic_info, get_appointment_locations
        # - book_appointment, modify_appointment, cancel_appointment (patient's own only)
        # - get_medical_info_non_recommendation (grounded in verified sources)
        response = (
            f"I'm your patient assistant. You asked: \"{user_input}\"\n\n"
            "I can help with appointment locations, clinic info, booking or changing appointments, "
            "and general health information (non-diagnostic). "
            "Full agent integration with OpenEMR FHIR is coming soon."
        )
        return ChatResponse(message=response)
    except Exception:
        return ChatResponse(
            message=f"Sorry, I couldn't process your request. Please call the front desk at {settings.escalation_phone} for assistance."
        )
