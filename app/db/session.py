"""Async database session and engine setup."""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


def _get_database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return None
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_url = _get_database_url()
engine = (
    create_async_engine(
        _url,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )
    if _url
    else None
)

AsyncSessionLocal = (
    async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    if engine
    else None
)


async def init_db() -> None:
    """Create all tables. Safe to call on startup (idempotent for existing tables).
    No-op if DATABASE_URL is not set."""
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency that yields an async session. Raises if DATABASE_URL is not set."""
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is required for conversation persistence. "
            "Set DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db"
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_optional():
    """Dependency that yields an async session or None if DATABASE_URL is not set."""
    if AsyncSessionLocal is None:
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
