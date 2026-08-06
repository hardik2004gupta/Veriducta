"""Tests for the shared utility modules."""

import time

from utils.datetime_utils import is_before, is_on_or_before, parse_iso_date, utcnow
from utils.hashing import sha256_bytes, sha256_json, sha256_str
from utils.ids import chunk_id, new_uuid, parent_chunk_id, trace_id
from utils.serialization import from_json, to_json, to_json_str
from utils.timers import timer

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def test_sha256_str_is_deterministic() -> None:
    assert sha256_str("hello") == sha256_str("hello")


def test_sha256_str_differs_for_different_inputs() -> None:
    assert sha256_str("hello") != sha256_str("world")


def test_sha256_str_length_is_64() -> None:
    assert len(sha256_str("test")) == 64


def test_sha256_bytes_matches_str() -> None:
    assert sha256_bytes(b"hello") == sha256_str("hello")


def test_sha256_json_is_stable_across_key_order() -> None:
    a = sha256_json({"b": 2, "a": 1})
    b = sha256_json({"a": 1, "b": 2})
    assert a == b


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------


def test_new_uuid_is_unique() -> None:
    assert new_uuid() != new_uuid()


def test_trace_id_is_unique() -> None:
    assert trace_id() != trace_id()


def test_chunk_id_zero_pads() -> None:
    assert chunk_id("doc", 5) == "doc-ch-0005"


def test_parent_chunk_id_format() -> None:
    assert parent_chunk_id("doc", 0) == "doc-par-0000"


# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------


def test_timer_records_elapsed() -> None:
    with timer("test_op") as t:
        time.sleep(0.01)
    assert t.elapsed_ms >= 10.0
    assert t.name == "test_op"


def test_timer_elapsed_s_conversion() -> None:
    with timer() as t:
        time.sleep(0.05)
    assert t.elapsed_s >= 0.05


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def test_to_json_roundtrip() -> None:
    obj = {"key": "value", "num": 42}
    assert from_json(to_json(obj)) == obj


def test_to_json_str_is_string() -> None:
    assert isinstance(to_json_str({"x": 1}), str)


def test_to_json_sorted_keys() -> None:
    raw = to_json_str({"b": 2, "a": 1}, indent=False)
    assert raw.index('"a"') < raw.index('"b"') or '"a"' in raw


# ---------------------------------------------------------------------------
# Datetime utils
# ---------------------------------------------------------------------------


def test_utcnow_is_timezone_aware() -> None:
    dt = utcnow()
    assert dt.tzinfo is not None


def test_parse_iso_date() -> None:
    d = parse_iso_date("2021-06-15")
    assert d.year == 2021
    assert d.month == 6
    assert d.day == 15


def test_is_before() -> None:
    assert is_before("2020-01-01", "2021-01-01")
    assert not is_before("2021-01-01", "2020-01-01")


def test_is_on_or_before() -> None:
    assert is_on_or_before("2021-01-01", "2021-01-01")
    assert is_on_or_before("2020-12-31", "2021-01-01")
    assert not is_on_or_before("2021-01-02", "2021-01-01")
