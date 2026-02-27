"""Unit tests for agent token usage aggregation."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from app.llm.agent import _aggregate_usage


def test_aggregate_usage_single_aimessage():
    """Single AIMessage with usage_metadata is aggregated."""
    msg = AIMessage(
        content="Hello",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
    )
    result = _aggregate_usage([msg])
    assert result == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


def test_aggregate_usage_multiple_aimessages():
    """Multiple AIMessages (tool loop) are summed."""
    msgs = [
        AIMessage(
            content="",
            usage_metadata={"input_tokens": 500, "output_tokens": 50, "total_tokens": 550},
        ),
        AIMessage(
            content="Here is the result.",
            usage_metadata={"input_tokens": 600, "output_tokens": 30, "total_tokens": 630},
        ),
    ]
    result = _aggregate_usage(msgs)
    assert result["input_tokens"] == 1100
    assert result["output_tokens"] == 80
    assert result["total_tokens"] == 1180


def test_aggregate_usage_ignores_human_messages():
    """HumanMessage and other non-AIMessage types are ignored."""
    msgs = [
        HumanMessage(content="Hi"),
        AIMessage(
            content="Hello",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        ),
    ]
    result = _aggregate_usage(msgs)
    assert result == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_aggregate_usage_no_metadata_returns_none():
    """AIMessage without usage_metadata returns None."""
    msg = AIMessage(content="Hello")
    result = _aggregate_usage([msg])
    assert result is None


def test_aggregate_usage_empty_list_returns_none():
    """Empty message list returns None."""
    assert _aggregate_usage([]) is None


def test_aggregate_usage_response_metadata_fallback():
    """Falls back to response_metadata.usage when usage_metadata missing."""
    msg = MagicMock(spec=AIMessage)
    msg.usage_metadata = None
    msg.response_metadata = {"usage": {"input_tokens": 50, "output_tokens": 10}}
    result = _aggregate_usage([msg])
    assert result == {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60}
