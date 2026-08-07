"""Tests for observability.rotation - LogRotator."""

import gzip
from pathlib import Path

from observability.rotation import LogRotator, _today_stem


def test_active_path_is_todays_jsonl(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    active = rotator.active_path()
    assert active.name == f"{_today_stem()}.jsonl"
    assert active.parent == tmp_path


def test_active_path_with_sequence_suffix(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    rotator._sequence = 2
    active = rotator.active_path()
    assert active.name == f"{_today_stem()}.2.jsonl"


def test_should_rotate_false_when_size_disabled(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, max_size_bytes=0)
    assert rotator.should_rotate() is False


def test_should_rotate_false_when_file_missing(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, max_size_bytes=1)
    assert rotator.should_rotate() is False


def test_should_rotate_true_when_file_exceeds_limit(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, max_size_bytes=5)
    active = rotator.active_path()
    active.write_bytes(b"hello world")  # 11 bytes > 5
    assert rotator.should_rotate() is True


def test_should_rotate_false_when_file_within_limit(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path, max_size_bytes=100)
    active = rotator.active_path()
    active.write_bytes(b"hi")
    assert rotator.should_rotate() is False


def test_rotate_active_increments_sequence(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    assert rotator._sequence == 0
    rotator.rotate_active()
    assert rotator._sequence == 1
    rotator.rotate_active()
    assert rotator._sequence == 2


def test_compress_stale_compresses_old_files(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    old_file = tmp_path / "2000-01-01.jsonl"
    old_file.write_bytes(b'{"trace_id": "x"}\n')

    compressed = rotator.compress_stale()

    gz_path = tmp_path / "2000-01-01.jsonl.gz"
    assert gz_path in compressed
    assert gz_path.exists()
    assert not old_file.exists()

    with gzip.open(gz_path, "rb") as fh:
        content = fh.read()
    assert b"trace_id" in content


def test_compress_stale_skips_todays_files(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    today_file = rotator.active_path()
    today_file.write_bytes(b"today entry\n")

    compressed = rotator.compress_stale()
    assert compressed == []
    assert today_file.exists()


def test_compress_stale_skips_already_compressed(tmp_path: Path) -> None:
    rotator = LogRotator(tmp_path)
    old_jsonl = tmp_path / "2000-01-02.jsonl"
    old_jsonl.write_bytes(b"data\n")
    old_gz = tmp_path / "2000-01-02.jsonl.gz"
    old_gz.write_bytes(b"")  # already exists

    compressed = rotator.compress_stale()
    assert compressed == []
    assert not old_jsonl.exists()  # plain file is unlinked


def test_compress_stale_crash_safe_removes_tmp(tmp_path: Path) -> None:
    """A leftover .tmp file from a prior crash does not block subsequent runs."""
    old_file = tmp_path / "2000-01-03.jsonl"
    old_file.write_bytes(b"data\n")
    tmp_file = tmp_path / "2000-01-03.jsonl.gz.tmp"
    tmp_file.write_bytes(b"partial")  # simulate crash artifact

    rotator = LogRotator(tmp_path)
    compressed = rotator.compress_stale()
    # The .tmp file is from before; the new compress overwrites it then renames
    assert (tmp_path / "2000-01-03.jsonl.gz") in compressed
