from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)


class ToolCallDebug(BaseModel):
    """Structured tool call info for debug display."""

    name: str
    args: dict
    output: str


class ChatResponse(BaseModel):
    message: str
    tool_calls: list[ToolCallDebug] | None = None
