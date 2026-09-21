"""
ENZAIme — Environment-Aware Suitability Model (Section 13)
=============================================================
A small fusion network:

    ESM-2 embedding --> projection(128) --\
                                            +--> fusion(160) --> hidden(64) --> output(1)
    environment features --> projection(32)-/

Trained (Section 14) to REGRESS TOWARD the transparent compatibility score
(scoring.py) as its reference target, since no large matched
enzyme-environment experimental suitability dataset exists yet. This keeps
the model scientifically honest: it is a learned *refinement/smoothing* of
the rule-based reference, not a claim of independently-validated ground
truth.

Kept intentionally small (Section 13: "do not build an unnecessarily deep
architecture") given the small verified enzyme dataset.
"""
from __future__ import annotations

from . import config

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    TORCH_AVAILABLE = False
    nn = object  # type: ignore


if TORCH_AVAILABLE:

    class SuitabilityNet(nn.Module):
        def __init__(
            self,
            embedding_dim: int,
            env_feature_dim: int,
            embedding_proj_dim: int = config.EMBEDDING_PROJECTION_DIM,
            env_proj_dim: int = config.ENV_PROJECTION_DIM,
            fusion_dim: int = config.FUSION_DIM,
            hidden_dim: int = config.HIDDEN_DIM,
            dropout: float = config.DROPOUT,
        ):
            super().__init__()
            self.embedding_proj = nn.Sequential(
                nn.Linear(embedding_dim, embedding_proj_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.env_proj = nn.Sequential(
                nn.Linear(env_feature_dim, env_proj_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            fused_input_dim = embedding_proj_dim + env_proj_dim
            self.fusion = nn.Sequential(
                nn.Linear(fused_input_dim, fusion_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.hidden = nn.Sequential(
                nn.Linear(fusion_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.output = nn.Linear(hidden_dim, 1)
            self.sigmoid = nn.Sigmoid()

        def forward(self, embedding, env_features):
            e = self.embedding_proj(embedding)
            v = self.env_proj(env_features)
            fused = torch.cat([e, v], dim=-1)
            x = self.fusion(fused)
            x = self.hidden(x)
            x = self.output(x)
            return self.sigmoid(x).squeeze(-1)  # constrained to [0, 1]

else:
    SuitabilityNet = None  # torch not installed; neural path unavailable


def encode_environment_features(pollutant_onehot, ph, temperature, salinity, pollutant_classes):
    """
    Build the environment feature vector described in Section 10:
      - pollutant: categorical (one-hot)
      - pH, temperature, salinity: min-max normalized numerical features
    `pollutant_onehot` is produced by the caller's fitted encoder; this
    helper just documents/enforces the expected ordering and normalization
    ranges used consistently between training (scripts/06) and inference
    (backend/app/services).
    """
    ph_norm = (ph - 0.0) / 14.0
    temp_norm = (temperature - config.TEMP_MIN_ALLOWED) / (config.TEMP_MAX_ALLOWED - config.TEMP_MIN_ALLOWED)
    sal_norm = (salinity - config.SALINITY_MIN_ALLOWED) / (config.SALINITY_MAX_ALLOWED - config.SALINITY_MIN_ALLOWED)
    return list(pollutant_onehot) + [ph_norm, temp_norm, sal_norm]
