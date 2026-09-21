"""Tests: explainable inference (src/inference.py)."""
import json

import pytest

import inference as inf


@pytest.fixture(scope="module")
def recommender(tmp_path_factory):
    # Build a tiny clean dataset through the real pipeline and a rule recommender on it.
    import pandas as pd
    import data_quality as dq

    master = pd.DataFrame({
        "enzyme_id": ["E1", "E2", "E3"],
        "accession": ["P1", "P2", "P3"],
        "enzyme_name": ["PETase", "MHETase", "cutinase"],
        "protein_sequence": ["MKT" * 40, "MKT" * 38, ""],
        "ec_number": ["3.1.1.101", "3.1.1.102", ""],
        "organism": ["a", "b", "c"],
        "pollutant_type": ["PET", "PET", "PUR"],
        "substrate": ["", "", ""],
        "evidence_type": ["curated", "curated", "predicted"],
        "evidence_score": ["", "", ""],
        "ph_opt": ["9.0", "7.5", "7.0"],
        "ph_min": ["7.0", "5.0", ""], "ph_max": ["11.0", "9.0", ""],
        "temperature_opt_c": ["30", "30", "65"],
        "temperature_min_c": ["", "", ""], "temperature_max_c": ["", "", ""],
        "salinity_opt": ["", "", ""], "salinity_min": ["", "", ""],
        "salinity_max": ["", "", ""],
        "sequence_length": ["", "", ""],
    })
    tmp = tmp_path_factory.mktemp("inf")
    master.to_csv(tmp / "master.csv", index=False)
    dq.run_data_quality(tmp / "master.csv", tmp, tmp / "reports")
    return inf.RuleBasedRecommender(clean_csv=tmp / "master_enzymes_clean.csv")


def test_rule_recommender_structure(recommender):
    out = recommender.recommend("PET", ph=8.0, temperature=35, salinity=0.5, top_k=3)
    assert out["mode"] == "rule_based_baseline"
    assert len(out["recommendations"]) >= 2
    r = out["recommendations"][0]
    for field in ["enzyme_id", "suitability_score", "confidence_score",
                  "evidence_score", "explanation", "limitations",
                  "known_ph_information", "known_salinity_information"]:
        assert field in r
    assert 0 <= r["suitability_score"] <= 1
    assert "derived compatibility estimate" in r["limitations"]


def test_rule_recommender_respects_pollutant_match(recommender):
    out = recommender.recommend("PET", ph=8.0, temperature=35, salinity=0.0, top_k=5)
    pets = [r for r in out["recommendations"] if r["pollutant_type"] == "PET"]
    assert len(pets) >= 2  # both PET enzymes scored higher than unrelated PUR


def test_rule_recommender_unknown_degrades_confidence(recommender):
    r = recommender.recommend("PUR", ph=7.0, temperature=50, salinity=0.0, top_k=5)
    rec = next(x for x in r["recommendations"] if x["enzyme_id"] == "E3")
    assert rec["known_salinity_information"] is False
    assert rec["limitations"].startswith("Limitations:")


def test_ml_recommender_falls_back_when_no_artifacts(recommender, tmp_path, monkeypatch):
    monkeypatch.setattr(inf, "REPO_ROOT", tmp_path)  # no artifacts dir exists
    monkeypatch.setattr(inf, "RuleBasedRecommender", lambda *a, **k: recommender)
    r = inf.MLRecommender()
    out = r.recommend("PET", 8.0, 35, 0.5, top_k=2)
    assert out["mode"] == "fallback_rule_based"