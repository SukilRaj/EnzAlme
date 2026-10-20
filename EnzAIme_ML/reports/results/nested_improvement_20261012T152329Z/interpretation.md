# What changed and what can be inferred

Date: 2026-10-12. All scores are pooled out-of-fold scores on the same 221 confirmed records. They are separate from the served legacy model's historical metrics.

| Evaluation procedure | MAE (uM) | RMSE (uM) | R2 | Spearman |
|---|---:|---:|---:|---:|
| Existing A: conditions only | 1420.713 | 5085.699 | -0.04897 | 0.44088 |
| Existing C: embedding + conditions | 1515.901 | 5116.623 | -0.06177 | 0.39197 |
| Nested selection for MAE | 1481.340 | 5099.290 | -0.05459 | 0.12592 |
| Nested selection for RMSE | 1523.457 | 5077.657 | -0.04566 | 0.31736 |

These are selection procedures: the algorithm is chosen independently using inner grouped validation in each outer training fold. They are not scores for one newly deployed model. Thirteen candidate specifications were recorded before fitting. Each uses only the original environmental inputs and, where applicable, existing frozen embeddings. No source identifiers or target-derived features were used.

The MAE-selected procedure improves MAE by approximately 2.28% versus C, but worsens MAE by approximately 4.27% versus the stronger A baseline. Its ranking correlation also falls. The RMSE-selected procedure improves RMSE by approximately 0.76% versus C and 0.16% versus A, with worse MAE than either baseline. No claim of statistical significance is supported. All pooled R2 values remain negative. These findings do not justify replacing the served model or claiming a major accuracy improvement.

## Remaining error and useful next work

PHL-7 still dominates squared error under the MAE-selected procedure. The dataset also has 47 groups with identical protein ID, temperature, pH and duration but more than one measured target. A deterministic predictor using only those inputs cannot distinguish those rows.

As a descriptive diagnostic, fitting the exact median to each identical-input group gives an empirical MAE floor of 297.026 uM; fitting its mean gives an empirical RMSE floor of 1594.508 uM. These calculations use all observed targets and are **not cross-validation scores, achievable unseen-protein estimates, or deployable predictions**. They show how much observed disagreement cannot be resolved using the current feature representation alone; they do not establish biological noise as the cause.

The next justified data work is to curate pre-assay enzyme loading, PET mass/concentration, material form/crystallinity, and reaction volume with explicit units and missingness. Start from retained source assay metadata; do not derive these features from outcomes or use publication IDs as predictors. Then compare a context-augmented model under the same protein-grouped discipline and sequence-cluster sensitivity analysis. More independently measured proteins and comparable assays are needed for a strong external test. The completed experiment does not prove that any proposed feature will improve generalization.

Existing artifacts and results were preserved, with 35 protected files hash-checked. Sixteen Python tests pass, including independent metric recomputation, inner/outer protein isolation and invariance of inner model selection to outer-test targets. Frontend lint/build and drawing-geometry checks pass.
