"""
ENZAIme — Compatibility Scoring Engine
========================================
Implements the transparent, project-defined "Environment-Aware Suitability
Score" (Section 12 of the design spec). This is the reliable, always-on
baseline used by DEMO_MODE, and it is also the reference signal the
optional neural model is trained against (Section 14).

None of the functions here require network access, GPU, or the ESM-2
embedding — they operate purely on the enzyme metadata table, which keeps
the recommendation pipeline responsive (Section 54) and fully functional
even when embeddings/artifacts are unavailable (Section 37).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

from . import config


# --------------------------------------------------------------------------
# Data container for a single query
# --------------------------------------------------------------------------
@dataclass
class EnvironmentQuery:
    pollutant: str
    ph: float
    temperature: float
    salinity: float


@dataclass
class CompatibilityBreakdown:
    pollutant: float
    ph: float
    temperature: float
    salinity: float
    salinity_status: str  # "known" | "unknown"


def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# --------------------------------------------------------------------------
# 11.1 Pollutant compatibility
# --------------------------------------------------------------------------
def pollutant_compatibility(row_pollutant: str, row_evidence_type: str, query_pollutant: str) -> float:
    """
    Verified activity on the queried pollutant  -> 1.0
    Predicted / homolog evidence on the pollutant -> 0.7
    Pollutant not matched / no evidence          -> 0.0
    """
    if not isinstance(row_pollutant, str) or row_pollutant.strip().upper() != query_pollutant.strip().upper():
        return config.POLLUTANT_SCORE_NONE

    evidence = (row_evidence_type or "").strip().lower()
    if evidence in {"verified", "experimental", "verified_activity"}:
        return config.POLLUTANT_SCORE_VERIFIED
    if evidence in {"predicted", "homolog", "literature_predicted", "computational"}:
        return config.POLLUTANT_SCORE_PREDICTED
    # Pollutant matches but evidence_type is unrecognised/blank -> treat as predicted
    # (conservative middle ground rather than silently claiming full verification)
    return config.POLLUTANT_SCORE_PREDICTED


# --------------------------------------------------------------------------
# 11.2 / 11.3 shared smooth-decay helper for range-based compatibility
# --------------------------------------------------------------------------
def _range_compatibility(
    value: float,
    v_min: Optional[float],
    v_max: Optional[float],
    v_opt: Optional[float],
    delta: float,
    opt_tolerance: float,
) -> float:
    """
    If [v_min, v_max] is available and value falls inside -> 1.0
    Outside the range -> linear decay from the nearest boundary, hitting 0
    at `delta` units past the boundary.
    If only v_opt is known, build a symmetric window of width
    `opt_tolerance` around it and apply the same decay logic.
    """
    has_range = v_min is not None and v_max is not None and not (
        _is_nan(v_min) or _is_nan(v_max)
    )
    if has_range:
        if v_min <= value <= v_max:
            return 1.0
        nearest_boundary = v_min if value < v_min else v_max
        distance = abs(value - nearest_boundary)
        return clip01(1 - distance / delta) if delta > 0 else 0.0

    has_opt = v_opt is not None and not _is_nan(v_opt)
    if has_opt:
        lo, hi = v_opt - opt_tolerance, v_opt + opt_tolerance
        if lo <= value <= hi:
            return 1.0
        nearest_boundary = lo if value < lo else hi
        distance = abs(value - nearest_boundary)
        return clip01(1 - distance / delta) if delta > 0 else 0.0

    # No information at all about this enzyme's tolerance for this variable.
    # Rather than silently defaulting to a score, callers should check
    # has_ph_info/has_temp_info first. This path returns a conservative
    # neutral value to avoid crashing on totally empty rows.
    return 0.5


def _is_nan(x) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except TypeError:
        return False


def ph_compatibility(input_ph: float, ph_min, ph_max, ph_opt) -> float:
    """Section 11.2. DELTA_PH default = 2.0 pH units."""
    return _range_compatibility(
        input_ph, ph_min, ph_max, ph_opt, config.DELTA_PH, config.PH_OPT_TOLERANCE
    )


def temperature_compatibility(input_temp: float, t_min, t_max, t_opt) -> float:
    """Section 11.3. DELTA_T default = 20 degrees C."""
    return _range_compatibility(
        input_temp, t_min, t_max, t_opt, config.DELTA_TEMP, config.TEMP_OPT_TOLERANCE
    )


def salinity_compatibility(input_salinity: float, s_min, s_max, has_evidence: bool):
    """
    Section 11.4. If salinity tolerance is documented, score via the same
    range-decay logic. Otherwise return the NEUTRAL DEFAULT and flag the
    result as "unknown" so the UI never presents it as measured data.
    """
    if has_evidence and s_min is not None and s_max is not None and not (
        _is_nan(s_min) or _is_nan(s_max)
    ):
        score = _range_compatibility(
            input_salinity, s_min, s_max, None, config.DELTA_SALINITY, config.DELTA_SALINITY
        )
        return score, "known"
    return config.SALINITY_UNKNOWN_SCORE, "unknown"


# --------------------------------------------------------------------------
# 12. Final suitability formula
# --------------------------------------------------------------------------
def suitability_score(breakdown: CompatibilityBreakdown) -> float:
    w = config.WEIGHTS
    s = (
        w["pollutant"] * breakdown.pollutant
        + w["ph"] * breakdown.ph
        + w["temperature"] * breakdown.temperature
        + w["salinity"] * breakdown.salinity
    )
    return clip01(s)


def score_enzyme(row: dict, query: EnvironmentQuery) -> tuple[float, CompatibilityBreakdown]:
    """
    Compute the full breakdown + final suitability score for a single
    enzyme metadata row against a single environmental query.
    `row` is expected to follow the data/processed/enzymes.csv schema.
    """
    l_poll = pollutant_compatibility(row.get("pollutant"), row.get("evidence_type"), query.pollutant)
    l_ph = ph_compatibility(query.ph, row.get("pH_min"), row.get("pH_max"), row.get("pH_opt"))
    l_t = temperature_compatibility(
        query.temperature, row.get("T_min"), row.get("T_max"), row.get("T_opt")
    )
    has_sal_evidence = str(row.get("salinity_evidence", "")).strip().lower() in {
        "true", "1", "yes", "known", "documented"
    }
    l_s, sal_status = salinity_compatibility(
        query.salinity, row.get("salinity_min"), row.get("salinity_max"), has_sal_evidence
    )

    breakdown = CompatibilityBreakdown(
        pollutant=round(l_poll, 4),
        ph=round(l_ph, 4),
        temperature=round(l_t, 4),
        salinity=round(l_s, 4),
        salinity_status=sal_status,
    )
    score = suitability_score(breakdown)
    return score, breakdown


def explain(row: dict, query: EnvironmentQuery, breakdown: CompatibilityBreakdown) -> dict:
    """Human-readable explanation payload for the 'Why this enzyme?' UI panel."""

    def _fmt_range(lo, hi):
        if lo is None or hi is None or _is_nan(lo) or _is_nan(hi):
            return None
        return f"{lo:g}-{hi:g}"

    ph_range = _fmt_range(row.get("pH_min"), row.get("pH_max"))
    t_range = _fmt_range(row.get("T_min"), row.get("T_max"))

    return {
        "pollutant": {
            "input": query.pollutant,
            "evidence_type": row.get("evidence_type") or "unknown",
            "compatibility": breakdown.pollutant,
            "note": (
                "Verified activity reported in source literature/database."
                if breakdown.pollutant >= 1.0
                else "Predicted/homologous evidence only — not experimentally verified for this exact pollutant."
                if breakdown.pollutant > 0
                else "No documented or predicted activity on this pollutant."
            ),
        },
        "ph": {
            "input": query.ph,
            "reported_range": ph_range or "not documented (default tolerance window used)",
            "compatibility": breakdown.ph,
        },
        "temperature": {
            "input": query.temperature,
            "reported_range": t_range or "not documented (default tolerance window used)",
            "compatibility": breakdown.temperature,
        },
        "salinity": {
            "input": query.salinity,
            "status": breakdown.salinity_status,
            "compatibility": breakdown.salinity,
            "note": (
                "Salinity tolerance is documented for this enzyme."
                if breakdown.salinity_status == "known"
                else "Salinity tolerance information unavailable — a neutral default "
                     f"score ({config.SALINITY_UNKNOWN_SCORE}) was used. This is NOT an "
                     "experimental measurement."
            ),
        },
    }
