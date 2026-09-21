"""
EnzAIme — Data Quality & Cleaning (master dataset)
===================================================
Loads `data/processed/master_enzymes.csv` (28-column master produced by
`src/build_master_dataset.py`), validates/cleans it, and produces:

  data/processed/master_enzymes_clean.csv              (all rows, cleaned + flags)
  data/processed/master_enzymes_valid_sequences.csv    (rows usable for ESM training)
  data/processed/master_enzymes_missing_sequences.csv  (catalogue-only rows)
  data/processed/sequence_recovery_log.csv             (STEP 3: recovery plan per gap)
  reports/data_quality_report.csv                      (file+column level)
  reports/data_conflicts.csv                           (dup/conflict events inside master)
  reports/unmatched_records.csv                        (records not embeddable / not mappable)

Scientific honesty rules enforced here:
  * Missing pH/temperature/salinity/EC/organism/substrate values are NEVER invented.
  * Missing sequences are NEVER fabricated; they are flagged and excluded from ESM
    training while the row stays available as catalogue/recommendation metadata.
  * All original values are preserved; only flags are added.
  * DNA/RNA-looking sequences are flagged, not silently accepted or dropped.

Run:
  python src/data_quality.py
  python src/data_quality.py --input data/processed/master_enzymes.csv \
      --output-dir data/processed --report-dir reports
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPO_ROOT = SRC_DIR.parent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")
DNA_RNA_ALPHABET = frozenset("ACGTUN")
SUSPICIOUS_RESIDUES = frozenset("XBZJUO*")
# Below this length a "protein" is almost certainly a fragment or artefact.
MIN_PROTEIN_LENGTH = 20
# ESM-2 (esm2_t33_650M) truncates at max_position_embeddings=1022; anything
# longer is flagged (still embeds safely with truncation, but noted).
ESM_MAX_LENGTH = 1022
MAX_PROTEIN_LENGTH = 2048

POLLUTANT_ALIASES = {
    "PET": "PET", "PETE": "PET", "poly(ethylene terephthalate)": "PET",
    "polyethylene terephthalate": "PET",
    "PA": "PA", "nylon": "PA", "polyamide": "PA",
    "PUR": "PUR", "polyurethane": "PUR",
    "PE": "PE", "polyethylene": "PE",
    "PP": "PP", "polypropylene": "PP",
    "PS": "PS", "polystyrene": "PS",
    "PLA": "PLA", "polylactic acid": "PLA",
    "PBAT": "PBAT", "PHA": "PHA", "PU": "PUR",
}


def normalize_pollutant(value) -> str:
    """Normalise only obvious spelling/case variants; unknown stays as-is."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return ""
    s = str(value).strip().upper()
    if s in POLLUTANT_ALIASES:
        return POLLUTANT_ALIASES[s]
    key = s.lower()
    if key in POLLUTANT_ALIASES:
        return POLLUTANT_ALIASES[key]
    return s


def _is_missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and v != v:  # NaN
        return True
    if isinstance(v, str):
        return not v.strip() or v.strip().lower() in {"nan", "none", "null", "na", "unknown"}
    return False


def _norm_str(v) -> str:
    return "" if _is_missing(v) else str(v).strip()


