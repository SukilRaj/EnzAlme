#!/usr/bin/env python3
"""
scripts/03_build_master_dataset.py
=====================================
Builds the canonical data/processed/enzymes.csv used by the backend and by
scripts 04-07, AND splits the stacked ESM-2 embeddings (data/processed/esm_embeddings.npy)
into per-enzyme files at artifacts/embeddings/<enzyme_id>.npy with a _meta.json
descriptor.

Consolidation strategy (based on STEP 1/2 inspection of real processed outputs):
  1. AUTHORITATIVE source: master_enzymes_clean.csv (75 rows, full provenance
     + QC metadata columns). This is the final, most-processed state:
       master_enzymes.csv (75) -> dedup (75 unchanged) -> clean (75 + QC cols)
       -> split into valid_sequences (70) vs missing_sequences (5).
     We use the CLEAN state and keep ALL 75 rows (Option B from STEP 2 report).
     The 5 no-sequence rows get demo_assumption=True and are served by the
     compatibility engine transparently.

  2. SCHEMA MAPPING (source -> canonical per data_loader.py REQUIRED_COLUMNS):
       enzyme_id            -> enzyme_id
       accession            -> accession
       enzyme_name          -> enzyme_name
       ec_number            -> ec_number
       pollutant_type       -> pollutant                 (renamed)
       protein_sequence     -> sequence                  (renamed)
       sequence_length      -> seq_length                (renamed)
       source_database      -> source                    (renamed)
       evidence_type        -> evidence_type
       ph_opt               -> pH_opt                    (case-renamed)
       ph_min               -> pH_min                    (case-renamed)
       ph_max               -> pH_max                    (case-renamed)
       temperature_opt_c    -> T_opt                     (renamed)
       temperature_min_c    -> T_min                     (renamed)
       temperature_max_c    -> T_max                     (renamed)
       <derived>            -> salinity_evidence         (salinity_min|max not NaN)
       salinity_min         -> salinity_min
       salinity_max         -> salinity_max
       notes + <provenance> -> notes
       <derived>            -> demo_assumption           (heuristic_opt_numerics OR
                                                          evidence_type=='predicted' OR
                                                          sequence missing)

  3. VALIDATION: full data-quality checks (duplicates, invalid AAs, pH/T bounds,
     salinity negativity, pollutant category validity). Report written to
     reports/data_quality_report.{json,csv}.

  4. EMBEDDING WIRING: esm_embedding_index.csv (70 rows) maps rows 0..69 of
     esm_embeddings.npy to enzyme_ids. Every index enzyme_id is confirmed to
     exist in the master canonical table. embeddings are split into
     artifacts/embeddings/<enzyme_id>.npy + _meta.json.

Independently executable: python scripts/03_build_master_dataset.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from enzaime_core import config  # noqa: E402
from enzaime_core.data_loader import REQUIRED_COLUMNS  # noqa: E402

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")
VALID_POLLUTANTS = set(config.SUPPORTED_POLLUTANTS)


COLUMN_RENAME_MAP = {
    "pollutant_type": "pollutant",
    "protein_sequence": "sequence",
    "sequence_length": "seq_length",
    "source_database": "source",
    "ph_opt": "pH_opt",
    "ph_min": "pH_min",
    "ph_max": "pH_max",
    "temperature_opt_c": "T_opt",
    "temperature_min_c": "T_min",
    "temperature_max_c": "T_max",
}


def load_authoritative_source(proc_dir: Path) -> pd.DataFrame:
    """STEP 2: pick the most-processed authoritative file and verify the
    pipeline stage row-count ordering."""
    m_raw = pd.read_csv(proc_dir / "master_enzymes.csv")
    m_dedup = pd.read_csv(proc_dir / "master_enzymes_deduplicated.csv")
    m_clean = pd.read_csv(proc_dir / "master_enzymes_clean.csv")
    m_valid = pd.read_csv(proc_dir / "master_enzymes_valid_sequences.csv")
    m_miss = pd.read_csv(proc_dir / "master_enzymes_missing_sequences.csv")

    order_ok = (
        len(m_clean) <= len(m_dedup) <= len(m_raw)
        and len(m_valid) + len(m_miss) == len(m_clean)
    )
    print(f"[STEP 2] Pipeline stage row counts:")
    print(f"  master_enzymes.csv                 -> {len(m_raw)} rows x {len(m_raw.columns)} cols")
    print(f"  master_enzymes_deduplicated.csv    -> {len(m_dedup)} rows x {len(m_dedup.columns)} cols")
    print(f"  master_enzymes_clean.csv           -> {len(m_clean)} rows x {len(m_clean.columns)} cols")
    print(f"  master_enzymes_valid_sequences.csv -> {len(m_valid)} rows")
    print(f"  master_enzymes_missing_sequences   -> {len(m_miss)} rows")
    print(f"  Stage ordering (non-increasing rows, valid+missing==clean): {order_ok and 'OK' or 'UNEXPECTED'}")

    # Report missing-sequence enzyme_ids (flagged per instructions: not silent)
    miss_ids = m_miss["enzyme_id"].tolist()
    print(f"  5 no-sequence rows kept (served by compatibility fallback): {miss_ids}")

    return m_clean.copy()


def map_to_canonical_schema(src: pd.DataFrame) -> pd.DataFrame:
    """STEP 3: apply the explicit column rename map, add derived columns,
    and reorder into REQUIRED_COLUMNS order."""

    df = src.rename(columns=COLUMN_RENAME_MAP).copy()

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df["salinity_evidence"] = df["salinity_min"].notna() | df["salinity_max"].notna()

    def _demo_flag(row):
        flag = str(row.get("data_quality_flag") or "")
        has_demo = "heuristic_opt_numerics" in flag
        missing_seq = not isinstance(row.get("sequence"), str) or len(str(row.get("sequence"))) == 0
        predicted = str(row.get("evidence_type", "")).lower() == "predicted"
        return has_demo or missing_seq or predicted

    df["demo_assumption"] = df.apply(_demo_flag, axis=1)

    def _build_notes(row):
        parts = []
        if isinstance(row.get("notes"), str) and len(row["notes"]) > 0:
            parts.append(row["notes"])
        if isinstance(row.get("source_file"), str) and len(row["source_file"]) > 0:
            parts.append(f"[source_file(s): {row['source_file']}]")
        if isinstance(row.get("data_quality_flag"), str) and len(row["data_quality_flag"]) > 0:
            parts.append(f"[data_quality_flag: {row['data_quality_flag']}]")
        return " || ".join(parts) if parts else ""

    df["notes"] = df.apply(_build_notes, axis=1)

    df = df[REQUIRED_COLUMNS]

    numeric_cols = ["seq_length", "pH_opt", "pH_min", "pH_max",
                    "T_opt", "T_min", "T_max", "salinity_min", "salinity_max"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def validate(df: pd.DataFrame) -> dict:
    """STEP 4: data quality checks matching (and extending) the existing format."""
    issues = {
        "duplicate_enzyme_ids": int(df["enzyme_id"].duplicated().sum()),
        "duplicate_sequences": int(
            df.loc[df["sequence"].notna() & (df["sequence"].astype(str).str.len() > 0), "sequence"]
            .duplicated().sum()
        ),
        "empty_sequences": int(
            (~(df["sequence"].notna() & (df["sequence"].astype(str).str.len() > 0))).sum()
        ),
        "invalid_amino_acids": [],
        "invalid_pH": [],
        "invalid_temperature": [],
        "negative_salinity": [],
        "missing_pollutant": [],
        "invalid_pollutant_categories": [],
    }

    for idx, row in df.iterrows():
        eid = row["enzyme_id"]
        seq = row.get("sequence")
        if isinstance(seq, str) and seq:
            bad = set(seq.upper()) - VALID_AA
            if bad:
                issues["invalid_amino_acids"].append({"enzyme_id": eid, "bad_chars": sorted(bad)})

        for col in ["pH_opt", "pH_min", "pH_max"]:
            v = row.get(col)
            if pd.notna(v) and not (config.PH_MIN_ALLOWED <= v <= config.PH_MAX_ALLOWED):
                issues["invalid_pH"].append({"enzyme_id": eid, "field": col, "value": float(v)})

        for col in ["T_opt", "T_min", "T_max"]:
            v = row.get(col)
            if pd.notna(v) and not (config.TEMP_MIN_ALLOWED <= v <= config.TEMP_MAX_ALLOWED):
                issues["invalid_temperature"].append({"enzyme_id": eid, "field": col, "value": float(v)})

        for col in ["salinity_min", "salinity_max"]:
            v = row.get(col)
            if pd.notna(v) and v < 0:
                issues["negative_salinity"].append({"enzyme_id": eid, "field": col, "value": float(v)})

        pollutant = row.get("pollutant")
        if pd.isna(pollutant) or str(pollutant).strip() == "":
            issues["missing_pollutant"].append({"enzyme_id": eid})
        elif str(pollutant).strip().upper() not in VALID_POLLUTANTS:
            issues["invalid_pollutant_categories"].append({
                "enzyme_id": eid, "pollutant": str(pollutant).strip()
            })

    issues["n_records"] = len(df)
    issues["n_records_with_sequence"] = int(
        (df["sequence"].notna() & (df["sequence"].astype(str).str.len() > 0)).sum()
    )
    issues["n_records_by_pollutant"] = df["pollutant"].value_counts().to_dict()
    return issues


def wire_embeddings(proc_dir: Path, df: pd.DataFrame) -> dict:
    """STEP 5: confirm mapping, split esm_embeddings.npy to per-enzyme files,
    write artifacts/embeddings/_meta.json. Returns a summary dict."""

    idx_path = proc_dir / "esm_embedding_index.csv"
    npy_path = proc_dir / "esm_embeddings.npy"
    model_json_path = proc_dir / "esm_embedding_model.json"

    if not idx_path.exists() or not npy_path.exists() or not model_json_path.exists():
        return {"ok": False, "reason": "esm_embedding files missing in data/processed/"}

    embedding_index = pd.read_csv(idx_path)
    stacked = np.load(npy_path)
    model_meta = json.loads(model_json_path.read_text())

    print(f"\n[STEP 5] ESM-2 embedding wiring:")
    print(f"  esm_embedding_index.csv rows: {len(embedding_index)}")
    print(f"  esm_embeddings.npy shape:     {stacked.shape}")
    print(f"  model used:                    {model_meta.get('model')}")
    print(f"  embedding dim:                 {model_meta.get('dim')}")

    master_ids = set(df["enzyme_id"].unique())
    index_ids = embedding_index["enzyme_id"].tolist()
    index_id_set = set(index_ids)
    in_index_not_master = sorted(index_id_set - master_ids)
    in_master_not_index = sorted((master_ids - index_id_set))
    shape_ok = stacked.shape[0] == len(embedding_index) == model_meta.get("n_embedded", -1)

    print(f"  index enzyme_ids in master table: {len(index_id_set & master_ids)}/{len(index_id_set)}")
    print(f"  master enzyme_ids WITHOUT an embedding:  {len(in_master_not_index)}")
    if in_master_not_index:
        print(f"    -> {in_master_not_index}")
    if in_index_not_master:
        print(f"  !! index enzyme_ids NOT in master table (unexpected): {in_index_not_master}")
    print(f"  shape consistency (npy rows == index rows == model_meta.n_embedded): {shape_ok and 'OK' or 'FAIL'}")

    if not shape_ok:
        print("  !! Shape mismatch — aborting embedding split.")
        return {"ok": False, "reason": "shape mismatch between npy, index, model_meta"}

    config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    for p in config.EMBEDDINGS_DIR.glob("*.npy"):
        p.unlink()
    meta_p = config.EMBEDDINGS_DIR / "_meta.json"
    if meta_p.exists():
        meta_p.unlink()

    written_ids = []
    for i, eid in enumerate(index_ids):
        vec = stacked[i]
        out_path = config.EMBEDDINGS_DIR / f"{eid}.npy"
        np.save(out_path, vec.astype(np.float32))
        written_ids.append(eid)

    embedding_dim = int(stacked.shape[1])
    meta = {
        "model_name": model_meta.get("model"),
        "embedding_dim": embedding_dim,
        "pooling": model_meta.get("pooling"),
        "device_used_for_generation": model_meta.get("device"),
        "n_embeddings": len(written_ids),
        "enzyme_ids": written_ids,
    }
    meta_p.write_text(json.dumps(meta, indent=2))

    print(f"  Wrote {len(written_ids)} per-enzyme .npy files -> {config.EMBEDDINGS_DIR}")
    print(f"  Wrote _meta.json with model={meta['model_name']}, dim={embedding_dim}")
    return {
        "ok": True,
        "n_written": len(written_ids),
        "master_missing_embeddings": in_master_not_index,
        "index_not_in_master": in_index_not_master,
        "meta": meta,
    }


def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    proc = config.PROCESSED_DIR

    print("=" * 78)
    print("ENZAIme — 03_build_master_dataset.py (real-data consolidation)")
    print("=" * 78)

    src = load_authoritative_source(proc)

    df = map_to_canonical_schema(src)
    print("\n[STEP 3] Schema mapping applied:")
    for from_name, to_name in COLUMN_RENAME_MAP.items():
        print(f"  {from_name:<22} -> {to_name}")
    print("  derived: salinity_evidence  = salinity_min.notna() | salinity_max.notna()")
    print("  derived: demo_assumption    = heuristic_opt_numerics OR no sequence OR predicted")
    print("  derived: notes              = original_notes || source_file(s) || data_quality_flag")
    print(f"\n  Final canonical dataset shape: {df.shape}")
    print(f"  REQUIRED_COLUMNS all present: {set(df.columns) >= set(REQUIRED_COLUMNS)}")

    df.to_csv(config.CANONICAL_ENZYME_CSV, index=False)
    print(f"\nWrote canonical dataset ({len(df)} rows) -> {config.CANONICAL_ENZYME_CSV}")

    print("\n[STEP 4] Data quality validation ...")
    report = validate(df)
    (config.REPORTS_DIR / "data_quality_report.json").write_text(
        json.dumps(report, indent=2, default=str)
    )
    flat_rows = []
    for check, val in report.items():
        if isinstance(val, list):
            for item in val:
                flat_rows.append({"check": check, **item})
        elif not isinstance(val, dict):
            flat_rows.append({"check": check, "value": val})
    pd.DataFrame(flat_rows).to_csv(
        config.REPORTS_DIR / "data_quality_report.csv", index=False
    )

    print(f"Data quality report -> {config.REPORTS_DIR / 'data_quality_report.json'}")
    print(f"  Records total:          {report['n_records']}")
    print(f"  Records with sequence:  {report['n_records_with_sequence']}")
    print(f"  By pollutant:           {report['n_records_by_pollutant']}")
    n_flags = sum(len(v) for v in report.values() if isinstance(v, list))
    print(f"  Flags raised:           {n_flags}")
    flag_keys = [k for k, v in report.items() if isinstance(v, list) and len(v) > 0]
    if flag_keys:
        for k in flag_keys:
            print(f"    - {k}: {len(report[k])} items")
    else:
        print("    (no flags — clean)")

    emb_summary = wire_embeddings(proc, df)

    print("\n" + "=" * 78)
    print("03_build_master_dataset.py — COMPLETE")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
