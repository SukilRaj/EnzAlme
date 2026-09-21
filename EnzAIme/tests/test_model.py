"""Tests: model architecture, baselines, group split, metrics (src/model.py)."""
import numpy as np
import pandas as pd
import pytest

import model as M


def _scenarios(n_enzymes=9, rows_per=20):
    frames = []
    for e in range(n_enzymes):
        frames.append(pd.DataFrame({
            "enzyme_id": [f"E{e}"] * rows_per,
            "pollutant_type": ["PET"] * rows_per,
            "scenario_ph": np.linspace(6, 10, rows_per),
            "scenario_temperature_c": np.linspace(25, 65, rows_per),
            "scenario_salinity": np.linspace(0, 2, rows_per),
            "pollutant_evidence_score": [0.85] * rows_per,
            "ph_metadata_available": [1] * rows_per,
            "temperature_metadata_available": [1] * rows_per,
            "salinity_metadata_available": [0] * rows_per,
            "has_sequence": [1] * rows_per,
            "has_accession": [1] * rows_per,
            "metadata_completeness": [0.75] * rows_per,
            "unknown_feature_count": [1] * rows_per,
            "derived_compatibility_label": np.random.RandomState(e).rand(rows_per),
        }))
    return pd.concat(frames, ignore_index=True)


def test_build_feature_matrix_shape_and_cats():
    df = _scenarios()
    X, scaler, cats = M.build_feature_matrix(df, scale=True)
    assert X.shape[0] == len(df)
    assert X.shape[1] == len(cats) + 11  # one-hot pollutants + 11 env columns
    assert "PET" in cats
    assert X.dtype == np.float32


def test_group_split_no_leakage():
    df = _scenarios()
    sp = M.GroupSplitter(test_size=0.2, seed=42)
    tr, te = sp.train_test_indices(df["enzyme_id"])
    g_tr, g_te = df["enzyme_id"].to_numpy()[tr], df["enzyme_id"].to_numpy()[te]
    assert sp.no_leakage(g_tr, g_te)
    assert set(g_tr).isdisjoint(g_te)


def test_group_split_holdout_when_few_groups():
    df = _scenarios(n_enzymes=3, rows_per=10)
    sp = M.GroupSplitter(n_splits=5, seed=42)
    folds = list(sp.cv_indices(df["enzyme_id"]))
    assert len(folds) == 1  # holdout instead of 5-fold
    tr, te = folds[0]
    assert sp.no_leakage(df["enzyme_id"].to_numpy()[tr], df["enzyme_id"].to_numpy()[te])


def test_cv_indices_enough_groups():
    df = _scenarios(n_enzymes=12)
    sp = M.GroupSplitter(n_splits=5, seed=42)
    folds = list(sp.cv_indices(df["enzyme_id"]))
    assert len(folds) == 5
    for tr, te in folds:
        assert sp.no_leakage(df["enzyme_id"].to_numpy()[tr], df["enzyme_id"].to_numpy()[te])


def test_baselines_fit_and_predict():
    X = np.random.RandomState(0).rand(60, 5).astype(np.float32)
    y = (X[:, 0] * 2 + X[:, 2]).astype(np.float32)
    for fn in [M.fit_ridge, M.fit_random_forest, M.fit_gradient_boosting]:
        m = fn(X, y)
        p = m.predict(X)
        assert p.shape == (60,)
        assert np.isfinite(p).all()


def test_evaluate_regression_metrics():
    y = np.linspace(0, 1, 50)
    m = M.evaluate_regression(y, y)
    assert m["mae"] == 0.0 and m["rmse"] == 0.0 and m["r2"] == 1.0 and m["spearman"] == 1.0
    bad = M.evaluate_regression(y, np.ones_like(y) * 0.5)
    assert bad["r2"] is None  # constant prediction


def test_top_k_consistency():
    y = np.asarray([0.9, 0.8, 0.1, 0.2, 0.3], dtype=float)
    p = np.asarray([0.9, 0.7, 0.4, 0.2, 0.1], dtype=float)
    tk = M.top_k_consistency(y, p, k=3)
    assert tk["top1_consistent"] == 1
    assert 0 <= tk["top3_consistent"] <= 1


def test_mlp_fit_predict_save_load(tmp_path):
    n = 120
    X_emb = np.random.RandomState(1).rand(n, 16).astype(np.float32)
    X_env = np.random.RandomState(2).rand(n, 6).astype(np.float32)
    y = np.clip(X_emb[:, 0] + X_env[:, 0], 0, 1).astype(np.float32)
    mlp = M.SuitabilityMLP(embedding_dim=16, env_dim=6, hidden=8, dropout=0.1)
    mlp.fit(X_emb, X_env, y, n_epochs=10, batch_size=32, patience=4,
            X_val_emb=X_emb, X_val_env=X_env, y_val=y)
    p = mlp.predict(X_emb, X_env)
    assert p.shape == (n,)
    assert np.isfinite(p).all()

    cfg = {"embedding_dim": 16, "env_dim": 6, "hidden_dim": 8, "dropout": 0.1}
    pth = tmp_path / "net.pt"
    mlp.save(pth, cfg)
    loaded = M.SuitabilityMLP.load(pth, cfg, embedding_dim=16, env_dim=6)
    p2 = loaded.predict(X_emb, X_env)
    assert np.allclose(p, p2, atol=1e-5)


def test_merge_embeddings_dim_check():
    table = pd.DataFrame({"enzyme_id": ["A", "B", "C"]})
    emb = {"A": np.zeros(4), "B": np.ones(4), "C": np.full(4, 2.0)}
    arr = M.merge_embeddings(table, emb, expected_dim=4)
    assert arr.shape == (3, 4)
    with pytest.raises(ValueError):
        M.merge_embeddings(table, emb, expected_dim=8)