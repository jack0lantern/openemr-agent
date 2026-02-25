"""
LangSmith observability for LangChain/LangGraph.

When LANGSMITH_API_KEY is set, traces are sent to LangSmith for debugging,
prompt management, and analytics. LangChain/LangGraph auto-trace via env vars.

Uses only environment variables: LANGSMITH_API_KEY, LANGSMITH_TRACING,
LANGSMITH_PROJECT (optional).
"""

import os


def _langsmith_configured() -> bool:
    return bool(
        os.environ.get("LANGSMITH_API_KEY")
        and os.environ.get("LANGSMITH_TRACING", "true").lower() != "false"
    )


def flush_langsmith() -> None:
    """Flush pending traces to LangSmith. Call on app shutdown."""
    if not _langsmith_configured():
        return
    try:
        from langsmith import Client

        Client().flush()
    except Exception:
        pass  # Ignore flush errors during shutdown
