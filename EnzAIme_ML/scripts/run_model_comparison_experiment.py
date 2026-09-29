import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.decomposition import PCA
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"
EMBEDDING_INDEX_PATH = EMBEDDINGS_DIR / "index.json"
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"
JSON_PATH = RESULTS_DIR / "model_comparison_results.json"
CSV_PATH = RESULTS_DIR / "model_comparison_results.csv"
CONFIG_PATH = RESULTS_DIR / "model_comparison_config.json"
RANDOM_SEED = 42
PCA_VALUES = [10, 25, 50, 100]
ENVIRONMENT_COLUMNS = ["temperature_c", "ph", "duration_hours"]


def finite_or_none(value):
    value = float(value)
    return value if np.isfinite(value) else None


def evaluate_predictions(y_true_log, predictions_log):
    y_true = np.expm1(y_true_log)
    predictions = np.expm1(predictions_log)
    spearman = spearmanr(y_true, predictions).statistic
    return {
        "mae": finite_or_none(mean_absolute_error(y_true, predictions)),
        "rmse": finite_or_none(mean_squared_error(y_true, predictions) ** 0.5),
        "r2": finite_or_none(r2_score(y_true, predictions)),
        "spearman": finite_or_none(spearman),
    }


def metric_mean(metrics, name):
    values = [metric[name] for metric in metrics if metric[name] is not None]
    return None if not values else float(np.mean(values))


def metric_std(metrics, name):
    values = [metric[name] for metric in metrics if metric[name] is not None]
    return None if len(values) < 2 else float(np.std(values, ddof=1))


def fold_features(esm_train, esm_validation, environment_train, environment_validation, components):
    pca = PCA(n_components=components, random_state=RANDOM_SEED)
    esm_train_pca = pca.fit_transform(esm_train)
    esm_validation_pca = pca.transform(esm_validation)

    environment_scaler = StandardScaler()
    environment_train_scaled = environment_scaler.fit_transform(environment_train)
    environment_validation_scaled = environment_scaler.transform(environment_validation)

    return (
        np.concatenate([esm_train_pca, environment_train_scaled], axis=1),
        np.concatenate([esm_validation_pca, environment_validation_scaled], axis=1),
    )


def model_specs():
    specs = []
    for alpha in [1, 10, 100]:
        specs.append(("Ridge", f"alpha={alpha}", {"alpha": alpha}))
    for alpha in [0.01, 0.1, 1.0]:
        for l1_ratio in [0.1, 0.5, 0.9]:
            specs.append(
                (
                    "ElasticNet",
                    f"alpha={alpha},l1_ratio={l1_ratio}",
                    {"alpha": alpha, "l1_ratio": l1_ratio},
                )
            )
    specs.append(
        (
            "RandomForestRegressor",
            "n_estimators=300,max_depth=5,min_samples_leaf=3,random_state=42",
            {
                "n_estimators": 300,
                "max_depth": 5,
                "min_samples_leaf": 3,
                "random_state": RANDOM_SEED,
            },
        )
    )
    specs.append(
        (
            "GradientBoostingRegressor",
            "n_estimators=200,learning_rate=0.03,max_depth=2,min_samples_leaf=3,random_state=42",
            {
                "n_estimators": 200,
                "learning_rate": 0.03,
                "max_depth": 2,
                "min_samples_leaf": 3,
                "random_state": RANDOM_SEED,
            },
        )
    )
    return specs


def make_model(name, parameters):
    if name == "Ridge":
        return Ridge(**parameters)
    if name == "ElasticNet":
        return ElasticNet(max_iter=10000, random_state=RANDOM_SEED, **parameters)
    if name == "RandomForestRegressor":
        return RandomForestRegressor(**parameters)
    if name == "GradientBoostingRegressor":
        return GradientBoostingRegressor(**parameters)
    raise ValueError(f"Unknown model: {name}")


