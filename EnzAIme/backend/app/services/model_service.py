"""
backend/app/services/model_service.py
========================================
Owns the "which scoring engine is currently serving requests" state
machine described in Section 35-37:

  * DEMO_MODE=true (config default)         -> always use the rule-based
                                                compatibility engine.
  * DEMO_MODE=false AND trained artifacts
    (artifacts/model.pt + scaler.pkl +
    encoders.pkl + config.json) all exist   -> use the trained neural model
                                                for the final suitability
                                                score, but the per-factor
                                                breakdown (pollutant/pH/
                                                temperature/salinity) is
                                                ALWAYS computed by the
                                                transparent compatibility
                                                engine, so the "Why this
                                                enzyme?" explanation never
                                                depends on an opaque model.
  * DEMO_MODE=false BUT artifacts missing   -> automatic, REQUIRED fallback
    (or fail to load for any reason)           to the compatibility engine.
                                                The app never crashes for
                                                this reason.

The UI badge text ("Demo / Compatibility Engine" vs "AI Model") is derived
directly from `ModelService.scoring_mode`, so the active mode is never
hidden from the user (Section 36).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

import numpy as np

from enzaime_core import config as core_config
from enzaime_core import embeddings as emb_mod

logger = logging.getLogger("enzaime.model_service")


class ModelService:
    def __init__(self):
        self.demo_mode_config = core_config.DEMO_MODE
        self.scoring_mode = "demo_compatibility_engine"
        self.model = None
        self.scaler = None
        self.encoder = None
        self.model_config = None
        self.embedding_cache: dict[str, np.ndarray] = {}
        self.device = "cpu"
        self.load_time_seconds: Optional[float] = None
        self.load_error: Optional[str] = None
        self._load()

    # ----------------------------------------------------------------
    def _load(self) -> None:
        t0 = time.time()
        if self.demo_mode_config:
            logger.info("DEMO_MODE=true (config) — serving via rule-based compatibility engine.")
            self.scoring_mode = "demo_compatibility_engine"
            self.load_time_seconds = round(time.time() - t0, 4)
            return

        required = [
            core_config.ARTIFACTS_DIR / "model.pt",
            core_config.ARTIFACTS_DIR / "scaler.pkl",
            core_config.ARTIFACTS_DIR / "encoders.pkl",
            core_config.ARTIFACTS_DIR / "config.json",
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            logger.warning(
                "DEMO_MODE=false but trained artifacts are missing (%s). "
                "Falling back to the rule-based compatibility engine (REQUIRED fallback).",
                missing,
            )
            self.scoring_mode = "demo_compatibility_engine"
            self.load_error = f"Missing artifacts: {missing}"
            self.load_time_seconds = round(time.time() - t0, 4)
            return

        try:
            import torch
            import joblib
            from enzaime_core.model import SuitabilityNet

            self.model_config = json.loads((core_config.ARTIFACTS_DIR / "config.json").read_text())
            self.scaler = joblib.load(core_config.ARTIFACTS_DIR / "scaler.pkl")
            self.encoder = joblib.load(core_config.ARTIFACTS_DIR / "encoders.pkl")
            self.device = emb_mod.detect_device()

            model = SuitabilityNet(
                embedding_dim=self.model_config["embedding_dim"],
                env_feature_dim=self.model_config["env_feature_dim"],
            )
            state = torch.load(core_config.ARTIFACTS_DIR / "model.pt", map_location=self.device)
            model.load_state_dict(state)
            model.eval().to(self.device)
            self.model = model

            self.embedding_cache = emb_mod.load_all_cached_embeddings()

            self.scoring_mode = "ai_model"
            logger.info(
                "Loaded trained AI model (embedding_dim=%s, env_feature_dim=%s, "
                "%d cached embeddings, device=%s).",
                self.model_config["embedding_dim"], self.model_config["env_feature_dim"],
                len(self.embedding_cache), self.device,
            )
        except Exception as e:
            logger.error("Failed to load trained AI model artifacts (%s). "
                         "Falling back to the rule-based compatibility engine.", e)
            self.model = None
            self.scoring_mode = "demo_compatibility_engine"
            self.load_error = str(e)
        finally:
            self.load_time_seconds = round(time.time() - t0, 4)

    def reload(self) -> dict:
        """Used by POST /reload-model — re-checks DEMO_MODE / artifacts."""
        self.demo_mode_config = core_config.DEMO_MODE
        self._load()
        return self.status()

    def status(self) -> dict:
        return {
            "demo_mode_config": self.demo_mode_config,
            "scoring_mode": self.scoring_mode,
            "model_loaded": self.model is not None,
            "device": self.device,
            "n_cached_embeddings": len(self.embedding_cache),
            "load_time_seconds": self.load_time_seconds,
            "load_error": self.load_error,
        }

    # ----------------------------------------------------------------
    def predict_ai_score(self, enzyme_id: str, env_feature_vector: list[float]) -> Optional[float]:
        """Returns the neural model's suitability score in [0,1], or None if
        unavailable for this enzyme (e.g. no cached embedding) — callers
        must fall back to the rule-based score in that case."""
        if self.model is None or enzyme_id not in self.embedding_cache:
            return None
        import torch
        emb = torch.tensor(self.embedding_cache[enzyme_id]).unsqueeze(0).to(self.device)
        env = torch.tensor(np.array(env_feature_vector, dtype=np.float32)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            pred = self.model(emb, env)
        return float(pred.item())


# Module-level singleton, created once at app startup (see main.py)
model_service: Optional[ModelService] = None


def get_model_service() -> ModelService:
    global model_service
    if model_service is None:
        model_service = ModelService()
    return model_service
