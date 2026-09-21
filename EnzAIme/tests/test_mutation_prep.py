"""Tests: mutation-candidate preparation (src/mutation_prep.py)."""
import json

import numpy as np
import pandas as pd
import pytest

import mutation_prep as mp


def test_aa_properties():
    props = mp._aa_properties("W")
    assert props["hydrophobic"] == 1
    assert props["positive"] == 0


def test_solvent_score_bounds():
    seq = "A" * 21
    assert 0 <= mp._solvent_score(seq, 10) <= 1


def test_generate_candidates_end_to_end(tmp_path):
    n = 4
    d = tmp_path / "d"
    d.mkdir()
    valid = pd.DataFrame({
        "enzyme_id": [f"E{i}" for i in range(n)],
        "protein_sequence": ["MKT" * 20 + aa for aa in "ACDE"],
    })
    valid.to_csv(d / "valid.csv", index=False)
    emb = np.random.RandomState(0).rand(n, 5)
    np.save(d / "esm_embeddings.npy", emb)
    pd.DataFrame({"enzyme_id": [f"E{i}" for i in range(n)],
                  "sequence_hash": [f"h{i}" for i in range(n)]},
                 ).to_csv(d / "esm_embedding_index.csv", index=False)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "feature_config.json").write_text(json.dumps({"embedding_dim": 5}))
    out_csv = d / "mutation_candidates.csv"
    report = tmp_path / "reports" / "mutation_prep_summary.json"

    df = mp.generate_mutation_candidates(d / "valid.csv", d / "esm_embeddings.npy",
                                         d / "esm_embedding_index.csv", artifacts,
                                         out_csv, report, top_k=5)
    assert len(df) == n * 5
    assert set(df["enzyme_id"]) == {f"E{i}" for i in range(n)}
    assert df["rank"].max() == 5
    assert (df["mutation_aa"] != df["original_aa"]).all()

    summ = json.loads(report.read_text())
    assert summ["total_candidates"] == n * 5
    assert "COMPUTATIONAL ONLY" in summ["caveat"].upper()