def main():
    df = pd.read_csv(
        DATASET_PATH,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    with EMBEDDING_INDEX_PATH.open(encoding="utf-8") as file:
        embedding_index = json.load(file)

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
    target_uM = df["target_value_standardized"].astype(float).to_numpy()
    target_log = np.log1p(target_uM)
    groups = df["protein_id"].to_numpy()

    splitter = GroupKFold(n_splits=5)
    splits = list(splitter.split(embeddings, target_log, groups))
    fold_metadata = [
        {
            "fold": fold_number,
            "train_records": len(train_index),
            "validation_records": len(validation_index),
            "train_proteins": int(pd.Series(groups[train_index]).nunique()),
            "validation_proteins": int(pd.Series(groups[validation_index]).nunique()),
        }
        for fold_number, (train_index, validation_index) in enumerate(splits, start=1)
    ]

    fold_rows = []
    summaries = []
    for pca_components in PCA_VALUES:
        for model_name, configuration, parameters in model_specs():
            metrics = []
            for fold_number, (train_index, validation_index) in enumerate(splits, start=1):
                train_features, validation_features = fold_features(
                    embeddings[train_index],
                    embeddings[validation_index],
                    environment[train_index],
                    environment[validation_index],
                    pca_components,
                )
                model = make_model(model_name, parameters)
                model.fit(train_features, target_log[train_index])
                predictions_log = model.predict(validation_features)
                fold_metric = evaluate_predictions(
                    target_log[validation_index],
                    predictions_log,
                )
                row = {
                    "model": model_name,
                    "configuration": configuration,
                    "pca_components": pca_components,
                    "fold": fold_number,
                    "records": len(validation_index),
                    **fold_metric,
                }
                fold_rows.append(row)
                metrics.append(fold_metric)
            summaries.append(
                {
                    "model": model_name,
                    "configuration": configuration,
                    "pca_components": pca_components,
                    "mean_mae": metric_mean(metrics, "mae"),
                    "std_mae": metric_std(metrics, "mae"),
                    "mean_rmse": metric_mean(metrics, "rmse"),
                    "std_rmse": metric_std(metrics, "rmse"),
                    "mean_r2": metric_mean(metrics, "r2"),
                    "std_r2": metric_std(metrics, "r2"),
                    "mean_spearman": metric_mean(metrics, "spearman"),
                    "std_spearman": metric_std(metrics, "spearman"),
                    "folds": [
                        {
                            "fold": fold_number,
                            **metrics[fold_number - 1],
                        }
                        for fold_number in range(1, 6)
                    ],
                }
            )

    baseline_specs = [
        ("EnvironmentalRidge", "environment_only,alpha=10", 0),
        ("MeanBaseline", "training_fold_mean_log_target", 0),
    ]
    for model_name, configuration, pca_components in baseline_specs:
        metrics = []
        for fold_number, (train_index, validation_index) in enumerate(splits, start=1):
            environment_scaler = StandardScaler()
            train_environment = environment_scaler.fit_transform(environment[train_index])
            validation_environment = environment_scaler.transform(environment[validation_index])
            if model_name == "EnvironmentalRidge":
                model = Ridge(alpha=10)
                model.fit(train_environment, target_log[train_index])
                predictions_log = model.predict(validation_environment)
            else:
                predictions_log = np.full(
                    len(validation_index),
                    target_log[train_index].mean(),
                )
            fold_metric = evaluate_predictions(
                target_log[validation_index],
                predictions_log,
            )
            row = {
                "model": model_name,
                "configuration": configuration,
                "pca_components": pca_components,
                "fold": fold_number,
                "records": len(validation_index),
                **fold_metric,
            }
            fold_rows.append(row)
            metrics.append(fold_metric)
        summaries.append(
            {
                "model": model_name,
                "configuration": configuration,
                "pca_components": pca_components,
                "mean_mae": metric_mean(metrics, "mae"),
                "std_mae": metric_std(metrics, "mae"),
                "mean_rmse": metric_mean(metrics, "rmse"),
                "std_rmse": metric_std(metrics, "rmse"),
                "mean_r2": metric_mean(metrics, "r2"),
                "std_r2": metric_std(metrics, "r2"),
                "mean_spearman": metric_mean(metrics, "spearman"),
                "std_spearman": metric_std(metrics, "spearman"),
                "folds": [
                    {
                        "fold": fold_number,
                        **metrics[fold_number - 1],
                    }
                    for fold_number in range(1, 6)
                ],
            }
        )

    config = {
        "dataset": str(DATASET_PATH.relative_to(PROJECT_ROOT)),
        "target": "target_value_standardized",
        "target_transform": "log1p",
        "features": {
            "esm_embedding_dimension": 1280,
            "environment": ENVIRONMENT_COLUMNS,
        },
        "group_column": "protein_id",
        "cv_strategy": "GroupKFold",
        "number_of_folds": 5,
        "PCA_values": PCA_VALUES,
        "models": {
            "Ridge": [1, 10, 100],
            "ElasticNet": {
                "alpha": [0.01, 0.1, 1.0],
                "l1_ratio": [0.1, 0.5, 0.9],
            },
            "RandomForestRegressor": {
                "n_estimators": 300,
                "max_depth": 5,
                "min_samples_leaf": 3,
            },
            "GradientBoostingRegressor": {
                "n_estimators": 200,
                "learning_rate": 0.03,
                "max_depth": 2,
                "min_samples_leaf": 3,
            },
            "EnvironmentalRidge": {"alpha": 10},
            "MeanBaseline": "training-fold mean log target",
        },
        "random_seed": RANDOM_SEED,
        "folds": fold_metadata,
        "preprocessing": (
            "PCA and environmental StandardScaler are fit separately within each training fold."
        ),
    }
    results = {
        "experiment": "ESM-2 PET/TPA model comparison",
        "dataset_records": len(df),
        "unique_proteins": int(df["protein_id"].nunique()),
        "folds": fold_metadata,
        "summaries": summaries,
        "fold_results": fold_rows,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(fold_rows).to_csv(CSV_PATH, index=False)
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary_frame = pd.DataFrame(summaries)
    print("Model | Configuration | PCA | MAE | RMSE | R2 | Spearman")
    for _, row in summary_frame.iterrows():
        print(
            f"{row.model} | {row.configuration} | {int(row.pca_components)} | "
            f"{row.mean_mae:.3f} +/- {row.std_mae:.3f} | "
            f"{row.mean_rmse:.3f} +/- {row.std_rmse:.3f} | "
            f"{row.mean_r2:.3f} +/- {row.std_r2:.3f} | "
            f"{row.mean_spearman:.3f} +/- {row.std_spearman:.3f}"
        )
    print("Results JSON:", JSON_PATH)
    print("Results CSV:", CSV_PATH)
    print("Config JSON:", CONFIG_PATH)
    print("MODEL COMPARISON COMPLETE")


if __name__ == "__main__":
    main()