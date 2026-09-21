"""Tests: transparent label + scenario generation (src/label_generation.py)."""
import numpy as np
import pandas as pd
import pytest

import label_generation as lg


def test_ph_optimal_matches():
    assert lg.ph_component(8.0, "9.0", "", "") == 1.0  # within tolerance 1.5
    assert lg.ph_component(6.0, "9.0", "", "") < 1.0  # outside tolerance


def test_temperature_known_optimum():
    c = lg.temperature_component(40.0, "50.0", "", "")
    assert np.isclose(c, 1.0)
    assert lg.temperature_component(80.0, "50.0", "", "") < 1.0


def test_salinity_neutral_without_metadata():
    assert lg.salinity_component(1.0, None, None, None) == 0.5


def test_unknown_evidence_low_confidence():
    assert lg.evidence_quality("experimental") == 1.0
    assert lg.evidence_quality("curated") == 0.85
    assert lg.evidence_quality("predicted") == 0.6
    assert lg.evidence_quality(None) == 0.1


def test_confidence_penalises_missing_metadata():
    hi = lg.confidence_score(0.85, has_ph=1, has_temp=1, has_sal=1)
    lo = lg.confidence_score(0.85, has_ph=0, has_temp=0, has_sal=0)
    assert hi > lo


def test_label_within_0_1():
    label = lg.compatibility_label(0.4, 1.0, 1.0, 0.5)
    assert 0.0 <= label <= 1.0


def test_generate_scenarios_grid_and_aliases(tmp_path):
    import data_quality as dq

    master = pd.DataFrame({
        "enzyme_id": ["E1", "E2"],
        "accession": ["P1", ""],
        "enzyme_name": ["a", "b"],
        "protein_sequence": ["MKT" * 40, "MKT" * 30],
        "ec_number": ["3.1.1.1", ""],
        "organism": ["x", ""],
        "pollutant_type": ["PET", "PE"],
        "substrate": ["", ""],
        "evidence_type": ["curated", "curated"],
        "evidence_score": ["", ""],
        "ph_opt": ["9.0", ""], "ph_min": ["7.0", ""], "ph_max": ["11.0", ""],
        "temperature_opt_c": ["30", "50"], "temperature_min_c": ["", ""],
        "temperature_max_c": ["", ""],
        "salinity_opt": ["", ""], "salinity_min": ["", ""], "salinity_max": ["", ""],
        "sequence_length": ["", ""],
    })
    inp = tmp_path / "master.csv"
    master.to_csv(inp, index=False)
    dq.run_data_quality(inp, tmp_path, tmp_path / "reports")

    clean = tmp_path / "master_enzymes_clean.csv"
    scenarios = lg.generate_scenarios(clean, tmp_path / "scenarios.csv")
    # E1 (PET) included; E2 pollutant "PE" unknown -> excluded (no evidence)
    two_enz = pd.DataFrame(master)
    two_enz.loc[1, "pollutant_type"] = "PET"
    two_enz.to_csv(tmp_path / "m2.csv", index=False)
    dq.run_data_quality(tmp_path / "m2.csv", tmp_path, tmp_path / "r2")
    sc = lg.generate_scenarios(tmp_path / "master_enzymes_clean.csv",
                               tmp_path / "scenarios2.csv")
    enzymes_used = sc["enzyme_id"].nunique()
    assert enzymes_used == 2
    assert sc["derived_compatibility_label"].between(0, 1).all()
    assert (sc["salinity_metadata_available"] == 0).all()
    # E1 has pH range -> 5-point grid for pH; temp range absent -> fallback grid
    e1 = sc[sc["enzyme_id"] == "E1"]
    assert e1["scenario_ph"].nunique() >= 1
    assert e1["ph_metadata_available"].eq(1).any()
    # derived label exists but is not experimental
    assert (sc["label_source"] == "derived_compatibility_label").all()