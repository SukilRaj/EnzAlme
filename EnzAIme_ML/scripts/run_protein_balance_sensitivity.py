import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"
EMBEDDING_INDEX_PATH = EMBEDDINGS_DIR / "index.json"
FULL_RESULTS_PATH = PROJECT_ROOT / "reports" / "results" / "model_comparison_results.json"
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"
BALANCED_PATH = RESULTS_DIR / "balanced_sensitivity_dataset.csv"
JSON_PATH = RESULTS_DIR / "protein_balance_sensitivity.json"
MARKDOWN_PATH = RESULTS_DIR / "protein_balance_sensitivity.md"
ENVIRONMENT_COLUMNS = ["temperature_c", "ph", "duration_hours"]
RANDOM_SEED = 42


def metric_value(value):
    value = float(value)
    return value if np.isfinite(value) else None


def calculate_metrics(y_true_log, predictions_log):
    y_true = np.expm1(y_true_log)
    predictions = np.expm1(predictions_log)
    correlation = spearmanr(y_true, predictions).statistic
    return {
        "mae": metric_value(mean_absolute_error(y_true, predictions)),
        "rmse": metric_value(mean_squared_error(y_true, predictions) ** 0.5),
        "r2": metric_value(r2_score(y_true, predictions)),
        "spearman": metric_value(correlation),
    }


def aggregate_metrics(fold_metrics):
    result = {}
    for name in ["mae", "rmse", "r2", "spearman"]:
        values = [metric[name] for metric in fold_metrics if metric[name] is not None]
        result[f"mean_{name}"] = None if not values else float(np.mean(values))
        result[f"std_{name}"] = (
            None if len(values) < 2 else float(np.std(values, ddof=1))
        )
    return result


def build_features(embeddings, environment, train_index, validation_index, components):
    pca = PCA(n_components=components, random_state=RANDOM_SEED)
    train_embedding = pca.fit_transform(embeddings[train_index])
    validation_embedding = pca.transform(embeddings[validation_index])

    scaler = StandardScaler()
    train_environment = scaler.fit_transform(environment[train_index])
    validation_environment = scaler.transform(environment[validation_index])

    return (
        np.concatenate([train_embedding, train_environment], axis=1),
        np.concatenate([validation_embedding, validation_environment], axis=1),
    )


def model_definitions():
    return [
        {
            "model": "Ridge",
            "configuration": "alpha=10",
            "pca_components": 10,
        },
        {
            "model": "GradientBoostingRegressor",
            "configuration": (
                "n_estimators=200,learning_rate=0.03,max_depth=2,"
                "min_samples_leaf=3,random_state=42"
            ),
            "pca_components": 25,
        },
    ]


def make_model(model_name):
    if model_name == "Ridge":
        return Ridge(alpha=10)
    return GradientBoostingRegressor(
        n_estimators=200,
        learning_rate=0.03,
        max_depth=2,
        min_samples_leaf=3,
        random_state=RANDOM_SEED,
    )


def summarize_dataset(df):
    counts = df.groupby(["protein_id", "protein_name"]).size()
    return {
        "total_records": len(df),
        "proteins": int(df["protein_id"].nunique()),
        "records_per_protein": {
            "minimum": int(counts.min()),
            "maximum": int(counts.max()),
            "median": float(counts.median()),
            "mean": float(counts.mean()),
            "distribution": [
                {
                    "protein_id": protein_id,
                    "protein_name": protein_name,
                    "record_count": int(record_count),
                }
                for (protein_id, protein_name), record_count in counts.items()
            ],
        },
    }


