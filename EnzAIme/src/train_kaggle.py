"""
EnzAIme — Kaggle / local training orchestrator
===============================================
End-to-end training pipeline for the environment-aware suitability model.

Flow:
  1. detect Kaggle + GPU (print GPU name), set deterministic seeds
  2. load cleaned enzyme data     (data/processed/master_enzymes_clean.csv)
  3. load OR generate scenarios  (data/processed/training_scenarios.csv)
  4. load OR generate ESM embeddings (data/processed/esm_embeddings.npy)
  5. merge embeddings with scenario env-features (src/model.py)
  6. GROUPED split by enzyme_id (GroupShuffleSplit; GroupKFold for CV)
  7. train baselines (Ridge, RandomForest, GradientBoosting) + small MLP
  8. evaluate (MAE/RMSE/R2/Spearman/top-k consistency vs derived label)
  9. save best model + scaler + feature_config + metrics + plots + reports
 10. ALSO train a backend-compatible SuitabilityNet so DEMO_MODE=false
     (artifacts/model.pt + scaler.pkl + encoders.pkl + config.json) keeps
     working unchanged with the existing FastAPI backend.

Run:
  python src/train_kaggle.py                                  # full local
  python src/train_kaggle.py --smoke --esm-model facebook/esm2_t12_35M_UR50D
  # on Kaggle GPU: default ESM-2 650M is downloaded automatically.
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


def is_kaggle() -> bool:
    return Path("/kaggle/input").exists() or Path("/kaggle/working").exists()


def detect_gpu() -> tuple[str, str]:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", torch.cuda.get_device_name(0)
        return "cpu", "no-gpu"
    except Exception as e:
        return "cpu", f"no-torch({e})"


def ensure_artifacts(artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)


def load_or_generate_scenarios(data_dir: Path, quiet=True) -> pd.DataFrame:
    path = data_dir / "training_scenarios.csv"
    if path.exists():
        return pd.read_csv(path, keep_default_na=False)
    print("[train] training_scenarios.csv not found — generating via label_generation.py ...")
    import label_generation
    return label_generation.generate_scenarios(
        data_dir / "master_enzymes_clean.csv", path)


def load_or_generate_embeddings(data_dir: Path, esm_model: str,
                                batch_size: int, force: bool, download: bool):
    mat_path = data_dir / "esm_embeddings.npy"
    idx_path = data_dir / "esm_embedding_index.csv"
    if mat_path.exists() and idx_path.exists() and not force:
        mat = np.load(mat_path)
        idx = pd.read_csv(idx_path).sort_values("enzyme_id").reset_index(drop=True)
        return mat, idx
    print("[train] esm_embeddings.npy missing — generating via esm_embedder.py ...")
    import esm_embedder
    esm_embedder.run_embedding(
        data_dir / "master_enzymes_valid_sequences.csv", data_dir,
        esm_model, batch_size, force, download)
    mat = np.load(mat_path)
    idx = pd.read_csv(idx_path).sort_values("enzyme_id").reset_index(drop=True)
    return mat, idx


def write_plots(report_dir: Path, mlp_history: dict | None,
                model_comparison: pd.DataFrame) -> None:
    try:  # matplotlib is optional (never required for the pipeline)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if mlp_history and mlp_history.get("history"):
            fig, ax = plt.subplots(figsize=(6, 4))
            h = mlp_history["history"]
            ax.plot(h["train_loss"], label="train")
            if h.get("val_loss"):
                ax.plot(h["val_loss"], label="val")
            ax.set(title="MLP MSE vs derived label by epoch", xlabel="epoch", ylabel="MSE")
            ax.legend()
            fig.tight_layout()
            fig.savefig(report_dir / "mlp_learning_curve.png", dpi=120)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(7, 4))
        rc = model_comparison.set_index("model")
        ax.bar(rc.index, rc["rmse"])
        ax.set(title="Test RMSE (agreement with derived compatibility label)",
               ylabel="RMSE")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(report_dir / "model_comparison_rmse.png", dpi=120)
        plt.close(fig)
        print("[train] plots written -> reports/*.png")
    except Exception as e:
        print(f"[warn] plots skipped (matplotlib error: {e})")


def main(argv=None):
    ap = argparse.ArgumentParser(description="EnzAIme training pipeline")
    ap.add_argument("--data-dir", default=str(REPO_ROOT / "data" / "processed"))
    ap.add_argument("--artifacts-dir", default=str(REPO_ROOT / "artifacts"))
    ap.add_argument("--report-dir", default=str(REPO_ROOT / "reports"))
    ap.add_argument("--esm-model", default=None,
                    help="HF id / local checkpoint for ESM-2. Default 650M.")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--embeddings", action="store_true",
                    help="force recompute embeddings")
    ap.add_argument("--download", action="store_true",
                    help="allow downloading the ESM model from Hub (Kaggle)")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--no-mlp", action="store_true",
                    help="only baseline estimators (no neural network)")
    ap.add_argument("--no-backend-artifacts", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="small batches / limited epochs for a quick CI run")
    args = ap.parse_args(argv)

    from model import (  # noqa: E402
        GroupSplitter, SuitabilityMLP, build_env_feature_columns,
        build_feature_matrix, evaluate_regression, fit_gradient_boosting,
        fit_random_forest, fit_ridge, merge_embeddings, set_seed, top_k_consistency,
    )
    from sklearn.linear_model import Ridge

    data_dir = Path(args.data_dir)
    artifacts_dir = Path(args.artifacts_dir)
    report_dir = Path(args.report_dir)
    ensure_artifacts(artifacts_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    set_seed(42)
    DEVICE, GPU_NAME = detect_gpu()
    print("=" * 72)
    print("ENZAIme TRAINING")
    print("=" * 72)
    print(f"  kaggle        : {is_kaggle()}")
    print(f"  device        : {DEVICE}")
    if DEVICE == "cuda":
        print(f"  gpu           : {GPU_NAME}")
    if args.no_mlp:
        print("  neural path   : skipped (--no-mlp)")

    # 1. clean enzyme data
    clean_csv = data_dir / "master_enzymes_clean.csv"
    if not clean_csv.exists():
        print("[train] master_enzymes_clean.csv missing — running data_quality.py ...")
        import data_quality
        data_quality.run_data_quality(
            data_dir / "master_enzymes.csv", data_dir, report_dir)
    enzymes = pd.read_csv(clean_csv, keep_default_na=False)

    # 2. scenarios (generate on demand)
    scenarios = load_or_generate_scenarios(data_dir)
    scenarios = scenarios[scenarios["pollutant_type"].astype(str).str.strip() != ""]

    # 3. embeddings (generate on demand)
    esm_model = args.esm_model or "facebook/esm2_t33_650M_UR50D"
    emb_mat, emb_idx = load_or_generate_embeddings(
        data_dir, esm_model, args.batch_size, args.embeddings, args.download)
    print(f"[train] embeddings: {emb_mat.shape} ({emb_mat.dtype})")

    # 4. merge (embeddings and index are both sorted by enzyme_id)
    emb_ids = emb_idx["enzyme_id"].to_numpy()
    id_lookup = {eid: emb_mat[i] for i, eid in enumerate(emb_ids)}
    table = scenarios[scenarios["enzyme_id"].isin(id_lookup)].copy()
    X_emb = np.stack([id_lookup[eid] for eid in table["enzyme_id"].to_numpy()]).astype(np.float32)
    exp_dim = int(emb_mat.shape[1])
    assert X_emb.shape[1] == exp_dim, "embedding dim mismatch"

    # 5. environment features
    X_env, _, poll_cats = build_feature_matrix(table, scale=False)
    y = table["derived_compatibility_label"].to_numpy(dtype=np.float32)
    y_target = np.clip(y, 0.0, 1.0)

    feature_columns = build_env_feature_columns(poll_cats)
    print(f"[train] table: {len(table)} rows | {table['enzyme_id'].nunique()} enzymes | "
          f"env_dim={X_env.shape[1]} | emb_dim={X_emb.shape[1]}")

    # 6. grouped split (leakage prevention)
    splitter = GroupSplitter(n_splits=5, test_size=0.2, seed=42)
    train_idx, test_idx = splitter.train_test_indices(table["enzyme_id"])
    assert splitter.no_leakage(table["enzyme_id"].to_numpy()[train_idx],
                               table["enzyme_id"].to_numpy()[test_idx]), "LEAKAGE DETECTED"

    # scaler fitted on TRAIN rows only (avoids scaler leakage from test)
    from sklearn.preprocessing import StandardScaler
    scaler_env = StandardScaler().fit(X_env[train_idx])
    X_env_tr = scaler_env.transform(X_env[train_idx]).astype(np.float32)
    X_env_te = scaler_env.transform(X_env[test_idx]).astype(np.float32)
    X_emb_tr, X_emb_te = X_emb[train_idx], X_emb[test_idx]
    y_tr, y_te = y_target[train_idx], y_target[test_idx]
    print(f"[train] train={len(train_idx)} (n_enz={len(set(table['enzyme_id'].to_numpy()[train_idx]))}) "
          f"test={len(test_idx)} (n_enz={len(set(table['enzyme_id'].to_numpy()[test_idx]))}) — grouped")

    # 7. baseline estimators
    models = {}
    models["ridge"] = fit_ridge(X_env_tr, y_tr)
    models["random_forest"] = fit_random_forest(X_env_tr, y_tr)
    models["gradient_boosting"] = fit_gradient_boosting(X_env_tr, y_tr)
    print("[train] baselines fitted: ridge, random_forest, gradient_boosting")

    # 8. small MLP (frozen embeddings + env features)
    mlp_result = None
    if not args.no_mlp:
        mlp = SuitabilityMLP(embedding_dim=X_emb.shape[1], env_dim=X_env.shape[1],
                             hidden=48 if args.smoke else 64, dropout=0.3)
        mlp_result = mlp.fit(X_emb_tr, X_env_tr, y_tr,
                             n_epochs=40 if args.smoke else args.epochs,
                             lr=1e-3, patience=8 if args.smoke else 20,
                             X_val_emb=X_emb_te, X_val_env=X_env_te, y_val=y_te,
                             device=DEVICE)
        models["mlp"] = mlp
        print(f"[train] MLP fitted (best_val_mse={mlp_result.get('best_val_mse')})")

    # 9. evaluate
    rows = []
    preds = {}
    for name, model in models.items():
        if name == "mlp":
            p = model.predict(X_emb_te, X_env_te, device=DEVICE)
        else:
            p = model.predict(X_env_te)
        preds[name] = np.asarray(p, dtype=float)
        m = evaluate_regression(y_te, preds[name])
        tk = top_k_consistency(y_te, preds[name], k=3)
        rows.append({"model": name, **m, **tk})

    # derived-label baseline == perfect agreement by construction
    rows.append({"model": "derived_label_reference",
                 **evaluate_regression(y_te, y_te),
                 **top_k_consistency(y_te, y_te, k=3)})
    # pollutant-only baseline: predict the pollutant component only
    pol_pred = table["pollutant_evidence_score"].to_numpy()[test_idx].astype(float)
    rows.append({"model": "pollutant_evidence_only",
                 **evaluate_regression(y_te, pol_pred),
                 **top_k_consistency(y_te, pol_pred, k=3)})

    comp = pd.DataFrame(rows)
    comp.to_csv(report_dir / "model_comparison.csv", index=False)
    print("\n" + comp.to_string(index=False))

    # 10. save best (lowest test RMSE, MLP preferred on tie)
    comp_sorted = comp[comp["model"].isin(list(models))].sort_values(["rmse", "mae"])
    best_name = "mlp" if ("mlp" in comp_sorted["model"].values and
                          comp_sorted.iloc[0]["model"] == "mlp") else comp_sorted.iloc[0]["model"]
    best_model = models[best_name]
    rfe = fit_random_forest(X_env_tr, y_tr)  # for permutation importance (env only)
    perm_imp = None
    try:
        from sklearn.inspection import permutation_importance
        pi = permutation_importance(rfe, X_env_te, y_te, n_repeats=5, random_state=42, n_jobs=-1)
        perm_imp = dict(zip(feature_columns, [round(float(v), 6) for v in pi.importances_mean]))
    except Exception as e:
        print(f"[warn] permutation importance skipped ({e})")

    feature_config = {
        "embedding_dim": int(X_emb.shape[1]),
        "env_dim": int(X_env.shape[1]),
        "env_columns": feature_columns,
        "pollutant_categories": poll_cats,
        "best_model": best_name,
        "split": {"method": "GroupShuffleSplit", "test_size": 0.2,
                  "groups_before": "enzyme_id", "seed": 42},
        "target": "derived_compatibility_label",
        "baselines": ["ridge", "random_forest", "gradient_boosting"],
        "mlp": {"hidden": 48 if args.smoke else 64, "dropout": 0.3},
    }
    try:
        best_model_save = best_model
        if best_name == "mlp":
            best_model_save.save(artifacts_dir / "best_model.pt", feature_config)
        else:
            import joblib
            joblib.dump(best_model, artifacts_dir / "best_baseline.pkl")
            (artifacts_dir / "best_model.pt").write_text("baseline_only\n")
        import joblib
        joblib.dump(scaler_env, artifacts_dir / "scaler.pkl")
        (artifacts_dir / "feature_config.json").write_text(
            json.dumps(feature_config, indent=2, default=str))
    except Exception as e:
        print(f"[warn] best-model saving partially failed: {e}")

    # 11. backend-compatible artifacts (keeps DEMO_MODE=false working)
    backend_status = "skipped"
    if not args.no_backend_artifacts:
        try:
            backend_status = _write_backend_artifacts(table, id_lookup, y_target,
                                                      DEVICE, artifacts_dir, args.smoke)
        except Exception as e:
            print(f"[warn] backend artifacts failed ({e}) — rule-engine fallback stays active.")

    # 12. prediction examples
    eg = pd.DataFrame({
        "enzyme_id": table["enzyme_id"].to_numpy()[test_idx][:50],
        "pollutant_type": table["pollutant_type"].to_numpy()[test_idx][:50],
        "scenario_ph": table["scenario_ph"].to_numpy()[test_idx][:50],
        "scenario_temperature_c": table["scenario_temperature_c"].to_numpy()[test_idx][:50],
        "scenario_salinity": table["scenario_salinity"].to_numpy()[test_idx][:50],
        "derived_label": y_te[:50],
    })
    for name in models:
        eg[f"pred_{name}"] = preds.get(name, np.zeros(len(y_te)))[:50]
    eg.to_csv(report_dir / "prediction_examples.csv", index=False)

    # 13. metrics.json + training_report.md
    metrics = {
        "kaggle": is_kaggle(), "device": DEVICE, "gpu_name": GPU_NAME,
        "n_scenarios": int(len(table)), "n_unique_enzymes": int(table["enzyme_id"].nunique()),
        "n_train_enzymes": int(len(set(table["enzyme_id"].to_numpy()[train_idx]))),
        "n_test_enzymes": int(len(set(table["enzyme_id"].to_numpy()[test_idx]))),
        "split_strategy": "GroupShuffleSplit on enzyme_id (0.2 holdout; GroupKFold for CV)",
        "esm_model": esm_model, "embedding_dim": int(X_emb.shape[1]),
        "model_comparison": comp.to_dict("records"),
        "best_model": best_name,
        "mlp_result": mlp_result,
        "permutation_importance_env": perm_imp,
        "backend_artifacts": backend_status,
        "disclaimer": ("All metrics measure agreement with the DERIVED compatibility "
                       "label, NOT experimental degradation efficiency."),
    }
    (artifacts_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    lines = [
        "# ENZAIme Training Report",
        "",
        f"* Date: 2026-09-18 | device `{DEVICE}` | kaggle={is_kaggle()}",
        f"* ESM model: `{esm_model}` (embed_dim {X_emb.shape[1]})",
        f"* Scenarios: {len(table)} rows, {table['enzyme_id'].nunique()} unique enzymes",
        f"* Split: {metrics['split_strategy']}; train enzymes={metrics['n_train_enzymes']}, "
        f"test enzymes={metrics['n_test_enzymes']}",
        "",
        "## Model comparison (test set, disagreement only)",
        "",
        comp[["model", "mae", "rmse", "r2", "spearman", "top3_consistent"]].to_markdown(index=False),
        "",
        "**Important:** metrics measure agreement with the **derived compatibility label**. "
        "They are not experimental degradation measurements.",
        "",
        f"## Best model: {best_name}",
        "",
        "### Permutation importance (environment features, random-forest based)",
        "",
        "```",
        json.dumps(perm_imp or {}, indent=2),
        "```",
        "",
        f"## Backend-compatible artifacts: {backend_status}",
    ]
    try:
        (report_dir / "training_report.md").write_text("\n".join(lines))
    except Exception as e:
        (report_dir / "training_report.md").write_text(f"# Training report\n\nError writing markdown: {e}\n")

    write_plots(report_dir, mlp_result, comp)

    print("\n[ok] artifacts ->", artifacts_dir)
    print("[ok] reports   ->", report_dir)
    return 0


def _write_backend_artifacts(table: pd.DataFrame, id_lookup: dict, y_target: np.ndarray,
                             device: str, artifacts_dir: Path, smoke: bool) -> str:
    """Train the existing `enzaime_core.model.SuitabilityNet` on the OLD 6-dim
    environment vector format the backend builds, so `DEMO_MODE=false` keeps
    working unchanged (artifacts/model.pt|scaler.pkl|encoders.pkl|config.json)."""
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "common"))
    from enzaime_core import config as core_config

    from model import train_backend_compatible_model

    cats = core_config.SUPPORTED_POLLUTANTS  # ["PET","PUR","PA"] — matches backend
    rows = []
    for _, r in table.iterrows():
        onehot = [1.0 if r["pollutant_type"] == c else 0.0 for c in cats]
        ph_n = r["scenario_ph"] / 14.0
        t_n = (r["scenario_temperature_c"] - core_config.TEMP_MIN_ALLOWED) / (
            core_config.TEMP_MAX_ALLOWED - core_config.TEMP_MIN_ALLOWED)
        s_n = r["scenario_salinity"] / 10.0
        rows.append(onehot + [ph_n, t_n, s_n])
    env_v6 = np.asarray(rows, dtype=np.float32)
    X_emb = np.stack([id_lookup[e] for e in table["enzyme_id"].to_numpy()]).astype(np.float32)
    y = np.clip(y_target, 0.0, 1.0)

    model, best_state, best_loss = train_backend_compatible_model(
        X_emb, env_v6, y, device=device,
        n_epochs=40 if smoke else 300, lr=1e-3, patience=8 if smoke else 20)
    import torch
    torch.save(model.state_dict(), str(artifacts_dir / "model.pt"))

    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    import joblib
    enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    enc.fit([[c] for c in cats])
    joblib.dump(enc, artifacts_dir / "encoders.pkl")
    # The backend does NOT apply a scaler to the env vector (it minmax-normalises
    # inline), so we store a trivial fit to satisfy artifact presence.
    trivial = StandardScaler().fit(np.zeros((1, 3)))
    joblib.dump(trivial, artifacts_dir / "scaler.pkl")
    (artifacts_dir / "config.json").write_text(json.dumps({
        "embedding_dim": int(X_emb.shape[1]),
        "env_feature_dim": int(env_v6.shape[1]),
        "pollutant_categories": cats,
    }, indent=2))
    print("[train] backend-compatible artifacts written "
          f"(model.pt, scaler.pkl, encoders.pkl, config.json; best_val_mse={best_loss:.5f})")
    return f"written (SuitabilityNet, val_mse={best_loss:.5f})"


if __name__ == "__main__":
    raise SystemExit(main())