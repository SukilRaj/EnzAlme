#!/usr/bin/env python3
"""
scripts/02_clean_sequences.py
================================
Cleans raw FASTA sequences found under data/raw/ (currently: the PAZy-derived
protein set):
  - strips whitespace/non-standard characters
  - removes duplicate sequences (exact match) and duplicate IDs
  - validates amino-acid alphabet
  - writes a cleaned FASTA + a per-record QC table to data/interim/

Independently executable: python scripts/02_clean_sequences.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from enzaime_core import config  # noqa: E402

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


def clean_sequence(seq: str) -> str:
    return "".join(ch for ch in seq.upper().strip() if ch.isalpha())


def main():
    from Bio import SeqIO

    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    src = config.RAW_DIR / "pazy" / "pazy_proteins.fasta"
    if not src.exists():
        print(f"[WARN] {src} not found — nothing to clean. "
              f"(This is OK for the MVP; data/demo/enzymes_demo.csv is used as a fallback "
              f"by scripts/03_build_master_dataset.py.)")
        return

    seen_seqs = set()
    seen_ids = set()
    records = []
    qc_rows = []

    for rec in SeqIO.parse(src, "fasta"):
        raw_seq = str(rec.seq)
        seq = clean_sequence(raw_seq)
        issues = []
        if rec.id in seen_ids:
            issues.append("duplicate_id")
        if seq in seen_seqs:
            issues.append("duplicate_sequence")
        if len(seq) == 0:
            issues.append("empty_sequence")
        invalid_chars = set(seq) - VALID_AA
        if invalid_chars:
            issues.append(f"invalid_chars:{''.join(sorted(invalid_chars))}")

        qc_rows.append({
            "id": rec.id, "length": len(seq), "issues": ";".join(issues) or "ok"
        })

        if not issues:
            seen_ids.add(rec.id)
            seen_seqs.add(seq)
            rec.seq = rec.seq.__class__(seq)
            records.append(rec)

    out_fasta = config.INTERIM_DIR / "pazy_proteins_clean.fasta"
    SeqIO.write(records, out_fasta, "fasta")

    import pandas as pd
    qc_df = pd.DataFrame(qc_rows)
    qc_path = config.INTERIM_DIR / "sequence_qc.csv"
    qc_df.to_csv(qc_path, index=False)

    print(f"Cleaned {len(records)}/{len(qc_rows)} sequences -> {out_fasta}")
    print(f"QC report -> {qc_path}")


if __name__ == "__main__":
    main()
