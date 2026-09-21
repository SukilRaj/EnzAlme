"""
EnzAIme — Explainable Recommendation (inference)
================================================
Two interchangeable recommenders + a shared explanation builder.

  RuleBasedRecommender    (Step 12, always available, no ML)
  MLRecommender           (Step 11, requires artifacts/best_model.pt +
                           feature_config.json + esm_embeddings.npy; transparently
                           falls back to the rule-based recommender)

Both return per-enzyme recommendation dicts:

  enzyme_id, enzyme_name, accession, pollutant_type, suitability_score,
  confidence_score, evidence_score, sequence_available,
  known_ph_information, known_temperature_information,
  known_salinity_information, metadata_completeness, explanation, limitations

SCIENTIFIC HONESTY (enforced in wording):
  * Never claims guaranteed degradation / experimental performance.
  * Missing metadata lowers confidence and is surfaced in `limitations`.
  * Salinity optimum is NEVER invented — scenario salinity is only an input.
  * `suitability_score` is a derived compatibility score, not measured efficiency.

Run:
  python src/inference.py --pollutant PET --ph 8.0 --temperature 35 --salinity 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
REPO_ROOT = SRC_DIR.parent

from label_generation import (  # noqa: E402
    EVIDENCE_WEIGHT, ph_component, pollutant_component,
    salinity_component, temperature_component,
    WEIGHT_POLLUTANT, WEIGHT_PH, WEIGHT_TEMP, WEIGHT_SALINITY,
)

TOP_K = 5


def _missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, str):
        return not v.strip()
    return False


def build_explanation(row: pd.Series, ph: float, temp: float, sal: float,
                      score: float, confidence: float) -> tuple[str, str]:
    """Return (explanation, limitations) strings with honest wording."""
    pol = str(row["pollutant_type"])
    ev = (str(row.get("evidence_type")) or "unknown").lower()
    has_ph = not _missing(row.get("ph_opt"))
    has_temp = not _missing(row.get("temperature_opt_c"))
    has_sal = row.get("has_salinity_data") == 1

    parts = []
    if pol:
        ev_word = {"experimental": "documented experimental", "curated": "curated",
                   "predicted": "predicted/homolog", "inferred": "inferred",
                   "heuristic": "approximate", "unknown": "unconfirmed"}.get(ev, "documented")
        parts.append(f"its {ev_word} pollutant evidence matches {pol}")
    if has_ph:
        opt = row["ph_opt"]
        diff = abs(ph - float(opt))
        parts.append(f"the requested pH ({ph}) is {'within' if diff <= 1.5 else 'within ' + f'{diff:.1f} units of'} its known optimum (~{opt})")
    else:
        parts.append("pH metadata is unavailable")
    if has_temp:
        opt = row["temperature_opt_c"]
        parts.append(f"the requested temperature ({temp}°C) is within {abs(temp - float(opt)):.0f}°C of its known optimum (~{opt}°C)")
    else:
        parts.append("temperature metadata is unavailable")
    if not has_sal:
        parts.append("salinity tolerance is undocumented, so the salinity term is neutral")

    expl = ("This enzyme received a derived compatibility score of "
            f"{score:.2f} because " + "; ".join(parts) + ".")
    if not has_ph or not has_temp:
        expl += " Confidence is reduced where metadata is missing."

    limits = []
    if not has_ph:
        limits.append("no documented pH information")
    if not has_temp:
        limits.append("no documented temperature information")
    if not has_sal:
        limits.append("no documented salinity information")
    limits.append("score is a derived compatibility estimate, not an experimental "
                  "degradation measurement")
    return expl, "Limitations: " + "; ".join(limits) + "."


class RuleBasedRecommender:
    """Step 12 baseline — transparent ranking, no ML, no hidden defaults."""

    def __init__(self, clean_csv: Path | None = None):
        self.csv = clean_csv or REPO_ROOT / "data" / "processed" / "master_enzymes_clean.csv"
        if not self.csv.exists():
            raise FileNotFoundError(f"{self.csv} missing — run src/data_quality.py first.")
        self.df = pd.read_csv(self.csv, keep_default_na=False)

    def recommend(self, pollutant_type: str, ph: float, temperature: float,
                  salinity: float, top_k: int = TOP_K) -> dict:
        q = pollutant_type.strip().upper()
        rows = []
        for _, r in self.df.iterrows():
            pol = str(r["pollutant_type"]).strip()
            if not pol:
                continue  # no evidence -> never recommended (honest)
            ev = str(r.get("evidence_confidence") or r.get("evidence_score") or "")
            try:
                p_ev = float(ev)
            except (TypeError, ValueError):
                p_ev = EVIDENCE_WEIGHT.get(str(r.get("evidence_type", "")).lower(), 0.1)
            p_comp = pollutant_component(r.get("evidence_type"), p_ev, q, pol)
            ph_c = ph_component(ph, r.get("ph_opt"), r.get("ph_min"), r.get("ph_max"))
            t_c = temperature_component(
                temperature, r.get("temperature_opt_c"), r.get("temperature_min_c"),
                r.get("temperature_max_c"))
            s_c = salinity_component(salinity, None, None, None)
            score = float(np.clip(
                WEIGHT_POLLUTANT * p_comp + WEIGHT_PH * ph_c +
                WEIGHT_TEMP * t_c + WEIGHT_SALINITY * s_c, 0, 1))
            has_ph = (not _missing(r.get("ph_opt"))) or (
                (not _missing(r.get("ph_min"))) and (not _missing(r.get("ph_max"))))
            has_temp = (not _missing(r.get("temperature_opt_c")))
            has_sal = int(r.get("has_salinity_data") == 1)
            confidence = float(np.clip(
                0.5 * p_ev + 0.5 * (int(has_ph) + int(has_temp) + int(has_sal)) / 3.0,
                0, 1))
            expl, limits = build_explanation(r, ph, temperature, salinity, score, confidence)
            rows.append({
                "enzyme_id": r["enzyme_id"], "enzyme_name": r.get("enzyme_name"),
                "accession": r.get("accession") or "",
                "pollutant_type": pol if pol else "unknown",
                "suitability_score": round(score, 4),
                "confidence_score": round(confidence, 4),
                "evidence_score": round(p_ev, 4),
                "sequence_available": bool(int(r.get("has_sequence") or 0)),
                "known_ph_information": bool(has_ph),
                "known_temperature_information": bool(has_temp),
                "known_salinity_information": bool(has_sal),
                "metadata_completeness": float(r.get("metadata_completeness") or 0.0),
                "explanation": expl, "limitations": limits,
            })
        rows.sort(key=lambda d: (d["suitability_score"], d["confidence_score"]), reverse=True)
        return {
            "mode": "rule_based_baseline",
            "recommendations": rows[:top_k],
            "n_candidates": len(rows),
            "disclaimer": ("Derived compatibility ranking. Not an experimental "
                           "degradation prediction."),
        }


class MLRecommender:
    """Step 11 — small trained model over frozen ESM-2 embeddings.
    Transparently falls back to RuleBasedRecommender when artifacts are missing."""

    def __init__(self, artifacts: Path | None = None,
                 embeddings_npy: Path | None = None,
                 embeddings_idx: Path | None = None):
        self.artifacts = artifacts or REPO_ROOT / "artifacts"
        self.npy = embeddings_npy or REPO_ROOT / "data" / "processed" / "esm_embeddings.npy"
        self.idx = embeddings_idx or REPO_ROOT / "data" / "processed" / "esm_embedding_index.csv"
        self.available = self._try_load()
        self.rule = RuleBasedRecommender()

    def _try_load(self) -> bool:
        try:
            cfg = json.loads((self.artifacts / "feature_config.json").read_text())
            if "best_model" not in cfg:
                return False
            best = cfg["best_model"]
            if best != "mlp":
                print("[inference] best model is a non-MLP baseline; using rule-based explainability.")
                return False
            import model as M
            if not (self.npy.exists() and self.idx.exists()):
                return False
            self.config = cfg
            self.env_mat = np.load(self.npy)  # for enzymes in index
            self.env_idx = pd.read_csv(self.idx)
            # Load the exact MLP net
            self.mlp = M.SuitabilityMLP.load(
                self.artifacts / "best_model.pt", cfg,
                embedding_dim=int(cfg["embedding_dim"]), env_dim=int(cfg["env_dim"]))
            return True
        except Exception as e:
            print(f"[inference] ML artifacts unavailable: {e} — using rule-based fallback.")
            return False

    def recommend(self, pollutant_type, ph, temperature, salinity, top_k=TOP_K):
        if not self.available:
            out = self.rule.recommend(pollutant_type, ph, temperature, salinity, top_k)
            out["mode"] = "fallback_rule_based"
            return out
        # ML scoring path: build features for every enzyme that has an embedding.
        cats = self.config["pollutant_categories"]
        emb_id_map = {eid: self.env_mat[i]
                      for i, eid in enumerate(self.env_idx["enzyme_id"].to_numpy())}
        rule_result = self.rule.recommend(pollutant_type, ph, temperature, salinity,
                                          top_k=len(self.rule.df))
        recs = []
        for rec in rule_result["recommendations"]:
            eid = rec["enzyme_id"]
            if eid not in emb_id_map:
                recs.append(rec)
                continue
            onehot = [1.0 if rec["pollutant_type"] == c else 0.0 for c in cats]
            env_vec = np.asarray(
                onehot + [ph / 14.0, (temperature + 10.0) / 130.0, salinity / 10.0,
                          rec["evidence_score"], float(rec["known_ph_information"]),
                          float(rec["known_temperature_information"]),
                          float(rec["known_salinity_information"]),
                          float(rec["sequence_available"]), 0.0,
                          rec["metadata_completeness"], 0.0],
                dtype=np.float32)
            # align env columns: their order must match training's build_env_feature_columns
            idx_cols = self.config["env_columns"]
            vec = np.zeros(len(idx_cols), dtype=np.float32)
            for col in idx_cols:
                try:
                    if col.startswith("pollutant_") and col.replace("pollutant_", "") == rec["pollutant_type"]:
                        vec[idx_cols.index(col)] = 1.0
                    elif col == "scenario_ph_norm":
                        vec[idx_cols.index(col)] = ph / 14.0
                    elif col == "scenario_temp_norm":
                        vec[idx_cols.index(col)] = (temperature + 10.0) / 130.0
                    elif col == "scenario_sal_norm":
                        vec[idx_cols.index(col)] = salinity / 10.0
                    elif col == "pollutant_evidence_score":
                        vec[idx_cols.index(col)] = rec["evidence_score"]
                    elif col == "ph_metadata_available":
                        vec[idx_cols.index(col)] = float(rec["known_ph_information"])
                    elif col == "temperature_metadata_available":
                        vec[idx_cols.index(col)] = float(rec["known_temperature_information"])
                    elif col == "salinity_metadata_available":
                        vec[idx_cols.index(col)] = float(rec["known_salinity_information"])
                    elif col == "has_sequence":
                        vec[idx_cols.index(col)] = float(rec["sequence_available"])
                    elif col == "has_accession":
                        vec[idx_cols.index(col)] = 0.0
                    elif col == "metadata_completeness":
                        vec[idx_cols.index(col)] = rec["metadata_completeness"]
                    elif col == "unknown_feature_count":
                        vec[idx_cols.index(col)] = (
                            1 - float(rec["known_ph_information"])
                            + 1 - float(rec["known_temperature_information"])
                            + 1 - float(rec["known_salinity_information"]))
                except (ValueError, KeyError):
                    pass
            pred = float(self.mlp.predict(
                np.asarray([emb_id_map[eid]], dtype=np.float32),
                vec[np.newaxis, :], device="cpu")[0])
            rec["suitability_score"] = round(float(np.clip(pred, 0, 1)), 4)
            recs.append(rec)
        recs.sort(key=lambda d: (d["suitability_score"], d["confidence_score"]), reverse=True)
        return {"mode": "ml_over_embeddings", "recommendations": recs[:top_k],
                "n_candidates": len(recs),
                "disclaimer": ("ML ranking over frozen ESM-2 embeddings; regresses toward a "
                               "derived compatibility label — not experimental efficiency.")}


def recommend(payload: dict, use_ml: bool = False) -> dict:
    cls = MLRecommender if use_ml else RuleBasedRecommender
    r = cls()
    return r.recommend(payload["pollutant_type"], float(payload["ph"]),
                       float(payload["temperature_c"]), float(payload["salinity"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme explainable inference")
    ap.add_argument("--pollutant", default="PET")
    ap.add_argument("--ph", type=float, default=8.0)
    ap.add_argument("--temperature", type=float, default=35.0)
    ap.add_argument("--salinity", type=float, default=0.5)
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--ml", action="store_true", help="use ML recommender if available")
    args = ap.parse_args(argv)
    cls = MLRecommender if args.ml else RuleBasedRecommender
    r = cls()
    out = r.recommend(args.pollutant, args.ph, args.temperature, args.salinity, args.top_k)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())