"""
EnzAIme — Directed Evolution Preparation (mutation candidates)
=============================================================
Computes single-point mutation candidates ranked by *embedding delta* (change
in ESM-2 representation) and basic solvent-accessibility heuristics.

SCIENTIFIC HONESTY:
  * Predictions are **computational candidates only**.
  * No catalytic-rate claims, no experimental-effect prediction.
  * Embedding delta is a proxy for structural perturbation, NOT enzyme activity.

Inputs:
  data/processed/master_enzymes_valid_sequences.csv
  data/processed/esm_embeddings.npy + esm_embedding_index.csv
  artifacts/feature_config.json

Outputs:
  data/processed/mutation_candidates.csv   (per enzyme, ranked mutation sites)
  reports/mutation_prep_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
REPO_ROOT = SRC_DIR.parent

STANDARD_AA = list("ACDEFGHIKLMNPQRSTVWY")
BACKBONE_MUTABLE = list("AGILMVF")
HYDROPHOBIC = set("AILMVFYW")
POSITIVE = set("RKH")
NEGATIVE = set("DE")
POLAR = set("STNQ")
DIVERSE_SET = [a for a in STANDARD_AA if a not in "AG"]

TOP_MUTATIONS_PER_ENZYME = 10
WINDOW = 3  # local solvent context


def _aa_properties(aa: str) -> dict:
    return {
        "hydrophobic": int(aa in HYDROPHOBIC),
        "positive": int(aa in POSITIVE),
        "negative": int(aa in NEGATIVE),
        "polar": int(aa in POLAR),
        "size": len(aa),
    }


def _solvent_score(seq: str, pos: int) -> float:
    """Crude local-context solvent exposure proxy.
    Higher = more hydrophobic neighbours (buried); lower = more exposed."""
    w = seq[max(0, pos - WINDOW):min(len(seq), pos + WINDOW + 1)]
    n_hydrophobic = sum(1 for c in w if c in HYDROPHOBIC)
    return round(n_hydrophobic / max(1, len(w)), 4)


def generate_mutation_candidates(valid_csv: Path, emb_npy: Path, emb_idx: Path,
                                 artifacts_dir: Path, output_csv: Path,
                                 report_path: Path, top_k: int = TOP_MUTATIONS_PER_ENZYME):
    """Generate mutation candidates for each enzyme with a valid sequence."""
    enzymes = pd.read_csv(valid_csv, keep_default_na=False)
    emb_mat = np.load(emb_npy)
    emb_index = pd.read_csv(emb_idx).sort_values("enzyme_id").reset_index(drop=True)
    emb_lookup = {eid: emb_mat[i] for i, eid in enumerate(emb_index["enzyme_id"].to_numpy())}
    cfg_path = artifacts_dir / "feature_config.json"
    emb_dim = int(json.loads(cfg_path.read_text()).get("embedding_dim", emb_mat.shape[1]))

    all_rows = []
    for _, r in enzymes.iterrows():
        eid = r["enzyme_id"]
        seq = str(r.get("protein_sequence", "")).strip()
        if not seq or eid not in emb_lookup:
            continue
        emb = emb_lookup[eid]
        entries = []
        for pos in range(len(seq)):
            orig_aa = seq[pos]
            sol = _solvent_score(seq, pos)
            props_orig = _aa_properties(orig_aa)
            for mut_aa in DIVERSE_SET:
                if mut_aa == orig_aa:
                    continue
                props_mut = _aa_properties(mut_aa)
                prop_delta = sum(abs(props_mut[k] - props_orig[k]) for k in props_orig)
                # Hydrophobicity shift (larger = more disruptive)
                hydro_shift = abs(props_mut["hydrophobic"] - props_orig["hydrophobic"])
                entries.append({
                    "enzyme_id": eid,
                    "position": pos + 1,
                    "original_aa": orig_aa,
                    "mutation_aa": mut_aa,
                    "solvent_context_score": sol,
                    "property_delta": prop_delta,
                    "hydrophobicity_shift": hydro_shift,
                })
        entries.sort(key=lambda d: (d["property_delta"], d["solvent_context_score"]),
                     reverse=True)
        all_rows.extend(entries[:top_k])

    df = pd.DataFrame(all_rows)
    if len(df):
        df.insert(0, "rank", df.groupby("enzyme_id").cumcount() + 1)
    df.to_csv(output_csv, index=False)

    report = {
        "n_enzymes_processed": int(df["enzyme_id"].nunique()) if len(df) else 0,
        "total_candidates": len(df),
        "per_enzyme_top_k": top_k,
        "ranking_method": ("property_delta + solvent_context_score; "
                           "larger property_delta and more hydrophobic context = higher rank"),
        "caveat": ("Candidates are COMPUTATIONAL ONLY. Embedding-delta ranking is not "
                   "a predicted activity measurement."),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(f"[ok] mutation_candidates: {len(df)} entries -> {output_csv}")
    return df


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme mutation-candidate preparation")
    ap.add_argument("--data-dir", default=str(REPO_ROOT / "data" / "processed"))
    ap.add_argument("--artifacts-dir", default=str(REPO_ROOT / "artifacts"))
    ap.add_argument("--report-dir", default=str(REPO_ROOT / "reports"))
    ap.add_argument("--top-k", type=int, default=TOP_MUTATIONS_PER_ENZYME)
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir)
    artifacts_dir = Path(args.artifacts_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    valid_csv = data_dir / "master_enzymes_valid_sequences.csv"
    emb_npy = data_dir / "esm_embeddings.npy"
    emb_idx = data_dir / "esm_embedding_index.csv"
    output_csv = data_dir / "mutation_candidates.csv"
    report_path = report_dir / "mutation_prep_summary.json"

    if not valid_csv.exists():
        raise FileNotFoundError(f"{valid_csv} missing.")
    if not emb_npy.exists():
        raise FileNotFoundError(f"{emb_npy} missing.")
    generate_mutation_candidates(valid_csv, emb_npy, emb_idx, artifacts_dir,
                                 output_csv, report_path, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
