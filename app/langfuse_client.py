"""
Langfuse observability for LangChain/LangGraph.

When LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, traces are sent to
Langfuse for debugging, prompt management, and analytics.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler


def _langfuse_configured() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _ensure_langfuse_env() -> None:
    """Set Langfuse env vars so CallbackHandler and get_client() use our config."""
    if _langfuse_configured():
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host


@lru_cache(maxsize=1)
def get_langfuse_handler() -> "CallbackHandler | None":
    """
    Return Langfuse CallbackHandler if configured, else None.
    Reuse a single instance across invocations.
    """
    if not _langfuse_configured():
        return None
    _ensure_langfuse_env()
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def get_invoke_config() -> dict:
    """Return config dict for agent.invoke() with Langfuse callback when enabled."""
    handler = get_langfuse_handler()
    if handler is None:
        return {}
    return {"callbacks": [handler]}


def flush_langfuse() -> None:
    """Flush pending traces to Langfuse. Call on app shutdown."""
    if not _langfuse_configured():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        pass  # Ignore flush errors during shutdown
