# Returned Kaggle activity checkpoint review

The user returned `enzaime_neural_results.zip` on 2026-10-13. Imported its 29 entries into `models/neural` and `data/neural_features` after checking paths, existing-file conflicts and the training dataset SHA-256. The checkpoint loaded with PyTorch's weights-only loader and produced finite candidate rankings with the project implementation.

Model: frozen ESM-2 35M per-residue features with Attention1D and assay conditions. Image branch was not trained; no thermostability output is available. No Ridge fallback was used.

## Independently recomputed test results

| Metric | Value |
|---|---:|
| Held-out measurements | 18 |
| Held-out proteins | 5 |
| MAE | 46.7844 µM |
| RMSE | 53.4576 µM |
| R² | -2.2965 |
| Observed concentration range | 0.3–106.2 µM |
| Predicted concentration range | 15.48–73.58 µM |
| Saved training-median baseline MAE | 387.0296 µM |

The raw MAE/RMSE agree with the exported manifest. The saved training-median baseline is worse, but the negative R² indicates poor performance relative to the held-out mean reference. That mean is a retrospective diagnostic, not a deployable baseline fitted without test data. This small test set covers only a low-concentration range and does not establish generalization across the full project target range.

Predictions for SM14est are around 73 µM whereas its observed held-out values range from 0.3 to 9.4 µM. This highlights substantial protein-specific error. Do not describe the model as accurate, superior to the existing Ridge model, or validated for mutation effects. Ridge has not been compared on this identical split.

## Integration and next experiments

The neural workspace displays held-out MAE, R², protein count and an experimental-use note. API status reports sequence/conditions readiness, with image and thermostability readiness explicit. `recommendation_smoke_test.json` records inference at 40°C, pH 8, 48 hours; these scores are hypotheses, not experimental activity measurements.

The current checkpoint used 208 rows after exclusions/deduplication, with 15/5/5 unique sequence groups in train/validation/test. Exact sequence grouping does not prevent family or publication leakage. Returned held-out records lack assay identifiers and conditions, limiting row-level auditability. Preserve this run and its test results; do not repeatedly tune on these five test proteins.

Next: audit assay/construct consistency and replicate variation; define stronger family/study splits before further training; compare condition-only and neural models on identical splits; add sequence-linked stability data and verified structures; evaluate image benefit separately. The present activity checkpoint can support interface and inference development while those scientific gaps are addressed.
