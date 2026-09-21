"""
backend/app/services/recommendation_service.py
==================================================
Implements the core pipeline from the architecture diagram:

  candidate enzyme database -> pollutant pre-filter -> compatibility engine
  -> (optional AI refinement) -> ranking -> top-K -> explanation

This does NOT compute ESM-2 embeddings per-request (Section 54) — it only
ever reads pre-cached embeddings via ModelService, and falls back
transparently to the rule-based compatibility engine otherwise.
"""
from __future__ import annotations

import logging
import time

from enzaime_core import config as core_config
from enzaime_core import data_loader, scoring
from enzaime_core.model import encode_environment_features

from app.services.model_service import ModelService

logger = logging.getLogger("enzaime.recommendation_service")


def get_recommendations(
    pollutant: str, ph: float, temperature: float, salinity: float, model_service: ModelService
) -> dict:
    t0 = time.time()
    query = scoring.EnvironmentQuery(pollutant=pollutant, ph=ph, temperature=temperature, salinity=salinity)

    df = data_loader.load_enzyme_table()
    n_total = len(df)

    # Pollutant pre-filter (Section 11.1 — "prefer filtering out completely
    # incompatible pollutant candidates before ranking").
    candidates = df[df["pollutant"].astype(str).str.upper() == pollutant.upper()].copy()
    n_with_evidence = len(candidates)

    scored_rows = []
    for _, row in candidates.iterrows():
        row_dict = row.to_dict()
        rule_score, breakdown = scoring.score_enzyme(row_dict, query)

        final_score = rule_score
        mode_used = "demo_compatibility_engine"

        if model_service.scoring_mode == "ai_model":
            try:
                env_vec = _build_env_vector(model_service, pollutant, ph, temperature, salinity)
                ai_score = model_service.predict_ai_score(row_dict["enzyme_id"], env_vec)
                if ai_score is not None:
                    final_score = ai_score
                    mode_used = "ai_model"
            except Exception as e:  # never let a model quirk break recommendations
                logger.warning("AI scoring failed for %s, using rule-based score: %s",
                                row_dict.get("enzyme_id"), e)

        if rule_score <= core_config.POLLUTANT_COMPAT_MIN_THRESHOLD and breakdown.pollutant == 0.0:
            continue  # no meaningful pollutant compatibility -> excluded (Section 11.1)

        explanation = scoring.explain(row_dict, query, breakdown)
        scored_rows.append({
            "row": row_dict,
            "score": final_score,
            "breakdown": breakdown,
            "explanation": explanation,
            "mode_used": mode_used,
        })

    scored_rows.sort(key=lambda r: r["score"], reverse=True)
    top = scored_rows[: core_config.TOP_K]

    recommendations = []
    for rank, item in enumerate(top, start=1):
        row = item["row"]
        breakdown = item["breakdown"]
        recommendations.append({
            "rank": rank,
            "enzyme_id": row["enzyme_id"],
            "enzyme_name": row["enzyme_name"],
            "accession": row.get("accession") if isinstance(row.get("accession"), str) else None,
            "pollutant": row["pollutant"],
            "suitability_score": round(float(item["score"]), 4),
            "score_percent": round(float(item["score"]) * 100, 2),
            "breakdown": {
                "pollutant": breakdown.pollutant,
                "ph": breakdown.ph,
                "temperature": breakdown.temperature,
                "salinity": breakdown.salinity,
            },
            "evidence": row.get("evidence_type"),
            "salinity_status": breakdown.salinity_status,
            "explanation": item["explanation"],
            "scoring_mode": item["mode_used"],
        })

    elapsed = round(time.time() - t0, 4)
    logger.info(
        "recommend: pollutant=%s ph=%s temp=%s salinity=%s -> %d/%d candidates evaluated, "
        "top=%s, elapsed=%.4fs, scoring_mode=%s",
        pollutant, ph, temperature, salinity, len(scored_rows), n_total,
        [r["enzyme_id"] for r in recommendations], elapsed, model_service.scoring_mode,
    )

    return {
        "recommendations": recommendations,
        "n_candidates_evaluated": len(scored_rows),
        "n_candidates_with_pollutant_evidence": n_with_evidence,
        "scoring_mode": model_service.scoring_mode,
        "elapsed_seconds": elapsed,
    }


def _build_env_vector(model_service: ModelService, pollutant, ph, temperature, salinity):
    categories = list(model_service.model_config["pollutant_categories"])
    onehot = [1.0 if c == pollutant else 0.0 for c in categories]
    return encode_environment_features(onehot, ph, temperature, salinity, categories)


DISCLAIMER = (
    "This is an in-silico decision-support recommendation, not a claim of experimentally "
    "measured degradation. The Environment-Aware Suitability Score is a project-defined "
    "compatibility score (see /metadata and docs/scoring.md)."
)
