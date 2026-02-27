"""
Retry utilities for Anthropic API rate limits (429).

Used by agent invocations and tests to handle RateLimitError with exponential
backoff. Honors retry-after header when present.
"""

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if the exception indicates a 429 rate limit."""
    exc_type = type(exc)
    exc_name = exc_type.__name__
    # Direct RateLimitError from anthropic
    if exc_name == "RateLimitError":
        return True
    # APIStatusError with status 429 (e.g. when wrapped)
    if exc_name == "APIStatusError" and getattr(exc, "status_code", None) == 429:
        return True
    # Check exception chain (e.g. LangChain may wrap)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return _is_rate_limit_error(cause)
    return False


def invoke_with_retry(
    fn: Callable[..., T],
    *args,
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 120.0,
    jitter: bool = True,
    **kwargs,
) -> T:
    """Invoke fn with retries on RateLimitError (429).

    Uses retry-after header when available, otherwise exponential backoff with
    optional jitter to avoid thundering herd.
    """
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if not _is_rate_limit_error(e):
                raise
            last_error = e
            if attempt == max_retries - 1:
                raise

            # Prefer retry-after header when present (anthropic.RateLimitError)
            retry_after: float | None = None
            exc = e
            while exc is not None and retry_after is None:
                if hasattr(exc, "response") and exc.response is not None:
                    headers = getattr(exc.response, "headers", None) or {}
                    raw = headers.get("retry-after")
                    if raw is not None:
                        try:
                            retry_after = float(raw)
                        except (ValueError, TypeError):
                            pass
                exc = getattr(exc, "__cause__", None)

            if retry_after is not None:
                wait_time = min(retry_after, max_delay)
            else:
                wait_time = min(base_delay * (2**attempt), max_delay)
                if jitter:
                    wait_time *= 0.5 + random.random()

            time.sleep(wait_time)

    raise last_error  # type: ignore[misc]
