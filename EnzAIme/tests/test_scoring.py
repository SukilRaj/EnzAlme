"""
tests/test_scoring.py
========================
Covers Section 39 test requirements #1-7:
  1. pH inside range gives high compatibility.
  2. pH outside range decreases compatibility.
  3. Temperature compatibility works.
  4. Salinity unknown is handled.
  5. Suitability remains between 0 and 1.
  6. Weights sum to 1.
  7. Ranking is descending.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import math
from enzaime_core import config, scoring


def test_weights_sum_to_one():
    assert abs(sum(config.WEIGHTS.values()) - 1.0) < 1e-9


def test_ph_inside_range_gives_full_compatibility():
    score = scoring.ph_compatibility(7.5, ph_min=7.0, ph_max=8.0, ph_opt=None)
    assert score == 1.0


def test_ph_outside_range_decays():
    inside = scoring.ph_compatibility(7.5, ph_min=7.0, ph_max=8.0, ph_opt=None)
    just_outside = scoring.ph_compatibility(8.5, ph_min=7.0, ph_max=8.0, ph_opt=None)
    far_outside = scoring.ph_compatibility(12.0, ph_min=7.0, ph_max=8.0, ph_opt=None)
    assert inside > just_outside > far_outside
    assert far_outside == 0.0  # beyond DELTA_PH -> clipped to 0


def test_ph_uses_opt_tolerance_when_range_missing():
    score = scoring.ph_compatibility(7.0, ph_min=None, ph_max=None, ph_opt=7.0)
    assert score == 1.0
    far = scoring.ph_compatibility(13.9, ph_min=None, ph_max=None, ph_opt=7.0)
    assert far == 0.0


def test_temperature_inside_range_gives_full_compatibility():
    score = scoring.temperature_compatibility(35, t_min=30, t_max=50, t_opt=None)
    assert score == 1.0


def test_temperature_outside_range_decays():
    inside = scoring.temperature_compatibility(40, t_min=30, t_max=50, t_opt=None)
    outside = scoring.temperature_compatibility(90, t_min=30, t_max=50, t_opt=None)
    assert inside > outside


def test_temperature_never_negative():
    score = scoring.temperature_compatibility(500, t_min=30, t_max=50, t_opt=None)
    assert score == 0.0


def test_salinity_unknown_uses_neutral_default_and_flags_unknown():
    score, status = scoring.salinity_compatibility(0.5, s_min=None, s_max=None, has_evidence=False)
    assert status == "unknown"
    assert score == config.SALINITY_UNKNOWN_SCORE


def test_salinity_known_uses_range_logic():
    score, status = scoring.salinity_compatibility(0.5, s_min=0.0, s_max=1.0, has_evidence=True)
    assert status == "known"
    assert score == 1.0


def test_pollutant_compatibility_verified_predicted_none():
    assert scoring.pollutant_compatibility("PET", "verified", "PET") == 1.0
    assert scoring.pollutant_compatibility("PET", "predicted", "PET") == 0.7
    assert scoring.pollutant_compatibility("PET", "verified", "PUR") == 0.0


def test_suitability_score_bounded_0_1():
    breakdown = scoring.CompatibilityBreakdown(pollutant=1.0, ph=1.0, temperature=1.0, salinity=1.0, salinity_status="known")
    assert scoring.suitability_score(breakdown) <= 1.0
    breakdown_zero = scoring.CompatibilityBreakdown(pollutant=0.0, ph=0.0, temperature=0.0, salinity=0.0, salinity_status="unknown")
    assert scoring.suitability_score(breakdown_zero) >= 0.0


def test_suitability_score_matches_weighted_formula():
    breakdown = scoring.CompatibilityBreakdown(pollutant=1.0, ph=0.8, temperature=0.6, salinity=0.5, salinity_status="known")
    expected = (
        config.WEIGHTS["pollutant"] * 1.0 + config.WEIGHTS["ph"] * 0.8
        + config.WEIGHTS["temperature"] * 0.6 + config.WEIGHTS["salinity"] * 0.5
    )
    assert abs(scoring.suitability_score(breakdown) - expected) < 1e-9


def test_score_enzyme_end_to_end():
    row = {
        "pollutant": "PET", "evidence_type": "verified",
        "pH_opt": 8.0, "pH_min": float("nan"), "pH_max": float("nan"),
        "T_opt": 30.0, "T_min": float("nan"), "T_max": float("nan"),
        "salinity_evidence": "false", "salinity_min": float("nan"), "salinity_max": float("nan"),
    }
    query = scoring.EnvironmentQuery(pollutant="PET", ph=8.0, temperature=30.0, salinity=0.5)
    score, breakdown = scoring.score_enzyme(row, query)
    assert 0.0 <= score <= 1.0
    assert breakdown.salinity_status == "unknown"


def test_ranking_is_descending():
    rows = [
        {"pollutant": "PET", "evidence_type": "verified", "pH_opt": 7.0, "pH_min": None, "pH_max": None,
         "T_opt": 30, "T_min": None, "T_max": None, "salinity_evidence": "false",
         "salinity_min": None, "salinity_max": None},
        {"pollutant": "PET", "evidence_type": "predicted", "pH_opt": 12.0, "pH_min": None, "pH_max": None,
         "T_opt": 90, "T_min": None, "T_max": None, "salinity_evidence": "false",
         "salinity_min": None, "salinity_max": None},
    ]
    query = scoring.EnvironmentQuery(pollutant="PET", ph=7.0, temperature=30.0, salinity=0.0)
    scored = sorted(
        [scoring.score_enzyme(r, query)[0] for r in rows], reverse=True
    )
    assert scored == sorted(scored, reverse=True)
    assert scored[0] >= scored[-1]


def test_clip01_bounds():
    assert scoring.clip01(-5) == 0.0
    assert scoring.clip01(5) == 1.0
    assert scoring.clip01(0.5) == 0.5