def evaluate_balanced(df, embedding_index):
    embeddings = np.vstack(
        [
            np.load(
                EMBEDDINGS_DIR / embedding_index[protein_id],
                allow_pickle=False,
            )
            for protein_id in df["protein_id"]
        ]
    )
    environment = df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
    target = df["target_value_standardized"].astype(float).to_numpy()
    target_log = np.log1p(target)
    groups = df["protein_id"].to_numpy()
    splits = list(GroupKFold(n_splits=5).split(embeddings, target_log, groups))
    fold_metadata = [
        {
            "fold": fold_number,
            "train_records": len(train_index),
            "validation_records": len(validation_index),
            "train_proteins": int(pd.Series(groups[train_index]).nunique()),
            "validation_proteins": int(pd.Series(groups[validation_index]).nunique()),
        }
        for fold_number, (train_index, validation_index) in enumerate(splits, 1)
    ]

    all_summaries = []
    for definition in model_definitions():
        fold_metrics = []
        for fold_number, (train_index, validation_index) in enumerate(splits, 1):
            train_features, validation_features = build_features(
                embeddings,
                environment,
                train_index,
                validation_index,
                definition["pca_components"],
            )
            model = make_model(definition["model"])
            model.fit(train_features, target_log[train_index])
            predictions_log = model.predict(validation_features)
            metrics = calculate_metrics(
                target_log[validation_index],
                predictions_log,
            )
            fold_metrics.append(
                {
                    "fold": fold_number,
                    "records": len(validation_index),
                    **metrics,
                }
            )
        all_summaries.append(
            {
                **definition,
                **aggregate_metrics(fold_metrics),
                "folds": fold_metrics,
            }
        )
    return {
        "dataset": summarize_dataset(df),
        "folds": fold_metadata,
        "summaries": all_summaries,
    }


def format_metric(summary, metric):
    mean = summary[f"mean_{metric}"]
    std = summary[f"std_{metric}"]
    if mean is None or std is None:
        return "NA"
    return f"{mean:.3f} +/- {std:.3f}"


