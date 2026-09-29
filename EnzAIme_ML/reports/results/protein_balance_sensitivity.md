# Protein Balance Sensitivity Analysis

## Scope

This is an analysis-only sensitivity experiment. The confirmed 221-row dataset and all model artifacts were left unchanged. Existing ESM-2 embeddings were reused.

The balanced subset keeps `min(record_count, 5)` observations per protein using deterministic `random_state=42` selection. It contains 82 records across 25 proteins.

## Balanced subset

{'minimum': 1, 'maximum': 5, 'median': 5.0, 'mean': 3.28, 'distribution': [{'protein_id': '1', 'protein_name': 'IsPETase', 'record_count': 5}, {'protein_id': '11', 'protein_name': 'Mors1', 'record_count': 1}, {'protein_id': '13', 'protein_name': 'MG8', 'record_count': 5}, {'protein_id': '148', 'protein_name': 'CtPl', 'record_count': 2}, {'protein_id': '149', 'protein_name': '606', 'record_count': 5}, {'protein_id': '15', 'protein_name': 'RgPETase', 'record_count': 5}, {'protein_id': '17', 'protein_name': 'BhrPETase', 'record_count': 5}, {'protein_id': '177', 'protein_name': 'Sub1', 'record_count': 5}, {'protein_id': '185', 'protein_name': 'SM14est', 'record_count': 5}, {'protein_id': '195', 'protein_name': 'BurPL', 'record_count': 5}, {'protein_id': '223', 'protein_name': 'HG-2', 'record_count': 1}, {'protein_id': '224', 'protein_name': 'HG-3', 'record_count': 1}, {'protein_id': '225', 'protein_name': 'HG-4', 'record_count': 1}, {'protein_id': '226', 'protein_name': 'HG-5', 'record_count': 1}, {'protein_id': '240', 'protein_name': 'Dkca1', 'record_count': 1}, {'protein_id': '25', 'protein_name': 'TfCut2', 'record_count': 1}, {'protein_id': '37', 'protein_name': 'PHL-7', 'record_count': 5}, {'protein_id': '4', 'protein_name': 'PET12', 'record_count': 2}, {'protein_id': '41', 'protein_name': 'PET46', 'record_count': 2}, {'protein_id': '42', 'protein_name': 'CalB', 'record_count': 5}, {'protein_id': '44', 'protein_name': 'HiC', 'record_count': 5}, {'protein_id': '481', 'protein_name': 'Sis', 'record_count': 5}, {'protein_id': '483', 'protein_name': 'DIEGO', 'record_count': 5}, {'protein_id': '495', 'protein_name': 'PET93', 'record_count': 2}, {'protein_id': '496', 'protein_name': 'PET94', 'record_count': 2}]}

The balanced subset was written to `reports/results/balanced_sensitivity_dataset.csv`.

## Validation

- Validation: `GroupKFold(n_splits=5)`
- Group column: `protein_id`
- One fixed split set was reused for Ridge and Gradient Boosting.
- PCA and environmental scaling were fitted within each training fold only.
- Targets were trained as `log1p(target_value_standardized)`.
- MAE and RMSE were calculated after `expm1` conversion to µM.

## Comparison

| Dataset   | Model                     | MAE                   | RMSE                  | R²               | Spearman        |
|:----------|:--------------------------|:----------------------|:----------------------|:-----------------|:----------------|
| Full 221  | Ridge                     | 1337.512 +/- 1919.637 | 3145.400 +/- 5044.101 | -0.541 +/- 1.136 | 0.320 +/- 0.373 |
| Full 221  | GradientBoostingRegressor | 1307.386 +/- 1967.428 | 3082.411 +/- 5103.596 | -0.058 +/- 0.232 | 0.238 +/- 0.412 |
| Balanced  | Ridge                     | 1356.370 +/- 1930.606 | 3249.359 +/- 5102.945 | 0.008 +/- 0.307  | 0.467 +/- 0.155 |
| Balanced  | GradientBoostingRegressor | 1358.692 +/- 1988.138 | 3258.148 +/- 5143.438 | -0.034 +/- 0.256 | 0.224 +/- 0.336 |

## Fold results

### Full-data reference

The full-data values above are extracted from `reports/results/model_comparison_results.json`; no full-data model was refit in this sensitivity run.

### Balanced sensitivity results

| Model                     |   Fold |   Records |       MAE |       RMSE |         R² |   Spearman |
|:--------------------------|-------:|----------:|----------:|-----------:|-----------:|-----------:|
| Ridge                     |      1 |        17 |  542.508  |  1655.82   | -0.0583934 |   0.423313 |
| Ridge                     |      2 |        17 |   65.5908 |    74.9155 |  0.546074  |   0.61747  |
| Ridge                     |      3 |        16 |  770.796  |  1233.01   | -0.208007  |   0.473661 |
| Ridge                     |      4 |        16 |  625.55   |   964.181  | -0.0816879 |   0.229919 |
| Ridge                     |      5 |        16 | 4777.4    | 12318.9    | -0.157799  |   0.592923 |
| GradientBoostingRegressor |      1 |        17 |  554.977  |  1694.65   | -0.10861   |   0.388348 |
| GradientBoostingRegressor |      2 |        17 |   74.6806 |    99.5289 |  0.198802  |   0.165231 |
| GradientBoostingRegressor |      3 |        16 |  781.722  |  1301.92   | -0.34682   |   0.294217 |
| GradientBoostingRegressor |      4 |        16 |  496.395  |   797.691  |  0.259621  |   0.582289 |
| GradientBoostingRegressor |      5 |        16 | 4885.68   | 12397      | -0.172522  |  -0.311441 |

## Interpretation

The balanced subset changes the validation distribution by limiting every protein to at most five records. It reduces the dominant contribution from proteins with many observations and makes protein groups more comparable in size. It is not the true production-data performance estimate.

The full-versus-balanced mean metric differences are:

| Model                     |   MAE delta |   RMSE delta |   R² delta |   Spearman delta |
|:--------------------------|------------:|-------------:|-----------:|-----------------:|
| Ridge                     |     18.8578 |      103.959 |  0.548656  |         0.14779  |
| GradientBoostingRegressor |     51.3055 |      175.737 |  0.0237571 |        -0.014225 |

These differences should be interpreted alongside the large fold standard deviations and the unequal original group sizes. If the balanced and full results differ materially, protein imbalance is an important limitation of the reported metrics. This experiment indicates sensitivity to group weighting; it does not establish which evaluation setting is the definitive performance estimate.

## Decision status

No model was selected, deployed, retrained, or written to production artifacts. No observations were deleted from the confirmed dataset.

PROTEIN BALANCE SENSITIVITY COMPLETE
