"""
ENZAIme — ESM-2 Embedding Pipeline (Section 9)
=================================================
Frozen ESM-2 protein sequence encoder -> mean-pooled fixed-size embedding.

Design notes
------------
* ESM-2 is used strictly as a FROZEN encoder (Section 8) — no fine-tuning.
  The verified enzyme dataset is far too small (<100 records) to fine-tune
  a 650M parameter transformer without catastrophic overfitting.
* MODEL_NAME is configurable (common/enzaime_core/config.py). If the
  primary model (esm2_t33_650M_UR50D) cannot be loaded (OOM, no network,
  no GPU/time budget), `resolve_and_load_model` automatically falls back
  to a smaller ESM-2 checkpoint so the pipeline never hard-fails.
* Embeddings are cached to disk (artifacts/embeddings/*.npy) so the
  recommendation API never recomputes them per-request (Section 54).
* This module intentionally has NO import-time dependency on torch/
  transformers being installed with network access — it only imports
  them inside functions, so the rest of the application (backend in
  DEMO_MODE, tests, etc.) can run in environments without a GPU or without
  internet access to Hugging Face.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import numpy as np

from . import config

logger = logging.getLogger("enzaime.embeddings")


def detect_device() -> str:
    """CUDA if available, otherwise CPU (Section 9/34)."""
    if config.DEVICE in {"cuda", "cpu"}:
        return config.DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def resolve_and_load_model(model_name: str = None, device: str = None):
    """
    Try to load the requested ESM-2 checkpoint; fall back to a smaller
    model on any failure (OOM, no internet, unsupported hardware).
    Returns (tokenizer, model, device, resolved_model_name).
    Raises RuntimeError only if BOTH the primary and fallback model fail
    to load (caller should catch this and use the rule-based fallback
    path instead — see Section 14/37).
    """
    import torch
    from transformers import AutoTokenizer, AutoModel

    device = device or detect_device()
    model_name = model_name or config.MODEL_NAME
    tried = [model_name]
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval().to(device)
        logger.info("Loaded ESM-2 model '%s' on device '%s'", model_name, device)
        return tokenizer, model, device, model_name
    except Exception as e:
        logger.warning("Primary model '%s' failed to load (%s); trying fallback '%s'",
                        model_name, e, config.MODEL_NAME_FALLBACK)
        tried.append(config.MODEL_NAME_FALLBACK)
        try:
            tokenizer = AutoTokenizer.from_pretrained(config.MODEL_NAME_FALLBACK)
            model = AutoModel.from_pretrained(config.MODEL_NAME_FALLBACK)
            model.eval().to(device)
            logger.info("Loaded fallback ESM-2 model '%s' on device '%s'",
                        config.MODEL_NAME_FALLBACK, device)
            return tokenizer, model, device, config.MODEL_NAME_FALLBACK
        except Exception as e2:
            raise RuntimeError(
                f"Could not load any ESM-2 checkpoint (tried {tried}). "
                f"Last error: {e2}. The application will fall back to the "
                "rule-based compatibility engine (DEMO_MODE)."
            ) from e2


def embed_sequences(
    sequences: Dict[str, str],
    model_name: str = None,
    batch_size: int = None,
) -> Dict[str, np.ndarray]:
    """
    Compute mean-pooled ESM-2 embeddings for a dict of {enzyme_id: sequence}.
    Uses torch.no_grad() and frees GPU memory between batches (Section 34).
    Returns {enzyme_id: 1D numpy array}.
    """
    import torch

    batch_size = batch_size or config.EMBEDDING_BATCH_SIZE
    tokenizer, model, device, resolved_name = resolve_and_load_model(model_name)

    ids = list(sequences.keys())
    seqs = [sequences[i][: config.EMBEDDING_MAX_LENGTH] for i in ids]

    results: Dict[str, np.ndarray] = {}
    with torch.no_grad():
        for start in range(0, len(seqs), batch_size):
            batch_ids = ids[start:start + batch_size]
            batch_seqs = seqs[start:start + batch_size]
            enc = tokenizer(batch_seqs, return_tensors="pt", padding=True, truncation=True,
                             max_length=config.EMBEDDING_MAX_LENGTH).to(device)
            out = model(**enc)
            hidden = out.last_hidden_state  # (B, L, H)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-9)
            mean_pooled = (summed / counts).cpu().numpy()
            for eid, vec in zip(batch_ids, mean_pooled):
                results[eid] = vec.astype(np.float32)
            if device == "cuda":
                torch.cuda.empty_cache()
    logger.info("Computed embeddings for %d sequences using '%s'", len(results), resolved_name)
    return results


# --------------------------------------------------------------------------
# Cache helpers
# --------------------------------------------------------------------------
def cache_path(enzyme_id: str) -> Path:
    config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in enzyme_id)
    return config.EMBEDDINGS_DIR / f"{safe_id}.npy"


def save_embeddings(embeddings: Dict[str, np.ndarray]) -> None:
    for eid, vec in embeddings.items():
        np.save(cache_path(eid), vec)


def load_cached_embedding(enzyme_id: str) -> np.ndarray | None:
    p = cache_path(enzyme_id)
    if p.exists():
        return np.load(p)
    return None


def load_all_cached_embeddings() -> Dict[str, np.ndarray]:
    if not config.EMBEDDINGS_DIR.exists():
        return {}
    out = {}
    for f in config.EMBEDDINGS_DIR.glob("*.npy"):
        out[f.stem] = np.load(f)
    return out
