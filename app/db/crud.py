"""CRUD operations for conversations and messages."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, ConversationMessage


async def create_conversation(
    session: AsyncSession,
    user_type: str,
    user_id: str,
    title: str,
) -> Conversation:
    """Create a new conversation."""
    conv = Conversation(
        user_type=user_type,
        user_id=user_id,
        title=title,
    )
    session.add(conv)
    await session.flush()
    return conv


async def append_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    messages: list[tuple[str, str, dict | None]],
) -> None:
    """Append messages to a conversation. Each tuple is (role, content, tool_calls_json)."""
    for role, content, tool_calls_json in messages:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls_json,
        )
        session.add(msg)
    await session.flush()


async def list_conversations(
    session: AsyncSession,
    user_type: str,
    user_id: str,
    limit: int = 50,
) -> list[Conversation]:
    """List conversations for a user, most recent first."""
    result = await session.execute(
        select(Conversation)
        .where(
            Conversation.user_type == user_type,
            Conversation.user_id == user_id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_conversation_with_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """Get a conversation with its messages, or None if not found."""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    return result.scalar_one_or_none()


async def delete_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> bool:
    """Delete a conversation. Returns True if deleted, False if not found."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        return False
    await session.delete(conv)
    await session.flush()
    return True


async def update_conversation_title(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    title: str,
    user_type: str | None = None,
    user_id: str | None = None,
) -> Conversation | None:
    """Update a conversation's title. Returns the conversation or None if not found.
    If user_type and user_id are provided, validates ownership."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        return None
    if user_type is not None and user_id is not None:
        if conv.user_type != user_type or conv.user_id != user_id:
            return None
    conv.title = title
    await session.flush()
    return conv
