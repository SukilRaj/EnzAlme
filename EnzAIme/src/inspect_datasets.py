#!/usr/bin/env python3
"""
src/inspect_datasets.py
=========================
Inspect and summarise every file in the project data directories before
master-dataset creation.  Writes a machine-readable JSON report and a
human-readable console summary.

Usage
-----
    python src/inspect_datasets.py --input_dir data datasets
    python src/inspect_datasets.py --input_dir data                # only data/
    python src/inspect_datasets.py --input_dir data --output_dir reports
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")

UNIPROT_ACC_RE = re.compile(
    r"[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}"
)
EC_RE = re.compile(r"\b[0-9]+(?:\.[0-9]+){3}\b")
ENZYME_NAME_RE = re.compile(
    r"(?:"
    r"(?:poly\w+|lipase|cutinase|esterase|PETase|hydrolase|peroxidase|oxygenase"
    r"|dehydrogenase|synthase|kinase|reductase|Nyl[A-Z0-9]*|CCPUR|LCC|CalB|CRL"
    r"|PPL|Thc_Cut|PHL|PET\d|MHETase)"
    r")",
    re.IGNORECASE,
)
POLLUTANT_KW = re.compile(
    r"(?:PET(?:ase)?|PUR|PU\b|PA\b|nylon|polyamide|polyurethane|polyester"
    r"|pvc\b|pe\b|pp\b|pla\b|pcl\b|polystyrene)",
    re.IGNORECASE,
)
PH_KW = re.compile(r"\bpH\b|pH_opt|pH_min|pH_max", re.IGNORECASE)
TEMP_KW = re.compile(r"\btemp|T_opt|T_min|T_max|celsius|degree", re.IGNORECASE)
SAL_KW = re.compile(r"\bsalin|salt|NaCl|M\s*sal", re.IGNORECASE)
EVIDENCE_KW = re.compile(
    r"\bverified|experimental|measured|prediction|inferred|curated|BRENDA"
    r"|PMID|DOI|doi", re.IGNORECASE,
)
SOURCE_DB_KW = re.compile(
    r"uniprot|br|PDB|RCSB|GenBank|PAZy|FireProt|BRENDA|Pfam|InterPro",
    re.IGNORECASE,
)
FILE_TYPE_HINTS = {
    ".csv": "csv", ".tsv": "tsv", ".tab": "tsv",
    ".fasta": "fasta", ".fa": "fasta", ".fna": "fasta",
    ".faa": "fasta", ".fasta.gz": "fasta_gz", ".fa.gz": "fasta_gz",
    ".json": "json", ".jsonl": "jsonl",
    ".xlsx": "excel", ".xls": "excel",
    ".gz": "compressed",
    ".zip": "archive",
    ".md": "text", ".txt": "text", ".rst": "text",
}
IGNORED_SUFFIXES = {".gitkeep", ".pyc", ".py", ".env", ".egg-info"}

EXCLUDED_FILES: dict[str, str] = {
    "uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz":
        "Contains ~12 tRNA dimethylallyltransferase sequences -- NOT "
        "plastic-degrading enzymes. Excluded from the enzyme dataset per "
        "project scope (documented in data/demo/SOURCES.md).",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def clean_sequence(raw: str) -> str:
    """Uppercase, strip whitespace/digits/punctuation, keep letters only."""
    return "".join(ch for ch in raw.upper() if ch.isalpha())


def _looks_like_dna(seq: str) -> bool:
    if len(seq) < 50:
        return False
    counts = sum(1 for c in seq if c in "ACGT")
    return counts / max(len(seq), 1) >= 0.95


def detect_file_type(path: Path) -> str:
    name = path.name.lower()
    for suffix, ftype in sorted(FILE_TYPE_HINTS.items(), key=lambda kv: -len(kv[0])):
        if name.endswith(suffix):
            return ftype
    if path.suffix in IGNORED_SUFFIXES:
        return "ignored"
    return "other"


def sample_text(path: Path, n_lines: int = 50) -> list[str]:
    opener = gzip.open if str(path).endswith(".gz") else open
    lines: list[str] = []
    try:
        with opener(path, "rt", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= n_lines:
                    break
                lines.append(line)
    except Exception:
        pass
    return lines


def _text_has_features(text: str) -> dict[str, bool]:
    return {
        "has_enzyme_name": bool(ENZYME_NAME_RE.search(text)),
        "has_uniprot_accession": bool(UNIPROT_ACC_RE.search(text)),
        "has_ec_number": bool(EC_RE.search(text)),
        "has_pollutant": bool(POLLUTANT_KW.search(text)),
        "has_ph_data": bool(PH_KW.search(text)),
        "has_temperature_data": bool(TEMP_KW.search(text)),
        "has_salinity_data": bool(SAL_KW.search(text)),
        "has_evidence": bool(EVIDENCE_KW.search(text)),
        "has_source_database": bool(SOURCE_DB_KW.search(text)),
    }


# ---------------------------------------------------------------------------
# per-file inspectors
# ---------------------------------------------------------------------------

def _inspect_fasta(path: Path) -> dict[str, Any]:
    opener = gzip.open if str(path).endswith(".gz") else open
    from Bio import SeqIO
    n_records = 0
    lengths: list[int] = []
    n_invalid = 0
    sample_header_text = ""
    seq_hashes: list[str] = []
    try:
        with opener(path, "rt") as fh:
            for rec in SeqIO.parse(fh, "fasta"):
                n_records += 1
                raw_seq = str(rec.seq)
                seq = clean_sequence(raw_seq)
                lengths.append(len(seq))
                bad = set(seq) - VALID_AA
                if bad:
                    n_invalid += 1
                seq_hashes.append(hashlib.md5(seq.encode()).hexdigest())
                if n_records <= 5:
                    sample_header_text += f"  {rec.description[:100]}\n"
    except Exception as exc:
        return {"error": str(exc)}
    unique_seqs = len(set(seq_hashes))
    return {
        "type": "fasta",
        "n_records": n_records,
        "min_length": min(lengths) if lengths else None,
        "max_length": max(lengths) if lengths else None,
        "mean_length": round(sum(lengths) / max(len(lengths), 1), 1),
        "records_with_invalid_chars": n_invalid,
        "unique_sequences": unique_seqs,
        "sample_headers": sample_header_text.strip(),
    }


def _inspect_tsv(path: Path, sample_rows: int = 200) -> dict[str, Any]:
    try:
        df = pd.read_csv(path, sep="\t", nrows=sample_rows, dtype=str)
        col_text = " ".join(df.columns)
        features = _text_has_features(col_text)
        n_total = sum(1 for _ in open(path, "r", errors="replace")) - 1
        return {
            "type": "tsv",
            "n_rows_total_approx": n_total,
            "n_rows_sampled": len(df),
            "columns": list(df.columns),
            "missing_pct": {
                col: round(100 * df[col].isna().mean(), 1) for col in df.columns
            },
            **features,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _inspect_csv(path: Path, sample_rows: int = 200) -> dict[str, Any]:
    try:
        df = pd.read_csv(path, nrows=sample_rows, dtype=str, on_bad_lines="skip")
        n_total = sum(1 for _ in open(path, "r", errors="replace")) - 1
        col_text = " ".join(df.columns)
        features = _text_has_features(col_text + " " + " ".join(
            str(v) for v in df.head(50).values.ravel()[:200]
        ))
        # duplicate rows in sample
        dup_pct = round(100 * df.duplicated().mean(), 1)
        missing = {
            col: round(100 * df[col].isna().mean(), 1) for col in df.columns
        }
        return {
            "type": "csv",
            "n_rows_total_approx": n_total,
            "n_rows_sampled": len(df),
            "columns": list(df.columns),
            "duplicate_pct_in_sample": dup_pct,
            "missing_pct": missing,
            **features,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _inspect_json(path: Path, sample_lines: int = 200) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, list):
            n_items = len(data)
            sample_text_val = json.dumps(data[:3], default=str)[:500]
        elif isinstance(data, dict):
            n_items = len(data)
            sample_text_val = json.dumps(data, default=str)[:500]
        else:
            n_items = 1
            sample_text_val = str(data)[:500]
        features = _text_has_features(sample_text_val)
        return {"type": "json", "n_items": n_items, "sample": sample_text_val[:300], **features}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def inspect_directory(input_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not input_dir.exists():
        print(f"[WARN] {input_dir} does not exist -- skipping.")
        return results
    for path in sorted(input_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = str(path.relative_to(input_dir))
        entry: dict[str, Any] = {
            "path": rel,
            "size_bytes": path.stat().st_size,
        }
        name_lower = path.name.lower()
        # check exclusion list
        if path.name in EXCLUDED_FILES:
            entry["status"] = "excluded"
            entry["exclusion_reason"] = EXCLUDED_FILES[path.name]
        elif path.suffix in IGNORED_SUFFIXES or name_lower in {".gitignore", "readme.md"}:
            entry["status"] = "skipped"
            entry["skip_reason"] = "Documentation or non-data file."
        else:
            ftype = detect_file_type(path)
            entry["file_type"] = ftype
            if ftype in {"fasta", "fasta_gz"}:
                entry.update(_inspect_fasta(path))
            elif ftype == "tsv":
                entry.update(_inspect_tsv(path))
            elif ftype == "csv":
                entry.update(_inspect_csv(path))
            elif ftype == "json":
                entry.update(_inspect_json(path))
            elif ftype in {"excel"}:
                try:
                    df = pd.read_excel(path, nrows=5, dtype=str)
                    entry["type"] = "excel"
                    entry["n_cols"] = len(df.columns)
                    entry["columns"] = list(df.columns)
                except Exception as exc:
                    entry["type"] = "excel"
                    entry["error"] = str(exc)
            elif ftype == "archive":
                entry["type"] = "archive"
                entry["note"] = "Archive file -- contents not inspected individually."
            elif ftype == "ignored":
                entry["status"] = "skipped"
                entry["skip_reason"] = f"Ignored suffix: {path.suffix}"
            else:
                entry["type"] = "other"
                lines = sample_text(path)
                entry["sample_lines"] = len(lines)
                features = _text_has_features("".join(lines))
                entry.update(features)
            if "status" not in entry:
                entry["status"] = "inspected"
        results.append(entry)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Inspect project data directories and write a summary report."
    )
    ap.add_argument(
        "--input_dir", nargs="*", default=None,
        help="One or more directories to scan.  Defaults to <repo>/data and "
             "<repo>/datasets (if it exists).",
    )
    ap.add_argument(
        "--output_dir", type=str, default=None,
        help="Directory for the JSON report.  Default: reports/",
    )
    args = ap.parse_args()

    if args.input_dir:
        input_dirs = [Path(d).resolve() for d in args.input_dir]
    else:
        input_dirs = [REPO_ROOT / "data"]
        if (REPO_ROOT / "datasets").is_dir():
            input_dirs.append(REPO_ROOT / "datasets")

    out_dir = Path(args.output_dir).resolve() if args.output_dir else REPO_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict[str, Any]] = []
    file_counts: dict[str, int] = {"used": 0, "excluded": 0, "skipped": 0, "inspected": 0}

    for inp_dir in input_dirs:
        print(f"\n=== Inspecting: {inp_dir} ===")
        entries = inspect_directory(inp_dir)
        for e in entries:
            e["source_root"] = str(inp_dir)
        all_results.extend(entries)

        for e in entries:
            status = e.get("status", "unknown")
            file_counts[status] = file_counts.get(status, 0) + 1
            ftype = e.get("file_type", e.get("type", "?"))
            tag = f" [{status}]" if status != "inspected" else ""
            n = e.get("n_records", e.get("n_rows_total_approx", e.get("n_items", "?")))
            print(f"  {e['path']:60s}  {ftype:10s}  records={n}{tag}")

    # summary
    print("\n=== File Status Summary ===")
    for status, count in sorted(file_counts.items()):
        print(f"  {status:12s}: {count}")

    report = {"files": all_results, "summary": file_counts}
    out_path = out_dir / "dataset_inspection.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nInspection report written to {out_path}")


if __name__ == "__main__":
    main()
