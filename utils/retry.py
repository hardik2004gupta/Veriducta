"""Retry logic with exponential back-off using tenacity."""

from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["RetryError", "with_retry"]


def with_retry(
    func: F,
    *,
    max_attempts: int = 3,
    min_wait_s: float = 1.0,
    max_wait_s: float = 10.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> F:
    """Wrap *func* with exponential back-off retry logic.

    Args:
        func: Callable to wrap.
        max_attempts: Maximum total attempts (including the first).
        min_wait_s: Minimum back-off delay in seconds.
        max_wait_s: Maximum back-off delay in seconds.
        retry_on: Exception types that trigger a retry.

    Returns:
        The wrapped callable with the same signature.
    """
    decorated = retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_s, max=max_wait_s),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    )(func)
    return decorated


def retry_on_transient(
    max_attempts: int = 3,
    min_wait_s: float = 0.5,
    max_wait_s: float = 5.0,
) -> Callable[[F], F]:
    """Decorator factory for retrying on transient (non-domain) errors."""

    def decorator(func: F) -> F:
        return with_retry(
            func,
            max_attempts=max_attempts,
            min_wait_s=min_wait_s,
            max_wait_s=max_wait_s,
            retry_on=(Exception,),
        )

    return decorator
