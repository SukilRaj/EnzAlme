# Step 4: Fold-Level Error and Generalization Analysis

## Reproduction and scope

The analysis uses the confirmed dataset with 221 records and 25 proteins. No ambiguous records, embeddings, source data, production models, or existing reports were modified.

No row-level out-of-fold prediction artifact was available, so predictions were reproduced with the original A/B/C implementation: GroupKFold(n_splits=5) by protein_id, train-fold-only StandardScaler/PCA, Ridge(alpha=10), log1p target transformation, and expm1 back-transformation. The original implementation contains no prediction clipping.

Reproduction check:

| Metric | Max absolute difference | Within tolerance | Undefined status matched |
|---|---:|---|---|
| mae_um | 1.8189894035458565e-12 | True | True |
| rmse_um | 5.4569682106375694e-12 | True | True |
| r2 | 1.7053025658242404e-13 | True | True |
| spearman | 9.020562075079397e-17 | True | True |

## Fold-level metrics

The full fold table is in `fold_metrics.csv`. SSE is the sum of squared residuals, SST is the sum of squared deviations from the fold target mean, and R² is calculated as `1 - SSE/SST`. Undefined values remain blank in CSV and are described in `undefined_metrics`.

| Configuration | Fold | Test proteins | Test records | MAE | RMSE | R² | Spearman | SSE | SST |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A | 1 | 44 | 75 | 1354.6368 | 1892.6467 | -0.6933 | 0.7575139302982451 | 268658359.2213 | 158663929.4808 |
| A | 2 | 17;223;226;37;4;42 | 37 | 4850.7148 | 12027.4208 | -0.1410 | 0.0776953085357601 | 5352377507.3896 | 4690771085.8255 |
| A | 3 | 1;11;148;149;185;496 | 37 | 136.4387 | 232.4289 | -0.7320 | -0.26575990252174453 | 1998858.9810 | 1154108.9206 |
| A | 4 | 177;195;225;25;483;495 | 36 | 624.6841 | 1584.8910 | -0.0515 | 0.34540085338402376 | 90427662.3767 | 85997505.1018 |
| A | 5 | 13;15;224;240;41;481 | 36 | 149.0675 | 266.4562 | 0.1590 | 0.6510381614771362 | 2555961.1676 | 3039284.3065 |
| B | 1 | 44 | 75 | 1667.1315 | 1862.0298 | -0.6389 | undefined | 260036626.3273 | 158663929.4808 |
| B | 2 | 17;223;226;37;4;42 | 37 | 4652.7254 | 12133.1341 | -0.1612 | -0.4875393471864524 | 5446878857.3566 | 4690771085.8255 |
| B | 3 | 1;11;148;149;185;496 | 37 | 2357.4173 | 3679.6421 | -433.0763 | -0.021246677361381635 | 500971330.5553 | 1154108.9206 |
| B | 4 | 177;195;225;25;483;495 | 36 | 757.3964 | 1717.5972 | -0.2350 | -0.5200258540689173 | 106205039.5057 | 85997505.1018 |
| B | 5 | 13;15;224;240;41;481 | 36 | 156.7955 | 324.6989 | -0.2488 | 0.12180903134049458 | 3795456.8825 | 3039284.3065 |
| C | 1 | 44 | 75 | 1088.0411 | 1233.9255 | 0.2803 | 0.7377313120254275 | 114192913.2077 | 158663929.4808 |
| C | 2 | 17;223;226;37;4;42 | 37 | 4720.9125 | 12112.9032 | -0.1573 | -0.14635311907147217 | 5428729672.7237 | 4690771085.8255 |
| C | 3 | 1;11;148;149;185;496 | 37 | 1277.5857 | 1909.8701 | -115.9399 | -0.04402523379591329 | 134961341.3088 | 1154108.9206 |
| C | 4 | 177;195;225;25;483;495 | 36 | 730.0577 | 1704.5029 | -0.2162 | 0.15833556464340368 | 104591879.1719 | 85997505.1018 |
| C | 5 | 13;15;224;240;41;481 | 36 | 144.0074 | 301.2110 | -0.0747 | 0.49147631797162655 | 3266211.0519 | 3039284.3065 |

## Pooled versus mean-fold metrics

| Configuration | Pooled MAE | Pooled RMSE | Pooled R² | Mean fold MAE | Mean fold RMSE | Mean fold R² |
|---|---:|---:|---:|---:|---:|---:|
| A | 1420.7127 | 5085.6992 | -0.0490 | 1423.1084 | 3200.7687 | -0.2917 |
| B | 1888.3306 | 5346.7490 | -0.1594 | 1918.2932 | 3943.4204 | -86.8720 |
| C | 1515.8998 | 5116.6227 | -0.0618 | 1592.1209 | 3452.4825 | -23.2216 |

## Main error-contributing proteins

The ten largest protein-level SSE contributions per configuration are in `top_squared_error_proteins.csv`. The corresponding largest rows are in `top_squared_error_rows.csv`.

- A: 37 (93.0%), 44 (4.7%), 483 (1.5%), 42 (0.4%), 17 (0.2%)
- B: 37 (86.0%), 149 (7.9%), 44 (4.1%), 483 (1.5%), 17 (0.2%)
- C: 37 (93.5%), 149 (2.3%), 44 (2.0%), 483 (1.6%), 17 (0.2%)

## Extreme R² evidence

The most extreme fold-level R² values are interpreted with SSE and SST together. A large negative R² requires SSE to be large relative to SST; low target variance makes SST small and amplifies that ratio.

| Configuration | Fold | R² | SSE | SST | Test target std | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| B | 3 | -433.0763 | 500971330.56 | 1154108.92 | 179.0491 | SSE/SST = 434.08; both error magnitude and target variance must be considered |
| C | 3 | -115.9399 | 134961341.31 | 1154108.92 | 179.0491 | SSE/SST = 116.94; both error magnitude and target variance must be considered |
| A | 3 | -0.7320 | 1998858.98 | 1154108.92 | 179.0491 | SSE/SST = 1.73; both error magnitude and target variance must be considered |
| A | 1 | -0.6933 | 268658359.22 | 158663929.48 | 1464.2770 | SSE/SST = 1.69; both error magnitude and target variance must be considered |
| B | 1 | -0.6389 | 260036626.33 | 158663929.48 | 1464.2770 | SSE/SST = 1.64; both error magnitude and target variance must be considered |

## Within-protein A/C and B/C comparisons

`within_protein_comparisons.csv` contains row-level exploratory differences. These comparisons are descriptive because each protein's records share a held-out fold and the data are observational; they are not causal evidence.

## Plots

- `actual_vs_predicted.png` preserves all observations for each configuration.
- `per_protein_squared_error.png` shows protein-level SSE without excluding observations.

## Limitations

Only 25 proteins are available, record counts are imbalanced, and some folds contain one high-count protein while others contain six smaller groups. Fold-level R² is therefore sensitive to target variance and a few large residuals. Protein-level comparisons are exploratory, and no production model is selected from this analysis.
