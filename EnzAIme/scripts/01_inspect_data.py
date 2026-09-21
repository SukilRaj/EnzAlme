#!/usr/bin/env python3
"""
scripts/01_inspect_data.py
===========================
Inventories every file under data/raw/, reports basic FASTA/TSV statistics,
and flags known data-quality issues called out in the project brief
(e.g. the tRNA dimethylallyltransferase UniProt file that must NOT be used
as plastic-enzyme data). Writes a machine-readable inventory to
reports/data_inventory.json.

Independently executable:  python scripts/01_inspect_data.py
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from enzaime_core import config  # noqa: E402

EXCLUDED_FILES = {
    "uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz":
        "Contains ~12 tRNA dimethylallyltransferase sequences — NOT plastic-degrading "
        "enzymes. Excluded from the enzyme recommendation dataset per project scope.",
}


def inspect_fasta(path: Path) -> dict:
    from Bio import SeqIO
    opener = gzip.open if path.suffix == ".gz" else open
    mode = "rt"
    n_records, lengths, invalid = 0, [], 0
    valid_aa = set("ACDEFGHIKLMNPQRSTVWYXBZJUO")
    try:
        with opener(path, mode) as fh:
            fmt = "fasta"
            for rec in SeqIO.parse(fh, fmt):
                n_records += 1
                lengths.append(len(rec.seq))
                if not set(str(rec.seq).upper()) <= valid_aa:
                    invalid += 1
    except Exception as e:
        return {"error": str(e)}
    return {
        "type": "fasta",
        "n_records": n_records,
        "min_length": min(lengths) if lengths else None,
        "max_length": max(lengths) if lengths else None,
        "mean_length": round(sum(lengths) / len(lengths), 1) if lengths else None,
        "records_with_invalid_chars": invalid,
    }


def inspect_tsv(path: Path) -> dict:
    import pandas as pd
    try:
        df = pd.read_csv(path, sep="\t", nrows=5000)
        return {"type": "tsv", "n_rows_sampled": len(df), "columns": list(df.columns)}
    except Exception as e:
        return {"error": str(e)}


def main():
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    inventory = {"raw_dir": str(config.RAW_DIR), "files": []}

    if not config.RAW_DIR.exists():
        print(f"[WARN] {config.RAW_DIR} does not exist.")
        return

    for path in sorted(config.RAW_DIR.rglob("*")):
        if path.is_dir():
            continue
        entry = {"path": str(path.relative_to(config.RAW_DIR)), "size_bytes": path.stat().st_size}
        if path.name in EXCLUDED_FILES:
            entry["excluded"] = True
            entry["exclusion_reason"] = EXCLUDED_FILES[path.name]
        elif path.suffix in {".fasta", ".fa"} or path.name.endswith(".fasta.gz"):
            entry.update(inspect_fasta(path))
        elif path.suffix == ".tsv":
            entry.update(inspect_tsv(path))
        else:
            entry["type"] = "other"
        inventory["files"].append(entry)
        print(f"- {entry['path']}: {entry.get('type', 'excluded' if entry.get('excluded') else 'unknown')}"
              f"{' [EXCLUDED: ' + entry.get('exclusion_reason', '') + ']' if entry.get('excluded') else ''}")

    out_path = config.REPORTS_DIR / "data_inventory.json"
    out_path.write_text(json.dumps(inventory, indent=2))
    print(f"\nInventory written to {out_path}")


if __name__ == "__main__":
    main()
