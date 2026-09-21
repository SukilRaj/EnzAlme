# Model Pipeline (ESM-2 + derived compatibility labels)

This document specifies the ML pipeline implemented in `src/` (`data_quality.py`,
`label_generation.py`, `esm_embedder.py`, `model.py`, `train_kaggle.py`,
`inference.py`, `mutation_prep.py`).

## 1. Data quality and missing-value strategy (`src/data_quality.py`)

Input: `data/processed/master_enzymes.csv` (75 rows × 28 cols).

Per-row cleaning and flags:

| Flag | Meaning |
| --- | --- |
| `sequence_missing` | no protein sequence present |
| `sequence_empty_after_cleaning` | non-empty raw but nothing valid left |
| `removed_ambiguous_residues:X,B,Z,…` | non-canonical letters stripped |
| `possible_dna_rna` | alphabet ⊆ {A,C,G,T,U,N} and long |
| `short_sequence` | `< 20 aa` |
| `excessively_long_sequence` | `> 2048 aa` |
| `longer_than_esm_max:truncated_at_1022` | embeds safely via truncation, noted |

Missingness is modelled explicitly, never imputed silently:

- `safe_numeric_imputation(series, missing)` fills missing numerics with a single
  **documented neutral value**; every enzyme gets the same constant so the network can
  learn “missing” unambiguously from the companion `has_*` flag.
- `add_missingness_features` adds `has_sequence, has_accession, has_ph_opt, has_ph_range,
  has_temperature_opt, has_temperature_range, has_salinity_data, has_substrate,
  has_ec_number, has_organism`.
- `calculate_metadata_completeness` = fraction of 8 core fields populated (0..1).
- `calculate_evidence_confidence` = ordinal provenance score derived **only** from the
  `evidence_type` label: experimental 1.0, curated 0.85, predicted 0.6, inferred 0.4,
  heuristic 0.25, unknown 0.1.
- `unknown_feature_count` = number of pH/temperature/salinity unknowns (0..3).

Outputs: clean CSV, valid/missing-sequence CSVs (STEP 2 outputs), `sequence_recovery_log.csv`
(STEP 3, recovery is **never automatic** — it records an identifier + an explicit,
user-approved download plan), plus `reports/data_quality_report.csv`,
`reports/data_conflicts.csv`, `reports/unmatched_records.csv`.

## 2. Transparent scenario + label generation (`src/label_generation.py`)

Per enzyme (only enzymes with **both** a valid sequence and a pollutant get scenarios):

- Conservative grid: pH {6,7,8,9,10} × temperature {25,35,45,55,65} °C × salinity {0,0.5,1,2}.
- If the enzyme documents min/max pH (resp. temperature), a 5-point inner grid spanning
  that range replaces the conservative pH (resp. temperature) axis.
- **Salinity**: no enzyme in the dataset documents salinity tolerance
  (`has_salinity_data = 0` everywhere) → the salinity component is neutral (0.5) in every
  row and flagged `salinity_metadata_available = 0`.

Derived label (identical columns `compatibility_score` / `suitability_label` /
`derived_compatibility_label`):

```
label = clip( 0.40·pollutant_term + 0.25·pH_term + 0.25·temp_term + 0.10·salinity_term, 0, 1 )
pH_term   = exp(-(|scenario_ph   - ph_opt|  / DELTA_PH)^2)   if known, flat tolerance ±1.5
temp_term = exp(-(|scenario_temp - T_opt|   / DELTA_TEMP)^2) if known, flat tolerance ±10
pollutant_term rounds and matches the enzyme's pollutant evidence
salinity_term = 0.5 (neutral) whenever undocumented
```

Confidence: `0.5·evidence_confidence + 0.5·(known pH + known temp + known salinity)/3`.
`label_source = derived_compatibility_label` in every row. Labels are never called
experimental degradation efficiency.

## 3. Frozen ESM-2 embeddings (`src/esm_embedder.py`)

