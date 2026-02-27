"""
Conversations API - List, get, delete, and rename saved chat conversations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_optional
from app.db.crud import (
    delete_conversation,
    get_conversation_with_messages,
    list_conversations,
    update_conversation_title,
)
from app.schemas import ChatMessage, ConversationDetail, ConversationSummary

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class RenameConversationBody(BaseModel):
    title: str


@router.get("", response_model=list[ConversationSummary])
async def list_conversations_endpoint(
    user_type: str = Query(..., pattern="^(patient|staff)$"),
    user_id: str = Query(..., min_length=1),
    session: AsyncSession | None = Depends(get_db_optional),
) -> list[ConversationSummary]:
    """List conversations for a user, most recent first."""
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation persistence is not configured. Set DATABASE_URL.",
        )
    convs = await list_conversations(session, user_type, user_id)
    return [
        ConversationSummary(
            id=str(c.id),
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: str,
    user_type: str = Query(..., pattern="^(patient|staff)$"),
    user_id: str = Query(..., min_length=1),
    session: AsyncSession | None = Depends(get_db_optional),
) -> ConversationDetail:
    """Get a conversation with its messages. Returns 404 if not found or not owned by user."""
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation persistence is not configured. Set DATABASE_URL.",
        )
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conv = await get_conversation_with_messages(session, cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_type != user_type or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in conv.messages
    ]
    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        messages=messages,
        created_at=conv.created_at,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: str,
    user_type: str = Query(..., pattern="^(patient|staff)$"),
    user_id: str = Query(..., min_length=1),
    session: AsyncSession | None = Depends(get_db_optional),
) -> None:
    """Delete a conversation. Returns 404 if not found or not owned by user."""
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation persistence is not configured. Set DATABASE_URL.",
        )
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conv = await get_conversation_with_messages(session, cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_type != user_type or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    deleted = await delete_conversation(session, cid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation_endpoint(
    conversation_id: str,
    body: RenameConversationBody,
    user_type: str = Query(..., pattern="^(patient|staff)$"),
    user_id: str = Query(..., min_length=1),
    session: AsyncSession | None = Depends(get_db_optional),
) -> ConversationSummary:
    """Rename a conversation. Returns 404 if not found or not owned by user."""
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation persistence is not configured. Set DATABASE_URL.",
        )
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conv = await update_conversation_title(
        session, cid, body.title, user_type=user_type, user_id=user_id
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationSummary(
        id=str(conv.id),
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )
