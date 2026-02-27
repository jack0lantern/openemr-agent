"""Unit tests for LLM cost calculation."""

import pytest

from app.llm.cost import compute_cost_usd


def test_compute_cost_usd_basic():
    """Compute cost for known token counts."""
    # 1M input @ $1/1M + 1M output @ $5/1M = $6
    cost = compute_cost_usd(1_000_000, 1_000_000)
    assert cost == 6.0


def test_compute_cost_usd_small():
    """Compute cost for typical small request."""
    # 1000 input @ $1/1M + 200 output @ $5/1M = 0.001 + 0.001 = 0.002
    cost = compute_cost_usd(1000, 200)
    assert cost == 0.002


def test_compute_cost_usd_zero_tokens():
    """Zero tokens yields zero cost."""
    cost = compute_cost_usd(0, 0)
    assert cost == 0.0


def test_compute_cost_usd_rounding():
    """Cost is rounded to 6 decimal places."""
    cost = compute_cost_usd(1234, 567)
    assert isinstance(cost, float)
    assert len(str(cost).split(".")[-1]) <= 6


def test_compute_cost_usd_unknown_model_uses_defaults(monkeypatch):
    """Unknown model falls back to default pricing."""
    monkeypatch.delenv("ANTHROPIC_INPUT_PRICE_PER_1M", raising=False)
    monkeypatch.delenv("ANTHROPIC_OUTPUT_PRICE_PER_1M", raising=False)
    cost = compute_cost_usd(1_000_000, 1_000_000, model="unknown-model")
    assert cost == 6.0


def test_compute_cost_usd_env_override(monkeypatch):
    """Env vars override default pricing."""
    monkeypatch.setenv("ANTHROPIC_INPUT_PRICE_PER_1M", "2.0")
    monkeypatch.setenv("ANTHROPIC_OUTPUT_PRICE_PER_1M", "10.0")
    # 1M input @ $2/1M + 1M output @ $10/1M = $12
    cost = compute_cost_usd(1_000_000, 1_000_000)
    assert cost == 12.0
