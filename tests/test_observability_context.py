"""Tests for observability.context — RequestContext and contextvar helpers."""

import time
from datetime import UTC, datetime

import pytest

from observability.context import (
    RequestContext,
    get_current_context,
    require_context,
    set_current_context,
)


def test_request_context_default_ids_are_non_empty() -> None:
    ctx = RequestContext()
    assert ctx.request_id
    assert ctx.trace_id
    assert ctx.request_id != ctx.trace_id


def test_request_context_started_at_is_utc() -> None:
    before = datetime.now(UTC)
    ctx = RequestContext()
    after = datetime.now(UTC)
    assert before <= ctx.started_at <= after


def test_request_context_elapsed_ms_increases_over_time() -> None:
    ctx = RequestContext()
    time.sleep(0.01)
    assert ctx.elapsed_ms() >= 10.0


def test_request_context_metadata_defaults_to_empty_dict() -> None:
    ctx = RequestContext()
    assert ctx.metadata == {}


def test_get_current_context_returns_none_when_unset() -> None:
    # We cannot guarantee the contextvar is unset across test isolation,
    # so we set it to None explicitly and then read it back.
    from contextvars import copy_context

    def _check() -> None:
        # Inside a fresh context copy, the var inherits from parent.
        # We deliberately set it to None to simulate "outside a request".
        from observability.context import _ctx_var

        _ctx_var.set(None)
        result = get_current_context()
        assert result is None

    copy_context().run(_check)


def test_set_and_get_current_context_roundtrip() -> None:
    ctx = RequestContext(request_id="req-123", trace_id="trace-456")
    set_current_context(ctx)
    retrieved = get_current_context()
    assert retrieved is ctx
    assert retrieved.request_id == "req-123"
    assert retrieved.trace_id == "trace-456"


def test_require_context_returns_active_context() -> None:
    ctx = RequestContext(request_id="req-789")
    set_current_context(ctx)
    assert require_context() is ctx


def test_require_context_raises_when_no_context_set() -> None:
    from contextvars import copy_context

    from observability.context import _ctx_var

    def _check() -> None:
        _ctx_var.set(None)
        with pytest.raises(RuntimeError, match="No active RequestContext"):
            require_context()

    copy_context().run(_check)


def test_request_context_custom_fields_preserved() -> None:
    ctx = RequestContext(
        request_id="r1",
        trace_id="t1",
        query_hash="abc123",
        metadata={"key": "value"},
    )
    assert ctx.query_hash == "abc123"
    assert ctx.metadata == {"key": "value"}
