"""High-resolution timing utilities."""

import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class TimerResult:
    """Captured timing for a named operation."""

    name: str
    elapsed_ms: float = field(default=0.0)

    @property
    def elapsed_s(self) -> float:
        """Elapsed time in seconds."""
        return self.elapsed_ms / 1000.0


@contextmanager
def timer(name: str = "operation") -> Generator[TimerResult, None, None]:
    """Context manager that records wall-clock elapsed time in milliseconds.

    Usage::

        with timer("retrieval") as t:
            result = do_retrieval()
        print(t.elapsed_ms)
    """
    result = TimerResult(name=name)
    start = time.perf_counter()
    try:
        yield result
    finally:
        result.elapsed_ms = (time.perf_counter() - start) * 1000.0


def now_ms() -> float:
    """Return current monotonic time in milliseconds."""
    return time.perf_counter() * 1000.0
