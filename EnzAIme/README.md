# ENZAIme

**Environment-Aware AI-Based Enzyme Suitability Prediction, Recommendation and Mutation Optimization System**

A working MVP: FastAPI backend + React frontend + a shared scientific core package,
recommending plastic-active enzymes for a specified environmental condition (pollutant,
pH, temperature, salinity) and prioritizing point mutations for a selected candidate.

> **Scientific disclaimer.** ENZAIme is an in-silico decision-support tool. It does not
> claim to experimentally prove enzyme degradation. Suitability scores are
> project-defined computational compatibility estimates, not measured degradation
> efficiency. Mutation predictions are computational and require experimental
> validation. Structural/docking validation is explicitly future work. See
> [Limitations](#19-limitations) below and `docs/viva_notes.md`.

---

## Contents

1. [Project overview](#1-project-overview)
2. [Research problem](#2-research-problem)
3. [Proposed solution](#3-proposed-solution)
4. [Architecture](#4-architecture)
5. [Novelty](#5-novelty)
6. [Dataset strategy](#6-dataset-strategy)
7. [Data schema](#7-data-schema)
8. [Suitability formula](#8-suitability-formula)
9. [ESM-2 explanation](#9-esm-2-explanation)
10. [ML architecture](#10-ml-architecture)
11. [Mutation module](#11-mutation-module)
12. [Installation](#12-installation)
13. [Kaggle training](#13-kaggle-training)
14. [Backend execution](#14-backend-execution)
15. [Frontend execution](#15-frontend-execution)
16. [API documentation](#16-api-documentation)
17. [Demo mode](#17-demo-mode)
18. [Testing](#18-testing)
19. [Limitations](#19-limitations)
20. [Future work](#20-future-work)
21. [Master dataset pipeline](#21-master-dataset-pipeline)
22. [ML pipeline (ESM-2 + derived labels)](#22-ml-pipeline-esm-2--derived-labels)
23. [Scientific disclaimer](#23-scientific-disclaimer)

---

## 1. Project overview

ENZAIme takes four inputs — pollutant, pH, temperature, salinity — and returns the top
2–3 plastic-active enzymes ranked by an environment-aware suitability score, each with a
full compatibility breakdown, evidence, and a plain-language explanation. Selecting a
recommended enzyme opens a mutation-prioritization module that ranks candidate
single-point substitutions for further investigation.

## 2. Research problem

Enzyme selection for plastic bioremediation currently requires manually
cross-referencing scattered literature and database records (PAZy, BRENDA, UniProt) —
and even then, in-vitro optimum conditions reported for an enzyme say little about
whether it will function at a specific site's actual pH/temperature/salinity.

## 3. Proposed solution

An environment-aware recommendation pipeline: filter candidates by documented pollutant
activity, score pH/temperature/salinity fit against each candidate's reported
tolerance, rank, and explain — with an optional ESM-2-based neural refinement layer
where enough training data exists, and a mutation module for downstream optimization.

## 4. Architecture

See `docs/architecture.md` for the full diagram and component table. Summary:

```
Frontend (React/Vite) --HTTP/CORS--> Backend (FastAPI) --imports--> common/enzaime_core
                                                                          |
                                                    data/processed/enzymes.csv (+ demo fallback)
                                                    artifacts/ (optional trained model + embeddings)
```

## 5. Novelty

**Not** ESM-2, not neural networks, not directed evolution (none of these are claimed
as novel). The novelty is **environment-aware integration**: combining protein sequence
information with explicit pollutant/pH/temperature/salinity conditioning for
context-specific enzyme suitability prediction and recommendation, plus downstream
mutation prioritization. `scripts/07_evaluate_model.py` computes concrete evidence that
this conditioning changes which enzyme ranks #1 versus a pollutant-only baseline (see
`reports/evaluation_summary.json` after running the pipeline).

## 6. Dataset strategy

The MVP ships a 9-record demo dataset (`data/demo/enzymes_demo.csv`) built from
independently verifiable public records (real UniProt/GenBank accessions, EC numbers,
and literature citations — see `data/demo/SOURCES.md`). Two sequences (IsPETase,
MHETase) were retrieved and cross-verified against multiple independent sources; the
rest ship with real metadata but a blank sequence field rather than a fabricated one.
The data abstraction layer (`common/enzaime_core/data_loader.py`) lets real
PAZy/BRENDA/UniProt/FireProtDB/wastewater datasets be dropped in later with **zero
application code changes** — see `docs/data_pipeline.md`.

Since the MVP, the verified enzyme set has been expanded from 9 to **75 enzyme-level
records (70 unique protein sequences)** via a reproducible master-dataset pipeline that
merges the curated demo backbone with PAZy exports, an RCSB PDB structure, and verified
raw sequences. See [Master dataset pipeline](#21-master-dataset-pipeline). The live
application still reads the canonical 20-column `data/processed/enzymes.csv`; the
richer 28-column `data/processed/master_enzymes.csv` is the upstream research dataset.

## 7. Data schema

See `docs/data_pipeline.md#data-schema-enzymescsv` for the full column reference.

## 8. Suitability formula

```
S = 0.40*L_poll + 0.25*L_pH + 0.25*L_T + 0.10*L_S      (clipped to [0,1])
```

Full derivation, worked example, and the salinity-unknown-default policy:
`docs/scoring.md`.

## 9. ESM-2 explanation

Used strictly as a **frozen** sequence encoder (no fine-tuning — the verified dataset
is far too small). Default `facebook/esm2_t33_650M_UR50D`, with automatic fallback to a
smaller checkpoint if impractical. Full pipeline: `docs/model.md`.

## 10. ML architecture

A small fusion network (embedding projection 128 → environment projection 32 → fusion
160 → hidden 64 → output 1, ReLU + dropout 0.3), trained to regress toward the
transparent compatibility score (no real matched experimental labels exist yet — see
"the label problem" in `docs/model.md`). **Required fallback:** if training data or
`torch`/`transformers` are unavailable, the system serves recommendations via the
rule-based compatibility engine — this is expected, not an error.

## 11. Mutation module

Generates bounded single-point substitution candidates, scores them via a
FireProtDB-backed provider (if a curated subset is present) or a documented
physicochemical heuristic (Kyte–Doolittle hydropathy, residue volume, helix
propensity), and ranks by `S_mut = 0.7*S_stability + 0.3*S_fitness_proxy`. Every result
is labeled "Computational prediction — experimental validation required." Details:
`docs/mutation.md`.

## 12. Installation

```bash
git clone <this-repo> && cd EnzAIme
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The shared core package installs automatically as part of `requirements.txt`
(`-e ./common`). If you prefer to install it separately: `pip install -e ./common`.

## 13. Kaggle training

Open `notebooks/EnzAIme_Kaggle_Training.ipynb` on Kaggle (attach the project as a
Dataset first), enable a GPU accelerator, and run all cells. It reuses
`scripts/01`–`07` directly, auto-detects CUDA vs CPU, and automatically falls back to a
smaller ESM-2 checkpoint if the primary model is impractical. Outputs land in
`artifacts/` (and are copied to `/kaggle/working/enzaime_artifacts` for download). Full
details: `docs/deployment.md#enabling-the-trained-ai-model`.

## 14. Backend execution

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/health`. Interactive docs at
`http://localhost:8000/docs`.

## 15. Frontend execution

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). Requires the backend
running on `http://localhost:8000` (configurable via `frontend/.env`).

## 16. API documentation

Full endpoint reference with request/response examples: `docs/api.md`. Endpoints:
`GET /health`, `GET /enzymes`, `GET /enzyme/{enzyme_id}`, `POST /recommend`,
`POST /mutations`, `GET /metadata`, `POST /reload-model`.

## 17. Demo mode

`DEMO_MODE=true` (the shipped default) serves every recommendation via the transparent
rule-based compatibility engine. `DEMO_MODE=false` switches to the trained neural model
**if and only if** all required artifact files load successfully — otherwise the system
automatically falls back to the compatibility engine. The active mode is always visible:
`GET /metadata` → `scoring_mode`, and every `/recommend` response, and a badge in the
UI ("Demo / Compatibility Engine" vs "AI Model"). It is never hidden.

## 18. Testing

```bash
pytest tests/ -v
```

54 tests across `test_data.py`, `test_scoring.py`, `test_mutation.py`, `test_api.py` —
covering pH/temperature/salinity compatibility behavior, weight validation, ranking
order, input validation (NaN/Infinity/absurd values/unsupported pollutants → HTTP 400),
mutation candidate validity, and end-to-end API flows including the full user journey
from `/recommend` through `/enzyme/{id}` to `/mutations`. All 54 pass; see
`reports/` for data-quality and evaluation output from the pipeline scripts.

Frontend: `cd frontend && npm run build` (production build) and `npx oxlint src/`
(lint) — both verified clean during development of this MVP.

## 19. Limitations

1. Small verified enzyme dataset (9 records in the shipped demo set).
2. Heterogeneous, partly literature-approximate (not fully BRENDA-curated) pH/temperature
   values — flagged `demo_assumption = true` throughout.
3. No matched enzyme-environment experimental suitability labels exist; the optional
   neural model is trained against a project-defined reference score, not ground truth.
4. Salinity tolerance is undocumented for every enzyme in the shipped dataset — every
   salinity score in this MVP uses the neutral default and is flagged "unknown."
5. Suitability is a derived compatibility metric, not measured degradation efficiency.
6. Mutation predictions are computational and require experimental validation.
7. Structural/docking validation is future work, not implemented in this MVP.
8. This is a computational decision-support tool, not a wet-lab replacement.

## 20. Future work

- Integrate real BRENDA-curated pH/temperature ranges and a real industrial wastewater
  environmental dataset (the synthetic scenario generator is designed to be swapped out
  with zero downstream code changes).
- Integrate a real FireProtDB subset for experimentally-grounded mutation scoring (the
  provider interface is ready).
- Structural modeling / molecular docking validation of top mutation candidates.
- Expand the verified enzyme dataset (target 30–50+ records) as BRENDA/PAZy curation
  continues. The master-dataset pipeline below already consolidates 75 records and grows
  by simply dropping new FASTA/CSV sources into `data/` or `datasets/` and re-running it.

## 21. Master dataset pipeline

Reproducible script pair under `src/` that inspects, merges, and quality-scores every
enzyme-bearing file in `data/` and `datasets/`.

```bash
# 1. inspect all candidate files -> reports/dataset_inspection.json
python src/inspect_datasets.py --input_dir data datasets

# 2. build the 28-column master dataset -> data/processed/master_enzymes.csv (+ 5 reports)
python src/build_master_dataset.py --input_dir data datasets --output_dir data/processed
python src/build_master_dataset.py --input_dir data datasets --output_dir data/processed --fireprotdb skip   # fast dev run
```

`--fireprotdb` defaults to `scan` (streams the full 5,465,660-row
`datasets/fireprotdb_20251015-164116.csv`, ~2–3 min) and proves there is zero
accession/name overlap with the enzyme set; `skip`/`sample` are faster mirrors.

**Sources used (5):** `data/demo/enzymes_demo.csv` (9 curated records),
`datasets/pazy_proteins.fasta` (59 nylonase records),
`datasets/pazy_proteins (1).fasta` (8 PET/cutinase-lipase records),
`datasets/rcsb_pdb_7CWQ.fasta` (1 PDB structure), `data/raw/pazy/pazy_proteins.fasta`
(2 verified sequences).

**Excluded (with reasons logged to `unmatched_records.csv`):**
`uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz` (tRNA dimethylallyltransferases
— not plastic-active), `new_release_structure_sequence.tsv` (535 generic PDB sequences,
zero sequence overlap, no pollutant annotation), `fireprotdb_*.csv` (evidence/provenance
only, zero accession overlap), plus `data/interim`/`data/processed` copies that duplicate
raw inputs or are pipeline outputs, and documentation.

**Outputs (6):**

| File | Contents |
| --- | --- |
| `master_enzymes.csv` | 75 enzyme-level rows, 28 columns |
| `master_enzymes_dedup.csv` | deduplicated snapshot (identical here) |
| `data_quality_report.csv` | per-file record counts, warnings |
| `data_conflicts.csv` | 17 merge/conflict/ambiguity events |
| `unmatched_records.csv` | every skipped/excluded file with reason |
| `dataset_summary.json` | aggregate counts, distributions, notes |

**Run 1 verified numbers:** 75 master rows (79 raw records minus 4 documented merges),
70 unique protein sequences, 7 unique accessions, 74 pollutant-labeled (7CWQ is
unlabeled), 9 with pH data, 9 with temperature data, **0 with salinity data** — no
salinity value was invented. The 17 conflict events cover merges (ENZ001/ENZ002 via
accession, ENZ003↔LCC and ENZ006↔NylB via unambiguous name) and ambiguity decisions
(NylA 54/59 and NylC 61/62/63 kept separate because each name maps to >1 distinct
sequence; NylB vs NylB' distinguished via name normalization).

**Honesty rules baked into the pipeline:** missing biochemical values stay missing;
pH/temperature optimums exist only on the 9 demo rows and stay flagged `heuristic`
(demo assumptions), never labeled experimental; `evidence_score` is a provenance score
derived only from the `evidence_type` label; `demo_assumption` numeric flags are carried
through everywhere.

## 22. ML pipeline (ESM-2 + derived labels)

A robust, honestly-labeled machine-learning upgrade on top of the master dataset.
Missing biochemical metadata is never invented — it becomes explicit `has_*` flags that
lower confidence. Labels are **derived compatibility scores** (never called experimental
degradation). Evaluation always uses **enzyme-group splits** to stop scenario leakage.

```bash
# 1. clean + explainable missingness flags -> data/processed/master_enzymes_clean.csv
#    (+ valid/missing sequences, sequence_recovery_log.csv, 3 report CSVs)
python src/data_quality.py

# 2. conservative scenario grid + transparent labels
#    -> data/processed/training_scenarios.csv (~6.9k rows)
python src/label_generation.py

# 3. frozen ESM-2 embeddings (default 650M, 1280-dim; local fallback supported)
#    -> data/processed/esm_embeddings.npy + esm_embedding_index.csv
python src/esm_embedder.py                      # Kaggle: add --download
python src/esm_embedder.py --model-name facebook/esm2_t12_35M_UR50D   # tiny local test

# 4. baselines (ridge/RF/GBM) + small MLP on a GroupShuffleSplit held-out enzyme set
#    -> artifacts/* + reports/{training_report.md,model_comparison.csv,prediction_examples.csv}
python src/train_kaggle.py --smoke --esm-model facebook/esm2_t12_35M_UR50D
python src/train_kaggle.py --esm-model facebook/esm2_t33_650M_UR50D --download

# 5. explainable recommendation (rule-based baseline always available; ML auto-fallbacks)
python src/inference.py --pollutant PET --ph 8.0 --temperature 35 --salinity 0.5

# 6. computational-only mutation candidates
python src/mutation_prep.py
```

Key design points (full detail in `docs/model_pipeline.md`):

- **Labels:** `derived_compatibility_label = 0.40·pollutant + 0.25·pH + 0.25·T + 0.10·salinity`,
  pH/temperature decaying exponentially outside known ranges; confidence drops with every
  missing metadata field (`salinity` has zero documented values in the shipped set — the
  salinity term is neutral everywhere, never invented).
- **ESM-2:** `facebook/esm2_t33_650M_UR50D` (1280-dim), fully frozen, mean-pooled excluding
  BOS/EOS tokens. On a machine without the checkpoint it transparently falls back to a
  cached smaller ESM (`t12_35M`), so the whole pipeline is runnable offline.
- **Leakage prevention:** grouped splits (`GroupShuffleSplit` + `GroupKFold`, monitored by
  `no_leakage()` assertions) guarantee no enzyme straddles train/test; the StandardScaler
  is fit on the training group only. Protocol documented in `reports/evaluation_protocol.md`.
- **Baselines matter:** with 70 enzymes the sklearn baselines are a real scientific rival to
  the MLP; the best-scoring model is what gets saved, with `best_model.pt` holding an actual
  network only when the MLP wins.
- **Backend compatibility:** `_write_backend_artifacts` also emits the legacy
  `artifacts/{model.pt, scaler.pkl, encoders.pkl, config.json}` so `DEMO_MODE=false` keeps
  working unchanged.
- **TPEs/smoke:** `--smoke` shrinks MLP epochs/batches for a fast CI run; 92 tests pass
  (`pytest tests/ -q`).

## 23. Scientific disclaimer

ENZAIme does not claim to experimentally prove enzyme degradation. All suitability
scores are project-defined computational compatibility estimates derived from
documented enzyme properties (and, where a trained model is active, a frozen ESM-2
sequence representation), not measured degradation efficiency. Mutation predictions are
computational screening aids requiring experimental validation. Structural/docking
validation is out of scope for this MVP and is explicitly future work. Where a demo/
assumed value is used, it is labeled as such everywhere it is displayed — never
presented as an experimental measurement.

---

## Repository layout

```
EnzAIme/
├── common/enzaime_core/     Shared scientific core (config, scoring, mutation, model, data_loader, embeddings)
├── backend/app/             FastAPI application
├── frontend/                React + Vite UI
├── scripts/                 Independently executable data/training pipeline (01-07)
├── src/                     Pipeline modules: inspect_datasets, build_master_dataset,
│                            data_quality, label_generation, esm_embedder, model,
│                            train_kaggle, inference, mutation_prep
├── notebooks/               EnzAIme_Kaggle_Training.ipynb, kaggle_full_training.ipynb
├── data/                     raw/ interim/ processed/ demo/ mutation/
├── artifacts/                Trained model output (best_model.pt + backend model.pt, …)
├── reports/                  Data-quality + evaluation reports (generated by scripts)
├── docs/                     architecture, data_pipeline, model_pipeline, kaggle_execution,
│                            scientific_limitations, data_pipeline, model, scoring, …
└── tests/                    pytest suite (92 tests)
```

## Project review demo scenarios

Four known-good scenarios are built into the Recommend page and also available at
`data/demo/demo_scenarios.json`:

1. PET · pH 8.0 · 35°C · 0.5%
2. PET · pH 7.0 · 45°C · 1.0%
3. PA (nylon) · pH 7.0 · 35°C · 0%
4. PUR · pH 7.5 · 30°C · 0%

Full user journey (verified working end-to-end during development):
select pollutant → enter conditions → Analyze & Recommend → view ranked results with
compatibility breakdown → View details on a recommendation → Analyze Mutations → view
ranked mutation table with the experimental-validation-required disclaimer.
