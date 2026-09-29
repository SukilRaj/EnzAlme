# Served model reproducibility and dataset lineage audit

Date: 2026-09-28, Asia/Calcutta. Scope: the running `EnzAIme_ML` backend, its saved PCA/scaler/Ridge artifacts, and the datasets they appear to describe. No model was trained, refitted, switched, or overwritten. Existing datasets, embeddings, reports, and application changes were preserved.

## Findings

1. **Version mismatch confirmed:** the PCA, StandardScaler, and Ridge artifacts identify scikit-learn **1.6.1**, while the active backend environment contains **1.9.1**. Loading each artifact emitted `InconsistentVersionWarning`; the warnings were retained in [current_inspection.log](current_inspection.log).
2. **227 means legacy assay rows, not the confirmed research set.** The legacy CSV has 227 rows across 25 proteins. Its multiset of protein/sequence/condition/original-target records equals the confirmed 221 rows plus the six excluded ambiguous rows, including duplicate multiplicities. Saved PCA and scaler each record 227 fitted samples. The scaler's environmental means and variances exactly match the legacy dataset.
3. **Excluded-row use in final Ridge fitting and saved evaluation remains unresolved.** Evidence strongly supports the legacy 227-row dataset as the source for preprocessing and suggests legacy-data evaluation. It does not establish per-row training or evaluation membership, because the producing training script, row manifest, and saved fold membership were not found. Do not assert definitively “both,” “training only,” “evaluation only,” or “neither.”
4. **Recommendations use the legacy CSV**, not the confirmed CSV. The same 25 protein/sequence pairs occur in both; four proteins have inflated evidence counts relative to the confirmed set.
5. **One-input reproducibility check passed:** live API, current numerical runtime, and isolated scikit-learn 1.6.1 runtime all returned **23.14270943023124 µM** for IsPETase at pH 8, 40 °C, 48 h. This is a prediction compatibility check, not training reproducibility or scientific validation.

## Repository and environment evidence

