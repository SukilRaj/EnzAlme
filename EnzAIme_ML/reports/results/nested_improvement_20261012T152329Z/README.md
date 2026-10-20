# Exploratory model improvement: nested protein-grouped evaluation

Primary selection minimizes inner pooled MAE; secondary selection minimizes inner pooled RMSE. All reported scores below use the same untouched outer test proteins. Original A/C baselines were reproduced and checked against archived metrics.

| Procedure | Pooled MAE (uM) | Pooled RMSE (uM) | Pooled R2 | Spearman | Macro-protein MAE (uM) |
|---|---:|---:|---:|---:|---:|
| baseline_A | 1420.713 | 5085.699 | -0.04897 | 0.44088 | 1111.139 |
| baseline_C | 1515.901 | 5116.623 | -0.06177 | 0.39197 | 1350.089 |
| nested_MAE | 1481.340 | 5099.290 | -0.05459 | 0.12592 | 1080.393 |
| nested_RMSE | 1523.457 | 5077.657 | -0.04566 | 0.31736 | 1277.778 |

## Interpretation

Exploratory nested CV on an already studied dataset; not an independent external validation. No production promotion.
Only 25 proteins are available. Near-homologs are not separated by sequence clusters. Repeated conditions with different measurements and incomplete assay-context features limit achievable accuracy. Lower MAE can coexist with worse RMSE, correlation, or protein-balanced error. A negative R2 remains a poor result relative to the test-set mean reference.

All candidate settings were saved before model fitting. Candidate selection occurs solely within each outer training fold. PCA uses unique training proteins and up to five components; interactions allow different condition responses by protein representation. Reference baselines retain their original repeated-row PCA and no clipping. New candidate predictions are clipped at zero after any log inverse transformation. No test-row deletion, target editing, new embeddings, or served-model replacement occurred.

`fold_manifest.json` records outer and inner row/protein membership; `selection.json` records every inner score and chosen candidate. `oof_predictions.csv`, `fold_metrics.csv`, and `protein_metrics.csv` retain the complete evaluation. `config.json` records hashes, runtime, and candidate settings.

Nested selection method: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html

Verified 35 protected files unchanged.