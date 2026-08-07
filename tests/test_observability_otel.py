"""Tests for observability.otel - record_span_attributes."""

from unittest.mock import MagicMock

from observability.otel import record_span_attributes


def _make_span() -> MagicMock:
    return MagicMock()


def test_record_span_attributes_sets_config_hash() -> None:
    span = _make_span()
    record_span_attributes(span, config_hash="abc123")
    span.set_attribute.assert_any_call("veriducta.config_hash", "abc123")


def test_record_span_attributes_sets_latency_ms() -> None:
    span = _make_span()
    record_span_attributes(span, latency_ms=42.5)
    span.set_attribute.assert_any_call("veriducta.latency_ms", 42.5)


def test_record_span_attributes_sets_model() -> None:
    span = _make_span()
    record_span_attributes(span, model="claude-sonnet-4-6")
    span.set_attribute.assert_any_call("veriducta.model", "claude-sonnet-4-6")


def test_record_span_attributes_sets_trace_id() -> None:
    span = _make_span()
    record_span_attributes(span, trace_id="my-trace-id")
    span.set_attribute.assert_any_call("veriducta.trace_id", "my-trace-id")


def test_record_span_attributes_sets_error_when_provided() -> None:
    span = _make_span()
    record_span_attributes(span, error="something went wrong")
    span.set_attribute.assert_any_call("error.message", "something went wrong")
    span.set_attribute.assert_any_call("error", True)


def test_record_span_attributes_skips_empty_strings() -> None:
    span = _make_span()
    record_span_attributes(span)  # all defaults
    span.set_attribute.assert_not_called()


def test_record_span_attributes_skips_zero_latency() -> None:
    span = _make_span()
    record_span_attributes(span, latency_ms=0.0)
    calls = [str(c) for c in span.set_attribute.call_args_list]
    assert not any("latency_ms" in c for c in calls)


def test_record_span_attributes_skips_empty_error() -> None:
    span = _make_span()
    record_span_attributes(span, error="")
    calls = [str(c) for c in span.set_attribute.call_args_list]
    assert not any("error" in c for c in calls)


def test_record_span_attributes_all_fields() -> None:
    span = _make_span()
    record_span_attributes(
        span,
        config_hash="h1",
        latency_ms=10.0,
        model="bge-large",
        trace_id="t1",
        error="oops",
    )
    # config_hash, latency_ms, model, trace_id, error.message, error=True → 6 calls
    assert span.set_attribute.call_count == 6
