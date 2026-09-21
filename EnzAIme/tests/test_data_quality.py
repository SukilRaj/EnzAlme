"""Tests: data quality & cleaning (src/data_quality.py)."""
import numpy as np
import pandas as pd
import pytest

import data_quality as dq


def test_clean_sequence_strips_fasta_artifacts():
    cleaned, flags = dq.clean_sequence(">\n  MKT--VAL 123 ...ITLE AAAAAAAAAAAAA")
    assert cleaned == "MKTVALITLEAAAAAAAAAAAAA"
    assert flags == []


def test_clean_sequence_rejects_short_and_dna():
    _, short = dq.clean_sequence("MK")
    assert "short_sequence" in short
    _, dnarna = dq.clean_sequence("ACGTACGTACGTACGTACGTACGT")
    assert "possible_dna_rna" in dnarna


def test_clean_sequence_flags_ambiguous():
    _, flags = dq.clean_sequence("MKVBXZ" + "A" * 40)
    assert any(f.startswith("removed_ambiguous_residues") for f in flags)


def test_clean_sequence_empty():
    cleaned, flags = dq.clean_sequence("")
    assert cleaned == ""
    assert "sequence_missing" in flags


def test_sequence_hash_deterministic():
    assert dq.sequence_hash("MKT") == dq.sequence_hash("MKT")
    assert dq.sequence_hash("MKT") != dq.sequence_hash("MKV")


def test_normalize_pollutant():
    assert dq.normalize_pollutant("PETE") == "PET"
    assert dq.normalize_pollutant("polyethylene terephthalate") == "PET"
    assert dq.normalize_pollutant("nylon") == "PA"
    assert dq.normalize_pollutant("RANDOM99") == "RANDOM99"  # preserved unchanged


def test_safe_numeric_imputation_uses_documented_neutral_value():
    s = pd.Series(["9.0", "", "5.0", "NA"], dtype=object)
    out = dq.safe_numeric_imputation(s, missing=-1.0)
    assert out.iloc[1] == -1.0 and out.iloc[3] == -1.0
    assert out.iloc[0] == 9.0


def test_missingness_features():
    df = pd.DataFrame({
        "protein_sequence": ["MKT" * 20, "", 1],
        "accession": ["P12345", "", "Q00000"],
        "ph_min": [5.0, np.nan, np.nan], "ph_max": [9.0, np.nan, np.nan],
        "ph_opt": [7.0, "", ""],
        "temperature_min_c": ["", "", ""], "temperature_max_c": ["", "", ""],
        "temperature_opt_c": ["", "", "40"],
        "salinity_min": ["", "", ""], "salinity_max": ["", "", ""],
        "salinity_opt": ["", "", "1.0"],
        "substrate": ["x", "y", "z"], "ec_number": ["3.1.1.1", "", "3.1.1.2"],
        "organism": ["a", "a", "b"],
    })
    out = dq.add_missingness_features(df)
    assert list(out["has_sequence"]) == [1, 0, 1]
    assert list(out["has_ph_opt"]) == [1, 0, 0]
    assert list(out["has_ph_range"])[0] == 1
    assert list(out["has_salinity_data"])[2] == 1


def test_metadata_completeness_score():
    row = pd.Series({
        "has_sequence": 1, "has_accession": 1, "has_ec_number": 1,
        "has_organism": 1, "has_substrate": 0, "has_ph_opt": 0,
        "has_temperature_opt": 0, "has_salinity_data": 0,
    })
    assert dq.calculate_metadata_completeness(row) == 0.5


def test_evidence_confidence_mapping():
    assert dq.calculate_evidence_confidence("experimental", None) == 1.0
    assert dq.calculate_evidence_confidence("curated", None) == 0.85
    assert dq.calculate_evidence_confidence("predicted", None) == 0.6
    assert dq.calculate_evidence_confidence("unknown", None) == 0.1
    assert dq.calculate_evidence_confidence("curated", "") == 0.85
    # explicit numeric score wins (still bounded)
    assert dq.calculate_evidence_confidence("predicted", "0.7") == 0.7


def test_run_data_quality_end_to_end(tmp_path):
    master = pd.DataFrame({
        "enzyme_id": ["E1", "E2", "E3"],
        "accession": ["P1", "P2", ""],
        "enzyme_name": ["a", "b", "c"],
        "protein_sequence": ["MKT" * 40, "", "MKT" * 30],
        "ec_number": ["3.1.1.1", "3.1.1.1", ""],
        "organism": ["x", "x", ""],
        "pollutant_type": ["PET", "PET", "nylon"],
        "substrate": ["", "", ""],
        "evidence_type": ["curated", "predicted", ""],
        "evidence_score": ["", "", ""],
    })
    inp = tmp_path / "master.csv"
    master.to_csv(inp, index=False)
    out_dir, rep_dir = tmp_path / "out", tmp_path / "reports"
    res = dq.run_data_quality(inp, out_dir, rep_dir)

    assert res["n_rows"] == 3
    assert res["n_valid_sequences"] == 2
    assert res["n_missing_sequences"] == 1
    assert res["n_events"] == 0  # "nylon" is an alias -> normalised to PA, not flagged

    clean = pd.read_csv(out_dir / "master_enzymes_clean.csv", keep_default_na=False)
    assert clean.loc[0, "pollutant_type"] == "PET"
    assert list(clean["has_sequence"]) == [1, 0, 1]
    assert clean["ph_opt"].map(dq._is_missing).all()  # never invented
    assert "has_salinity_data" in clean.columns
    assert clean["evidence_confidence"].max() == 0.85

    valid = pd.read_csv(out_dir / "master_enzymes_valid_sequences.csv")
    assert len(valid) == 2
    missing = pd.read_csv(out_dir / "master_enzymes_missing_sequences.csv")
    assert len(missing) == 1
    log = pd.read_csv(out_dir / "sequence_recovery_log.csv")
    assert (log["recovery_status"] == "not_recovered_no_auto_download").all()
    assert (rep_dir / "data_quality_report.csv").exists()
    assert (rep_dir / "data_conflicts.csv").exists()
    assert (rep_dir / "unmatched_records.csv").exists()