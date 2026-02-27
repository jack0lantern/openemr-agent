"""
LangSmith observability for LangChain/LangGraph.

When LANGSMITH_API_KEY is set, traces are sent to LangSmith for debugging,
prompt management, and analytics. LangChain/LangGraph auto-trace via env vars.

Uses only environment variables: LANGSMITH_API_KEY, LANGSMITH_TRACING,
LANGSMITH_PROJECT (optional).
"""

import os


def add_cost_breakdown_to_langsmith(
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cost_usd: float | None,
    model: str = "claude-haiku-4-5",
) -> None:
    """
    Add token usage and cost breakdown to the current LangSmith run metadata.

    Call from within a traced context (e.g., inside agent.invoke). No-op if
    LangSmith is not configured or no active run.
    """
    if not _langsmith_configured():
        return
    try:
        from langsmith.run_helpers import get_current_run_tree, set_run_metadata

        run = get_current_run_tree()
        if run is None:
            return
        metadata: dict[str, object] = {
            "token_usage.input_tokens": input_tokens,
            "token_usage.output_tokens": output_tokens,
            "token_usage.total_tokens": total_tokens,
            "ls_provider": "anthropic",
            "ls_model_name": model,
        }
        if cost_usd is not None:
            metadata["cost_breakdown.cost_usd"] = cost_usd
        set_run_metadata(**metadata)
    except Exception:
        pass  # Do not fail the request if LangSmith metadata update fails


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
