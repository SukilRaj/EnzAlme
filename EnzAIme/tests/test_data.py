"""
tests/test_data.py
=====================
Section 39 tests #1 (implicitly via scoring, see test_scoring.py) plus data
integrity checks that back every other test in this suite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from enzaime_core import config, data_loader


def test_enzyme_table_loads():
    df = data_loader.load_enzyme_table(force_reload=True)
    assert len(df) > 0


def test_required_columns_present():
    df = data_loader.load_enzyme_table()
    for col in data_loader.REQUIRED_COLUMNS:
        assert col in df.columns, f"missing required column: {col}"


def test_no_duplicate_enzyme_ids():
    df = data_loader.load_enzyme_table()
    assert df["enzyme_id"].is_unique


def test_no_fabricated_dmatase_sequences():
    """Section 5 — the tRNA dimethylallyltransferase UniProt records must
    never appear in the enzyme recommendation dataset."""
    df = data_loader.load_enzyme_table()
    names = df["enzyme_name"].astype(str).str.lower()
    assert not names.str.contains("dimethylallyltransferase").any()


def test_all_pollutants_are_supported_categories():
    df = data_loader.load_enzyme_table()
    assert set(df["pollutant"].dropna().unique()) <= set(config.SUPPORTED_POLLUTANTS)


def test_sequences_only_contain_valid_amino_acids():
    df = data_loader.load_enzyme_table()
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    for _, row in df.iterrows():
        seq = row.get("sequence")
        if isinstance(seq, str) and len(seq) > 0:
            assert set(seq.upper()) <= valid_aa, f"invalid residues in {row['enzyme_id']}"


def test_get_enzyme_by_id():
    row = data_loader.get_enzyme_by_id("ENZ001")
    assert row is not None
    assert row["enzyme_id"] == "ENZ001"


def test_get_enzyme_by_id_unknown_returns_none():
    assert data_loader.get_enzyme_by_id("NOT_A_REAL_ID") is None


def test_candidates_for_pollutant():
    pet = data_loader.candidates_for_pollutant("PET")
    assert len(pet) > 0
    assert (pet["pollutant"].str.upper() == "PET").all()
