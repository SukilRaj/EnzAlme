# Controlled Ablation Report

## 1. Objective

This study compares the approved feature blocks A, B, and C without changing the underlying confirmed dataset or model family. The only systematic change is the feature block, while the validation protocol, model, and preprocessing discipline remain fixed.

## 2. Dataset and Validation

- Records: 221
- Proteins: 25
- Target: target_value_standardized
- Transform: log1p(target_value_standardized) inside each training fold only
- Validation: GroupKFold(n_splits=5) by protein_id
- Leakage check: no protein appears in both train and test within any fold

## 3. Configuration A — Environment Only

- Features: temperature_c, ph, duration_hours
- Model: Ridge(alpha=10)
- Preprocessing: StandardScaler fit on training data only

## 4. Configuration B — ESM-2 Only

- Features: ESM-2 embedding
- Model: Ridge(alpha=10)
- Preprocessing: StandardScaler + PCA(n_components=10), both fitted on training data only

## 5. Configuration C — ESM-2 + Environment

- Features: ESM-2 embedding + temperature_c + ph + duration_hours
- Model: Ridge(alpha=10)
- Preprocessing: PCA on ESM-2 training embeddings, then concatenation with environment features, then final StandardScaler fitted on training data only

## 6. Metric Interpretation

- MAE and RMSE are reported in original µM units after expm1 back-transformation.
- R² and Spearman are reported on the original scale and should be interpreted alongside the small-sample protein-grouped fold structure.
- Negative R² values are not treated as a model failure; they reflect the observed fold-level distribution and variation under small group-split conditions.

## 7. Research Questions

### 1. Does environment-only information contain predictive signal?
The environment block is a minimal check of whether pre-assay conditions alone carry signal beyond protein identity. The observed A results must be interpreted in the context of a small set of proteins and strong protein-level clustering.

### 2. Does ESM-2 alone contain predictive signal?
B indicates whether the protein representation alone contains actionable information under the same group splits. Because the model is fixed and the folds remain identical, differences between A and B reflect the feature block rather than training protocol changes.

### 3. Does combining ESM-2 with environmental conditions improve performance?
C isolates the combined effect of the ESM-2 representation and environmental features. Comparisons should be made against both A and B using the same folds and metrics; improvements or declines should be discussed as observed differences rather than model ranking.

### 4. Which metrics change between A, B and C?
The calculated metrics are reported in the JSON and CSV files for each fold. The interpretation should compare MAE, RMSE, R², and Spearman together because each metric reflects different aspects of predictive error and ranking behavior.

### 5. How stable are the results across protein folds?
The results are observed across the same 5 GroupKFold protein splits. Fold-level variability is a key limitation because several proteins are represented by a small number of records and some folds are more heavily skewed toward high-count proteins.

### 6. Are conclusions consistent across MAE, RMSE, R² and Spearman?
A single metric should not be used in isolation. Agreement across metrics is a stronger indicator of signal than any single metric alone, especially in the small-sample setting with variable protein counts.

### 7. What limitations remain because of the small number of proteins and imbalanced records?
The confirmed dataset contains only 25 proteins and uneven record counts across proteins. This leads to fold instability, strong dependence on the protein held out, and limited statistical confidence in small differences between configurations. The experiment is therefore a controlled comparison rather than a production-model decision.

## 8. Summary

The study is designed to quantify the contribution of the environment-only, protein-only, and combined feature blocks while keeping all else fixed. No product model is selected and no final deployment claim is made from this experiment.

