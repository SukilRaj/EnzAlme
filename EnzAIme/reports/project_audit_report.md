# ENZAIme — Full Project Audit Report

Date: 18-09-2026
Environment: Windows (win32), Python 3.14.7, pandas 3.0.5, numpy 2.5.2,
torch 2.14.0+cpu, transformers 5.16.1, scikit-learn 1.9.0, joblib 1.6.0,
BioPython 1.88, scipy 1.18.1, tqdm 4.70.0, matplotlib 3.11.2.
GPU on this machine: **none**. Kaggle GPU: **expected** (notebook provided).

---

## 1. Existing project structure (top level)

```
EnzAIme/
├── backend/app/            FastAPI (main.py, schemas.py, services/{model,recommendation,mutation}_service.py)
├── common/enzaime_core/    Shared scientific core (config, data_loader, scoring, model, embeddings, mutation)
├── frontend/               React + Vite UI
├── scripts/                01_inspect_data .. 07_evaluate_model (old 20-column pipeline)
├── src/                    inspect_datasets.py, build_master_dataset.py (28-column master pipeline, NEW)
├── notebooks/              EnzAIme_Kaggle_Training.ipynb
├── data/                   demo/ raw/ interim/ processed/ mutation/
├── datasets/               PAZy, RCSB, UniProt, FireProtDB, new_release TSV (raw bags)
├── artifacts/              metrics.json only (no trained model yet)
├── reports/                dataset_inspection.json, data_inventory.json, evaluation_summary.json, CSV/JSON quality files
├── docs/                   api, architecture, data_pipeline, deployment, model, mutation, scoring, viva_notes
└── tests/                  conftest.py, test_api.py, test_data.py, test_mutation.py, test_scoring.py
```

## 2. Data files and shapes

| File | Rows | Kind | Used by master pipeline |
| --- | --- | --- | --- |
| `data/processed/master_enzymes.csv` | 75 | 28-col enzyme table | **primary catalogue** (output of `src/build_master_dataset.py`) |
| `data/processed/master_enzymes_deduplicated.csv` | 75 | same rows deduped | identical (no dup seqs) |
| `data/processed/enzymes.csv` | 9 | 20-col canonical app table | backend `data_loader` (must remain intact) |
| `data/processed/environmental_scenarios.csv` | 225 | synthetic grid | old scripts/04 |
| `data/processed/model_ready_dataset.csv` | 675 | old training table | old scripts/06 |
| `data/demo/enzymes_demo.csv` | 9 | curated demo | upstream of master |
| `datasets/pazy_proteins.fasta` | 59 | nylonase seqs | upstream of master |
| `datasets/pazy_proteins (1).fasta` | 8 | PET/cutinase-lipase | upstream of master |
| `datasets/rcsb_pdb_7CWQ.fasta` | 1 | PDB structure | upstream of master |
| `data/raw/pazy/pazy_proteins.fasta` | 2 | verified seqs | upstream of master |
| `datasets/fireprotdb_20251015-164116.csv` | 5,465,660 | mutation ddG | evidence-only, 0 overlap |
| `datasets/new_release_structure_sequence.tsv` | 535 | generic PDB seqs | excluded (no overlap/annotation) |
| `datasets/uniprot...dmatase...fasta.gz` | ~12 | tRNA dimethylallyltransferase | excluded (scope) |

## 3. master_enzymes.csv columns (28)

`enzyme_id, accession, enzyme_name, protein_sequence, sequence_length,
enzyme_family, ec_number, organism, pollutant_type, substrate, ph_opt, ph_min,
ph_max, temperature_opt_c, temperature_min_c, temperature_max_c, salinity_opt,
salinity_min, salinity_max, salinity_unit, evidence_type, evidence_score,
source_database, source_file, source_record_id, sequence_hash, data_quality_flag,
notes`

## 4. Missing-value statistics (computed from master_enzymes.csv)

| Field | Missing % | Notes |
| --- | --- | --- |
| protein_sequence | 6.7 (5/75) | ENZ004, ENZ005, ENZ007, ENZ008, ENZ009 |
| sequence_hash / sequence_length | 6.7 | same 5 |
| accession | 90.7 | only 7 real accessions |
| organism | 86.7 | |
| ec_number | 90.7 | |
| ph_opt | 88.0 | 9 present (demo rows), all heuristic |
| ph_min / ph_max | 100 | no pH ranges exist |
| temperature_opt_c | 88.0 | 9 present (demo rows), all heuristic |
| temperature_min/max | 100 | no temperature ranges exist |
| salinity_* | 100 | **no salinity data in any source** |
| pollutant_type | 1.3 | 1 unknown (7CWQ) |
| enzyme_family / substrate | 100 | no source annotates these |

No matrix cell is invented: missing values remain missing and are flagged.

## 5. Duplicate / invalid-sequence audit

- Duplicate enzyme_ids: **0**. Duplicate accessions: **0** (only 7 are filled).
- Duplicate sequences among the 70 with sequence: **0** (hash-verified).
- Exact-sequence cross-source duplicates already merged by `build_master_dataset.py`.
- Invalid amino-acid residues: **0** (all 70 pass the standard-20 filter).

## 6. Existing ML/model architecture (common/enzaime_core)

- `scoring.py`: transparent rule-based "Environment-Aware Suitability Score"
  `S = 0.40*L_poll + 0.25*L_pH + 0.25*L_T + 0.10*L_S`. Weights validated to sum
  to 1.0. Range/optimum decay logic; salinity unknown→neutral default (0.8).
- `model.py`: `SuitabilityNet` — ESM embedding → proj(128); env features →
  proj(32); fusion(160)→hidden(64)→sigmoid[0,1]. Regresses toward the rule-based
  score (reference label), never claims experimental ground truth.
