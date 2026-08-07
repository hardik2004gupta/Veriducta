"""Tests for RetrievalSettings in config/settings.py."""

import pytest

from config.settings import RetrievalSettings, Settings


def test_retrieval_settings_defaults() -> None:
    s = RetrievalSettings()
    assert s.bm25_top_k == 100
    assert s.dense_top_k == 100
    assert s.rrf_k == 60
    assert s.reranker_model_id == "cross-encoder/ms-marco-MiniLM-L-12-v2"
    assert s.reranker_input_top_k == 40
    assert s.reranker_output_top_k == 8
    assert s.embedding_cache_size == 1000
    assert s.embedding_cache_ttl_seconds == 3600
    assert s.temporal_filtering_enabled is True


def test_retrieval_settings_custom() -> None:
    s = RetrievalSettings(bm25_top_k=50, rrf_k=30, reranker_output_top_k=4)
    assert s.bm25_top_k == 50
    assert s.rrf_k == 30
    assert s.reranker_output_top_k == 4


def test_retrieval_settings_bm25_top_k_min() -> None:
    with pytest.raises(ValueError):
        RetrievalSettings(bm25_top_k=0)


def test_settings_has_retrieval_field() -> None:
    s = Settings()
    assert hasattr(s, "retrieval")
    assert isinstance(s.retrieval, RetrievalSettings)
