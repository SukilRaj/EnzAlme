"""
EnzAIme — ESM-2 650M Frozen Embedder
=====================================
Computes mean-pooled ESM-2 embeddings (BOS/EOS tokens excluded) for every
enzyme sequence in `master_enzymes_valid_sequences.csv` and saves:

  data/processed/esm_embeddings.npy     (N x D float32 matrix, D=1280 for 650M)
  data/processed/esm_embedding_index.csv(full description / provenance)

Key properties
--------------
* MODEL DEFAULT IS `facebook/esm2_t33_650M_UR50D` (D=1280). You are NOT forced
  into the old 35M model — the pipeline defaults to 650M and only falls back
  when the 650M cannot be obtained on the current machine/network.
* Frozen encoder only — never fine-tuned (dataset is far too small).
* BOS/EOS tokens excluded from the mean pool (they are not residue features).
* Embeddings cached by SEQUENCE HASH on disk, so re-runs are free and a change
  to the model name invalidates the old cache (different subdirectory).
* Handles long sequences by truncation (ESM-2 context window = 1022).
* Invalid/empty sequences are skipped and logged, never guessed.
* Supports:
    - Kaggle GPU (cuda) with fp16 autocast
    - CPU fallback
    - a local Hugging Face checkpoint directory
    - a raw `state_dict` checkpoint (no config.json) by pairing it with a
      compatible EsmConfig discovered locally.
* No automatic download unless `--download` is given (default: try cache first,
  then download the requested model on Kaggle where internet exists).

Run:
  python src/esm_embedder.py
  python src/esm_embedder.py --model-name facebook/esm2_t33_650M_UR50D --batch-size 4
  python src/esm_embedder.py --model-name ./artifacts/esm2_650m_checkpoint --download
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
REPO_ROOT = SRC_DIR.parent

DEFAULT_MODEL_NAME = "facebook/esm2_t33_650M_UR50D"
DEFAULT_FALLBACKS = ["facebook/esm2_t6_8M_UR50D", "facebook/esm2_t12_35M_UR50D"]
MAX_LENGTH = 1022
ESM_VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


def detect_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _cached_hf_models() -> list[str]:
    """List ESM-2 model ids already present in the local Hugging Face cache."""
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.exists():
        return []
    out = []
    for d in hub.glob("models--*--*"):
        parts = d.name.split("--")
        if len(parts) >= 3 and "esm2" in d.name:
            out.append("/".join(parts[1:]))
    return sorted(out)


def _find_esm_config_dir() -> Path | None:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.exists():
        return None
    for d in hub.glob("models--*--esm2*"):
        for snap in (d / "snapshots").glob("*"):
            if (snap / "config.json").exists():
                return snap
    return None


def resolve_model(model_name: str = DEFAULT_MODEL_NAME, device: str = "cpu",
                  download: bool = False) -> tuple:
    """
    Return (tokenizer, model, device, resolved_name, status).
    Resolution ladder:
      1. local directory/checkpoint path (HF or raw state_dict)
      2. local HF cache match for `model_name`
      3. requested model from Hugging Face Hub (only with model_name first);
         downloads are attempted when `download=True` (Kaggle)
      4. any cached ESM-2 model as a documented fallback
    """
    from transformers import AutoModel, AutoTokenizer, EsmConfig, EsmModel

    def _try(name: str, **kw) -> tuple:
        tok = AutoTokenizer.from_pretrained(name, **kw)
        model = AutoModel.from_pretrained(name, **kw)
        model.eval().to(device)
        return tok, model

    status = "cache"

    # 1) explicit local path (Hugging Face layout)
    p = Path(model_name)
    if model_name != DEFAULT_MODEL_NAME and (p.is_dir() and (p / "config.json").exists()):
        try:
            return (*_try(str(p)), device, str(p), "local_hf_dir")
        except Exception as e:
            print(f"[warn] local HF dir failed ({e}); trying raw state_dict.")

    if model_name != DEFAULT_MODEL_NAME and p.is_dir() and not (p / "config.json").exists():
        cfg_dir = _find_esm_config_dir()
        if cfg_dir is None:
            raise FileNotFoundError(
                f"{p} is not a complete HF checkpoint and no cached EsmConfig was found "
                "to pair with its state dict.")
        files = list(p.glob("*.safetensors")) + list(p.glob("pytorch_model.bin"))
        if files:
            import torch
            config = EsmConfig.from_pretrained(str(cfg_dir))
            model = EsmModel(config)
            state = torch.load(files[0], map_location="cpu")
            if "state_dict" in state:
                state = state["state_dict"]
            state = {k: v for k, v in state.items() if "lm_head" not in k}
            model.load_state_dict(state, strict=False)
            model.eval().to(device)
            tok = AutoTokenizer.from_pretrained(str(cfg_dir))
            return tok, model, device, str(p), "local_raw_state_dict"

    # 2) local cache match for requested name
    cached = _cached_hf_models()
    for c in cached:
        if c == model_name:
            try:
                return (*_try(model_name, local_files_only=True), device, model_name, "cache")
            except Exception:
                break

    # 3) download path (Kaggle has internet)
    if download:
        try:
            print(f"[info] downloading/loading model '{model_name}' ...")
            return (*_try(model_name), device, model_name, "hub")
        except Exception as e:
            print(f"[warn] '{model_name}' unavailable ({e}).")

    # 4) documented fallback among cached models
    for fb in DEFAULT_FALLBACKS + cached:
        try:
            res = _try(fb, local_files_only=True)
            print(f"[warn] using FALLBACK model '{fb}' (requested {model_name} unavailable).")
            return (*res, device, fb, "fallback_cache")
        except Exception:
            continue
    raise RuntimeError(
        f"Could not load any ESM-2 checkpoint (requested {model_name}). "
        "Install internet on Kaggle, or provide a local checkpoint with --model-name.")


def _embed_batch(model, tokenizer, seqs, device) -> np.ndarray:
    """Mean-pooled embeddings with BOS/EOS excluded. Returns (B, D) float32."""
    import torch
    with torch.no_grad():
        enc = tokenizer(
            list(seqs), return_tensors="pt", padding=True, truncation=True,
            max_length=MAX_LENGTH)
        enc = {k: v.to(device) for k, v in enc.items()}
        dtype = torch.float16 if device == "cuda" else torch.float32
        with torch.autocast(device_type=device, dtype=dtype, enabled=(device == "cuda")):
            hidden = model(**enc).last_hidden_state  # (B, L, D)
        hidden = hidden.to(torch.float32)
        mask = enc["attention_mask"].float()  # (B, L)
        pooled = np.zeros((hidden.shape[0], hidden.shape[-1]), dtype=np.float32)
        for i in range(hidden.shape[0]):
            idx = mask[i].nonzero(as_tuple=True)[0]
            if idx.numel() <= 2:  # degenerate — pool over everything masked
                sel = idx
            else:
                sel = idx[1:-1]  # exclude BOS and EOS
            pooled[i] = hidden[i, sel].mean(dim=0).cpu().numpy()
    return pooled


def embed_sequences(sequences: pd.DataFrame, model_name: str = DEFAULT_MODEL_NAME,
                    batch_size: int = 4, device: str | None = None,
                    download: bool = False,
                    progress: bool = True) -> dict:
    """sequences: DataFrame with columns enzyme_id, protein_sequence.
    Returns {enzyme_id: np.ndarray} for successfully embedded rows and also
    writes per-hash cache files under artifacts/esm_cache/<hash>.npy."""
    from transformers import AutoTokenizer, AutoModel  # noqa: F401  (import check)
    import torch  # noqa: F401

    device = device or detect_device()
    tokenizer, model, device, resolved, status = resolve_model(
        model_name, device=device, download=download)

    out: dict[str, np.ndarray] = {}
    skipped = []
    cache_dir = REPO_ROOT / "artifacts" / "esm_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # iterate ALL rows so that enzymes sharing an identical sequence each get the
    # same cached embedding and appear in the index (dedup only the forward pass)
    seq_map = {}  # hash -> set(enzyme ids)
    seq_by_hash = {}  # hash -> sequence
    idx_rows = []
    for _, r in sequences.iterrows():
        seq = str(r["protein_sequence"]).strip()
        if not seq:
            skipped.append((r.get("enzyme_id"), "empty_sequence"))
            continue
        if not set(seq) <= ESM_VALID_AA:
            skipped.append((r.get("enzyme_id"), "invalid_amino_acids"))
            continue
        h = hashlib.sha256(seq.encode()).hexdigest()
        seq_map.setdefault(h, set()).add(str(r["enzyme_id"]))
        seq_by_hash[h] = seq

    # compute unique hashes (avoid recomputing identical sequences)
    unique = list(seq_map.keys())
    it = tqdm(range(0, len(unique), batch_size), desc="ESM embed", disable=not progress)

    for start in it:
        batch_h = unique[start:start + batch_size]
        batch_seqs = [seq_by_hash[h] for h in batch_h]
        vectors = _embed_batch(model, tokenizer, batch_seqs, device)
        for h, vec in zip(batch_h, vectors):
            np.save(cache_dir / f"{h}.npy", vec)
            for eid in sorted(seq_map[h]):
                out[eid] = vec
                idx_rows.append({
                    "enzyme_id": eid, "sequence_hash": h, "embedding_file": f"{h}.npy",
                    "embedding_dim": int(vec.shape[0]), "model": resolved,
                    "model_source": status, "pooling": "mean_no_bos_eos",
                })

    print(f"[info] embedded {len(out)} enzymes | model={resolved} ({status}) | device={device}")
    if skipped:
        print(f"[warn] skipped {len(skipped)} invalid/empty: {skipped[:10]}")
    hash_by_id = {}
    idx_rows_clean = []
    for row in idx_rows:
        hash_by_id[row["enzyme_id"]] = row["sequence_hash"]
        idx_rows_clean.append(row)
    return {"embeddings": out, "index_rows": idx_rows_clean,
            "sequence_hash_by_id": hash_by_id, "model": resolved,
            "model_source": status, "device": device, "n_skipped": len(skipped)}  # type: ignore


def run_embedding(input_csv: Path, output_dir: Path, model_name: str,
                  batch_size: int, force: bool, download: bool) -> dict:
    if not input_csv.exists():
        raise FileNotFoundError(f"{input_csv} missing — run src/data_quality.py first.")
    df = pd.read_csv(input_csv, keep_default_na=False)

    old_mat = output_dir / "esm_embeddings.npy"
    old_index = output_dir / "esm_embedding_index.csv"
    old_meta = output_dir / "esm_embedding_model.json"
    if old_mat.exists() and old_index.exists() and not force:
        print(f"[info] esm_embeddings.npy already exists — use --force to recompute.")
        return {"skipped_existing": True}

    res = embed_sequences(df, model_name=model_name, batch_size=batch_size,
                          download=download)
    embs = res["embeddings"]

    n = len(embs)
    if n:
        items = sorted(embs.items(), key=lambda kv: kv[0])  # deterministic enzyme order
        first = items[0][1]
        mat = np.zeros((n, first.shape[0]), dtype=np.float32)
        ids = []
        idx_rows = []
        for row_i, (eid, vec) in enumerate(items):
            mat[row_i] = vec
            ids.append(eid)
            idx_rows.append({
                "enzyme_id": eid,
                "sequence_hash": res["sequence_hash_by_id"].get(eid, ""),
                "embedding_file": "", "embedding_dim": int(vec.shape[0]),
                "model": res["model"], "model_source": res.get("model_source", ""),
                "pooling": "mean_no_bos_eos",
            })
        index_csv = pd.DataFrame(idx_rows)
    else:
        mat = np.zeros((0, 0), dtype=np.float32)
        ids = []
        index_csv = pd.DataFrame(columns=["enzyme_id", "sequence_hash", "embedding_file",
                                          "embedding_dim", "model", "model_source", "pooling"])

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "esm_embeddings.npy", mat)
    (output_dir / "esm_embedding_index.csv").write_text(index_csv.to_csv(index=False))
    (output_dir / "esm_embedding_model.json").write_text(json.dumps({
        "model": res["model"], "device": res["device"], "n_embedded": int(n),
        "dim": int(first.shape[0]) if n else None, "pooling": "mean_no_bos_eos",
        "enzyme_ids": ids, "n_skipped": int(res["n_skipped"]),
    }, indent=2))
    print(f"[ok] esm_embeddings.npy ({mat.shape}) + esm_embedding_index.csv -> {output_dir}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme ESM-2 embedder")
    ap.add_argument("--input", default=str(REPO_ROOT / "data" / "processed" /
                                           "master_enzymes_valid_sequences.csv"))
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "data" / "processed"))
    ap.add_argument("--model-name", default=DEFAULT_MODEL_NAME,
                    help="HF id, OR a local checkpoint directory (HF or raw state_dict)")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--download", action="store_true",
                    help="Allow downloading the model from Hugging Face Hub (Kaggle).")
    args = ap.parse_args(argv)
    try:
        run_embedding(Path(args.input), Path(args.output_dir), args.model_name,
                      args.batch_size, args.force, args.download)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())