- `embeddings.py`: ESM-2 mean-pooling (BOS/EOS not excluded in current code —
  masks cover padding but include BOS/EOS tokens), per-enzyme `.npy` cache,
  `resolve_and_load_model` with single fallback.
- `mutation.py`: `MutationDataProvider` ABC + `FireProtDBProvider` (reads
  `data/mutation/fireprotdb_subset.csv` when present) + `DemoStatisticalMutationProvider`
  (Kyte-Doolittle / residue volume / helix propensity heuristic). Honest labelling.

## 7. Existing training flow (scripts/04-06)

1. `04_generate_scenarios.py`: synthetic environmental grid (225 rows).
2. `05_generate_embeddings.py`: frozen ESM-2 embeddings, cached per enzyme.
3. `06_train_model.py`: builds model_ready_dataset (reference score cross),
   enzyme-level K-fold (split on enzyme_id — correct), trains baselines +
   `SuitabilityNet` only if torch + >= MIN_TRAINING_ROWS + embeddings present,
   otherwise documented skip. Metrics in `artifacts/metrics.json`.
4. `07_evaluate_model.py`: ranking-change analysis + evaluation_summary.json.

## 8. Existing inference flow (backend)

`POST /recommend` → pollutant pre-filter → `scoring.score_enzyme` per candidate →
optional AI refinement (`ModelService.predict_ai_score`) if `DEMO_MODE=false` and
artifacts load → rank → top-K → `scoring.explain` payload + disclaimer.
`ModelService` auto-falls back to the rule engine on missing/broken artifacts.

## 9. Current problems identified

1. **Master dataset has 28 columns but training code (`scripts/*`) assumes the old
   20-column canonical schema** — the new master table is not consumed by any
   training/eval script yet.
2. **No explicit missingness feature engineering** — pH/temp/salinity gaps are not
   represented to the model as flags; the old table just drops/keeps silently.
3. **No scenario generator that works over the 75-enzyme master**; old scenarios
   cover only the 9 demo enzymes.
4. **No transparent, documented label-generation module** for the master dataset;
   the reference target exists only implicitly inside `scripts/06`.
5. **Embedder does not exclude BOS/EOS** and only has a single hard-coded fallback
   (`esm2_t6_8M`); no state_dict-only checkpoint handling; no hash-keyed cache; no
   `npy`-matrix + index output.
6. **No averaged/aggregated model comparison** (rule vs ridge vs RF/GBM vs MLP),
   no calibrated metrics (RMSE/MAE/Spearman/top-k consistency), no saved scaler/
   config bundle for the new pipeline, no feature-importance summary.
7. **No Kaggle-ready orchestrating script** (`src/train_kaggle.py`) and no
   leakage-prevention protocol doc.
8. **No inference module** exposing explainable recommendations with confidence +
   uncertainty from the master schema.
9. **Directed-evolution prep** exists in `common/enzaime_core/mutation.py` but there is
   no embedding-delta comparison layer for mutations.
10. `requirements.txt` lists torch/transformers as commented-out optional deps.
11. No tests for the new `src/` pipeline (data quality, labels, embedder, group split).

## 10. Recommended changes (implemented in this pass)

- **ADD** `src/data_quality.py` — clean/validate master, add missingness
  indicators, dedup/conflict detection, missing-sequence catalogue.
- **ADD** `src/label_generation.py` — scenario generation over the master +
  transparent, documented derived-compatibility labels.
- **ADD** `src/esm_embedder.py` — ESM-2 650M (default), BOS/EOS exclusion, mean
  pooling, mixed precision, hash-keyed caching, local/state_dict checkpoint
  handling, `.npy` + index CSV outputs.
- **ADD** `src/model.py` — env feature builder + small MLP + baselines
  (ridge / random forest) + metrics (MAE/RMSE/R²/Spearman/top-k).
- **ADD** `src/train_kaggle.py` — Kaggle/local orchestrator; **grouped split**
  (GroupShuffleSplit/GroupKFold on enzyme_id); outputs `artifacts/*`,
  `reports/training_report.md`, `reports/model_comparison.csv`,
  `reports/prediction_examples.csv`, plots; ALSO writes backend-compatible
  artifacts so `DEMO_MODE=false` AI mode keeps working unchanged.
- **ADD** `src/inference.py` — rule-based baseline recommender + ML recommender
  with confidence, completeness, and uncertainty explanations.
- **ADD** `src/mutation_prep.py` — mutation candidate generation + embedding-delta
  ranking layer ("computational candidate", wet-lab validation required).
- **ADD** `notebooks/kaggle_full_training.ipynb`, `docs/model_pipeline.md`,
  `docs/kaggle_execution.md`, `docs/scientific_limitations.md`; extend
  `docs/data_pipeline.md`; update `README.md` and `requirements.txt`.
- **ADD** tests: `test_data_quality.py`, `test_labels.py`, `test_embedder.py`,
  `test_model.py`, `test_group_split.py`, `test_inference.py`, `test_mutation_prep.py`.

## 11. Compatibility constraints (must not break)

- `common/enzaime_core/data_loader.py` REQUIRED_COLUMNS (20) and
  `data/processed/enzymes.csv` must stay intact (backend + tests depend on them).
- `ModelService` expects `artifacts/model.pt | scaler.pkl | encoders.pkl | config.json`
  with `SuitabilityNet`-compatible state dict + env vector
  `[pollutant_onehot..., ph_norm, temp_norm, sal_norm]`.
- Existing tests (54) must keep passing (`pytest tests/ -v`).