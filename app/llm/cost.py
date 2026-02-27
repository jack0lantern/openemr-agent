"""Cost calculation for LLM token usage."""

import os

# Claude Haiku 4.5 pricing per Anthropic docs (per million tokens)
DEFAULT_INPUT_PRICE_PER_1M = 1.0
DEFAULT_OUTPUT_PRICE_PER_1M = 5.0

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (DEFAULT_INPUT_PRICE_PER_1M, DEFAULT_OUTPUT_PRICE_PER_1M),
}


def compute_cost_usd(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-haiku-4-5",
) -> float:
    """
    Compute cost in USD for token usage.

    Uses env vars ANTHROPIC_INPUT_PRICE_PER_1M and ANTHROPIC_OUTPUT_PRICE_PER_1M
    when set; otherwise falls back to MODEL_PRICING for known models.
    """
    input_price = _parse_float_env("ANTHROPIC_INPUT_PRICE_PER_1M")
    output_price = _parse_float_env("ANTHROPIC_OUTPUT_PRICE_PER_1M")

    if input_price is None or output_price is None:
        pricing = MODEL_PRICING.get(model)
        if pricing:
            input_price, output_price = pricing
        else:
            input_price = DEFAULT_INPUT_PRICE_PER_1M
            output_price = DEFAULT_OUTPUT_PRICE_PER_1M

    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return round(input_cost + output_cost, 6)


def _parse_float_env(name: str) -> float | None:
    val = os.getenv(name)
    if val is None or val == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None
