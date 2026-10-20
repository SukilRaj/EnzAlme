# EnzAIme neural and multimodal upgrade

## Status and objective

User-approved objective: improve both PET-degrading activity and thermostability; Kaggle T4 x2 available. No paired images/structures/measurements supplied yet.

Implemented: paper-inspired Attention1D activity oracle, optional frozen ResNet18 view features, grouped research training, checkpoint-backed candidate ranking, numerical image ablation, attention display, optional local Ollama commentary, bounded ESM mutation proposal/search utilities, and Pareto-front filtering. These are new research components, not trained or validated biological models. Existing Ridge workflows remain clearly labeled legacy while the new path requires its own checkpoint.

Pending: curated stability dataset and trained Tm/dTm model, structure/image matching, full paper reproduction, a mutation-trained PET oracle, joint search integration, calibrated uncertainty, stronger family/publication splits and experimental validation. The mutation search utility is not exposed as an activity-improvement endpoint: the current 25-protein activity dataset cannot establish mutation effects. The Pareto utility rejects missing stability scores.

## What the base paper actually does

Tran and Hy, IEEE TEVC 29(2), 418–428 (2025), DOI: https://doi.org/10.1109/TEVC.2024.3439690.

Figure 1 and Section IV: mask positions, propose amino acids using ESM-2, score with a trained Attention1D fitness oracle, retain the best parents and offspring, repeat. Protein drawings illustrate the workflow; images are not model inputs. Section V describes a 35M ESM-2 mutation proposer and a 33-layer ESM-2 optimization oracle. Optimization and evaluation use separate oracles. Reported settings include population 128, beam 4, random ratio 0.6, k=1, five experimental repeats.

Our initial oracle uses 35M residue features for a smaller training setup, adds environmental and optional image inputs, and does not reproduce the exact paper configuration. Importance masking clips negative TF-IDF weights and handles zero denominators. These adaptations must be disclosed.

### Dataset details from Table I

| Dataset | Target as listed by the paper | Length in table | Records |
|---|---|---:|---:|
| avGFP | Brightness | 237 | 51,715 |
| AAV | AAV viability | 28 | 42,330 |
| TEM | Thermodynamic stability | 286 | 5,199 |
| E4B | Ubiquitin ligase activity | 102 | 91,032 |
| AMIE | Hydrolysis activity | 341 | 6,417 |
| LGK | Levoglucosan utilization | 439 | 7,633 |
| Pab1 | mRNA binding | 75 | 36,389 |
| UBE2I | Growth rescue rate | 159 | 3,022 |

Lengths include benchmark regions rather than necessarily full proteins. Preserve the original assay definitions. In particular, the TEM table label does not establish that its fitness score is a measured melting temperature in degrees C; check the Firnberg et al. source and preprocessing before using it as a stability target. Do not combine these different fitness scales into TPA concentrations.

Official code: https://github.com/HySonLab/Directed_Evolution

Official processed datasets: https://github.com/HySonLab/Directed_Evolution/tree/main/preprocessed_data

The authors identify `scripts/train_decoder.py` as oracle training and `scripts/run_discrete_de.py` as directed evolution. Use their processed splits for a separate reproduction experiment. Repository code is GPL-3.0; this project's additions are independently implemented from the method description. Dataset permissions must be checked at source.

## Data needed for both objectives

1. **Activity:** keep the existing confirmed PAZy PET/TPA measurements, including assay conditions, units, construct sequence, substrate properties, enzyme loading, and DOI. Add PETase/cutinase variant measurements with their actual mutant sequences and matched assays. General DMS activity is useful for benchmark work but is not PET-to-TPA ground truth.
2. **Thermostability:** use FireProtDB records with reference sequence, verified mutation numbering, mutant sequence, Tm or dTm, units, pH, method, and reference. The project already has a large FireProtDB export and a smaller extract; audit these before downloading more. Do not conflate Tm, dTm, dG, and ddG or infer activity from stability.
3. **Structures:** map exact constructs to experimental PDB/mmCIF structures or clearly labeled predicted structures. Record chain, residue mapping, missing residues, sequence coverage and confidence. Do not silently assign wild-type structures to mutants.
4. **Images:** generate consistent views from the verified structures, without fitness labels, legends, or publication text. Keep every view and every measurement of a protein in the same split. Images are derived structure representations, not independent experimental evidence. An arbitrary screenshot cannot establish a sequence or a mutation's function.

Authoritative resources:

- FireProtDB downloads: https://loschmidt.chemi.muni.cz/fireprotdb/download/
- FireProtDB original data model: https://pmc.ncbi.nlm.nih.gov/articles/PMC7778887/
- ProteinGym official benchmark/data/structure resources: https://github.com/OATML-Markslab/ProteinGym
- ESM models: https://github.com/facebookresearch/esm
- Llama 3.2 text model: https://ollama.com/library/llama3.2

