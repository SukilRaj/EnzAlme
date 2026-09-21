"""
ENZAIme — Central Configuration
================================
Every tunable parameter used by the data pipeline, the compatibility engine,
the neural model, the mutation module and the backend API is declared here
so that behaviour can be changed WITHOUT touching any application logic.

Values are read from environment variables first (see .env.example) and
fall back to the scientifically-documented defaults specified in the
project design document.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at import time
    pass

# --------------------------------------------------------------------------
# Project paths
# --------------------------------------------------------------------------
# common/enzaime_core/config.py -> repo root is two levels up
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
DEMO_DIR = DATA_DIR / "demo"
MUTATION_DIR = DATA_DIR / "mutation"

ARTIFACTS_DIR = REPO_ROOT / "artifacts"
EMBEDDINGS_DIR = ARTIFACTS_DIR / "embeddings"
REPORTS_DIR = REPO_ROOT / "reports"

CANONICAL_ENZYME_CSV = PROCESSED_DIR / "enzymes.csv"
DEMO_ENZYME_CSV = DEMO_DIR / "enzymes_demo.csv"
SCENARIOS_JSON = DEMO_DIR / "demo_scenarios.json"


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    try:
        return float(val) if val is not None else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# ESM-2 / representation model configuration
# --------------------------------------------------------------------------
# Primary recommended model. If GPU memory / time on Kaggle makes the 650M
# parameter model impractical, MODEL_NAME_FALLBACK is used automatically
# (see scripts/05_generate_embeddings.py: `resolve_model_name`).
MODEL_NAME = os.getenv("MODEL_NAME", "facebook/esm2_t12_35M_UR50D")
MODEL_NAME_FALLBACK = os.getenv("MODEL_NAME_FALLBACK", "facebook/esm2_t12_35M_UR50D")
EMBEDDING_BATCH_SIZE = _env_int("EMBEDDING_BATCH_SIZE", 4)
EMBEDDING_MAX_LENGTH = _env_int("EMBEDDING_MAX_LENGTH", 1024)
DEVICE = os.getenv("DEVICE", "auto")  # "auto" | "cuda" | "cpu"

# --------------------------------------------------------------------------
# Recommendation engine
# --------------------------------------------------------------------------
TOP_K = _env_int("TOP_K", 3)

# DEMO_MODE=true  -> transparent rule-based compatibility engine (Section 12)
# DEMO_MODE=false -> trained neural suitability model (Section 13), with an
#                    AUTOMATIC fallback to the compatibility engine if no
#                    trained artifact is found (Section 35-37, REQUIRED).
DEMO_MODE = _env_bool("DEMO_MODE", True)

# Compatibility-function tolerances
DELTA_PH = _env_float("DELTA_PH", 2.0)
DELTA_TEMP = _env_float("DELTA_TEMP", 20.0)
DELTA_SALINITY = _env_float("DELTA_SALINITY", 1.5)
PH_OPT_TOLERANCE = _env_float("PH_OPT_TOLERANCE", 1.5)   # used only if pH_min/max missing
TEMP_OPT_TOLERANCE = _env_float("TEMP_OPT_TOLERANCE", 10.0)  # used only if T_min/max missing

# Default / neutral scoring assumptions (explicitly surfaced to the user)
SALINITY_UNKNOWN_SCORE = _env_float("SALINITY_UNKNOWN_SCORE", 0.8)
POLLUTANT_SCORE_VERIFIED = 1.0
POLLUTANT_SCORE_PREDICTED = 0.7
POLLUTANT_SCORE_NONE = 0.0
POLLUTANT_COMPAT_MIN_THRESHOLD = _env_float("POLLUTANT_COMPAT_MIN_THRESHOLD", 0.0)

# Suitability weights (Section 12) — MUST sum to 1.0 (validated at import time)
_default_weights = {"pollutant": 0.40, "ph": 0.25, "temperature": 0.25, "salinity": 0.10}
_weights_env = os.getenv("WEIGHTS")
if _weights_env:
    try:
        WEIGHTS: Dict[str, float] = json.loads(_weights_env)
    except json.JSONDecodeError:
        WEIGHTS = _default_weights
else:
    WEIGHTS = _default_weights

_weight_sum = sum(WEIGHTS.values())
if abs(_weight_sum - 1.0) > 1e-6:
    raise ValueError(
        f"Suitability weights must sum to 1.0, got {_weight_sum} for {WEIGHTS}. "
        "Fix the WEIGHTS environment variable or config default."
    )

SUPPORTED_POLLUTANTS = ["PET", "PUR", "PA"]

# Reasonable input validation bounds (Section 26 / 53)
PH_MIN_ALLOWED, PH_MAX_ALLOWED = 0.0, 14.0
TEMP_MIN_ALLOWED, TEMP_MAX_ALLOWED = -10.0, 120.0
SALINITY_MIN_ALLOWED, SALINITY_MAX_ALLOWED = 0.0, 10.0

# --------------------------------------------------------------------------
# Mutation module
# --------------------------------------------------------------------------
MAX_MUTATIONS = _env_int("MAX_MUTATIONS", 500)
TOP_CANDIDATE_POSITIONS = _env_int("TOP_CANDIDATE_POSITIONS", 20)
MUTATION_ALPHA = _env_float("MUTATION_ALPHA", 0.7)  # weight of stability vs fitness proxy
AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")

# --------------------------------------------------------------------------
# Neural model architecture (Section 13)
# --------------------------------------------------------------------------
EMBEDDING_PROJECTION_DIM = _env_int("EMBEDDING_PROJECTION_DIM", 128)
ENV_PROJECTION_DIM = _env_int("ENV_PROJECTION_DIM", 32)
FUSION_DIM = _env_int("FUSION_DIM", 160)
HIDDEN_DIM = _env_int("HIDDEN_DIM", 64)
DROPOUT = _env_float("DROPOUT", 0.3)
WEIGHT_DECAY = _env_float("WEIGHT_DECAY", 1e-4)
LEARNING_RATE = _env_float("LEARNING_RATE", 1e-3)
MAX_EPOCHS = _env_int("MAX_EPOCHS", 100)
EARLY_STOPPING_PATIENCE = _env_int("EARLY_STOPPING_PATIENCE", 10)
MIN_TRAINING_ROWS_REQUIRED = _env_int("MIN_TRAINING_ROWS_REQUIRED", 200)

# --------------------------------------------------------------------------
# Environmental scenario generator (Section 17)
# --------------------------------------------------------------------------
SCENARIO_PH_VALUES = [6, 7, 8, 9, 10]
SCENARIO_TEMP_VALUES = [25, 35, 45, 55, 65]
SCENARIO_SALINITY_VALUES = [0, 0.5, 1.0]
SCENARIO_POLLUTANTS = SUPPORTED_POLLUTANTS

# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = _env_int("API_PORT", 8000)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
]

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def to_dict() -> dict:
    """Expose the active configuration (used by GET /metadata)."""
    return {
        "model_name": MODEL_NAME,
        "model_name_fallback": MODEL_NAME_FALLBACK,
        "device": DEVICE,
        "demo_mode": DEMO_MODE,
        "top_k": TOP_K,
        "weights": WEIGHTS,
        "delta_ph": DELTA_PH,
        "delta_temp": DELTA_TEMP,
        "delta_salinity": DELTA_SALINITY,
        "salinity_unknown_score": SALINITY_UNKNOWN_SCORE,
        "max_mutations": MAX_MUTATIONS,
        "mutation_alpha": MUTATION_ALPHA,
        "supported_pollutants": SUPPORTED_POLLUTANTS,
    }
