"""
EnzAIme — Scenario Generation & Transparent Label Generation
=============================================================
Creates the training dataset for the compatibility/ranking model:

  data/processed/training_scenarios.csv

For every enzyme with a valid sequence we generate realistic environmental
scenarios restricted to the pollutant the enzyme actually has evidence for,
then compute a TRANSPARENT, documentable derived-compatibility label.

SCIENTIFIC HONESTY
------------------
* Labels are ALWAYS lower-case aliases of:
    - `derived_compatibility_label` (this script's output)
    - `derived_suitability_score`
    - `heuristic_environmental_compatibility` (when metadata is missing)
  They are NEVER called "experimental degradation efficiency".
* If pH/temperature metadata is missing we do NOT pretend it is known: the
  component contributes a neutral 0.5 AND the corresponding `*_metadata_available`
  flag is 0; additionally an uncertainty penalty lowers `confidence_score`.
* No salinity optimum is invented: only the scenario (user/environment) salinity
  is used, with `salinity_metadata_available = 0` for every enzyme now.
* Formulas are documented in reports/label_generation_method.md.

Pseudo-equation (documented weights from common/enzaime_core/config.py):

  compatibility =
      w_poll * poll(evidence)                      # 0.40
    + w_ph   * ph_comp(opt/range, scenario_ph)     # 0.25  (neutral 0.5 if missing)
    + w_t    * temp_comp(opt/range, scenario_t)    # 0.25  (neutral 0.5 if missing)
    + w_s    * sal_comp(scenario_salinity)         # 0.10  (always neutral now)

  confidence = w_poll * evidence_confidence
             + 0.5 * (ph_metadata_available + temperature_metadata_available
                      + salinity_metadata_available)   # scaled, penalised

Run:
  python src/label_generation.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
REPO_ROOT = SRC_DIR.parent

# Weighting constants documented in reports/label_generation_method.md.
WEIGHT_POLLUTANT = 0.40
WEIGHT_PH = 0.25
WEIGHT_TEMP = 0.25
WEIGHT_SALINITY = 0.10

# Decay parameters (mirror common/enzaime_core/config.py defaults).
DELTA_PH = 2.0
DELTA_TEMP = 20.0
PH_OPT_TOLERANCE = 1.5
TEMP_OPT_TOLERANCE = 10.0

# Evidence-type -> provenance weight (documented ordinal, not a measurement).
EVIDENCE_WEIGHT = {
    "experimental": 1.0, "curated": 0.85, "predicted": 0.6, "inferred": 0.4,
    "heuristic": 0.25, "unknown": 0.1,
}

# Default conservative scenario grid (used when no metadata range is available).
SCENARIO_PH = [6.0, 7.0, 8.0, 9.0, 10.0]
SCENARIO_TEMP = [25.0, 35.0, 45.0, 55.0, 65.0]
SCENARIO_SALINITY = [0.0, 0.5, 1.0, 2.0]


def _missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, str):
        return not v.strip()
    return False


def _num(v):
    if _missing(v):
        return None
    try:
        c = float(v)
        return None if c != c else c
    except (TypeError, ValueError):
        return None


def _decay(value: float, lo: float, hi: float, delta: float) -> float:
    """Linear decay: inside [lo,hi] -> 1.0; outside -> 1 - distance/delta (min 0)."""
    if lo <= value <= hi:
        return 1.0
    nearest = lo if value < lo else hi
    d = abs(value - nearest)
    return max(0.0, 1.0 - d / delta) if delta > 0 else 0.0


def pollutant_component(evidence_type, evidence_score, scenario_pollutant, enzyme_pollutant) -> float:
    """Pollutant evidence: match + provenance weight. Unknown pollutant -> 0."""
    if not enzyme_pollutant or _missing(enzyme_pollutant):
        return 0.0
    if str(enzyme_pollutant).upper() != str(scenario_pollutant).upper():
        return 0.0
    key = (evidence_type or "").strip().lower()
    base = EVIDENCE_WEIGHT.get(key, 0.6)
    if not _missing(evidence_score):
        try:
            s = float(evidence_score)
            if 0 <= s <= 1:
                base = s
        except (TypeError, ValueError):
            pass
    return round(base, 4)


def ph_component(scenario_ph, ph_opt, ph_min, ph_max):
    """Known range/opt -> window decay; unknown -> neutral 0.5 (flagged elsewhere)."""
    lo, hi = _num(ph_min), _num(ph_max)
    if lo is not None and hi is not None:
        return round(_decay(scenario_ph, lo, hi, DELTA_PH), 4)
    opt = _num(ph_opt)
    if opt is not None:
        return round(_decay(scenario_ph, opt - PH_OPT_TOLERANCE, opt + PH_OPT_TOLERANCE, DELTA_PH), 4)
    return 0.5


def temperature_component(scenario_t, t_opt, t_min, t_max):
    lo, hi = _num(t_min), _num(t_max)
    if lo is not None and hi is not None:
        return round(_decay(scenario_t, lo, hi, DELTA_TEMP), 4)
    opt = _num(t_opt)
    if opt is not None:
        return round(_decay(scenario_t, opt - TEMP_OPT_TOLERANCE, opt + TEMP_OPT_TOLERANCE, DELTA_TEMP), 4)
    return 0.5


def salinity_component(scenario_salinity, s_opt, s_min, s_max):
    """No salinity metadata exists in the dataset -> neutral 0.5 (flagged)."""
    lo, hi = _num(s_min), _num(s_max)
    if lo is not None and hi is not None:
        return round(_decay(scenario_salinity, lo, hi, 1.5), 4)
    return 0.5


def compatibility_label(pollutant_comp: float, ph_comp: float,
                        temp_comp: float, sal_comp: float) -> float:
    """Weighted, clipped derived compatibility score from the four components."""
    raw = (WEIGHT_POLLUTANT * float(pollutant_comp)
           + WEIGHT_PH * float(ph_comp)
           + WEIGHT_TEMP * float(temp_comp)
           + WEIGHT_SALINITY * float(sal_comp))
    return round(float(np.clip(raw, 0.0, 1.0)), 4)


def confidence_score(evidence_c, has_ph, has_temp, has_sal) -> float:
    """
    confidence ~ provenance of pollutant evidence + fraction of environment
    metadata actually known. Missing metadata reduces confidence (uncertainty
    penalty) instead of being hidden.
    """
    metadata_known = int(has_ph) + int(has_temp) + int(has_sal)
    env_part = 0.5 * metadata_known / 3.0  # 0..0.5
    return round(min(1.0, 0.5 * evidence_c + env_part), 4)


def metadata_completeness(has_ph, has_temp, has_sal, has_seq, has_acc) -> float:
    return round((int(has_ph) + int(has_temp) + int(has_sal) + int(has_seq) + int(has_acc)) / 5.0, 4)


def evidence_quality(evidence_type) -> float:
    return EVIDENCE_WEIGHT.get((evidence_type or "").strip().lower(), 0.1)


def generate_scenarios(clean_csv: Path, output_csv: Path) -> pd.DataFrame:
    if not clean_csv.exists():
        raise FileNotFoundError(f"{clean_csv} missing — run src/data_quality.py first.")
    enzymes = pd.read_csv(clean_csv, keep_default_na=False)
    enzymes = enzymes[enzymes["has_sequence"] == 1].copy()

    rows = []
    for _, r in enzymes.iterrows():
        pol = str(r["pollutant_type"]).strip()
        if not pol:
            continue  # no pollutant evidence -> nothing to generate (honest)
        if r["has_ph_opt"] == 1 and not _missing(r.get("ph_min")):
            ph_grid = np.linspace(_num(r["ph_min"]), _num(r["ph_max"]), 5).tolist()
        else:
            ph_grid = SCENARIO_PH
        if r["has_temperature_opt"] == 1 and not _missing(r.get("temperature_min_c")):
            t_grid = np.linspace(_num(r["temperature_min_c"]), _num(r["temperature_max_c"]), 5).tolist()
        else:
            t_grid = SCENARIO_TEMP
        sal_grid = SCENARIO_SALINITY  # no enzyme-specific salinity ever

        for ph in ph_grid:
            ph = float(ph)
            for t in t_grid:
                t = float(t)
                for s in sal_grid:
                    s = float(s)
                    ev = str(r.get("evidence_confidence") or "")
                    # evidence_confidence column holds the provenance score (0..1)
                    try:
                        p_ev = float(ev)
                    except (TypeError, ValueError):
                        p_ev = evidence_quality(r.get("evidence_type"))
                    p_comp = pollutant_component(
                        r.get("evidence_type"), p_ev, pol, pol)
                    ph_c = ph_component(ph, r.get("ph_opt"), r.get("ph_min"), r.get("ph_max"))
                    t_c = temperature_component(
                        t, r.get("temperature_opt_c"), r.get("temperature_min_c"),
                        r.get("temperature_max_c"))
                    s_c = salinity_component(s, None, None, None)
                    comp = (
                        WEIGHT_POLLUTANT * p_comp
                        + WEIGHT_PH * ph_c
                        + WEIGHT_TEMP * t_c
                        + WEIGHT_SALINITY * s_c
                    )
                    has_ph = int(r["has_ph_opt"] == 1 or r["has_ph_range"] == 1)
                    has_t = int(r["has_temperature_opt"] == 1 or r["has_temperature_range"] == 1)
                    has_s = int(r["has_salinity_data"] == 1)
                    conf = confidence_score(p_ev, has_ph, has_t, has_s)
                    mdc = metadata_completeness(
                        has_ph, has_t, has_s, int(r.get("has_sequence")), int(r.get("has_accession")))
                    rows.append({
                        "enzyme_id": r["enzyme_id"],
                        "protein_sequence": r["protein_sequence"],
                        "pollutant_type": pol,
                        "scenario_ph": ph,
                        "scenario_temperature_c": t,
                        "scenario_salinity": s,
                        "pollutant_evidence_score": p_comp,
                        "ph_metadata_available": has_ph,
                        "temperature_metadata_available": has_t,
                        "salinity_metadata_available": has_s,
                        "scenario_source": "derived_conservative_grid",
                        "label_source": "derived_compatibility_label",
                        "label_confidence": conf,
                        "metadata_completeness": mdc,
                        "evidence_quality": p_ev,
                        "unknown_feature_count": (1 - has_ph) + (1 - has_t) + (1 - has_s),
                        "compatibility_score": round(float(np.clip(comp, 0, 1)), 4),
                        "suitability_label": round(float(np.clip(comp, 0, 1)), 4),
                        "derived_compatibility_label": round(float(np.clip(comp, 0, 1)), 4),
                    })
    out = pd.DataFrame(rows)
    out.to_csv(output_csv, index=False)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme scenario + label generation")
    ap.add_argument("--input", default=str(REPO_ROOT / "data" / "processed" / "master_enzymes_clean.csv"))
    ap.add_argument("--output", default=str(REPO_ROOT / "data" / "processed" / "training_scenarios.csv"))
    args = ap.parse_args(argv)
    try:
        df = generate_scenarios(Path(args.input), Path(args.output))
        print("=" * 72)
        print("LABEL GENERATION — derived_compatibility_label (transparent)")
        print("=" * 72)
        print(f" enzymes used        : {df['enzyme_id'].nunique()}")
        print(f" scenario rows       : {len(df)}")
        print(f" label range         : {df['derived_compatibility_label'].min()}..{df['derived_compatibility_label'].max()}")
        print(f" rows w/ ph metadata : {int(df['ph_metadata_available'].sum())}  ({df['ph_metadata_available'].mean():.2%})")
        print(f" rows w/ temp metadata: {int(df['temperature_metadata_available'].sum())} ({df['temperature_metadata_available'].mean():.2%})")
        print(f" rows w/ sal metadata: {int(df['salinity_metadata_available'].sum())} ({df['salinity_metadata_available'].mean():.2%})")
        print(f" -> {args.output}")
        print("  labels are DERIVED compatibility scores, NOT experimental degradation efficiency.")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())