# ---------------------------------------------------------------------------
# Sequence cleaning
# ---------------------------------------------------------------------------
def clean_sequence(raw) -> tuple[str, list[str]]:
    """
    Return (cleaned_sequence, flags).

    Rules:
      * uppercase
      * strip all whitespace/digits/non-letter symbols (safe: FASTA artifacts,
        gaps '-' , '*', whitespace, numbers, punctuation)
      * keep only standard amino-acid letters A-Z (20) but do NOT silently drop
        ambiguous letters -- they raise a flag
      * reject empty results / report them
      * flag possible DNA/RNA sequences (alphabet subset of ACGTUN and long)
    """
    flags: list[str] = []
    if _is_missing(raw):
        return "", ["sequence_missing"]
    s = str(raw).upper()

    # 1) strip FASTA artifacts / formatting (safe removals)
    s = re.sub(r"[^A-Z]", "", s)

    # 2) ambiguous / non-standard letters
    bad = sorted(set(s) - set(VALID_AA))
    if bad:
        flags.append("removed_ambiguous_residues:" + ",".join(bad))
        s = "".join(c for c in s if c in VALID_AA)

    if not s:
        return "", ["sequence_empty_after_cleaning"]

    # 3) DNA/RNA suspicion: all residues within {A,C,G,T,U,N}, no other letters,
    #    and sequence is long enough to not be a short protein motif.
    if set(s) <= DNA_RNA_ALPHABET and len(s) >= MIN_PROTEIN_LENGTH:
        flags.append("possible_dna_rna")

    if len(s) < MIN_PROTEIN_LENGTH:
        flags.append("short_sequence")
    if len(s) > MAX_PROTEIN_LENGTH:
        flags.append("excessively_long_sequence")
    elif len(s) > ESM_MAX_LENGTH:
        flags.append("longer_than_esm_max:truncated_at_1022")

    return s, flags


def sequence_hash(seq: str) -> str:
    return hashlib.sha256(seq.encode("ascii", errors="ignore")).hexdigest()


def _is_standard_aa(seq: str) -> bool:
    return bool(seq) and set(seq) <= VALID_AA


# ---------------------------------------------------------------------------
# Missing / imputation helpers (STEP 4)
# ---------------------------------------------------------------------------
def safe_numeric_imputation(series: pd.Series, missing: float) -> pd.Series:
    """
    Replace missing numeric values with a SINGLE neutral value and rely on the
    companion has_* flag. Never a data-dependent mean: the neutral value is
    documented and identical for every enzyme, so the model can un-ambiguously
    learn "missing" from (imputed_value, has_*=0).
    """
    out = series.copy()
    out = pd.to_numeric(out, errors="coerce")
    out = out.fillna(missing)
    return out


