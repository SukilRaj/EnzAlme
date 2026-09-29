"""Step 4: fold-level error and generalization analysis for the ablation study."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from run_controlled_ablation import (
    CONFIGURATION_INFO,
    DATASET_PATH,
    EMBEDDING_INDEX_PATH,
    EMBEDDINGS_DIR,
    ENVIRONMENT_COLUMNS,
    PCA_COMPONENTS,
    PROJECT_ROOT,
    RANDOM_SEED,
    build_group_splits,
    load_embeddings,
)


OUTPUT_DIR = PROJECT_ROOT / "reports" / "results" / "ablation_error_analysis"
EXISTING_RESULTS_PATH = PROJECT_ROOT / "reports" / "results" / "controlled_ablation_results.csv"
CONFIGURATIONS = ["A", "B", "C"]


def metric_or_undefined(metric_name, value, reason=None):
    if reason:
        return {"value": None, "status": "undefined", "reason": reason}
    return {"value": float(value), "status": "defined", "reason": None}


def spearman_metric(actual, predicted):
    if len(actual) < 2:
        return metric_or_undefined("spearman", None, "fewer than two observations")
    if np.allclose(actual, actual[0]):
        return metric_or_undefined("spearman", None, "constant actual target")
    if np.allclose(predicted, predicted[0]):
        return metric_or_undefined("spearman", None, "constant predictions")
    value = spearmanr(actual, predicted).statistic
    if not np.isfinite(value):
        return metric_or_undefined("spearman", None, "non-finite correlation")
    return metric_or_undefined("spearman", value)


def regression_metrics(actual, predicted):
    residual = actual - predicted
    sse = float(np.sum(residual ** 2))
    centered = actual - np.mean(actual)
    sst = float(np.sum(centered ** 2))
    metrics = {
        "mae_um": metric_or_undefined("mae_um", mean_absolute_error(actual, predicted)),
        "rmse_um": metric_or_undefined("rmse_um", np.sqrt(mean_squared_error(actual, predicted))),
        "r2": metric_or_undefined(
            "r2", 1.0 - sse / sst if sst > 0 else None,
            "constant actual target; SST is zero" if sst == 0 else None,
        ),
        "spearman": spearman_metric(actual, predicted),
        "sse": metric_or_undefined("sse", sse),
        "sst": metric_or_undefined("sst", sst),
    }
    return metrics


def metric_value(metrics, name):
    return metrics[name]["value"]


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def target_summary(values):
    values = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(values)) if len(values) else None,
        "median": float(np.median(values)) if len(values) else None,
        "max": float(np.max(values)) if len(values) else None,
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else None,
        "std_status": "defined" if len(values) > 1 else "undefined: fewer than two observations",
    }


def predict_configuration(df, embeddings, config_name, train_idx, test_idx):
    train_df = df.iloc[train_idx]
    test_df = df.iloc[test_idx]
    y_train_log = np.log1p(train_df["target_value_standardized"].astype(float).to_numpy())

    if config_name == "A":
        train_features = train_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        test_features = test_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        scaler = StandardScaler()
        train_features = scaler.fit_transform(train_features)
        test_features = scaler.transform(test_features)
    elif config_name == "B":
        scaler = StandardScaler()
        train_features = scaler.fit_transform(embeddings[train_idx])
        test_features = scaler.transform(embeddings[test_idx])
        pca = PCA(n_components=PCA_COMPONENTS, random_state=RANDOM_SEED)
        train_features = pca.fit_transform(train_features)
        test_features = pca.transform(test_features)
    elif config_name == "C":
        esm_scaler = StandardScaler()
        train_esm = esm_scaler.fit_transform(embeddings[train_idx])
        test_esm = esm_scaler.transform(embeddings[test_idx])
        pca = PCA(n_components=PCA_COMPONENTS, random_state=RANDOM_SEED)
        train_esm = pca.fit_transform(train_esm)
        test_esm = pca.transform(test_esm)
        train_env = train_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        test_env = test_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        train_features = np.hstack([train_esm, train_env])
        test_features = np.hstack([test_esm, test_env])
        final_scaler = StandardScaler()
        train_features = final_scaler.fit_transform(train_features)
        test_features = final_scaler.transform(test_features)
    else:
        raise ValueError(f"Unsupported configuration: {config_name}")

    model = Ridge(alpha=10)
    model.fit(train_features, y_train_log)
    return np.expm1(model.predict(test_features))


def make_prediction_table(df, embeddings, splits):
    rows = []
    for config_name in CONFIGURATIONS:
        for fold_number, (train_idx, test_idx) in enumerate(splits, start=1):
            predictions = predict_configuration(df, embeddings, config_name, train_idx, test_idx)
            actual = df.iloc[test_idx]["target_value_standardized"].astype(float).to_numpy()
            for row_position, source_row_id in enumerate(test_idx):
                residual = float(actual[row_position] - predictions[row_position])
                rows.append(
                    {
                        "source_row_id": int(source_row_id),
                        "source_record_id": str(df.iloc[source_row_id].get("source_record_id", "")),
                        "protein_id": str(df.iloc[source_row_id]["protein_id"]),
                        "configuration": config_name,
                        "fold": fold_number,
                        "actual_target_um": float(actual[row_position]),
                        "predicted_target_um": float(predictions[row_position]),
                        "residual_um": residual,
                        "absolute_error_um": abs(residual),
                        "squared_error_um2": residual ** 2,
                    }
                )
    result = pd.DataFrame(rows)
    result["configuration"] = pd.Categorical(result["configuration"], CONFIGURATIONS, ordered=True)
    return result.sort_values(["configuration", "source_row_id"]).reset_index(drop=True)


def make_fold_table(df, predictions):
    rows = []
    for (config_name, fold), group in predictions.groupby(["configuration", "fold"], observed=True):
        test_indices = group["source_row_id"].to_numpy()
        test_df = df.iloc[test_indices]
        train_df = df.loc[~df.index.isin(test_indices)]
        actual = group["actual_target_um"].to_numpy()
        predicted = group["predicted_target_um"].to_numpy()
        metrics = regression_metrics(actual, predicted)
        train_proteins = sorted(train_df["protein_id"].astype(str).unique().tolist())
        test_proteins = sorted(test_df["protein_id"].astype(str).unique().tolist())
        rows.append(
            {
                "configuration": str(config_name),
                "fold": int(fold),
                "train_records": int(len(train_df)),
                "test_records": int(len(test_df)),
                "train_proteins": int(train_df["protein_id"].nunique()),
                "test_proteins": int(test_df["protein_id"].nunique()),
                "test_protein_ids": ";".join(test_proteins),
                "train_target_min_um": target_summary(train_df["target_value_standardized"].astype(float))["min"],
                "train_target_median_um": target_summary(train_df["target_value_standardized"].astype(float))["median"],
                "train_target_max_um": target_summary(train_df["target_value_standardized"].astype(float))["max"],
                "train_target_std_um": target_summary(train_df["target_value_standardized"].astype(float))["std"],
                "test_target_min_um": target_summary(actual)["min"],
                "test_target_median_um": target_summary(actual)["median"],
                "test_target_max_um": target_summary(actual)["max"],
                "test_target_std_um": target_summary(actual)["std"],
                "mae_um": metric_value(metrics, "mae_um"),
                "rmse_um": metric_value(metrics, "rmse_um"),
                "r2": metric_value(metrics, "r2"),
                "spearman": metric_value(metrics, "spearman"),
                "sse_um2": metric_value(metrics, "sse"),
                "sst_um2": metric_value(metrics, "sst"),
                "r2_formula": "1 - SSE/SST",
                "undefined_metrics": "; ".join(
                    f"{name}: {details['reason']}"
                    for name, details in metrics.items()
                    if details["status"] == "undefined"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["configuration", "fold"]).reset_index(drop=True)


def make_protein_table(predictions):
    total_sse = predictions.groupby("configuration", observed=True)["squared_error_um2"].sum()
    rows = []
    for (config_name, protein_id), group in predictions.groupby(["configuration", "protein_id"], observed=True):
        actual = group["actual_target_um"].to_numpy()
        predicted = group["predicted_target_um"].to_numpy()
        metrics = regression_metrics(actual, predicted)
        sse = float(group["squared_error_um2"].sum())
        summary = target_summary(actual)
        rows.append(
            {
                "configuration": str(config_name),
                "protein_id": str(protein_id),
                "record_count": int(len(group)),
                "target_min_um": summary["min"],
                "target_median_um": summary["median"],
                "target_max_um": summary["max"],
                "target_std_um": summary["std"],
                "mae_um": metric_value(metrics, "mae_um"),
                "rmse_um": metric_value(metrics, "rmse_um"),
                "sse_um2": sse,
                "share_total_squared_error": sse / float(total_sse[config_name]) if total_sse[config_name] else None,
                "r2": metric_value(metrics, "r2"),
                "spearman": metric_value(metrics, "spearman"),
                "undefined_metrics": "; ".join(
                    f"{name}: {details['reason']}"
                    for name, details in metrics.items()
                    if details["status"] == "undefined"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["configuration", "sse_um2"], ascending=[True, False]).reset_index(drop=True)


def make_comparison_table(predictions):
    wide = predictions.pivot(index=["source_row_id", "protein_id", "fold"], columns="configuration", values=["actual_target_um", "predicted_target_um", "absolute_error_um", "squared_error_um2"])
    wide.columns = ["_".join(column) for column in wide.columns]
    wide = wide.reset_index()
    for left, right, label in [("A", "C", "A_vs_C"), ("B", "C", "B_vs_C")]:
        wide[f"{label}_prediction_delta_um"] = wide[f"predicted_target_um_{right}"] - wide[f"predicted_target_um_{left}"]
        wide[f"{label}_absolute_error_delta_um"] = wide[f"absolute_error_um_{right}"] - wide[f"absolute_error_um_{left}"]
        wide[f"{label}_squared_error_delta_um2"] = wide[f"squared_error_um2_{right}"] - wide[f"squared_error_um2_{left}"]
    return wide.sort_values("source_row_id").reset_index(drop=True)


def pooled_metrics(predictions):
    rows = []
    for config_name, group in predictions.groupby("configuration", observed=True):
        metrics = regression_metrics(group["actual_target_um"].to_numpy(), group["predicted_target_um"].to_numpy())
        rows.append(
            {
                "configuration": str(config_name),
                "record_count": int(len(group)),
                "mae_um": metric_value(metrics, "mae_um"),
                "rmse_um": metric_value(metrics, "rmse_um"),
                "r2": metric_value(metrics, "r2"),
                "spearman": metric_value(metrics, "spearman"),
                "sse_um2": metric_value(metrics, "sse"),
                "sst_um2": metric_value(metrics, "sst"),
                "r2_formula": "1 - SSE/SST",
            }
        )
    return pd.DataFrame(rows).sort_values("configuration").reset_index(drop=True)


def save_plots(predictions, protein_metrics):
    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    for axis, config_name in zip(axes, CONFIGURATIONS):
        group = predictions[predictions["configuration"] == config_name]
        axis.scatter(group["actual_target_um"], group["predicted_target_um"], alpha=0.65, s=20)
        limits = [0, max(group["actual_target_um"].max(), group["predicted_target_um"].max()) * 1.05]
        axis.plot(limits, limits, "k--", linewidth=1)
        axis.set_title(f"{config_name}: actual vs predicted")
        axis.set_xlabel("Actual target (uM)")
        axis.set_ylabel("Predicted target (uM)")
    figure.savefig(OUTPUT_DIR / "actual_vs_predicted.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    for axis, config_name in zip(axes, CONFIGURATIONS):
        group = protein_metrics[protein_metrics["configuration"] == config_name].sort_values("sse_um2", ascending=False)
        axis.bar(group["protein_id"], group["sse_um2"])
        axis.set_title(f"{config_name}: protein squared error")
        axis.set_xlabel("Protein ID")
        axis.set_ylabel("SSE (uM^2)")
        axis.tick_params(axis="x", rotation=75)
    figure.savefig(OUTPUT_DIR / "per_protein_squared_error.png", dpi=180)
    plt.close(figure)


def verify_reproduction(fold_metrics):
    existing = pd.read_csv(EXISTING_RESULTS_PATH)
    merged = fold_metrics.merge(existing, on=["configuration", "fold"], suffixes=("_analysis", "_existing"))
    checks = {}
    for metric_name in ["mae_um", "rmse_um", "r2", "spearman"]:
        analysis = merged[f"{metric_name}_analysis"]
        existing_values = pd.to_numeric(merged[f"{metric_name}_existing"], errors="coerce")
        valid = analysis.notna() & existing_values.notna()
        checks[metric_name] = {
            "max_absolute_difference": float(np.max(np.abs(analysis[valid] - existing_values[valid]))) if valid.any() else None,
            "all_within_tolerance": bool(np.allclose(analysis[valid], existing_values[valid], rtol=1e-9, atol=1e-8)) if valid.any() else True,
            "undefined_match": bool((~analysis.notna()).equals(~existing_values.notna())),
        }
    return checks


def make_report(df, fold_metrics, protein_metrics, pooled, comparisons, reproduction):
    lines = [
        "# Step 4: Fold-Level Error and Generalization Analysis",
        "",
        "## Reproduction and scope",
        "",
        f"The analysis uses the confirmed dataset with {len(df)} records and {df['protein_id'].nunique()} proteins. No ambiguous records, embeddings, source data, production models, or existing reports were modified.",
        "",
        "No row-level out-of-fold prediction artifact was available, so predictions were reproduced with the original A/B/C implementation: GroupKFold(n_splits=5) by protein_id, train-fold-only StandardScaler/PCA, Ridge(alpha=10), log1p target transformation, and expm1 back-transformation. The original implementation contains no prediction clipping.",
        "",
        "Reproduction check:",
        "",
        "| Metric | Max absolute difference | Within tolerance | Undefined status matched |",
        "|---|---:|---|---|",
    ]
    for metric_name, check in reproduction.items():
        lines.append(f"| {metric_name} | {check['max_absolute_difference']} | {check['all_within_tolerance']} | {check['undefined_match']} |")
    lines += [
        "",
        "## Fold-level metrics",
        "",
        "The full fold table is in `fold_metrics.csv`. SSE is the sum of squared residuals, SST is the sum of squared deviations from the fold target mean, and R² is calculated as `1 - SSE/SST`. Undefined values remain blank in CSV and are described in `undefined_metrics`.",
        "",
        "| Configuration | Fold | Test proteins | Test records | MAE | RMSE | R² | Spearman | SSE | SST |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in fold_metrics.iterrows():
        lines.append(f"| {row.configuration} | {row.fold} | {row.test_protein_ids} | {row.test_records} | {row.mae_um:.4f} | {row.rmse_um:.4f} | {row.r2:.4f} | {row.spearman if pd.notna(row.spearman) else 'undefined'} | {row.sse_um2:.4f} | {row.sst_um2:.4f} |")

    lines += ["", "## Pooled versus mean-fold metrics", "", "| Configuration | Pooled MAE | Pooled RMSE | Pooled R² | Mean fold MAE | Mean fold RMSE | Mean fold R² |", "|---|---:|---:|---:|---:|---:|---:|"]
    for config_name in CONFIGURATIONS:
        pooled_row = pooled[pooled.configuration == config_name].iloc[0]
        folds = fold_metrics[fold_metrics.configuration == config_name]
        lines.append(f"| {config_name} | {pooled_row.mae_um:.4f} | {pooled_row.rmse_um:.4f} | {pooled_row.r2:.4f} | {folds.mae_um.mean():.4f} | {folds.rmse_um.mean():.4f} | {folds.r2.mean():.4f} |")

    lines += ["", "## Main error-contributing proteins", "", "The ten largest protein-level SSE contributions per configuration are in `top_squared_error_proteins.csv`. The corresponding largest rows are in `top_squared_error_rows.csv`.", ""]
    for config_name in CONFIGURATIONS:
        top = protein_metrics[protein_metrics.configuration == config_name].head(5)
        names = ", ".join(f"{row.protein_id} ({row.share_total_squared_error:.1%})" for _, row in top.iterrows())
        lines.append(f"- {config_name}: {names}")

    lines += ["", "## Extreme R² evidence", "", "The most extreme fold-level R² values are interpreted with SSE and SST together. A large negative R² requires SSE to be large relative to SST; low target variance makes SST small and amplifies that ratio.", ""]
    extreme = fold_metrics.sort_values("r2").head(5)
    lines.append("| Configuration | Fold | R² | SSE | SST | Test target std | Interpretation |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for _, row in extreme.iterrows():
        lines.append(f"| {row.configuration} | {row.fold} | {row.r2:.4f} | {row.sse_um2:.2f} | {row.sst_um2:.2f} | {row.test_target_std_um:.4f} | SSE/SST = {row.sse_um2 / row.sst_um2:.2f}; both error magnitude and target variance must be considered |")

    lines += ["", "## Within-protein A/C and B/C comparisons", "", "`within_protein_comparisons.csv` contains row-level exploratory differences. These comparisons are descriptive because each protein's records share a held-out fold and the data are observational; they are not causal evidence.", "", "## Plots", "", "- `actual_vs_predicted.png` preserves all observations for each configuration.", "- `per_protein_squared_error.png` shows protein-level SSE without excluding observations.", "", "## Limitations", "", "Only 25 proteins are available, record counts are imbalanced, and some folds contain one high-count protein while others contain six smaller groups. Fold-level R² is therefore sensitive to target variance and a few large residuals. Protein-level comparisons are exploratory, and no production model is selected from this analysis.", ""]
    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False, low_memory=False)
    df["target_value_standardized"] = pd.to_numeric(df["target_value_standardized"], errors="raise")
    with EMBEDDING_INDEX_PATH.open(encoding="utf-8") as file:
        embedding_index = json.load(file)
    embeddings = load_embeddings(df, embedding_index)
    splits, fold_assignments = build_group_splits(df)
    predictions = make_prediction_table(df, embeddings, splits)
    fold_metrics = make_fold_table(df, predictions)
    protein_metrics = make_protein_table(predictions)
    comparisons = make_comparison_table(predictions)
    pooled = pooled_metrics(predictions)
    reproduction = verify_reproduction(fold_metrics)

    predictions.to_csv(OUTPUT_DIR / "oof_predictions.csv", index=False, encoding="utf-8-sig")
    fold_metrics.to_csv(OUTPUT_DIR / "fold_metrics.csv", index=False, encoding="utf-8-sig")
    protein_metrics.to_csv(OUTPUT_DIR / "protein_metrics.csv", index=False, encoding="utf-8-sig")
    protein_metrics.groupby("configuration", observed=True).head(10).to_csv(OUTPUT_DIR / "top_squared_error_proteins.csv", index=False, encoding="utf-8-sig")
    predictions.sort_values("squared_error_um2", ascending=False).head(30).to_csv(OUTPUT_DIR / "top_squared_error_rows.csv", index=False, encoding="utf-8-sig")
    comparisons.to_csv(OUTPUT_DIR / "within_protein_comparisons.csv", index=False, encoding="utf-8-sig")
    pooled.to_csv(OUTPUT_DIR / "pooled_metrics.csv", index=False, encoding="utf-8-sig")
    save_plots(predictions, protein_metrics)

    summary = {
        "dataset": {"records": int(len(df)), "proteins": int(df["protein_id"].nunique()), "source": str(DATASET_PATH.relative_to(PROJECT_ROOT))},
        "reproduction": reproduction,
        "protocol": {"folds": fold_assignments, "same_splits_across_configurations": True, "prediction_clipping": "none in original implementation", "ambiguous_records_excluded": True},
        "pooled_metrics": pooled.where(pd.notna(pooled), None).to_dict(orient="records"),
        "mean_fold_metrics": {config: {metric: float(fold_metrics.loc[fold_metrics.configuration == config, metric].mean()) for metric in ["mae_um", "rmse_um", "r2", "spearman"]} for config in CONFIGURATIONS},
        "extreme_r2_folds": fold_metrics.sort_values("r2").head(5).where(pd.notna(fold_metrics.sort_values("r2").head(5)), None).to_dict(orient="records"),
        "output_files": sorted(path.name for path in OUTPUT_DIR.iterdir()),
    }
    (OUTPUT_DIR / "analysis_summary.json").write_text(json.dumps(json_safe(summary), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "ablation_error_analysis_report.md").write_text(make_report(df, fold_metrics, protein_metrics, pooled, comparisons, reproduction), encoding="utf-8")

    print("ABLATION ERROR ANALYSIS COMPLETE")
    print("OOF rows:", len(predictions))
    print("Reproduction:", all(check["all_within_tolerance"] and check["undefined_match"] for check in reproduction.values()))
    print("Output directory:", OUTPUT_DIR.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()