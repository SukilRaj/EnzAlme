# ENZAIme — Evaluation Protocol (leakage prevention)

> Version 1 · Date 18-09-2026

## 1. The problem

Every training row is a (enzyme, environmental scenario) pair generated from one
enzyme. Scenario rows of the same enzyme share the same sequence/embedding and
differ only in pH/temperature/salinity. A **random row-level split would place
near-identical rows of the same enzyme in both train and test**, inflating every
metric and giving a false impression of generalization.

## 2. Mandatory grouped splitting

All model evaluation **must** split by the group `enzyme_id` (equivalently by
`sequence_hash`):

- Primary: `sklearn.model_selection.GroupShuffleSplit(n_splits=1, test_size=0.2)`
  with `groups = enzyme_id`, `random_state = 42`.
- Cross-validation: `GroupKFold(n_splits=5)` with `groups = enzyme_id`.
- Fallback (documented): if fewer than 5 unique enzymes exist, a single
  enzyme-level 70/30 holdout is used and reported explicitly.

`src/model.py::GroupSplitter` implements both, plus a `no_leakage()` assertion
used by tests: a split is invalid if any enzyme_id appears on both sides.

## 3. What the metrics mean (and do not mean)

- Target = `derived_compatibility_label` produced by `src/label_generation.py`
  (documented in `reports/label_generation_method.md`).
- Metrics (MAE / RMSE / R² / Spearman / top-k consistency) measure **agreement
  with the derived label**, not experimental degradation efficiency.
- The rule-based / derived-label baseline has MAE = 0 vs the reference by
  construction; it exists as a sanity anchor, not as a claim about biology.
- ML models are compared against (a) pollutant-only constant and (b) the
  derived label baseline. No claim of superiority is made without evidence.

## 4. Held-out recommendation evaluation

For each test scenario the top-k ranking produced by each model is compared with
the ranking of the derived label; `top1_consistent` and `topk_consistent` are
reported. This is ranking-agreement evaluation only.

## 5. Reproducibility

- Seeds: all random operations use `random_state=42` (see `src/model.py::set_seed`).
- Artifacts: `artifacts/metrics.json`, `reports/model_comparison.csv`,
  `reports/training_report.md`, `reports/prediction_examples.csv` record the exact
  split, model hyperparameters and per-fold/overall metrics so runs can be audited.
- `artifacts/feature_config.json` stores the feature schema + pollutant categories
  used at training time so inference builds identical vectors.