import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.esm_encoder import ESMEncoder
from backend.app.services.recommender import (
    EMBEDDINGS_DIR,
    INDEX_PATH,
    load_candidates,
)


def load_embedding_index():
    if not INDEX_PATH.is_file():
        return {}

    try:
        with INDEX_PATH.open(encoding="utf-8") as index_file:
            index = json.load(index_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read embedding index: {error}") from error

    if not isinstance(index, dict):
        raise RuntimeError("Embedding index must contain a JSON object.")
    return index


def save_embedding_index(index):
    with INDEX_PATH.open("w", encoding="utf-8") as index_file:
        json.dump(index, index_file, indent=2, sort_keys=True)
        index_file.write("\n")


def main():
    candidates = load_candidates()
    embedding_index = load_embedding_index()
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    pending_candidates = []
    for position, candidate in enumerate(candidates, start=1):
        protein_id = candidate["protein_id"]
        embedding_filename = embedding_index.get(
            protein_id,
            f"protein_{protein_id}.npy",
        )
        embedding_path = EMBEDDINGS_DIR / embedding_filename
        embedding_index[protein_id] = embedding_filename

        if embedding_path.is_file():
            print(
                f"[{position}/{len(candidates)}] Skipping {protein_id}; "
                "embedding exists"
            )
        else:
            pending_candidates.append((candidate, embedding_path))

    if not pending_candidates:
        save_embedding_index(embedding_index)
        print(f"All {len(candidates)} protein embeddings already exist.")
        return

    encoder = ESMEncoder()
    errors = 0
    for position, (candidate, embedding_path) in enumerate(
        pending_candidates,
        start=1,
    ):
        protein_id = candidate["protein_id"]
        print(
            f"[{position}/{len(pending_candidates)}] Encoding "
            f"{protein_id} ({candidate['protein_name']})..."
        )
        try:
            embedding = encoder.encode(candidate["sequence"])
            np.save(embedding_path, embedding)
            save_embedding_index(embedding_index)
        except Exception as error:
            errors += 1
            print(f"ERROR encoding protein {protein_id}: {error}")

    if errors:
        raise RuntimeError(f"Precomputation failed for {errors} protein(s).")

    print(f"Precomputed {len(pending_candidates)} protein embeddings.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Precomputation failed: {error}", file=sys.stderr)
        raise SystemExit(1)