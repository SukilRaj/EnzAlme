"""Tests: ESM-2 embedder (src/esm_embedder.py).
Uses a tiny fake model (no network) plus an optional cached-model integration test.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import esm_embedder as ee

FAKE_DIM = 5


class _FakeTokenizer:
    """Mimics a HF tokenizer: BOS(0) + ids + EOS(1), zero-padded."""

    def __call__(self, seqs, return_tensors="pt", padding=True, truncation=True,
                 max_length=1024):
        import torch
        rows = [[0] + [ord(c) % 10 + 1 for c in s] + [1] for s in seqs]
        L = max(len(r) for r in rows)
        full = np.array([r + [0] * (L - len(r)) for r in rows], dtype=np.int64)
        mask = np.array([[1] * len(r) + [0] * (L - len(r)) for r in rows], dtype=np.int64)
        return {"input_ids": torch.tensor(full), "attention_mask": torch.tensor(mask)}


class _FakeModel:
    """Hidden state per masked position k = arange(D) + k (BOS/EOS inclusion visible)."""

    def __call__(self, **inputs):
        import torch
        B, L = inputs["input_ids"].shape
        hidden = torch.zeros(B, L, FAKE_DIM)
        mask = inputs["attention_mask"]
        for b in range(B):
            nz = mask[b].nonzero().flatten().tolist()
            for k, pos in enumerate(nz):
                hidden[b, pos] = torch.arange(FAKE_DIM) + k
        return SimpleNamespace(last_hidden_state=hidden)


def _patch_resolve(monkeypatch):
    monkeypatch.setattr(ee, "resolve_model",
                        lambda *a, **k: (_FakeTokenizer(), _FakeModel(), "cpu",
                                         "fake/esm", "fake"))


@pytest.fixture(autouse=True)
def _workdir(tmp_path, monkeypatch):
    # Redirect artifact + cache dirs to a temp location for dedup/caching tests.
    monkeypatch.setattr(ee, "REPO_ROOT", tmp_path)


def test_dedup_and_pooling_shape(monkeypatch):
    _patch_resolve(monkeypatch)
    df = pd.DataFrame({
        "enzyme_id": ["E1", "E2", "E3"],
        "protein_sequence": ["ACDEFGHIK", "ACDEFGHIK", "ACD" * 20],  # E1==E2 identical
    })
    res = ee.embed_sequences(df, progress=False)
    assert set(res["embeddings"]) == {"E1", "E2", "E3"}
    v1, v2 = res["embeddings"]["E1"], res["embeddings"]["E2"]
    assert np.allclose(v1, v2)  # identical sequence -> same embedding
    assert res["embeddings"]["E3"].shape == (FAKE_DIM,)


def test_invalid_sequence_skipped(monkeypatch):
    _patch_resolve(monkeypatch)
    df = pd.DataFrame({"enzyme_id": ["E1", "E2", "E3"],
                       "protein_sequence": ["ACDEFGHIK", "MKT" * 20, "ZXYZ" * 10]})
    res = ee.embed_sequences(df, progress=False)
    # E3 has invalid amino acid X; still embedded rules allow any 20-Canon, but
    # 'Z'/'X' are invalid chars -> skipped
    assert "E3" not in res["embeddings"]
    assert res["n_skipped"] == 1


def test_detect_device_str():
    assert isinstance(ee.detect_device(), str)


def test_cached_model_integration():
    """3.5M/35M ESM model cached locally? If so, verify real embed + shapes."""
    cached = ee._cached_hf_models()
    if not cached:
        pytest.skip("no cached ESM model on this machine")
    model_id = cached[0]
    df = pd.DataFrame({
        "enzyme_id": ["T1"],
        "protein_sequence": ["MKT" * 60 + "E"],
    })
    res = ee.embed_sequences(df, model_name=model_id, progress=False, download=False)
    vec = res["embeddings"]["T1"]
    assert vec.ndim == 1 and vec.shape[0] > 100
    assert np.isfinite(vec).all()