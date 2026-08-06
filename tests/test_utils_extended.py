"""Extended utility tests to reach coverage threshold."""

import tempfile
from pathlib import Path

import pytest

from utils.datetime_utils import (
    date_to_iso,
    is_before,
    is_on_or_before,
    parse_iso_datetime,
    utcnow_iso,
)
from utils.filesystem import ensure_dir, file_size_bytes, safe_filename
from utils.hashing import sha256_file, sha256_json, sha256_str
from utils.retry import with_retry
from utils.serialization import _default, from_json, model_to_dict, to_json_str

# ---------------------------------------------------------------------------
# datetime_utils
# ---------------------------------------------------------------------------


def test_utcnow_iso_is_string() -> None:
    iso = utcnow_iso()
    assert isinstance(iso, str)
    assert "T" in iso


def test_parse_iso_datetime_naive_gets_utc() -> None:
    from datetime import UTC

    dt = parse_iso_datetime("2021-06-15T10:00:00")
    assert dt.tzinfo is not None
    assert dt.tzinfo == UTC


def test_parse_iso_datetime_aware_preserved() -> None:
    dt = parse_iso_datetime("2021-06-15T10:00:00+00:00")
    assert dt.tzinfo is not None


def test_date_to_iso() -> None:
    from datetime import date

    assert date_to_iso(date(2021, 6, 15)) == "2021-06-15"


def test_is_before_equal_dates() -> None:
    assert not is_before("2021-01-01", "2021-01-01")


def test_is_on_or_before_future() -> None:
    assert not is_on_or_before("2022-01-01", "2021-01-01")


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------


def test_ensure_dir_creates_nested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        nested = Path(tmp) / "a" / "b" / "c"
        result = ensure_dir(nested)
        assert result.exists()
        assert result.is_dir()


def test_ensure_dir_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "existing"
        ensure_dir(path)
        ensure_dir(path)
        assert path.exists()


def test_safe_filename_removes_special_chars() -> None:
    assert safe_filename("hello world!") == "hello_world_"
    assert safe_filename("file-name_v1.0") == "file-name_v1.0"
    assert safe_filename("path/to/file") == "path_to_file"


def test_file_size_bytes() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"hello world")
        fname = f.name
    assert file_size_bytes(fname) == 11


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------


def test_sha256_file_matches_str() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        fname = f.name
    expected = sha256_str("test content")
    assert sha256_file(fname) == expected


def test_sha256_json_nested() -> None:
    h = sha256_json({"nested": {"list": [1, 2, 3]}})
    assert len(h) == 64


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------


def test_from_json_with_string_input() -> None:
    result = from_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_default_raises_for_unknown_type() -> None:
    with pytest.raises(TypeError):
        _default(object())


def test_to_json_pretty() -> None:
    data = {"a": 1}
    pretty = to_json_str(data, indent=True)
    assert "\n" in pretty


def test_model_to_dict_roundtrip() -> None:
    from pydantic import BaseModel

    class Sample(BaseModel):
        name: str
        value: int

    sample = Sample(name="test", value=42)
    d = model_to_dict(sample)
    assert d["name"] == "test"
    assert d["value"] == 42


# ---------------------------------------------------------------------------
# retry
# ---------------------------------------------------------------------------


def test_with_retry_succeeds_on_first_attempt() -> None:
    call_count = 0

    def succeeds() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    wrapped = with_retry(succeeds, max_attempts=3)
    assert wrapped() == "ok"
    assert call_count == 1


def test_with_retry_exhausts_and_raises() -> None:
    call_count = 0

    def always_fails() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("always fails")

    wrapped = with_retry(always_fails, max_attempts=2, min_wait_s=0.0, max_wait_s=0.0)
    with pytest.raises(ValueError, match="always fails"):
        wrapped()
    assert call_count == 2


def test_with_retry_retries_on_specified_exception() -> None:
    attempts = 0

    def fails_then_succeeds() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("transient")
        return "ok"

    wrapped = with_retry(
        fails_then_succeeds,
        max_attempts=3,
        min_wait_s=0.0,
        max_wait_s=0.0,
        retry_on=(ConnectionError,),
    )
    assert wrapped() == "ok"
    assert attempts == 3


# ---------------------------------------------------------------------------
# api dependencies
# ---------------------------------------------------------------------------


def test_get_app_settings_returns_settings() -> None:
    from api.dependencies import get_app_settings
    from config.settings import Settings

    settings = get_app_settings()
    assert isinstance(settings, Settings)
