from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    # In production, resolved from OAuth token. For demo, frontend can send when known.
    patient_id: str | None = None
    staff_id: str | None = None
    conversation_id: str | None = None


class ToolCallDebug(BaseModel):
    """Structured tool call info for debug display."""

    name: str
    args: dict
    output: str


class TokenUsage(BaseModel):
    """Token usage and optional cost per request."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float | None = None


class ChatResponse(BaseModel):
    message: str
    tool_calls: list[ToolCallDebug] | None = None
    conversation_id: str | None = None
    token_usage: TokenUsage | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[ChatMessage]
    created_at: datetime
