#!/usr/bin/env python3
"""
scripts/05_generate_embeddings.py
====================================
Computes frozen ESM-2 mean-pooled embeddings for every enzyme in
data/processed/enzymes.csv that has a sequence, and caches them to
artifacts/embeddings/<enzyme_id>.npy (Section 9/54 — cached so the API
never recomputes them per-request).

REQUIRES: `pip install torch transformers` and (for the first run) internet
access to Hugging Face Hub to download the ESM-2 checkpoint. This is
expected to be run either locally with GPU/internet, or in the provided
Kaggle notebook (notebooks/EnzAIme_Kaggle_Training.ipynb).

Per Section 37 (fallback architecture), if torch/transformers are not
installed, or no internet/GPU is available, this script exits cleanly with
a clear message instead of crashing the pipeline — the backend's DEMO_MODE
compatibility engine does not depend on embeddings at all.

Independently executable: python scripts/05_generate_embeddings.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from enzaime_core import config  # noqa: E402


def main():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception as e:
        print("=" * 70)
        print("[SKIP] torch/transformers not installed in this environment.")
        print(f"       ({e})")
        print("       Install with:  pip install torch transformers")
        print("       This is NOT a fatal error for the ENZAIme MVP: the backend's")
        print("       DEMO_MODE compatibility engine (rule-based scoring) works fully")
        print("       without ESM-2 embeddings. Run this script later (locally with a")
        print("       GPU, or via notebooks/EnzAIme_Kaggle_Training.ipynb) to enable")
        print("       the optional neural refinement model (scripts/06).")
        print("=" * 70)
        return 0

    import pandas as pd
    from enzaime_core import embeddings as emb

    if not config.CANONICAL_ENZYME_CSV.exists():
        print(f"[ERROR] {config.CANONICAL_ENZYME_CSV} not found. "
              f"Run scripts/03_build_master_dataset.py first.")
        return 1

    df = pd.read_csv(config.CANONICAL_ENZYME_CSV)
    df = df[df["sequence"].notna() & (df["sequence"].astype(str).str.len() > 0)]
    if len(df) == 0:
        print("[SKIP] No enzymes with a known sequence yet — nothing to embed.")
        return 0

    sequences = dict(zip(df["enzyme_id"], df["sequence"]))
    print(f"Embedding {len(sequences)} sequences with model={config.MODEL_NAME} "
          f"(fallback={config.MODEL_NAME_FALLBACK}), device={emb.detect_device()} ...")

    try:
        vectors = emb.embed_sequences(sequences)
    except RuntimeError as e:
        print(f"[SKIP] Could not load any ESM-2 checkpoint: {e}")
        print("       Falling back to DEMO_MODE (rule-based compatibility engine).")
        return 0

    emb.save_embeddings(vectors)
    print(f"Cached {len(vectors)} embeddings -> {config.EMBEDDINGS_DIR}")

    import json
    meta = {
        "model_used": config.MODEL_NAME,
        "n_embedded": len(vectors),
        "embedding_dim": int(next(iter(vectors.values())).shape[0]) if vectors else None,
        "enzyme_ids": list(vectors.keys()),
    }
    (config.EMBEDDINGS_DIR / "_meta.json").write_text(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
