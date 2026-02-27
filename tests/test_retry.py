"""
Unit tests for rate limit retry logic.

Verifies invoke_with_retry retries on RateLimitError and succeeds after backoff.
No API key required.
"""

import pytest

from app.llm.retry import _is_rate_limit_error, invoke_with_retry


def test_is_rate_limit_error_direct():
    """Mock RateLimitError is detected by name."""
    class RateLimitError(Exception):
        pass
    exc = RateLimitError("429")
    assert _is_rate_limit_error(exc) is True


def test_is_rate_limit_error_api_status():
    """APIStatusError with status_code 429 is detected."""
    class APIStatusError(Exception):
        def __init__(self, msg, status_code=500):
            super().__init__(msg)
            self.status_code = status_code
    exc = APIStatusError("rate limit", status_code=429)
    assert _is_rate_limit_error(exc) is True


def test_is_rate_limit_error_wrapped():
    """Rate limit in __cause__ chain is detected."""
    class RateLimitError(Exception):  # noqa: A801
        pass

    inner = RateLimitError("429")
    try:
        raise ValueError("wrapped") from inner
    except ValueError as outer:
        assert _is_rate_limit_error(outer) is True


def test_is_rate_limit_error_other_exception():
    """Non-rate-limit exceptions are not detected."""
    assert _is_rate_limit_error(ValueError("other")) is False
    assert _is_rate_limit_error(RuntimeError("500")) is False


def test_invoke_with_retry_succeeds_immediately():
    """Successful call returns without retry."""
    result = invoke_with_retry(lambda: 42)
    assert result == 42


def test_invoke_with_retry_succeeds_after_retries():
    """Call succeeds after one rate limit, then success."""
    class RateLimitError(Exception):  # noqa: A801
        """Local mock; _is_rate_limit_error checks type name."""
        pass

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 2:
            raise RateLimitError("429")
        return "ok"

    # _is_rate_limit_error checks exc_type.__name__ == "RateLimitError"
    result = invoke_with_retry(flaky, max_retries=3, base_delay=0.01, jitter=False)
    assert result == "ok"
    assert len(attempts) == 2


def test_invoke_with_retry_propagates_non_rate_limit():
    """Non-rate-limit exceptions are propagated immediately."""

    def raise_value_error():
        raise ValueError("not retried")

    with pytest.raises(ValueError, match="not retried"):
        invoke_with_retry(raise_value_error)