def main():
    df = pd.read_csv(
        DATASET_PATH,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    balanced_parts = []
    for protein_id in sorted(df["protein_id"].unique(), key=lambda value: int(value)):
        group = df[df["protein_id"] == protein_id]
        balanced_parts.append(
            group.sample(
                n=min(len(group), 5),
                random_state=RANDOM_SEED,
            )
        )
    balanced = pd.concat(balanced_parts, ignore_index=True)
    balanced.to_csv(BALANCED_PATH, index=False, encoding="utf-8-sig")

    with EMBEDDING_INDEX_PATH.open(encoding="utf-8") as file:
        embedding_index = json.load(file)
    balanced_results = evaluate_balanced(balanced, embedding_index)

    full_results = json.loads(FULL_RESULTS_PATH.read_text(encoding="utf-8"))
    full_lookup = {
        (summary["model"], summary["configuration"], summary["pca_components"]): summary
        for summary in full_results["summaries"]
    }
    requested_keys = [
        ("Ridge", "alpha=10", 10),
        (
            "GradientBoostingRegressor",
            "n_estimators=200,learning_rate=0.03,max_depth=2,min_samples_leaf=3,random_state=42",
            25,
        ),
    ]
    full_summaries = [full_lookup[key] for key in requested_keys]
    comparison = []
    for full_summary, balanced_summary in zip(
        full_summaries,
        balanced_results["summaries"],
    ):
        comparison.append(
            {
                "model": balanced_summary["model"],
                "configuration": balanced_summary["configuration"],
                "pca_components": balanced_summary["pca_components"],
                "full_dataset": full_summary,
                "balanced_dataset": balanced_summary,
                "balanced_minus_full": {
                    metric: (
                        None
                        if full_summary[f"mean_{metric}"] is None
                        or balanced_summary[f"mean_{metric}"] is None
                        else balanced_summary[f"mean_{metric}"]
                        - full_summary[f"mean_{metric}"]
                    )
                    for metric in ["mae", "rmse", "r2", "spearman"]
                },
            }
        )

    output = {
        "experiment": "Protein-balance sensitivity analysis",
        "random_state": RANDOM_SEED,
        "selection_rule": "min(record_count, 5) per protein",
        "balanced_dataset": balanced_results["dataset"],
        "balanced_folds": balanced_results["folds"],
        "comparisons": comparison,
        "interpretation": {
            "not_production_performance": True,
            "fold_reuse": "One fixed five-fold GroupKFold split set was reused for both balanced models.",
            "imbalance_effect_note": (
                "The balanced subset changes both the number of observations and the relative weight "
                "of proteins. Differences from the full-data results are sensitivity evidence, not a "
                "replacement performance estimate."
            ),
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    full_rows = {summary["model"]: summary for summary in full_summaries}
    balanced_rows = {summary["model"]: summary for summary in balanced_results["summaries"]}
    table_rows = []
    for dataset_name, rows in [("Full 221", full_rows), ("Balanced", balanced_rows)]:
        for model_name in ["Ridge", "GradientBoostingRegressor"]:
            summary = rows[model_name]
            table_rows.append(
                {
                    "Dataset": dataset_name,
                    "Model": model_name,
                    "MAE": format_metric(summary, "mae"),
                    "RMSE": format_metric(summary, "rmse"),
                    "R²": format_metric(summary, "r2"),
                    "Spearman": format_metric(summary, "spearman"),
                }
            )
    table = pd.DataFrame(table_rows)
    markdown = f"""# Protein Balance Sensitivity Analysis

## Scope

This is an analysis-only sensitivity experiment. The confirmed 221-row dataset and all model artifacts were left unchanged. Existing ESM-2 embeddings were reused.

The balanced subset keeps `min(record_count, 5)` observations per protein using deterministic `random_state=42` selection. It contains {len(balanced)} records across {balanced['protein_id'].nunique()} proteins.

## Balanced subset

{balanced_results['dataset']['records_per_protein']}

The balanced subset was written to `reports/results/balanced_sensitivity_dataset.csv`.

## Validation

- Validation: `GroupKFold(n_splits=5)`
- Group column: `protein_id`
- One fixed split set was reused for Ridge and Gradient Boosting.
- PCA and environmental scaling were fitted within each training fold only.
- Targets were trained as `log1p(target_value_standardized)`.
- MAE and RMSE were calculated after `expm1` conversion to µM.

## Comparison

{table.to_markdown(index=False)}

## Fold results

### Full-data reference

The full-data values above are extracted from `reports/results/model_comparison_results.json`; no full-data model was refit in this sensitivity run.

### Balanced sensitivity results

{pd.DataFrame([
    {
        'Model': summary['model'],
        'Fold': fold['fold'],
        'Records': fold['records'],
        'MAE': fold['mae'],
        'RMSE': fold['rmse'],
        'R²': fold['r2'],
        'Spearman': fold['spearman'],
    }
    for summary in balanced_results['summaries']
    for fold in summary['folds']
]).to_markdown(index=False)}

## Interpretation

The balanced subset changes the validation distribution by limiting every protein to at most five records. It reduces the dominant contribution from proteins with many observations and makes protein groups more comparable in size. It is not the true production-data performance estimate.

The full-versus-balanced mean metric differences are:

{pd.DataFrame([
    {
        'Model': item['model'],
        'MAE delta': item['balanced_minus_full']['mae'],
        'RMSE delta': item['balanced_minus_full']['rmse'],
        'R² delta': item['balanced_minus_full']['r2'],
        'Spearman delta': item['balanced_minus_full']['spearman'],
    }
    for item in comparison
]).to_markdown(index=False)}

These differences should be interpreted alongside the large fold standard deviations and the unequal original group sizes. If the balanced and full results differ materially, protein imbalance is an important limitation of the reported metrics. This experiment indicates sensitivity to group weighting; it does not establish which evaluation setting is the definitive performance estimate.

## Decision status

No model was selected, deployed, retrained, or written to production artifacts. No observations were deleted from the confirmed dataset.

PROTEIN BALANCE SENSITIVITY COMPLETE
"""
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")

    print("Dataset | Model | MAE | RMSE | R² | Spearman")
    print(table.to_string(index=False))
    print("Balanced subset:", BALANCED_PATH)
    print("Sensitivity JSON:", JSON_PATH)
    print("Sensitivity Markdown:", MARKDOWN_PATH)
    print("MODEL COMPARISON BALANCE SENSITIVITY COMPLETE")
    print("PROTEIN BALANCE SENSITIVITY COMPLETE")


if __name__ == "__main__":
    main()