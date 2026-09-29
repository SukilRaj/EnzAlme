import csv
import json
import logging
from pathlib import Path

import numpy as np

from backend.app.services.predictor import Predictor
from backend.app.config import LEGACY_MODEL_NAME, LEGACY_MODEL_LINEAGE


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"
INDEX_PATH = EMBEDDINGS_DIR / "index.json"

EMBEDDINGS_MISSING_MESSAGE = (
    "Precomputed embeddings not found. "
    "Run scripts/precompute_embeddings.py first."
)


class Recommender:
    def __init__(self, predictor: Predictor):
        self.predictor = predictor
        self.embedding_cache = {}
        self.candidates = load_candidates()
        self._load_embeddings()

    def _load_embeddings(self):
        if not INDEX_PATH.is_file():
            raise FileNotFoundError(EMBEDDINGS_MISSING_MESSAGE)

        try:
            with INDEX_PATH.open(encoding="utf-8") as index_file:
                embedding_index = json.load(index_file)

        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Could not read precomputed embedding index: {error}"
            ) from error

        for candidate in self.candidates:
            protein_id = candidate["protein_id"]

            embedding_filename = embedding_index.get(protein_id)

            if not embedding_filename:
                raise FileNotFoundError(
                    EMBEDDINGS_MISSING_MESSAGE
                )

            embedding_path = EMBEDDINGS_DIR / embedding_filename

            if not embedding_path.is_file():
                raise FileNotFoundError(
                    EMBEDDINGS_MISSING_MESSAGE
                )

            try:
                self.embedding_cache[protein_id] = np.load(
                    embedding_path,
                    allow_pickle=False,
                )

            except (OSError, ValueError) as error:
                raise RuntimeError(
                    f"Could not load embedding for protein "
                    f"{protein_id}: {error}"
                ) from error

        logger.info(
            "Loaded %d precomputed protein embeddings",
            len(self.embedding_cache),
        )

    def recommend(
        self,
        ph: float,
        temperature: float,
        duration_hours: float,
        top_n: int,
    ):
        ranked_candidates = []

        for candidate in self.candidates:

            protein_id = candidate["protein_id"]

            logger.info(
                "Predicting TPA activity for candidate %s "
                "at pH=%s, temperature=%s, duration=%s",
                protein_id,
                ph,
                temperature,
                duration_hours,
            )

            predicted_activity = self.predictor.predict(
                embedding=self.embedding_cache[protein_id],
                temperature=temperature,
                ph=ph,
                duration_hours=duration_hours,
            )

            ranked_candidates.append(
                {
                    "protein_id": protein_id,
                    "protein_name": candidate["protein_name"],
                    "predicted_activity_um": predicted_activity,

                    # Evidence information
                    "evidence": {
                        "sequence_available": candidate[
                            "sequence_available"
                        ],
                        "esm2_embedding_available": (
                            protein_id in self.embedding_cache
                        ),
                        "experimental_activity_records": candidate[
                            "activity_record_count"
                        ],
                        "experimental_activity_available": (
                            candidate["activity_record_count"] > 0
                        ),
                        "source": (
                            "PAZy / confirmed TPA/PET evidence "
                            "(data/processed/tpa_pet_ml_confirmed.csv)"
                        ),
                    },

                    # Scientific interpretation
                    "prediction_status": (
                        f"Computational prediction from {LEGACY_MODEL_NAME}"
                    ),

                    "validation_note": (
                        f"{LEGACY_MODEL_LINEAGE} "
                        "Confirmed records provide evidence counts only. "
                        "Scores require experimental validation."
                    ),
                }
            )

        ranked_candidates.sort(
            key=lambda candidate: candidate[
                "predicted_activity_um"
            ],
            reverse=True,
        )

        return [
            {
                "rank": rank,
                **candidate,
            }
            for rank, candidate in enumerate(
                ranked_candidates[:top_n],
                start=1,
            )
        ]


def load_candidates():
    candidates = {}

    with DATASET_PATH.open(
        newline="",
        encoding="utf-8-sig",
    ) as dataset_file:

        reader = csv.DictReader(dataset_file)

        required_columns = {
            "protein_id",
            "protein_name",
            "sequence",
        }

        missing_columns = (
            required_columns
            - set(reader.fieldnames or [])
        )

        if missing_columns:
            raise ValueError(
                "Dataset is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row in reader:

            protein_id = (
                row["protein_id"] or ""
            ).strip()

            protein_name = (
                row["protein_name"] or ""
            ).strip()

            sequence = (
                row["sequence"] or ""
            ).strip()

            if protein_id and protein_id not in candidates:

                candidates[protein_id] = {
                    "protein_id": protein_id,
                    "protein_name": protein_name,
                    "sequence": sequence,

                    "sequence_available": bool(sequence),

                    "activity_record_count": 0,
                }

            if protein_id:

                candidates[protein_id][
                    "activity_record_count"
                ] += 1

    if not candidates:
        raise ValueError(
            "Dataset does not contain any protein candidates."
        )

    logger.info(
        "Loaded %d unique protein candidates",
        len(candidates),
    )

    return list(candidates.values())
