# Data Pipeline

## Directory layout

```
data/
  raw/        Unmodified original source files (never overwritten)
  interim/    Cleaned/intermediate outputs (script 02)
  processed/  Canonical model-ready tables (scripts 03-06)
  demo/       Shipped MVP demo dataset + synthetic scenarios
  mutation/   Optional FireProtDB subset (fireprotdb_subset.csv), if curated
```

## Pipeline stages

```
raw FASTA (data/raw/pazy/pazy_proteins.fasta)
        |
        v
sequence cleaning + deduplication + validation   (scripts/02_clean_sequences.py)
        |
        v
identifier normalization + biological metadata integration
        |
        v
canonical enzymes.csv                             (scripts/03_build_master_dataset.py)
        |
        v
scenario generation (synthetic pH x T x salinity x pollutant grid)
                                                    (scripts/04_generate_scenarios.py)
        |
        v
model-ready dataset (enzyme x scenario, reference compatibility score)
                                                    (scripts/06_train_model.py)
```

Each script is independently executable from the repo root:

```bash
python scripts/01_inspect_data.py
python scripts/02_clean_sequences.py
python scripts/03_build_master_dataset.py
python scripts/04_generate_scenarios.py
python scripts/05_generate_embeddings.py   # optional, requires torch+transformers
python scripts/06_train_model.py           # optional, requires torch+transformers
python scripts/07_evaluate_model.py        # optional, requires 06 to have run
```

## Data abstraction layer (Section 4 / 19)

`common/enzaime_core/data_loader.py` is the single place that knows where the enzyme
table physically lives. Load order:

1. `data/processed/enzymes.csv` — output of `scripts/03_build_master_dataset.py`
2. `data/demo/enzymes_demo.csv` — shipped MVP demo dataset (fallback)

**To plug in real data later** (BRENDA/UniProt/PAZy/FireProtDB/industrial wastewater),
drop the real files into `data/raw/` using the names documented in
`data/raw/README.md`, then re-run scripts 01-04. No application code changes are
required — `scoring.py`, `mutation.py`, the backend, and the tests all consume the same
`enzymes.csv` schema regardless of where the rows came from.

## Why the shipped dataset looks the way it does

This MVP package was assembled without direct access to the project's original lab
files. The demo dataset (`data/demo/enzymes_demo.csv`) was built instead from
independently verifiable public records — see `data/demo/SOURCES.md` for the full
citation table. Two sequences (IsPETase, MHETase) were retrieved and cross-verified
against multiple independent sources; the remaining seven records ship with real
accessions/EC numbers/citations but a blank `sequence` field rather than a fabricated
one. Numeric pH/temperature values that could not be independently curated from BRENDA
within this MVP's scope are flagged `demo_assumption = true` and are never presented in
the UI as experimental measurements.

## Data schema (`enzymes.csv`)

| Column | Type | Notes |
|---|---|---|
| `enzyme_id` | string | Primary key, e.g. `ENZ001` |
| `accession` | string | UniProt (or GenBank) accession |
| `enzyme_name` | string | Common name |
| `ec_number` | string | Enzyme Commission number |
| `pollutant` | string | One of `PET`, `PUR`, `PA` |
| `sequence` | string | Amino-acid sequence, blank if not yet curated |
| `seq_length` | int | Residue count |
| `source` | string | Database/literature origin |
| `evidence_type` | string | `verified` / `predicted` |
| `pH_opt`, `pH_min`, `pH_max` | float | pH tolerance |
| `T_opt`, `T_min`, `T_max` | float | Temperature tolerance (°C) |
| `salinity_evidence` | bool | Whether salinity tolerance is documented |
| `salinity_min`, `salinity_max` | float | Salinity tolerance, if known |
| `notes` | string | Free text, always includes citations |
| `demo_assumption` | bool | True if any numeric value is a literature-approximate/demo value rather than a directly curated BRENDA figure |

## Data quality validation (Section 38)

`scripts/03_build_master_dataset.py` runs automatic checks (duplicate IDs/sequences,
invalid amino acids, out-of-range pH/temperature, negative salinity, missing/invalid
pollutant categories) and writes `reports/data_quality_report.json` and `.csv`.

## Synthetic environmental scenarios (Section 17)

`scripts/04_generate_scenarios.py` builds a 5 (pH) x 5 (temperature) x 3 (salinity) x 3
(pollutant) = 225-row grid of **synthetic evaluation scenarios**, explicitly labelled as
such (`is_synthetic: true`) — they are not real wastewater observations. This grid is
used only to build the model-ready training table for the optional neural model
(Section 14); it is never presented to the end user as real environmental data.

## ML-ready cleaning + scenario pipeline (`src/`)

The master dataset (`master_enzymes.csv`, see README §21) feeds a second, robust stage
that adds **explainable missingness** and **transparent labels** without ever inventing
biology:

```
master_enzymes.csv
   │  src/data_quality.py
   ├─ master_enzymes_clean.csv              (75 rows · cleaning flags + has_* indicators)
   ├─ master_enzymes_valid_sequences.csv    (70 rows · unique, embeddable)
   ├─ master_enzymes_missing_sequences.csv  (5 rows  · catalogue-only)
   ├─ sequence_recovery_log.csv             (STEP 3: no auto-download; UniProt template URL)
   ├─ reports/data_quality_report.csv       (per-column missing %)
   ├─ reports/data_conflicts.csv / unmatched_records.csv
   │
   │  src/label_generation.py
   ├─ training_scenarios.csv                (~6,900 rows · conservative 5×5×4 grid)
   │
   │  src/esm_embedder.py
   ├─ esm_embeddings.npy + esm_embedding_index.csv   (aligned, sorted by enzyme_id)
   │
   │  src/train_kaggle.py  (+ src/model.py)
   └─ artifacts/  +  reports/{training_report.md, model_comparison.csv, prediction_examples.csv}
```

Missing-value policy (documented onboarding for STEP 4 in the audit report):

- Missing numeric `ph_opt` / `temperature_opt_c` → neutral imputed value + `has_*_opt=0`.
- Missing salinity (0/75 documented) → neutral salinity term + `has_salinity_data=0`.
- `metadata_completeness` = fraction of 8 core fields present (0..1).
- `evidence_confidence` = ordinal provenance score from `evidence_type` only.
- `unknown_feature_count` = how many of pH/temperature/salinity are unknown for the row —
  a direct uncertainty feature for the model.

Full design, formula and leakage protocol: `docs/model_pipeline.md`, and local/Kaggle run
commands in `docs/kaggle_execution.md`. Scientific limits: `docs/scientific_limitations.md`.