- Model: `facebook/esm2_t33_650M_UR50D` (1280-dim), fully frozen (`torch.no_grad()`),
  mean pooling over hidden states with **BOS/EOS excluded** (degenerate fallback to the
  full masked window when ≤ 2 real tokens).
- Loading ladder: local HF dir → raw `state_dict` paired with a cached `EsmConfig`
  (`lm_head` keys filtered, `strict=False`) → local HF cache match → Hub download
  (`--download`, Kaggle) → any cached fallback ESM (`t12_35M` 480-dim first). This makes
  the entire pipeline runnable **offline**.
- Dedup: identical sequences are embedded once per hash and cached at
  `artifacts/esm_cache/<sha256>.npy`; every enzyme still receives its own index row.
- Outputs (aligned, both sorted by `enzyme_id`): `esm_embeddings.npy` (N×D float32) and
  `esm_embedding_index.csv`; `esm_embedding_model.json` records model/source/dim.
- Mixed precision (`autocast` fp16) is enabled only on CUDA.

## 4. Model architecture and baselines (`src/model.py`)

Feature vector per (enzyme, scenario) row:

```
[ ESM embedding (D)   pollutant one-hots   scenario_ph/temp/salinity (standardised)
  pollutant_evidence_score   ph/temperature/salinity_metadata_available
  has_sequence  has_accession  metadata_completeness  unknown_feature_count ]
```

- `SuitabilityMLP` — intentionally tiny (64 hidden, dropout 0.3, residual block), Adam,
  MSE on the derived label, early stopping on the held-out group, `BatchNorm1d`.
- Baselines: `Ridge`, `RandomForestRegressor` (300 trees, depth ≤ 6),
  `GradientBoostingRegressor` (200, depth 3, lr 0.05).
- Metrics (`evaluate_regression`/`top_k_consistency`) report MAE / RMSE / R² / Spearman
  and top-k rank consistency **against the derived label** — the metrics docstring and
  every report state this explicitly.
- `train_backend_compatible_model`: trains the legacy `enzaime_core.model.SuitabilityNet`
  on `[pollutant_onehot(3), ph/14, (T+10)/130, sal/10]` and saves
  `artifacts/{model.pt, scaler.pkl, encoders.pkl, config.json}` so the FastAPI
  `ModelService` (AICO model path) keeps working unchanged.

## 5. Training, artifacts and leakage prevention (`src/train_kaggle.py`)

- Refuses to proceed if the group split leaks (`no_leakage` assertion).
- StandardScaler is fit on the **train enzyme group only** — no scaler leakage.
- `GroupShuffleSplit(test_size=0.2, seed=42)` hold-out **and** `GroupKFold(5)` (fallback
  single enzyme-level hold-out when < 5 enzymes) — protocol in
  `reports/evaluation_protocol.md`.
- The best model (lowest test RMSE; MLP preferred on a tie) is saved; if a baseline wins,
  `best_model.pt` records a marker and `best_baseline.pkl` holds the estimator.
- Outputs: `artifacts/{best_model.pt, best_baseline.pkl, scaler.pkl, feature_config.json,
  metrics.json, model.pt, encoders.pkl, config.json}`; `reports/{training_report.md,
  model_comparison.csv, prediction_examples.csv}` plus optional plots.

## 6. Inference (`src/inference.py`) and mutation prep (`src/mutation_prep.py`)

- `RuleBasedRecommender`: fully transparent, no ML — rank by the same weighted formula
  with per-enzyme `explanation`/`limitations` strings and confidence that drops with
  missing metadata.
- `MLRecommender`: uses frozen embeddings + saved MLP; **auto-falls back** to the rule-based
  recommender when the best saved model is a baseline or artifacts are absent.
- `mutation_prep.py`: deterministic single-point mutation candidates scored by residue
  property delta + local solvent-context heuristic, labelled computational-only.

## 7. Reproducibility

`set_seed(42)` is applied at the start of training; the splitter, all sklearn estimators
and the MLP carry explicit `random_state`/`torch.manual_seed`. The exact runs to reproduce
local and Kaggle results are in `docs/kaggle_execution.md`.