No `AGENTS.md` was found in the project, its parent chain searched through `D:\`, or the repository search. Git root is `D:\Final_Year_Project`; `EnzAIme_ML` is untracked (`?? ./` when run from this project). There is no Git history for this subtree from which to recover the original training run. The root project README, `.env.example`, `.gitignore`, and `backend/requirements.txt` are empty. No Python lockfile or training environment export was found in this project. The sibling `EnzAIme` project has broad minimum-version requirements and different training programs; no script/notebook reference to this project's `ridge_model.pkl`, `pca.pkl`, `training_metrics.json`, or `tpa_pet_ml_dataset.csv` was found there. Those files are not established provenance for these served artifacts.

The live process command is `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`. Windows reports the virtual-environment launcher and its base Python child; details are in [backend_process.json](backend_process.json). Python is **3.11.9, Windows x64**, using `.venv`. The existing environment was not downgraded. The sandbox cannot launch this interpreter normally, so approved execution outside the sandbox was used.

| Dependency | Active `.venv` | Isolated comparison environment |
|---|---:|---:|
| Python | 3.11.9 | 3.11.9 |
| scikit-learn | 1.9.1 | 1.6.1 |
| NumPy | 2.4.6 | 1.26.4 |
| SciPy | 1.17.1 | 1.13.1 |
| joblib | 1.6.0 | 1.4.2 |
| threadpoolctl | 3.7.0 | 3.6.0 |

Current encoder/API packages include torch 2.14.0, transformers 5.17.0, FastAPI 0.141.1, and uvicorn 0.53.0. See [current_packages.json](current_packages.json) for the full observed inventory. Original training versions other than scikit-learn are **unknown**. The comparison pins are a working compatible stack, not a recovered training lockfile.

## Served inference path and missing training provenance

- `backend/app/api/routes.py` instantiates `ESMEncoder`, `Predictor`, and `Recommender` on startup. Prediction performs fresh sequence encoding and calls `Predictor.predict`.
- `backend/app/services/predictor.py:13` loads `models/pca.pkl`, `models/scaler.pkl`, and `models/ridge_model.pkl`. `model_config.json` is read, but does not configure or validate the loaded transforms. Runtime behavior comes from the artifacts and hard-coded inference implementation.
- Input is a 1280-dimensional ESM-2 vector, cast to float32, transformed by PCA to 10 components. Temperature, pH, and duration in hours are appended in that order. The resulting 13 features are scaled, fed to Ridge, transformed with `expm1`, and clipped at zero.
- Saved artifact inspection confirms PCA with 10 components and `random_state=42`, a 13-feature StandardScaler, and a 13-feature Ridge with `alpha=10`. The config reports TPA concentration in uM, PET substrate, log1p target transform, 227 records, and 25 proteins. The original target-conversion/training implementation cannot be verified from the serving code alone.
- No producing training script or notebook was found in `EnzAIme_ML`. Its `notebooks` directory contains only `.gitkeep`. Searches of its scripts and the sibling project's Python/notebook files did not find a producer for these artifacts. Existing `run_controlled_ablation.py` and `run_model_comparison_experiment.py` explicitly use `data/processed/tpa_pet_ml_confirmed.csv` and write separate research results; they are not demonstrated producers of the served model.
- `backend/app/api/evaluation.py` reads `models/training_metrics.json`; it hard-codes the model label, five folds, and GroupKFold description. `backend/app/api/cross_validation.py` reads `reports/results/cross_validation_results.json`. Neither endpoint verifies that its metrics belong to the loaded artifact hashes. Matching labels are not an artifact-to-run provenance link.

### Encoder reproducibility limits

`backend/app/services/esm_encoder.py` selects `facebook/esm2_t33_650M_UR50D` without a pinned revision. It chooses CUDA/float16 when available, otherwise CPU/float32; truncates at 1024 tokens; and mean-pools all attention-mask tokens, including special tokens. These choices can affect reproduction across machines. This audit observed CPU/float32 and revision `08e4846e537177426273712802403f7ba8261b6c`. The embedding index maps protein IDs to filenames without sequence/checkpoint/run provenance.

The encoder emitted unauthenticated-Hub and deprecated-`torch_dtype` notices, a missing Visual C++ Redistributable warning, and a checkpoint report listing unexpected LM-head keys and newly initialized pooler keys. They are retained in [comparison.log](comparison.log). Inference uses `last_hidden_state`, not the pooled output. No missing dependency prevented this run; these messages were not hidden or “fixed” by altering the environment or model.

## What the 227 records establish

The following source files are distinct:

| File | Role | Rows / proteins |
|---|---|---|
| `data/tpa_pet_ml_dataset.csv` | Legacy reduced assay dataset; current recommendation source | 227 / 25 |
| `data/processed/tpa_activity_provenance_audit.csv` | Provenance classification of the legacy rows | 227 |
| `data/processed/tpa_pet_ml_confirmed.csv` | Confirmed TPA/PET research dataset | 221 / 25 |
| `data/processed/tpa_pet_ambiguous_excluded.csv` | Six excluded ambiguous observations | 6 / 4 |

`scripts/build_confirmed_tpa_dataset.py:44` separates `TPA_CONFIRMED` from `TPA_AMBIGUOUS`, asserts 227/221/6 counts, and writes the two datasets. It does not retrain the served artifacts. This audit did not execute that script. [dataset_reconciliation.json](dataset_reconciliation.json) independently verifies the multiset identity using protein ID, sequence, substrate, temperature, pH, original duration and unit, original target and unit. Numeric formatting was normalized; duplicate multiplicity was retained.

The saved PCA's `n_samples_` and scaler's `n_samples_seen_` are both **227**. Saved scaler environmental statistics are exactly:

| Statistic, order temperature / pH / hours | Saved scaler and legacy CSV | Confirmed CSV |
|---|---|---|
| Mean | 50.11013215859031 / 7.812775330396476 / 122.8546255506608 | 50.34389140271493 / 7.82579185520362 / 119.75113122171946 |
| Population variance | 192.38875196491347 / 0.5034931785984584 / 20592.970055696813 | 194.0536844044963 / 0.5047193955897713 / 18204.340779263322 |

These statistics provide strong evidence that preprocessing was fitted on the legacy full dataset, which contains the excluded observations. Aggregate statistics do not uniquely identify training rows, and the Ridge object retains no row IDs or fitted sample count. No fitting was performed to try to reverse-engineer membership.

The saved CV fold record counts are **77, 38, 38, 37, 37**, totaling **227**. Their rounded mean metrics closely match `training_metrics.json` (for example MAE 1441.9014 versus 1441.9015591122761). This is consistent with evaluation on the legacy cohort, not a 221-row cohort. The saved file does not contain test row IDs, protein membership, out-of-fold predictions, training indices, dataset hashes, or a training-run ID. Consequently the six rows' evaluation membership, whether fold preprocessing was leakage-free, and the connection between these metrics and the final Ridge coefficients remain **unresolved**. If conventional exhaustive five-fold CV used exactly the legacy CSV, all six would appear in held-out evaluation and other folds' training; that is a conditional inference, not saved proof.

### The six exclusions

| Protein | Legacy zero-based row positions | Rows | Original target | Ambiguity from saved review |
|---|---|---:|---|---|
| PET46 (41) | 49 | 1 | 1.91 µM | Same value for TPA and total aromatic products |
| CalB (42) | 57, 63 | 2 | 3.4 µM | TPA/BHET value collision; assay variant absent |
| HiC (44) | 141, 146 | 2 | 0 µM | TPA/BHET/MHET all zero; assay strategy and time-zero interpretation unresolved |
| SM14est (185) | 185 | 1 | 2.3 µM | TPA versus di-aromatic oligomers under different salt/assay conditions |

These are provenance exclusions, not proof that the source lacks TPA measurements. The original reduced records do not identify the exact measurement. The saved `tpa_ambiguous_review.md` calls these “original ML row index 0” through “5”; direct reconciliation finds the positions above instead. Do not use that review's 0–5 enumeration as source row IDs. Duplicate pairs cannot be distinguished by their reduced fields. See [lineage_evidence.json](lineage_evidence.json) for matching positions, conditions, and saved exclusion reasons.

**Membership conclusion:** legacy-dataset presence is confirmed; legacy preprocessing use is strongly supported; final Ridge fitting and served CV inclusion of each excluded record are unresolved. The separate confirmed A/B/C experiment uses the 221-row CSV and excludes these six by construction. Its results must remain distinct from the served artifact's 227-record metadata.

## Recommendation lineage

`backend/app/services/recommender.py:15` points to `data/tpa_pet_ml_dataset.csv`. `load_candidates` creates one candidate per protein ID, takes its first sequence/name, and counts every legacy row as `experimental_activity_records`. It reads stored vectors through `data/embeddings/index.json` and scores candidates with the same served Predictor; it does not fit a model on recommendation requests.

The legacy and confirmed data have exactly the same 25 protein/sequence pairs, so switching only candidate metadata would not remove any candidate. Evidence counts differ:

| Protein | Current legacy evidence count | Confirmed count |
|---|---:|---:|
| PET46 | 3 | 2 |
| CalB | 22 | 20 |
| HiC | 77 | 75 |
| SM14est | 8 | 7 |

The other 21 proteins' counts agree. Current evidence counts therefore should not be interpreted as counts of confirmed TPA records. Changing this CSV path would also not remove any influence the ambiguous records may have had on the saved model.

## Isolated compatibility comparison

A new environment was created at `D:\Final_Year_Project\EnzAIme_ML\.venv-served-model-audit-161`, with `include-system-site-packages = false`. Its numerical dependencies are pinned in [requirements-comparison.txt](requirements-comparison.txt). Installation completed, and `pip check` returned “No broken requirements found.”

To avoid copying or replacing encoder weights and to hold the encoder fixed, the unchanged current `ESMEncoder` generated a single inference vector in memory. The probe sent that same vector through stdin to separate current and compatible Python processes, each importing the unchanged `Predictor` and loading the original artifacts. This is a complete sequence-to-prediction comparison with a shared encoder stage; **the new environment is an isolated numerical inference environment, not a standalone replacement API/torch environment**. No server was switched. It does not reproduce unknown training-time torch/transformers versions.

Input: the existing protein ID 1 IsPETase sequence from the legacy dataset (also present unchanged in the confirmed dataset), pH 8, temperature 40 °C, duration 48 h. Sequence SHA-256: `12c59fe9dab495ee536f1c2a5fc28c66e212192096c2351044d4dc139042f5af`.

| Path | Full-precision prediction (µM) | Binary float representation |
|---|---:|---|
| Live current API | 23.14270943023124 | Same value as current worker |
| Current worker, scikit-learn 1.9.1 | 23.14270943023124 | `0x1.724889aefac89p+4` |
| Compatible worker, scikit-learn 1.6.1 | 23.14270943023124 | `0x1.724889aefac89p+4` |

Absolute and relative differences are **0.0** for this input. The fresh encoder vector exactly equals the existing stored IsPETase vector (1280 elements; maximum absolute difference 0.0). No vector was saved or overwritten. Current-worker artifact warnings were emitted and saved; the compatible worker's stderr log is empty. NumPy/SciPy/joblib versions also differ, so this tests the two stacks rather than isolating scikit-learn as the sole variable. One matching case does not establish compatibility for every input or validate the scientific model.

Machine-readable evidence: [prediction_comparison.json](prediction_comparison.json), [live_api_prediction.json](live_api_prediction.json), [current_worker_stderr.log](current_worker_stderr.log), and [compatible_worker_stderr.log](compatible_worker_stderr.log).

### Commands used

From the project root, with approved execution outside the sandbox where needed:

```powershell
& C:\Users\Welcome\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv-served-model-audit-161
.\.venv-served-model-audit-161\Scripts\python.exe -m pip install -r reports/results/served_model_audit/requirements-comparison.txt
.\.venv-served-model-audit-161\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B reports/results/served_model_audit/audit_probe.py inspect
python -B reports/results/served_model_audit/audit_probe.py lineage
.\.venv\Scripts\python.exe -B reports/results/served_model_audit/audit_probe.py compare D:\Final_Year_Project\EnzAIme_ML\.venv-served-model-audit-161\Scripts\python.exe
```

The install was executed with the same five exact pins as command-line arguments. No `fit`, `fit_transform`, embedding precomputation script, or research experiment was run. The comparison probe captures worker warnings to logs and re-emits them; it does not filter or suppress them.

## Unresolved questions and smallest recommended correction

Unresolved: the original training program and run identity; exact final Ridge training rows and target conversions; exact CV row membership and fold preprocessing; original dependency lockfile and encoder checkpoint/device; and a cryptographic link between the served coefficients and the saved metrics. No dependency blocker remains for the scoped compatibility comparison. A complete reconstruction of training remains blocked by missing provenance, not by this audit environment.

The smallest immediate correction is documentary: label the served artifact and its evaluation as **legacy 227-record metadata, with six ambiguous records present in the apparent source cohort and exact fitting/evaluation membership unverified**; label recommendation evidence counts as legacy rather than confirmed. Do not relabel the model as trained on 221 records, replace saved metrics, or assume the newer A/B/C experiment validates this artifact.

For a later approved runtime correction, pin and validate a dedicated serving environment using scikit-learn 1.6.1 and an explicitly pinned encoder revision/device policy before changing deployment. This audit's numerical environment is a starting point, not a production lockfile. Recover the producing training notebook/run and bind artifact, dataset, row/fold manifests, preprocessing rules, dependency versions, and metrics with hashes. If that evidence cannot be recovered, retain the legacy status; any new confirmed-only model would require a separately authorized training/evaluation task.

No application labels, scientific claims, dataset paths, served model, or active environment were changed by this audit.

## Preservation and deliverables

All new evidence and this report are under `reports/results/served_model_audit/`; the only other addition is `.venv-served-model-audit-161/`. The audit probe is included for repeatability. Baseline SHA-256 hashes cover existing models, datasets, embeddings, research reports, scripts, backend source, frontend source, and the two root data CSVs. See [preservation_before.json](preservation_before.json) and [preservation_check.json](preservation_check.json) for the final comparison. Existing application files were not edited, so frontend lint/build were not rerun for this audit.

Final preservation result: **128 existing files checked; zero changed or missing; no new files in the checked source/data/report trees outside the audit directory.** The separate environment lies outside those trees. The active environment's package inventory is unchanged, verified in [active_environment_preservation.json](active_environment_preservation.json). The compatible environment's successful dependency check and installed pins are saved in [compatible_dependency_check.txt](compatible_dependency_check.txt) and [compatible_freeze.txt](compatible_freeze.txt).