The local `fireprotdb_20251015-164116.csv` header contains `SEQUENCE_ID`, `SOURCE_SEQUENCE_ID`, `TARGET_SEQUENCE_ID`, `SUBSTITUTION`, `TM` and `DTM`, but no amino-acid sequence column. Obtain the corresponding sequence table or sequence-inclusive JSON/SQL export from FireProtDB. Matching a UniProt accession alone is insufficient because experimental constructs and mutation numbering can differ. Minimum curated stability handoff fields: `record_id, reference_sequence, mutant_sequence, mutation, target_kind, target_value, target_unit, ph, assay_method, publication_doi, sequence_mapping_verified`. Keep `target_kind` explicit (`Tm` or `dTm`); missing measurements remain missing. Do not spend Kaggle GPU time training on sequence IDs as if they were sequences.

For joint ranking, train separate activity and thermostability predictors initially. Score the same candidate with both, preserve each target's units, and select a Pareto front (no candidate is worse in both objectives than another selected candidate). Missing labels are not zeros. A future shared multitask encoder needs masked losses, compatible assay targets, and explicit missing-label handling.

## Kaggle: first runnable activity baseline

This is a neural feasibility baseline, not the final dual-objective model. Upload the supplied `outputs/neural_kaggle_starter.zip` as a private Kaggle dataset, unzip in `/kaggle/working/EnzAIme_ML`, enable Internet for model downloads, and use the included notebook. It contains no trained checkpoint or paired images.

From the project root:

```bash
pip install -r backend/requirements-neural.txt
python -m scripts.prepare_neural_features
python -m scripts.train_neural_oracle --sequence-only --output models/neural
```

For image fusion, prepare a JSON file such as `{"1": ["views/1_front.png", "views/1_side.png"]}`. Image paths are relative to the JSON file. Only include views whose sequence/structure mapping has been checked. Run:

```bash
python -m scripts.prepare_neural_features --images data/protein_views.json
python -m scripts.train_neural_oracle --output models/neural_images
python -m scripts.train_neural_oracle --sequence-only --output models/neural_sequence
```

The scripts use one visible GPU. On T4 x2, run independent seeds or ablations with `CUDA_VISIBLE_DEVICES=0` and `CUDA_VISIBLE_DEVICES=1`, using distinct output directories. Two GPUs do not automatically pool memory, and distributed training is not implemented. Frozen encoders and batch size 8 keep the initial model modest; reduce batch size in the training script if a long-sequence run exhausts memory.

Return `models/neural/manifest.json`, `weights.pt`, `held_out_predictions.json`, and the entire matching `data/neural_features` directory. Keep a separate directory for each experiment. Use the same immutable source CSV in training and serving.

Training excludes nonfinite targets/conditions, negative activity and nonpositive duration; deduplicates a documented sequence/condition/target/source key; splits by exact sequence into train/validation/test; fits condition normalization on train only; uses validation early stopping; exports held-out errors and a training-median baseline. This is not a sequence-homology split. Paper/family leakage and assay heterogeneity remain limitations. Do not repeatedly select architectures on the held-out test set.

## Local serving and explanation

```bash
python -m uvicorn backend.app.neural_main:app --port 8001
```

The existing frontend has a Neural recommendations section using port 8001. Override with `VITE_NEURAL_API_BASE` if needed. The independent entry point avoids loading legacy Ridge artifacts or the old 650M encoder. It returns a training-required state until trained files exist. Restart after replacing artifacts.

`GET /api/neural/status` checks readiness; `POST /api/neural/recommend` accepts `temperature`, `ph`, `duration`, `top_n`, and optional `explain`. No Ridge fallback is present. Tm is explicitly unavailable until its separate pipeline is trained.

Llama 3.2 1B is text-only. `ollama serve` and the installed `llama3.2:1b` tag are needed for optional evidence narration; the service was unreachable during initial inspection. Narration does not alter rankings and is labeled generated commentary. Numerical image ablation is a model sensitivity comparison, attention is model focus, and neither establishes biological causality. Residue-level causal claims require stronger attribution and experimental support.

## Evidence required before reviewer-facing claims

- Hold out sequence families and, where possible, studies; group all variants/views/replicates appropriately.
- Compare neural sequence+conditions, image+conditions, full fusion, shuffled-image controls, and simple baselines on identical splits. Keep Ridge as a scientific comparator even though the new serving path is neural.
- Report MAE/RMSE separately by target, within-assay rank correlation, top-k enrichment, multiple seeds, and uncertainty calibration.
- Evaluate directed evolution independently of the oracle used to optimize it. Track diversity, mutation budget, protected residues and performance versus random mutation.
- Show that images help held-out predictions; a branch's existence does not demonstrate useful multimodality.
- Call proposed variants computational hypotheses until laboratory testing confirms improvement.
