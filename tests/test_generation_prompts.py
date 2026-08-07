"""Tests for generation/prompts.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from generation.prompts import PromptRegistry, PromptVersion, SystemPromptManager

# ---------------------------------------------------------------------------
# PromptVersion
# ---------------------------------------------------------------------------


def test_prompt_version_hash_computed_automatically() -> None:
    pv = PromptVersion(name="gen", version="v1", template="hello world")
    assert len(pv.hash) == 64  # SHA-256 hex
    assert pv.hash != ""


def test_prompt_version_same_template_same_hash() -> None:
    pv1 = PromptVersion(name="gen", version="v1", template="same content")
    pv2 = PromptVersion(name="gen", version="v2", template="same content")
    assert pv1.hash == pv2.hash


def test_prompt_version_different_templates_different_hash() -> None:
    pv1 = PromptVersion(name="gen", version="v1", template="content A")
    pv2 = PromptVersion(name="gen", version="v1", template="content B")
    assert pv1.hash != pv2.hash


def test_prompt_version_explicit_hash_preserved() -> None:
    pv = PromptVersion(name="gen", version="v1", template="t", hash="explicit-hash")
    assert pv.hash == "explicit-hash"


# ---------------------------------------------------------------------------
# PromptRegistry
# ---------------------------------------------------------------------------


def _make_pv(name: str = "gen", version: str = "v1", text: str = "tmpl") -> PromptVersion:
    return PromptVersion(name=name, version=version, template=text)


def test_registry_register_and_get() -> None:
    reg = PromptRegistry()
    pv = _make_pv()
    reg.register(pv)
    assert reg.get("gen", "v1") is pv


def test_registry_get_unknown_raises_key_error() -> None:
    reg = PromptRegistry()
    with pytest.raises(KeyError, match="version"):
        reg.get("gen", "v99")


def test_registry_latest_returns_highest_version() -> None:
    reg = PromptRegistry()
    reg.register(_make_pv("gen", "v1", "a"))
    reg.register(_make_pv("gen", "v2", "b"))
    reg.register(_make_pv("gen", "v10", "c"))
    latest = reg.latest("gen")
    assert latest.version == "v2"  # lexicographic: "v2" > "v10" > "v1"


def test_registry_latest_unknown_raises_key_error() -> None:
    reg = PromptRegistry()
    with pytest.raises(KeyError, match="name"):
        reg.latest("nonexistent")


def test_registry_registered_names() -> None:
    reg = PromptRegistry()
    reg.register(_make_pv("gen", "v1"))
    reg.register(_make_pv("eval", "v1"))
    assert set(reg.registered_names) == {"gen", "eval"}


# ---------------------------------------------------------------------------
# SystemPromptManager
# ---------------------------------------------------------------------------


def test_system_prompt_manager_v1_registered_at_init() -> None:
    mgr = SystemPromptManager()
    pv = mgr.get_system_prompt("v1")
    assert pv.name == "generation"
    assert pv.version == "v1"
    assert len(pv.template) > 100


def test_system_prompt_manager_hash_is_hex() -> None:
    mgr = SystemPromptManager()
    h = mgr.snapshot_hash("v1")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_system_prompt_manager_hash_stable() -> None:
    mgr1 = SystemPromptManager()
    mgr2 = SystemPromptManager()
    assert mgr1.snapshot_hash("v1") == mgr2.snapshot_hash("v1")


def test_system_prompt_manager_unknown_version_raises() -> None:
    mgr = SystemPromptManager()
    with pytest.raises(KeyError):
        mgr.get_system_prompt("v99")


def test_system_prompt_manager_load_from_file(tmp_path: Path) -> None:
    prompt_file = tmp_path / "custom.txt"
    prompt_file.write_text("custom prompt template", encoding="utf-8")
    mgr = SystemPromptManager()
    pv = mgr.load_from_file("custom", "v1", str(prompt_file))
    assert pv.template == "custom prompt template"
    assert isinstance(mgr, SystemPromptManager)
    assert mgr.registry.get("custom", "v1") is pv


def test_system_prompt_manager_registry_property() -> None:
    mgr = SystemPromptManager()
    assert isinstance(mgr.registry, PromptRegistry)
