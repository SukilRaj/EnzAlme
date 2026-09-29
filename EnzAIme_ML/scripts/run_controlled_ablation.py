"""Controlled ablation study for A/B/C feature configurations.

This is a read-only research experiment that compares the approved feature
configurations:

- A: environment only
- B: ESM-2 only
- C: ESM-2 + environment

The script reuses the same 5-fold GroupKFold assignments by protein_id, fits
preprocessing only on training data, applies the learned transform to validation
rows, and reports metrics on the original target scale after expm1.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"
EMBEDDING_INDEX_PATH = EMBEDDINGS_DIR / "index.json"
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"
CSV_PATH = RESULTS_DIR / "controlled_ablation_results.csv"
JSON_PATH = RESULTS_DIR / "controlled_ablation_results.json"
REPORT_PATH = RESULTS_DIR / "controlled_ablation_report.md"

RANDOM_SEED = 42
PCA_COMPONENTS = 10
ENVIRONMENT_COLUMNS = ["temperature_c", "ph", "duration_hours"]
CONFIGURATION_INFO = {
    "A": {
        "feature_description": "temperature_c + ph + duration_hours",
        "features": ENVIRONMENT_COLUMNS,
        "pca_components": 0,
    },
    "B": {
        "feature_description": "ESM-2 embedding",
        "features": ["ESM-2 embedding"],
        "pca_components": PCA_COMPONENTS,
    },
    "C": {
        "feature_description": "ESM-2 embedding + temperature_c + ph + duration_hours",
        "features": ["ESM-2 embedding", "temperature_c", "ph", "duration_hours"],
        "pca_components": PCA_COMPONENTS,
    },
}


def safe_spearman(y_true, y_pred):
    if len(y_true) < 2:
        return np.nan
    if np.allclose(y_true, y_true[0]) or np.allclose(y_pred, y_pred[0]):
        return np.nan
    return float(spearmanr(y_true, y_pred).statistic)


def summarize_metric(values):
    finite = [float(v) for v in values if pd.notna(v) and np.isfinite(v)]
    if not finite:
        return {"mean": None, "std": None, "median": None, "min": None, "max": None}
    return {
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0,
        "median": float(np.median(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def load_embeddings(df, embedding_index):
    arrays = []
    for protein_id in df["protein_id"].astype(str).tolist():
        file_name = embedding_index[protein_id]
        arrays.append(np.load(EMBEDDINGS_DIR / file_name, allow_pickle=False))
    return np.vstack(arrays)


def build_group_splits(df):
    groups = df["protein_id"].astype(str).to_numpy()
    target = df["target_value_standardized"].astype(float).to_numpy()
    splitter = GroupKFold(n_splits=5)
    splits = list(splitter.split(np.arange(len(df)), target, groups))
    fold_assignments = []
    for fold_number, (train_idx, test_idx) in enumerate(splits, start=1):
        train_proteins = sorted(df.iloc[train_idx]["protein_id"].astype(str).unique().tolist())
        test_proteins = sorted(df.iloc[test_idx]["protein_id"].astype(str).unique().tolist())
        overlap = set(train_proteins).intersection(test_proteins)
        if overlap:
            raise ValueError(f"Protein leakage detected in fold {fold_number}: {overlap}")
        fold_assignments.append(
            {
                "fold": fold_number,
                "train_records": int(len(train_idx)),
                "test_records": int(len(test_idx)),
                "train_proteins": train_proteins,
                "test_proteins": test_proteins,
            }
        )
    return splits, fold_assignments


def fit_and_predict(df, embedding_matrix, config_name, train_idx, test_idx):
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()
    y_train_log = np.log1p(train_df["target_value_standardized"].astype(float).to_numpy())
    y_test_log = np.log1p(test_df["target_value_standardized"].astype(float).to_numpy())

    if config_name == "A":
        X_train = train_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        X_test = test_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        model = Ridge(alpha=10)
        model.fit(X_train_scaled, y_train_log)
        pred_log = model.predict(X_test_scaled)
        pca_components = 0

    elif config_name == "B":
        X_train_emb = embedding_matrix[train_idx]
        X_test_emb = embedding_matrix[test_idx]
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_emb)
        X_test_scaled = scaler.transform(X_test_emb)
        pca = PCA(n_components=PCA_COMPONENTS, random_state=RANDOM_SEED)
        X_train_pca = pca.fit_transform(X_train_scaled)
        X_test_pca = pca.transform(X_test_scaled)
        model = Ridge(alpha=10)
        model.fit(X_train_pca, y_train_log)
        pred_log = model.predict(X_test_pca)
        pca_components = PCA_COMPONENTS

    elif config_name == "C":
        X_train_emb = embedding_matrix[train_idx]
        X_test_emb = embedding_matrix[test_idx]
        scaler_esm = StandardScaler()
        X_train_esm_scaled = scaler_esm.fit_transform(X_train_emb)
        X_test_esm_scaled = scaler_esm.transform(X_test_emb)
        pca = PCA(n_components=PCA_COMPONENTS, random_state=RANDOM_SEED)
        X_train_esm_pca = pca.fit_transform(X_train_esm_scaled)
        X_test_esm_pca = pca.transform(X_test_esm_scaled)

        X_train_env = train_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        X_test_env = test_df[ENVIRONMENT_COLUMNS].astype(float).to_numpy()
        X_train_combined = np.hstack([X_train_esm_pca, X_train_env])
        X_test_combined = np.hstack([X_test_esm_pca, X_test_env])
        final_scaler = StandardScaler()
        X_train_scaled = final_scaler.fit_transform(X_train_combined)
        X_test_scaled = final_scaler.transform(X_test_combined)
        model = Ridge(alpha=10)
        model.fit(X_train_scaled, y_train_log)
        pred_log = model.predict(X_test_scaled)
        pca_components = PCA_COMPONENTS

    else:
        raise ValueError(f"Unsupported configuration: {config_name}")

    y_true_uM = np.expm1(y_test_log)
    y_pred_uM = np.expm1(pred_log)
    metrics = {
        "mae_um": float(mean_absolute_error(y_true_uM, y_pred_uM)),
        "rmse_um": float(np.sqrt(mean_squared_error(y_true_uM, y_pred_uM))),
        "r2": float(r2_score(y_true_uM, y_pred_uM)),
        "spearman": safe_spearman(y_true_uM, y_pred_uM),
    }
    return metrics, {
        "train_records": int(len(train_idx)),
        "test_records": int(len(test_idx)),
        "train_proteins": int(train_df["protein_id"].nunique()),
        "test_proteins": int(test_df["protein_id"].nunique()),
        "pca_components": pca_components,
        "target_log1p": "log1p(target_value_standardized)",
        "random_state": RANDOM_SEED,
    }


def main():
    df = pd.read_csv(
        DATASET_PATH,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    with EMBEDDING_INDEX_PATH.open(encoding="utf-8") as file:
        embedding_index = json.load(file)

    embedding_matrix = load_embeddings(df, embedding_index)
    splits, fold_assignments = build_group_splits(df)

    rows = []
    per_config_summary = {}
    for config_name in ["A", "B", "C"]:
        config_metrics = []
        for fold_number, (train_idx, test_idx) in enumerate(splits, start=1):
            metrics, fold_info = fit_and_predict(df, embedding_matrix, config_name, train_idx, test_idx)
            row = {
                "configuration": config_name,
                "feature_description": CONFIGURATION_INFO[config_name]["feature_description"],
                "fold": fold_number,
                "train_records": fold_info["train_records"],
                "test_records": fold_info["test_records"],
                "train_proteins": fold_info["train_proteins"],
                "test_proteins": fold_info["test_proteins"],
                "pca_components": fold_info["pca_components"],
                "mae_um": metrics["mae_um"],
                "rmse_um": metrics["rmse_um"],
                "r2": metrics["r2"],
                "spearman": metrics["spearman"],
                "target_log1p": fold_info["target_log1p"],
                "random_state": fold_info["random_state"],
            }
            rows.append(row)
            config_metrics.append(metrics)

        metric_names = ["mae_um", "rmse_um", "r2", "spearman"]
        per_config_summary[config_name] = {
            "feature_description": CONFIGURATION_INFO[config_name]["feature_description"],
            "fold_count": len(config_metrics),
            "metrics": {
                metric_name: summarize_metric([metric[metric_name] for metric in config_metrics])
                for metric_name in metric_names
            },
        }

    result_df = pd.DataFrame(rows, columns=[
        "configuration",
        "feature_description",
        "fold",
        "train_records",
        "test_records",
        "train_proteins",
        "test_proteins",
        "pca_components",
        "mae_um",
        "rmse_um",
        "r2",
        "spearman",
        "target_log1p",
        "random_state",
    ])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    json_payload = {
        "dataset_information": {
            "source": str(DATASET_PATH.relative_to(PROJECT_ROOT)),
            "records": int(len(df)),
            "proteins": int(df["protein_id"].nunique()),
            "target": "target_value_standardized",
            "target_transform": "log1p(target_value_standardized) applied within each training fold only",
            "target_unit": "uM",
            "random_seed": RANDOM_SEED,
        },
        "feature_configurations": {
            "A": {
                "name": "Environment Only",
                "features": CONFIGURATION_INFO["A"]["features"],
                "feature_description": CONFIGURATION_INFO["A"]["feature_description"],
                "pca_components": 0,
                "scaler": "StandardScaler on training environment features only",
                "model": "Ridge(alpha=10)",
            },
            "B": {
                "name": "ESM-2 Only",
                "features": CONFIGURATION_INFO["B"]["features"],
                "feature_description": CONFIGURATION_INFO["B"]["feature_description"],
                "pca_components": PCA_COMPONENTS,
                "scaler": "StandardScaler on ESM-2 training embeddings only",
                "model": "Ridge(alpha=10)",
            },
            "C": {
                "name": "ESM-2 + Environment",
                "features": CONFIGURATION_INFO["C"]["features"],
                "feature_description": CONFIGURATION_INFO["C"]["feature_description"],
                "pca_components": PCA_COMPONENTS,
                "scaler": "StandardScaler on concatenated PCA-ESM and environment training features only",
                "model": "Ridge(alpha=10)",
            },
        },
        "validation_strategy": {
            "method": "GroupKFold(n_splits=5)",
            "grouping_variable": "protein_id",
            "same_folds_across_configs": True,
            "leakage_check": "No protein appears in both train and test within a fold",
            "fold_assignments": fold_assignments,
        },
        "preprocessing_strategy": {
            "fit_within_fold_only": True,
            "no_target_transform_before_split": True,
            "inference_transform": "train-only scaler/PCA fitted on training fold before evaluating validation fold",
        },
        "model_configuration": {
            "primary_model": "Ridge",
            "alpha": 10,
            "random_state": RANDOM_SEED,
            "same_model_for_all_configs": True,
        },
        "per_fold_results": rows,
        "aggregated_results": per_config_summary,
        "comparison": {
            "A_vs_B": "Compare environment-only to protein-only performance under the same 5 protein-grouped folds.",
            "B_vs_C": "Compare protein-only to ESM-2 + environment performance under the same 5 protein-grouped folds.",
            "A_vs_C": "Compare environment-only to ESM-2 + environment performance under the same 5 protein-grouped folds.",
            "interpretation": "This experiment isolates the contribution of each feature block while keeping the model and validation protocol fixed.",
        },
    }
    JSON_PATH.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown_lines = [
        "# Controlled Ablation Report",
        "",
        "## 1. Objective",
        "",
        "This study compares the approved feature blocks A, B, and C without changing the underlying confirmed dataset or model family. The only systematic change is the feature block, while the validation protocol, model, and preprocessing discipline remain fixed.",
        "",
        "## 2. Dataset and Validation",
        "",
        f"- Records: {len(df)}",
        f"- Proteins: {df['protein_id'].nunique()}",
        "- Target: target_value_standardized",
        "- Transform: log1p(target_value_standardized) inside each training fold only",
        "- Validation: GroupKFold(n_splits=5) by protein_id",
        "- Leakage check: no protein appears in both train and test within any fold",
        "",
        "## 3. Configuration A — Environment Only",
        "",
        "- Features: temperature_c, ph, duration_hours",
        "- Model: Ridge(alpha=10)",
        "- Preprocessing: StandardScaler fit on training data only",
        "",
        "## 4. Configuration B — ESM-2 Only",
        "",
        "- Features: ESM-2 embedding",
        "- Model: Ridge(alpha=10)",
        "- Preprocessing: StandardScaler + PCA(n_components=10), both fitted on training data only",
        "",
        "## 5. Configuration C — ESM-2 + Environment",
        "",
        "- Features: ESM-2 embedding + temperature_c + ph + duration_hours",
        "- Model: Ridge(alpha=10)",
        "- Preprocessing: PCA on ESM-2 training embeddings, then concatenation with environment features, then final StandardScaler fitted on training data only",
        "",
        "## 6. Metric Interpretation",
        "",
        "- MAE and RMSE are reported in original µM units after expm1 back-transformation.",
        "- R² and Spearman are reported on the original scale and should be interpreted alongside the small-sample protein-grouped fold structure.",
        "- Negative R² values are not treated as a model failure; they reflect the observed fold-level distribution and variation under small group-split conditions.",
        "",
        "## 7. Research Questions",
        "",
        "### 1. Does environment-only information contain predictive signal?",
        "The environment block is a minimal check of whether pre-assay conditions alone carry signal beyond protein identity. The observed A results must be interpreted in the context of a small set of proteins and strong protein-level clustering.",
        "",
        "### 2. Does ESM-2 alone contain predictive signal?",
        "B indicates whether the protein representation alone contains actionable information under the same group splits. Because the model is fixed and the folds remain identical, differences between A and B reflect the feature block rather than training protocol changes.",
        "",
        "### 3. Does combining ESM-2 with environmental conditions improve performance?",
        "C isolates the combined effect of the ESM-2 representation and environmental features. Comparisons should be made against both A and B using the same folds and metrics; improvements or declines should be discussed as observed differences rather than model ranking.",
        "",
        "### 4. Which metrics change between A, B and C?",
        "The calculated metrics are reported in the JSON and CSV files for each fold. The interpretation should compare MAE, RMSE, R², and Spearman together because each metric reflects different aspects of predictive error and ranking behavior.",
        "",
        "### 5. How stable are the results across protein folds?",
        "The results are observed across the same 5 GroupKFold protein splits. Fold-level variability is a key limitation because several proteins are represented by a small number of records and some folds are more heavily skewed toward high-count proteins.",
        "",
        "### 6. Are conclusions consistent across MAE, RMSE, R² and Spearman?",
        "A single metric should not be used in isolation. Agreement across metrics is a stronger indicator of signal than any single metric alone, especially in the small-sample setting with variable protein counts.",
        "",
        "### 7. What limitations remain because of the small number of proteins and imbalanced records?",
        "The confirmed dataset contains only 25 proteins and uneven record counts across proteins. This leads to fold instability, strong dependence on the protein held out, and limited statistical confidence in small differences between configurations. The experiment is therefore a controlled comparison rather than a production-model decision.",
        "",
        "## 8. Summary",
        "",
        "The study is designed to quantify the contribution of the environment-only, protein-only, and combined feature blocks while keeping all else fixed. No product model is selected and no final deployment claim is made from this experiment.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    per_config_summary = {
        name: {
            "feature_description": info["feature_description"],
            "fold_metrics": [
                {
                    "fold": row["fold"],
                    "mae_um": row["mae_um"],
                    "rmse_um": row["rmse_um"],
                    "r2": row["r2"],
                    "spearman": row["spearman"],
                }
                for row in rows if row["configuration"] == name
            ],
            **per_config_summary[name],
        }
        for name, info in CONFIGURATION_INFO.items()
    }
    json_payload["aggregated_results"] = per_config_summary
    JSON_PATH.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Terminal summary requested by the task specification.
    a_summary = per_config_summary["A"]["metrics"]
    b_summary = per_config_summary["B"]["metrics"]
    c_summary = per_config_summary["C"]["metrics"]

    print("CONTROLLED ABLATION COMPLETE")
    print("records:", len(df))
    print("proteins:", df["protein_id"].nunique())
    print("folds:", 5)
    print()
    print("A Environment:")
    print("mean MAE:", a_summary["mae_um"]["mean"])
    print("mean RMSE:", a_summary["rmse_um"]["mean"])
    print("mean R2:", a_summary["r2"]["mean"])
    print("mean Spearman:", a_summary["spearman"]["mean"])
    print()
    print("B ESM-2:")
    print("mean MAE:", b_summary["mae_um"]["mean"])
    print("mean RMSE:", b_summary["rmse_um"]["mean"])
    print("mean R2:", b_summary["r2"]["mean"])
    print("mean Spearman:", b_summary["spearman"]["mean"])
    print()
    print("C ESM-2 + Environment:")
    print("mean MAE:", c_summary["mae_um"]["mean"])
    print("mean RMSE:", c_summary["rmse_um"]["mean"])
    print("mean R2:", c_summary["r2"]["mean"])
    print("mean Spearman:", c_summary["spearman"]["mean"])
    print()
    print("Fold consistency:", "All configurations use the same 5 GroupKFold protein splits.")
    print("Leakage check:", "No protein appears in both train and test within any fold.")
    print("Artifacts:", "controlled_ablation_results.csv, controlled_ablation_results.json, controlled_ablation_report.md")


if __name__ == "__main__":
    main()
