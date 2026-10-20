"""Exploratory nested protein-grouped model selection; never replaces served artifacts.

Primary objective: pooled inner-fold MAE in original uM. Secondary, separately
reported selection: pooled inner-fold RMSE. Outer folds are never used to tune.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import sklearn
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/tpa_pet_ml_confirmed.csv"
ENV = ["temperature_c", "ph", "duration_hours"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(actual, predicted, groups=None):
    result = {"mae_um": float(mean_absolute_error(actual, predicted)),
              "rmse_um": float(mean_squared_error(actual, predicted)**.5),
              "r2": float(r2_score(actual, predicted)) if np.ptp(actual) else None,
              "spearman": float(spearmanr(actual, predicted).statistic) if np.ptp(actual) and np.ptp(predicted) else None}
    if groups is not None:
        result["macro_protein_mae_um"] = float(np.mean([mean_absolute_error(actual[groups == g], predicted[groups == g]) for g in np.unique(groups)]))
    return result


def candidate_specs():
    return [
        dict(name="training_median", features="env", model="median", target="raw"),
        dict(name="environment_log_ridge_10", features="env", model="ridge", target="log", alpha=10),
        dict(name="environment_raw_ridge_10", features="env", model="ridge", target="raw", alpha=10),
        dict(name="environment_raw_ridge_100", features="env", model="ridge", target="raw", alpha=100),
        dict(name="environment_quadratic_log_ridge", features="env_poly", model="ridge", target="log", alpha=100),
        dict(name="combined_log_ridge", features="combined", model="ridge", target="log", alpha=100),
        dict(name="protein_condition_interactions_100", features="interactions", model="ridge", target="log", alpha=100),
        dict(name="protein_condition_interactions_1000", features="interactions", model="ridge", target="log", alpha=1000),
        dict(name="environment_raw_forest_depth3", features="env", model="forest", target="raw", depth=3),
        dict(name="environment_raw_forest_depth5", features="env", model="forest", target="raw", depth=5),
        dict(name="environment_log_forest", features="env", model="forest", target="log", depth=5),
        dict(name="combined_raw_forest", features="combined", model="forest", target="raw", depth=5),
        dict(name="combined_raw_extra_trees", features="combined", model="extra", target="raw", depth=5),
    ]


def feature_pair(environment, embeddings, groups, train, test, kind):
    """Every learned transform sees train only, including unique-protein PCA."""
    train_env, test_env = environment[train], environment[test]
    if kind == "env_poly":
        polynomial = PolynomialFeatures(degree=2, include_bias=False)
        train_env = polynomial.fit_transform(train_env)
        test_env = polynomial.transform(test_env)
    if kind in ("env", "env_poly"):
        scaler = StandardScaler().fit(train_env)
        return scaler.transform(train_env), scaler.transform(test_env)
    _, first = np.unique(groups[train], return_index=True)
    unique_train = embeddings[train[first]]
    embedding_scaler = StandardScaler().fit(unique_train)
    components = min(5, len(first) - 1)
    if components < 1:
        raise ValueError("Need at least two training proteins for PCA.")
    pca = PCA(n_components=components, svd_solver="full").fit(embedding_scaler.transform(unique_train))
    train_pc = pca.transform(embedding_scaler.transform(embeddings[train]))
    test_pc = pca.transform(embedding_scaler.transform(embeddings[test]))
    if kind == "interactions":
        env_scaler = StandardScaler().fit(train_env)
        train_env, test_env = env_scaler.transform(train_env), env_scaler.transform(test_env)
        pc_scaler = StandardScaler().fit(train_pc)
        train_pc, test_pc = pc_scaler.transform(train_pc), pc_scaler.transform(test_pc)
        train_cross = (train_pc[:, :, None] * train_env[:, None, :]).reshape(len(train), -1)
        test_cross = (test_pc[:, :, None] * test_env[:, None, :]).reshape(len(test), -1)
        train_features = np.hstack([train_pc, train_env, train_cross])
        test_features = np.hstack([test_pc, test_env, test_cross])
    else:
        train_features, test_features = np.hstack([train_pc, train_env]), np.hstack([test_pc, test_env])
    scaler = StandardScaler().fit(train_features)
    return scaler.transform(train_features), scaler.transform(test_features)


def predict_spec(spec, features, target):
    if spec["model"] == "median":
        model = DummyRegressor(strategy="median")
    elif spec["model"] == "ridge":
        model = Ridge(alpha=spec["alpha"])
    else:
        constructor = RandomForestRegressor if spec["model"] == "forest" else ExtraTreesRegressor
        model = constructor(n_estimators=200, max_depth=spec["depth"], min_samples_leaf=5, random_state=42, n_jobs=1)
    transformed = np.log1p(target) if spec["target"] == "log" else target
    model.fit(features[0], transformed)
    prediction = model.predict(features[1])
    if spec["target"] == "log":
        prediction = np.expm1(prediction)
    if not np.isfinite(prediction).all():
        raise ValueError(f"Non-finite predictions from {spec['name']}; do not silently omit a fold.")
    return np.maximum(0, prediction)


def manifest_split(groups, train, test):
    assert not set(groups[train]) & set(groups[test])
    return {"train_rows": train.tolist(), "test_rows": test.tolist(),
            "train_proteins": sorted(set(groups[train])), "test_proteins": sorted(set(groups[test]))}


def select_inner(specs, target, groups, outer_train, environment, embeddings):
    predictions = {spec["name"]: np.full(len(target), np.nan) for spec in specs}
    manifests = []
    for relative_train, relative_test in GroupKFold(n_splits=3).split(outer_train, groups=groups[outer_train]):
        train, test = outer_train[relative_train], outer_train[relative_test]
        manifests.append(manifest_split(groups, train, test))
        cache = {}
        for spec in specs:
            kind = spec["features"]
            if kind not in cache:
                cache[kind] = feature_pair(environment, embeddings, groups, train, test, kind)
            predictions[spec["name"]][test] = predict_spec(spec, cache[kind], target[train])
    scores = {name: metrics(target[outer_train], prediction[outer_train], groups[outer_train]) for name, prediction in predictions.items()}
    selected = {objective: min(specs, key=lambda spec: (scores[spec["name"]][objective], spec["name"])) for objective in ("mae_um", "rmse_um")}
    return selected, scores, manifests


def original_baseline(environment, embeddings, target, train, test, combined):
    if combined:
        scaler = StandardScaler().fit(embeddings[train])
        train_emb, test_emb = scaler.transform(embeddings[train]), scaler.transform(embeddings[test])
        pca = PCA(n_components=10, random_state=42)
        train_pc, test_pc = pca.fit_transform(train_emb), pca.transform(test_emb)
        train_x, test_x = np.hstack([train_pc, environment[train]]), np.hstack([test_pc, environment[test]])
    else:
        train_x, test_x = environment[train], environment[test]
    scaler = StandardScaler().fit(train_x)
    prediction = Ridge(alpha=10).fit(scaler.transform(train_x), np.log1p(target[train])).predict(scaler.transform(test_x))
    return np.expm1(prediction)  # Reproduce original A/C, including no clipping.


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    frame = pd.read_csv(DATA, dtype=str, keep_default_na=False)
    index_path = ROOT / "data/embeddings/index.json"
    index = json.loads(index_path.read_text())
    groups = frame.protein_id.to_numpy()
    embedding_paths = sorted({ROOT / "data/embeddings" / index[g] for g in groups})
    preserved_paths = [DATA, index_path, *embedding_paths, *sorted((ROOT / "models").glob("*")),
                       ROOT / "reports/results/controlled_ablation_results.json",
                       ROOT / "reports/results/ablation_error_analysis/pooled_metrics.csv"]
    before = {str(p.relative_to(ROOT)): digest(p) for p in preserved_paths if p.is_file()}
    environment = frame[ENV].astype(float).to_numpy()
    embeddings = np.vstack([np.load(ROOT / "data/embeddings" / index[g], allow_pickle=False) for g in groups])
    target = frame.target_value_standardized.astype(float).to_numpy()
    assert len(target) == 221 and len(set(groups)) == 25
    assert np.isfinite(environment).all() and np.isfinite(embeddings).all() and np.isfinite(target).all() and (target >= 0).all()
    # Identical sequences under different IDs would defeat protein-ID isolation.
    assert frame.groupby("sequence").protein_id.nunique().max() == 1
    specs = candidate_specs()
    config = {"created_utc": datetime.now(timezone.utc).isoformat(), "primary_objective": "mae_um", "secondary_objective": "rmse_um",
              "outer_folds": 5, "inner_folds": 3, "grouping": "protein_id", "seed": 42, "features": ENV + ["frozen ESM-2"],
              "candidates": specs, "python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__,
              "script_sha256": digest(Path(__file__)), "input_sha256": before,
              "interpretation": "Exploratory nested CV on an already studied dataset; not an independent external validation. No production promotion."}
    (output / "config.json").write_text(json.dumps(config, indent=2))
    predictions = {name: np.full(len(target), np.nan) for name in ("baseline_A", "baseline_C", "nested_MAE", "nested_RMSE")}
    fold_rows, manifests, selections = [], [], []
    assignments = np.zeros(len(target), dtype=int)
    for fold, (train, test) in enumerate(GroupKFold(n_splits=5).split(environment, target, groups), 1):
        print(f"Outer fold {fold}/5: {len(train)} training / {len(test)} test rows", flush=True)
        outer_manifest = manifest_split(groups, train, test)
        selected, scores, inner = select_inner(specs, target, groups, train, environment, embeddings)
        outer_manifest.update(fold=fold, inner_splits=inner)
        manifests.append(outer_manifest)
        selections.append({"fold": fold, "selected": selected, "inner_scores": scores})
        for objective, name in (("mae_um", "nested_MAE"), ("rmse_um", "nested_RMSE")):
            spec = selected[objective]
            features = feature_pair(environment, embeddings, groups, train, test, spec["features"])
            predictions[name][test] = predict_spec(spec, features, target[train])
            print(f"  {name}: {spec['name']}", flush=True)
        for name in ("baseline_A", "baseline_C"):
            predictions[name][test] = original_baseline(environment, embeddings, target, train, test, name == "baseline_C")
        for name in predictions:
            fold_rows.append({"fold": fold, "model": name, "records": len(test), **metrics(target[test], predictions[name][test], groups[test])})
        assignments[test] = fold
    assert (assignments > 0).all() and all(np.isfinite(p).all() for p in predictions.values())
    pooled = {name: metrics(target, values, groups) for name, values in predictions.items()}
    archived = pd.read_csv(ROOT / "reports/results/ablation_error_analysis/pooled_metrics.csv").set_index("configuration")
    for label in ("A", "C"):
        for metric in ("mae_um", "rmse_um", "r2"):
            np.testing.assert_allclose(pooled[f"baseline_{label}"][metric], archived.loc[label, metric], rtol=1e-4, atol=1e-4)
    for path, expected in before.items():
        assert digest(ROOT / path) == expected, f"Protected input changed: {path}"
    oof = pd.DataFrame({"row_index": np.arange(len(target)), "protein_id": groups, "protein_name": frame.protein_name, "fold": assignments,
                        "actual_um": target, **predictions})
    oof.to_csv(output / "oof_predictions.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(output / "fold_metrics.csv", index=False)
    protein_rows = []
    for name, prediction in predictions.items():
        for protein in np.unique(groups):
            mask = groups == protein
            protein_rows.append({"model": name, "protein_id": protein, "records": int(mask.sum()), **metrics(target[mask], prediction[mask])})
    pd.DataFrame(protein_rows).to_csv(output / "protein_metrics.csv", index=False)
    (output / "fold_manifest.json").write_text(json.dumps(manifests, indent=2))
    (output / "selection.json").write_text(json.dumps(selections, indent=2))
    summary = {"pooled": pooled, "preserved_input_count": len(before), "baseline_reproduction_passed": True,
               "primary": "nested_MAE", "secondary": "nested_RMSE", "limitations": config["interpretation"]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    lines = ["# Exploratory model improvement: nested protein-grouped evaluation", "",
             "Primary selection minimizes inner pooled MAE; secondary selection minimizes inner pooled RMSE. All reported scores below use the same untouched outer test proteins. Original A/C baselines were reproduced and checked against archived metrics.", "",
             "| Procedure | Pooled MAE (uM) | Pooled RMSE (uM) | Pooled R2 | Spearman | Macro-protein MAE (uM) |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, scores in pooled.items():
        lines.append(f"| {name} | {scores['mae_um']:.3f} | {scores['rmse_um']:.3f} | {scores['r2']:.5f} | {scores['spearman']:.5f} | {scores['macro_protein_mae_um']:.3f} |")
    lines += ["", "## Interpretation", "", config["interpretation"],
              "Only 25 proteins are available. Near-homologs are not separated by sequence clusters. Repeated conditions with different measurements and incomplete assay-context features limit achievable accuracy. Lower MAE can coexist with worse RMSE, correlation, or protein-balanced error. A negative R2 remains a poor result relative to the test-set mean reference.",
              "", "All candidate settings were saved before model fitting. Candidate selection occurs solely within each outer training fold. PCA uses unique training proteins and up to five components; interactions allow different condition responses by protein representation. Reference baselines retain their original repeated-row PCA and no clipping. New candidate predictions are clipped at zero after any log inverse transformation. No test-row deletion, target editing, new embeddings, or served-model replacement occurred.",
              "", "`fold_manifest.json` records outer and inner row/protein membership; `selection.json` records every inner score and chosen candidate. `oof_predictions.csv`, `fold_metrics.csv`, and `protein_metrics.csv` retain the complete evaluation. `config.json` records hashes, runtime, and candidate settings.",
              "", "Nested selection method: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html",
              f"\nVerified {len(before)} protected files unchanged."]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/results" / ("nested_improvement_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        run(args.output)
