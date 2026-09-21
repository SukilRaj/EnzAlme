"""
ENZAIme — Data Abstraction Layer
===================================
Single entry point used by scripts, the backend, and tests to load the
canonical enzyme table. This isolates every other module from knowing
WHERE the data physically lives, so that:

  * real datasets (BRENDA/UniProt/PAZy-derived processed CSVs) can be
    dropped into data/processed/enzymes.csv later, and
  * FireProtDB / industrial wastewater datasets remain fully optional,

...without any downstream code changes (Section 4, Section 19).

Load order (first match wins):
  1. data/processed/enzymes.csv   (output of scripts/03_build_master_dataset.py)
  2. data/demo/enzymes_demo.csv   (shipped MVP demo dataset)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from . import config

logger = logging.getLogger("enzaime.data_loader")

REQUIRED_COLUMNS = [
    "enzyme_id", "accession", "enzyme_name", "ec_number", "pollutant",
    "sequence", "seq_length", "source", "evidence_type",
    "pH_opt", "pH_min", "pH_max", "T_opt", "T_min", "T_max",
    "salinity_evidence", "salinity_min", "salinity_max", "notes",
    "demo_assumption",
]

_cache: Optional[pd.DataFrame] = None
_cache_source: Optional[str] = None


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = ["seq_length", "pH_opt", "pH_min", "pH_max",
                     "T_opt", "T_min", "T_max", "salinity_min", "salinity_max"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def load_enzyme_table(force_reload: bool = False) -> pd.DataFrame:
    """
    Load the canonical enzyme metadata table with graceful fallback.
    Returns a pandas DataFrame with (at least) REQUIRED_COLUMNS.
    """
    global _cache, _cache_source
    if _cache is not None and not force_reload:
        return _cache

    if config.CANONICAL_ENZYME_CSV.exists():
        path = config.CANONICAL_ENZYME_CSV
    elif config.DEMO_ENZYME_CSV.exists():
        path = config.DEMO_ENZYME_CSV
        logger.info("processed/enzymes.csv not found — falling back to demo dataset at %s", path)
    else:
        raise FileNotFoundError(
            "No enzyme dataset found. Expected data/processed/enzymes.csv "
            "(run scripts/03_build_master_dataset.py) or data/demo/enzymes_demo.csv "
            "to be present."
        )

    df = pd.read_csv(path)
    df = _coerce_types(df)
    _cache = df
    _cache_source = str(path)
    logger.info("Loaded %d enzyme records from %s", len(df), path)
    return df


def get_data_source() -> str:
    if _cache_source is None:
        load_enzyme_table()
    return _cache_source


def get_enzyme_by_id(enzyme_id: str) -> Optional[dict]:
    df = load_enzyme_table()
    match = df[df["enzyme_id"] == enzyme_id]
    if len(match) == 0:
        return None
    return match.iloc[0].to_dict()


def candidates_for_pollutant(pollutant: str) -> pd.DataFrame:
    """
    Return all enzymes that have ANY documented/predicted evidence for the
    given pollutant (Section 11.1 — full exclusion of unrelated pollutants
    happens later in the scoring/filtering step, this is just a fast
    pre-filter to keep the candidate set relevant).
    """
    df = load_enzyme_table()
    return df[df["pollutant"].astype(str).str.upper() == pollutant.strip().upper()].copy()
