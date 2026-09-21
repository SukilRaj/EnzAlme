"""
backend/app/services/simulation_service.py
=============================================
Service functions for the Environmental Sensitivity Simulator.
Evaluates the existing compatibility formula in `common/enzaime_core/scoring.py`
for a single target enzyme across specified operating conditions or a swept
variable range (pH, temperature, salinity).
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from enzaime_core import data_loader, scoring
from enzaime_core.model import encode_environment_features
from app.services.model_service import ModelService

logger = logging.getLogger("enzaime.simulation_service")


class EnzymeNotFoundError(Exception):
    """Raised when enzyme_id does not exist in the dataset."""
    pass


def _none_if_nan(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    return v if isinstance(v, str) else str(v) if v is not None else None


def _build_env_vector(model_service: ModelService, pollutant: str, ph: float, temperature: float, salinity: float):
    if model_service.model_config and "pollutant_categories" in model_service.model_config:
        categories = list(model_service.model_config["pollutant_categories"])
    else:
        categories = ["PET", "PUR", "PA"]
    onehot = [1.0 if c == pollutant else 0.0 for c in categories]
    return encode_environment_features(onehot, ph, temperature, salinity, categories)


def simulate_enzyme(
    enzyme_id: str,
    pollutant: str,
    ph: float,
    temperature: float,
    salinity: float,
    model_service: ModelService,
) -> dict:
    """
    Look up the enzyme by enzyme_id and score it against the given environmental query
    using enzaime_core.scoring.score_enzyme().
    """
    row = data_loader.get_enzyme_by_id(enzyme_id)
    if row is None:
        raise EnzymeNotFoundError(f"No enzyme found with enzyme_id='{enzyme_id}'.")

    query = scoring.EnvironmentQuery(
        pollutant=pollutant, ph=ph, temperature=temperature, salinity=salinity
    )
    rule_score, breakdown = scoring.score_enzyme(row, query)

    final_score = rule_score
    mode_used = "demo_compatibility_engine"

    if model_service.scoring_mode == "ai_model":
        try:
            env_vec = _build_env_vector(model_service, pollutant, ph, temperature, salinity)
            ai_score = model_service.predict_ai_score(row["enzyme_id"], env_vec)
            if ai_score is not None:
                final_score = ai_score
                mode_used = "ai_model"
        except Exception as e:
            logger.warning(
                "AI scoring failed for %s in simulation, using rule-based score: %s",
                row.get("enzyme_id"), e
            )

    explanation = scoring.explain(row, query, breakdown)

    return {
        "enzyme_id": row["enzyme_id"],
        "enzyme_name": row["enzyme_name"],
        "accession": _none_if_nan(row.get("accession")),
        "pollutant": pollutant,
        "suitability_score": round(float(final_score), 4),
        "score": round(float(final_score), 4),
        "score_percent": round(float(final_score) * 100, 2),
        "breakdown": {
            "pollutant": breakdown.pollutant,
            "ph": breakdown.ph,
            "temperature": breakdown.temperature,
            "salinity": breakdown.salinity,
        },
        "evidence": row.get("evidence_type"),
        "salinity_status": breakdown.salinity_status,
        "explanation": explanation,
        "scoring_mode": mode_used,
        "query": {
            "enzyme_id": enzyme_id,
            "pollutant": pollutant,
            "ph": ph,
            "temperature": temperature,
            "salinity": salinity,
        },
    }


def simulate_sweep(
    enzyme_id: str,
    pollutant: str,
    sweep_variable: str,
    sweep_min: float,
    sweep_max: float,
    steps: int,
    fixed_ph: float,
    fixed_temperature: float,
    fixed_salinity: float,
    model_service: ModelService,
) -> List[dict]:
    """
    Hold the two non-swept variables fixed, vary sweep_variable across `steps`
    evenly-spaced points from sweep_min to sweep_max, and call score_enzyme() at each point.
    """
    row = data_loader.get_enzyme_by_id(enzyme_id)
    if row is None:
        raise EnzymeNotFoundError(f"No enzyme found with enzyme_id='{enzyme_id}'.")

    if steps < 1 or steps > 200:
        raise ValueError(f"steps must be between 1 and 200, got {steps}")

    if steps == 1:
        values = [float(sweep_min)]
    else:
        step_size = (sweep_max - sweep_min) / (steps - 1)
        values = [float(sweep_min + i * step_size) for i in range(steps)]
        values[-1] = float(sweep_max)  # exact boundary match

    points = []
    for val in values:
        curr_ph = val if sweep_variable == "ph" else fixed_ph
        curr_temp = val if sweep_variable == "temperature" else fixed_temperature
        curr_sal = val if sweep_variable == "salinity" else fixed_salinity

        query = scoring.EnvironmentQuery(
            pollutant=pollutant, ph=curr_ph, temperature=curr_temp, salinity=curr_sal
        )
        rule_score, breakdown = scoring.score_enzyme(row, query)
        final_score = rule_score

        if model_service.scoring_mode == "ai_model":
            try:
                env_vec = _build_env_vector(model_service, pollutant, curr_ph, curr_temp, curr_sal)
                ai_score = model_service.predict_ai_score(row["enzyme_id"], env_vec)
                if ai_score is not None:
                    final_score = ai_score
            except Exception:
                pass

        points.append({
            "value": round(float(val), 4),
            "suitability_score": round(float(final_score), 4),
            "score": round(float(final_score), 4),
            "score_percent": round(float(final_score) * 100, 2),
            "breakdown": {
                "pollutant": breakdown.pollutant,
                "ph": breakdown.ph,
                "temperature": breakdown.temperature,
                "salinity": breakdown.salinity,
            },
        })

    return points
