#!/usr/bin/env python3
"""
scripts/06_train_model.py
============================
Builds the model-ready training table (embeddings + environment features),
computes the transparent compatibility score as the REFERENCE target
(Section 14 — no real matched enzyme-environment experimental suitability
labels exist), then trains:

  BASELINE 1 : pollutant-only ranking            (Section 15)
  BASELINE 2 : rule-based compatibility score     (Section 15) -- this IS
               the reference target, included for completeness
  PROPOSED   : ESM-2 embedding + environment features -> small neural net
               (Section 13), trained to regress toward the reference score

Data splitting (Section 16): enzyme-level K-fold. Because every synthetic
scenario reuses the same small set of enzymes, a naive row-level split
would leak near-identical rows (same enzyme, slightly different pH/T/S)
across train/test. We split on `enzyme_id` instead so an enzyme's
embedding never appears in both folds.

If torch/transformers are unavailable, or there is not enough data
(config.MIN_TRAINING_ROWS_REQUIRED) to train a scientifically meaningful
model, this script SKIPS the proposed model and leaves the system on the
rule-based compatibility engine (Section 14/37 — REQUIRED fallback). It
never fabricates metrics.

Independently executable: python scripts/06_train_model.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from enzaime_core import config, scoring  # noqa: E402


def build_training_table() -> pd.DataFrame:
    """Cross enzymes (that HAVE evidence for a pollutant) with synthetic
    scenarios for that same pollutant, and compute the reference
    compatibility score for every (enzyme, scenario) pair."""
    enzymes = pd.read_csv(config.CANONICAL_ENZYME_CSV)
    scenarios_path = config.PROCESSED_DIR / "environmental_scenarios.csv"
    if not scenarios_path.exists():
        raise FileNotFoundError(f"{scenarios_path} missing — run scripts/04_generate_scenarios.py first.")
    scenarios = pd.read_csv(scenarios_path)

    rows = []
    for _, erow in enzymes.iterrows():
        matching = scenarios[scenarios["pollutant"].str.upper() == str(erow["pollutant"]).upper()]
        for _, srow in matching.iterrows():
            query = scoring.EnvironmentQuery(
                pollutant=srow["pollutant"], ph=srow["pH"],
                temperature=srow["temperature"], salinity=srow["salinity"],
            )
            score, breakdown = scoring.score_enzyme(erow.to_dict(), query)
            rows.append({
                "enzyme_id": erow["enzyme_id"],
                "pollutant": srow["pollutant"],
                "ph": srow["pH"],
                "temperature": srow["temperature"],
                "salinity": srow["salinity"],
                "reference_score": score,
                "has_sequence": isinstance(erow.get("sequence"), str) and len(str(erow.get("sequence"))) > 0,
            })
    return pd.DataFrame(rows)


def baseline_pollutant_only(df: pd.DataFrame) -> np.ndarray:
    """BASELINE 1: score = 1.0 if the enzyme's pollutant matches the query
    pollutant, else 0.0. Ignores pH/T/S entirely."""
    enzymes = pd.read_csv(config.CANONICAL_ENZYME_CSV).set_index("enzyme_id")["pollutant"]
    return (df["enzyme_id"].map(enzymes).astype(str).str.upper() == df["pollutant"].str.upper()).astype(float).values


def enzyme_level_folds(enzyme_ids: list, n_splits: int = 5, seed: int = 42):
    """Section 16 — enzyme-level K-fold (falls back to a single documented
    holdout if too few unique enzymes exist for K-fold)."""
    unique_ids = sorted(set(enzyme_ids))
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    if len(unique_ids) < n_splits:
        # Too few enzymes for meaningful K-fold cross-validation.
        # Use a single documented 70/30 enzyme-level holdout instead.
        n_test = max(1, round(len(unique_ids) * 0.3))
        test_ids = set(unique_ids[:n_test])
        train_ids = set(unique_ids[n_test:])
        yield train_ids, test_ids
        return

    folds = np.array_split(unique_ids, n_splits)
    for i in range(n_splits):
        test_ids = set(folds[i])
        train_ids = set(unique_ids) - test_ids
        yield train_ids, test_ids


def main():
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    if not config.CANONICAL_ENZYME_CSV.exists():
        print("[ERROR] enzymes.csv missing — run scripts/03_build_master_dataset.py first.")
        return 1

    print("Building model-ready training table (embeddings + environment features + "
          "reference compatibility score) ...")
    table = build_training_table()
    table_path = config.PROCESSED_DIR / "model_ready_dataset.csv"
    table.to_csv(table_path, index=False)
    print(f"Training table: {len(table)} rows across {table['enzyme_id'].nunique()} enzymes -> {table_path}")

    unique_enzymes = table["enzyme_id"].nunique()
    metrics = {
        "n_rows": len(table),
        "n_unique_enzymes": int(unique_enzymes),
        "split_strategy": None,
        "baseline_pollutant_only": {},
        "baseline_rule_based": {},
        "proposed_model": None,
    }

    # --- Enzyme-level split bookkeeping -----------------------------------
    if unique_enzymes < 5:
        metrics["split_strategy"] = (
            f"Only {unique_enzymes} unique enzymes available — full 5-fold "
            "cross-validation is not statistically meaningful. Using a single "
            "documented enzyme-level 70/30 holdout instead (Section 16)."
        )
    else:
        metrics["split_strategy"] = "5-fold enzyme-level cross-validation (no enzyme appears in both train and test of the same fold)."

    fold_maes_baseline1 = []
    fold_maes_rule = []
    pred_pollutant_only = baseline_pollutant_only(table)
    table["pred_pollutant_only"] = pred_pollutant_only

    for train_ids, test_ids in enzyme_level_folds(table["enzyme_id"].tolist()):
        test_mask = table["enzyme_id"].isin(test_ids)
        y_true = table.loc[test_mask, "reference_score"].values
        y_pred_b1 = table.loc[test_mask, "pred_pollutant_only"].values
        fold_maes_baseline1.append(float(np.mean(np.abs(y_true - y_pred_b1))))
        # Baseline 2 (rule-based) == reference score by construction (MAE 0),
        # reported for completeness/transparency per Section 15.
        fold_maes_rule.append(0.0)

    metrics["baseline_pollutant_only"] = {
        "description": "Score = 1.0 if pollutant matches, else 0.0 (ignores pH/T/salinity entirely).",
        "mean_absolute_error_vs_reference": round(float(np.mean(fold_maes_baseline1)), 4),
        "note": "Agreement with the compatibility REFERENCE score, not an experimental accuracy metric.",
    }
    metrics["baseline_rule_based"] = {
        "description": "The transparent compatibility engine itself (Section 11-12) — used as the reference target.",
        "mean_absolute_error_vs_reference": 0.0,
    }

    # --- Proposed model (optional, requires torch + enough data + embeddings)
    try:
        import torch
    except Exception as e:
        print(f"[SKIP] torch unavailable ({e}) — proposed neural model not trained. "
              "System remains on the rule-based compatibility engine (Section 14/37, REQUIRED fallback).")
        torch = None

    n_with_seq = int(table["has_sequence"].sum())
    embeddings_available = config.EMBEDDINGS_DIR.exists() and any(config.EMBEDDINGS_DIR.glob("*.npy"))

    if torch is not None and n_with_seq >= config.MIN_TRAINING_ROWS_REQUIRED and embeddings_available:
        metrics["proposed_model"] = _train_proposed_model(table)
    else:
        reasons = []
        if torch is None:
            reasons.append("torch not installed")
        if n_with_seq < config.MIN_TRAINING_ROWS_REQUIRED:
            reasons.append(
                f"only {n_with_seq} rows have a known sequence "
                f"(need >= {config.MIN_TRAINING_ROWS_REQUIRED} for a scientifically meaningful fit)"
            )
        if not embeddings_available:
            reasons.append("no cached ESM-2 embeddings found (run scripts/05_generate_embeddings.py)")
        print("[SKIP] Proposed neural model not trained: " + "; ".join(reasons) + ".")
        print("       This is an EXPECTED, REQUIRED fallback path for the MVP (Section 14/37): "
              "the backend serves recommendations via the rule-based compatibility engine instead.")
        metrics["proposed_model"] = {
            "trained": False,
            "reason": "; ".join(reasons),
        }

    (config.ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    print(f"\nMetrics written -> {config.ARTIFACTS_DIR / 'metrics.json'}")
    print(json.dumps(metrics, indent=2, default=str))
    return 0


def _train_proposed_model(table: pd.DataFrame) -> dict:
    """Trains the small fusion network (Section 13) with early stopping.
    Only called when torch + transformers + enough labeled rows + cached
    embeddings are all available."""
    import torch
    import torch.nn as nn
    from enzaime_core import embeddings as emb_mod
    from enzaime_core.model import SuitabilityNet
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    import joblib

    cached = emb_mod.load_all_cached_embeddings()
    table = table[table["enzyme_id"].isin(cached.keys())].reset_index(drop=True)

    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    pollutant_oh = encoder.fit_transform(table[["pollutant"]])
    scaler = StandardScaler()
    num_feats = scaler.fit_transform(table[["ph", "temperature", "salinity"]])
    env_features = np.concatenate([pollutant_oh, num_feats], axis=1).astype(np.float32)

    embedding_dim = next(iter(cached.values())).shape[0]
    X_emb = np.stack([cached[eid] for eid in table["enzyme_id"]]).astype(np.float32)
    y = table["reference_score"].values.astype(np.float32)

    unique_enzymes = table["enzyme_id"].unique().tolist()
    fold_iter = enzyme_level_folds(table["enzyme_id"].tolist())
    train_ids, test_ids = next(fold_iter)
    train_mask = table["enzyme_id"].isin(train_ids).values
    test_mask = ~train_mask

    model = SuitabilityNet(embedding_dim=embedding_dim, env_feature_dim=env_features.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE, weight_decay=config.WEIGHT_DECAY)
    loss_fn = nn.MSELoss()

    X_emb_t = torch.tensor(X_emb)
    env_t = torch.tensor(env_features)
    y_t = torch.tensor(y)

    best_val, patience, best_state = float("inf"), 0, None
    for epoch in range(config.MAX_EPOCHS):
        model.train()
        optimizer.zero_grad()
        pred = model(X_emb_t[train_mask], env_t[train_mask])
        loss = loss_fn(pred, y_t[train_mask])
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_emb_t[test_mask], env_t[test_mask])
            val_loss = loss_fn(val_pred, y_t[test_mask]).item()
        if val_loss < best_val - 1e-5:
            best_val, patience = val_loss, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
            if patience >= config.EARLY_STOPPING_PATIENCE:
                break

    if best_state:
        model.load_state_dict(best_state)

    torch.save(model.state_dict(), config.ARTIFACTS_DIR / "model.pt")
    joblib.dump(scaler, config.ARTIFACTS_DIR / "scaler.pkl")
    joblib.dump(encoder, config.ARTIFACTS_DIR / "encoders.pkl")
    (config.ARTIFACTS_DIR / "config.json").write_text(json.dumps({
        "embedding_dim": embedding_dim,
        "env_feature_dim": env_features.shape[1],
        "pollutant_categories": encoder.categories_[0].tolist(),
    }, indent=2))

    return {
        "trained": True,
        "n_rows_used": int(train_mask.sum() + test_mask.sum()),
        "n_train_enzymes": len(train_ids),
        "n_test_enzymes": len(test_ids),
        "best_val_mse_vs_reference": round(float(best_val), 5),
        "note": "MSE is agreement with the compatibility REFERENCE score (Section 14), not experimental accuracy.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
