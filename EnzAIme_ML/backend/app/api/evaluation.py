import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from backend.app.config import LEGACY_MODEL_NAME, LEGACY_MODEL_LINEAGE

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
METRICS_PATH = PROJECT_ROOT / "models" / "training_metrics.json"


@router.get("/evaluation")
def get_evaluation():
    try:
        with METRICS_PATH.open("r", encoding="utf-8") as file:
            metrics = json.load(file)

        return {
            "model": LEGACY_MODEL_NAME,
            "lineage_note": LEGACY_MODEL_LINEAGE,
            "training_records": metrics["training_records"],
            "unique_proteins": metrics["unique_proteins"],
            "cross_validation": {
                "folds": 5,
                "split_strategy": "GroupKFold by protein",
                "mae": {
                    "mean": metrics["cv_MAE_mean"],
                    "std": metrics["cv_MAE_std"],
                    "unit": "uM",
                },
                "rmse": {
                    "mean": metrics["cv_RMSE_mean"],
                    "std": metrics["cv_RMSE_std"],
                    "unit": "uM",
                },
                "r2": {
                    "mean": metrics["cv_R2_mean"],
                    "std": metrics["cv_R2_std"],
                },
                "spearman": {
                    "mean": metrics["cv_Spearman_mean"],
                    "std": metrics["cv_Spearman_std"],
                },
            },
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Training metrics file not found."
        )

    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid training metrics file: {error}"
        )
