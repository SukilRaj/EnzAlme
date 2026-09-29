import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from backend.app.config import LEGACY_MODEL_NAME, LEGACY_MODEL_LINEAGE

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "results"
    / "cross_validation_results.json"
)


@router.get("/cross-validation")
def get_cross_validation():
    try:
        with RESULTS_PATH.open("r", encoding="utf-8") as file:
            results = json.load(file)

        return {
            **results,
            "model": LEGACY_MODEL_NAME,
            "lineage_note": LEGACY_MODEL_LINEAGE,
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Cross-validation results file not found.",
        )

    except (json.JSONDecodeError, KeyError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid cross-validation results file: {error}",
        )