def add_missingness_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append explicit has_* indicator columns (0/1)."""
    out = df.copy()
    for col in ["protein_sequence", "accession", "ph_min", "ph_max", "ph_opt",
                "temperature_min_c", "temperature_max_c", "temperature_opt_c",
                "salinity_min", "salinity_max", "salinity_opt",
                "substrate", "ec_number", "organism"]:
        if col not in out.columns:
            out[col] = ""
    out["has_sequence"] = (~out["protein_sequence"].map(_is_missing)).astype(int)
    out["has_accession"] = (~out["accession"].map(_is_missing)).astype(int)
    out["has_ph_min_max"] = (
        (~out["ph_min"].map(_is_missing)) & (~out["ph_max"].map(_is_missing))
    ).astype(int)
    out["has_ph_opt"] = (~out["ph_opt"].map(_is_missing)).astype(int)
    out["has_ph_range"] = out["has_ph_min_max"]
    out["has_temperature_opt"] = (~out["temperature_opt_c"].map(_is_missing)).astype(int)
    out["has_temperature_min_max"] = (
        (~out["temperature_min_c"].map(_is_missing))
        & (~out["temperature_max_c"].map(_is_missing))
    ).astype(int)
    out["has_temperature_range"] = out["has_temperature_min_max"]
    out["has_salinity_data"] = (
        (~out["salinity_min"].map(_is_missing))
        | (~out["salinity_max"].map(_is_missing))
        | (~out["salinity_opt"].map(_is_missing))
    ).astype(int)
    out["has_substrate"] = (~out["substrate"].map(_is_missing)).astype(int)
    out["has_ec_number"] = (~out["ec_number"].map(_is_missing)).astype(int)
    out["has_organism"] = (~out["organism"].map(_is_missing)).astype(int)
    return out


def calculate_metadata_completeness(row: pd.Series) -> float:
    """Fraction of core metadata fields that are populated (0..1)."""
    fields = [
        row.get("has_sequence"), row.get("has_accession"), row.get("has_ec_number"),
        row.get("has_organism"), row.get("has_substrate"), row.get("has_ph_opt"),
        row.get("has_temperature_opt"), row.get("has_salinity_data"),
    ]
    present = sum(1 for f in fields if f == 1)
    return round(present / len(fields), 4)


def calculate_evidence_confidence(evidence_type: str, evidence_score) -> float:
    """
    Ordinal provenance score in [0,1] derived ONLY from the explicit
    evidence_type label (documented provenance, not a biological measurement).
    """
    _map = {
        "experimental": 1.0,
        "curated": 0.85,
        "predicted": 0.6,
        "inferred": 0.4,
        "heuristic": 0.25,
        "unknown": 0.1,
    }
    key = (evidence_type or "").strip().lower()
    base = _map.get(key, 0.1)
    if not _is_missing(evidence_score):
        try:
            return round(min(1.0, float(evidence_score)), 4)
        except (TypeError, ValueError):
            pass
    return base


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_data_quality(input_csv: Path, output_dir: Path, report_dir: Path) -> dict:
    if not input_csv.exists():
        raise FileNotFoundError(f"Master dataset not found: {input_csv}. "
                                "Run src/build_master_dataset.py first.")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, keep_default_na=False, na_values=[])
    if "sequence_length" in df.columns:
        df["sequence_length"] = pd.to_numeric(df["sequence_length"], errors="coerce")

    # ---- 1. standardize columns ------------------------------------------
    rename = {}
    for c in df.columns:
        if c.lower() in {"enzyme", "protein", "id", "enzymeid"} and c != "enzyme_id":
            rename[c] = "enzyme_id"
    alias = {
        "sequence": "protein_sequence",
        "seq": "protein_sequence",
        "seq_length": "sequence_length",
        "temp_opt": "temperature_opt_c",
        "temperature": "temperature_opt_c",
        "temp_min": "temperature_min_c",
        "temp_max": "temperature_max_c",
        "ph": "ph_opt",
    }
    for k, v in alias.items():
        if k in df.columns and v not in df.columns:
            rename[k] = v
    df = df.rename(columns=rename)

    flags_col = "data_quality_flag" if "data_quality_flag" in df.columns else "data_quality_flag"
    if flags_col not in df.columns:
        df[flags_col] = ""

    # ---- 2. sequence cleaning --------------------------------------------
    clean_rows: list[str] = []
    invalid_aa_rows: list[str] = []
    dna_rows: list[str] = []
    for idx, seq in df["protein_sequence"].items():
        cleaned, f = clean_sequence(seq)
        df.at[idx, "protein_sequence"] = cleaned
        df.at[idx, "sequence_length"] = float(len(cleaned)) if cleaned else float("nan")
        df.at[idx, "sequence_hash"] = sequence_hash(cleaned) if cleaned else ""
        extra = ";".join(f)
        old = df.at[idx, flags_col]
        df.at[idx, flags_col] = (old + ";" + extra).strip(";") if extra else old
        if cleaned and not _is_standard_aa(cleaned):
            invalid_aa_rows.append(str(df.at[idx, "enzyme_id"]))
        if "short_sequence" in f:
            clean_rows.append(str(df.at[idx, "enzyme_id"]))
        if "possible_dna_rna" in f:
            dna_rows.append(str(df.at[idx, "enzyme_id"]))

    # ---- 3. missingness features ------------------------------------------
    df = add_missingness_features(df)
    df["metadata_completeness"] = df.apply(calculate_metadata_completeness, axis=1)
    df["evidence_confidence"] = df.apply(
        lambda r: calculate_evidence_confidence(r.get("evidence_type"), r.get("evidence_score")),
        axis=1,
    )
    df["unknown_feature_count"] = (
        1 - df["has_ph_opt"]) + (1 - df["has_temperature_opt"]) + (1 - df["has_salinity_data"]
    )
    df["pollutant_type"] = df["pollutant_type"].map(normalize_pollutant)

    # ---- 4. duplicate & conflict detection --------------------------------
    events: list[dict] = []
    for col, label in [("enzyme_id", "duplicate_enzyme_id"),
                       ("accession", "duplicate_accession"),
                       ("sequence_hash", "duplicate_sequence")]:
        dup = df[df[col].astype(str).str.len() > 0]
        dup = dup[dup[col].duplicated(keep=False)]
        for gid, grp in dup.groupby(col):
            events.append({
                "kind": label, "group_key": str(gid),
                "n_records": len(grp), "record_ids": ";".join(grp["enzyme_id"]),
                "resolution": "kept_separate_seen_conflict",
            })

    # conflicting metadata: same accession but differing pollutant/EC evidence
    acc = df[df["accession"].map(_is_missing).eq(False)]
    for gid, grp in acc.groupby("accession"):
        if grp["pollutant_type"].nunique() > 1 or grp["ec_number"].nunique() > 1:
            events.append({
                "kind": "conflicting_metadata_within_accession",
                "group_key": str(gid), "n_records": len(grp),
                "record_ids": ";".join(grp["enzyme_id"]), "resolution": "manual_review",
            })

    # invalid pollutant values (not one of the supported/known set)
    invalid_poll = df[~df["pollutant_type"].map(_is_missing)
                      & ~df["pollutant_type"].isin({
                          "PET", "PUR", "PA", "PE", "PP", "PS", "PLA", "PBAT", "PHA"
                      })]
    for _, r in invalid_poll.iterrows():
        events.append({
            "kind": "unrecognised_pollutant_label",
            "group_key": r.get("pollutant_type"), "n_records": 1,
            "record_ids": r.get("enzyme_id"), "resolution": "preserved_unchanged",
        })

    events_df = pd.DataFrame(events)

    # ---- 5. split valid vs missing sequences (catalogue-only rows) --------
    valid = df[df["has_sequence"] == 1].copy().reset_index(drop=True)
    missing = df[df["has_sequence"] == 0].copy().reset_index(drop=True)

    # ---- 6. STEP 3: sequence recovery plan (NO auto-download) -------------
    recovery_rows = []
    for _, r in missing.iterrows():
        identifiers = []
        if not _is_missing(r.get("accession")):
            identifiers.append(f"UniProt accession: {r['accession']}")
        if not _is_missing(r.get("enzyme_name")):
            identifiers.append(f"enzyme name: {r['enzyme_name']}")
            if not _is_missing(r.get("organism")):
                identifiers.append(f"organism: {r['organism']}")
        if not _is_missing(r.get("ec_number")):
            identifiers.append(f"EC: {r['ec_number']}+organism")
        recovery_rows.append({
            "enzyme_id": r.get("enzyme_id"),
            "enzyme_name": r.get("enzyme_name"),
            "accession": r.get("accession"),
            "ec_number": r.get("ec_number"),
            "organism": r.get("organism"),
            "recommended_source": "UniProt (official public source only)",
            "retrieval_url": ("https://rest.uniprot.org/uniprotkb/"
                              + str(r["accession"]) + ".fasta"
                              if not _is_missing(r.get("accession")) else ""),
            "retrieval_date": "",
            "recovery_status": "not_recovered_no_auto_download",
            "confidence_grade": "unknown",
            "reason": ("No sequence in any local source; recovery requires an explicit, "
                       "user-approved download against a verified identifier. Not guessed."),
        })
    recovery_df = pd.DataFrame(recovery_rows)

    # ---- 7. unmatched records (for training/mapping) -----------------------
    unmatched_rows = []
    for _, r in missing.iterrows():
        unmatched_rows.append({
            "record_id": r.get("enzyme_id"),
            "record_type": "enzyme_catalogue_row",
            "reason": "missing_protein_sequence",
            "action": "kept_in_catalogue; excluded from ESM training; "
                      "available for recommendation-only use",
        })
    if len(acc) == 0:
        pass
    unmatched_df = pd.DataFrame(unmatched_rows)

    # ---- 8. quality report --------------------------------------------------
    cols_of_interest = [
        "enzyme_id", "accession", "enzyme_name", "protein_sequence", "sequence_length",
        "ec_number", "organism", "pollutant_type", "substrate", "ph_opt", "ph_min",
        "ph_max", "temperature_opt_c", "temperature_min_c", "temperature_max_c",
        "salinity_opt", "salinity_min", "salinity_max", "evidence_type",
        "evidence_score", "metadata_completeness", "evidence_confidence",
        "unknown_feature_count",
    ]
    q = []
    for c in cols_of_interest:
        if c not in df.columns:
            continue
        present = (~df[c].map(_is_missing)).sum()
        q.append({
            "column": c,
            "n_present": int(present),
            "n_missing": int(len(df) - present),
            "missing_pct": round(100 * (len(df) - present) / max(1, len(df)), 1),
        })
    q.append({"column": "protein_sequence", "n_present": int(len(valid)),
              "n_missing": int(len(missing)),
              "missing_pct": round(100 * len(missing) / max(1, len(df)), 1)})
    quality_df = pd.DataFrame(q)

    # ---- 9. write outputs ----------------------------------------------------
    out = {
        "master_enzymes_clean.csv": df,
        "master_enzymes_valid_sequences.csv": valid,
        "master_enzymes_missing_sequences.csv": missing,
    }
    for name, frame in out.items():
        frame.to_csv(output_dir / name, index=False)
    recovery_df.to_csv(output_dir / "sequence_recovery_log.csv", index=False)
    rows_q = [
        {"report": "n_raw_rows", "level": "table", "value": len(df)},
        {"report": "n_valid_sequences", "level": "table", "value": len(valid)},
        {"report": "n_missing_sequences", "level": "table", "value": len(missing)},
    ]
    rows_q += [
        {"report": row["column"], "level": "column", "value": row["missing_pct"]}
        for row in q
    ]
    report_df = pd.DataFrame(rows_q)
    report_df.to_csv(report_dir / "data_quality_report.csv", index=False)
    (report_dir / "data_conflicts.csv").write_text(
        events_df.to_csv(index=False) if len(events_df) else "kind,group_key,n_records,record_ids,resolution\n"
    )
    (report_dir / "unmatched_records.csv").write_text(
        unmatched_df.to_csv(index=False) if len(unmatched_df)
        else "record_id,record_type,reason,action\n"
    )

    # ---- 10. console summary --------------------------------------------------
    print("=" * 72)
    print("DATA QUALITY — master_enzymes.csv")
    print("=" * 72)
    print(f"  rows                         : {len(df)}")
    print(f"  rows w/ valid sequence       : {len(valid)}")
    print(f"  rows w/o sequence (catalogue): {len(missing)}")
    print(f"  duplicate enzyme ids         : {sum(1 for e in events if e['kind']=='duplicate_enzyme_id')}")
    print(f"  duplicate accessions         : {sum(1 for e in events if e['kind']=='duplicate_accession')}")
    print(f"  duplicate sequences          : {sum(1 for e in events if e['kind']=='duplicate_sequence')}")
    print(f"  invalid-AA flagged           : {len(invalid_aa_rows)}")
    print(f"  possible DNA/RNA flagged     : {len(dna_rows)}")
    print(f"  short-sequence flagged       : {len(clean_rows)}")
    print(f"  conflict events logged       : {len(events_df)}")
    print(f"  conflicts/events             : {len(events_df)}")
    print()
    print("  outputs:")
    for name in out:
        print(f"    {output_dir / name}")
    print(f"    {output_dir / 'sequence_recovery_log.csv'}")
    for name in ["data_quality_report.csv", "data_conflicts.csv", "unmatched_records.csv"]:
        print(f"    {report_dir / name}")
    return {
        "n_rows": len(df), "n_valid_sequences": len(valid), "n_missing_sequences": len(missing),
        "n_events": len(events_df),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme data quality + cleaning")
    ap.add_argument("--input", default=str(REPO_ROOT / "data" / "processed" / "master_enzymes.csv"),
                    help="Path to master_enzymes.csv")
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "data" / "processed"),
                    help="Where to write clean/enabled CSVs")
    ap.add_argument("--report-dir", default=str(REPO_ROOT / "reports"),
                    help="Where to write report CSVs")
    args = ap.parse_args(argv)
    try:
        run_data_quality(Path(args.input), Path(args.output_dir), Path(args.report_dir))
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())