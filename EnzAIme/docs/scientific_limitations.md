# Scientific Limitations of the EnzAIme ML Pipeline

This document lists the honest, explicit boundaries of the dataset + ML upgrade. Every
one of these points is enforced in code and mirrored in the UI wording where applicable.

## 1. Labels are derived compatibility scores, not measurements

`derived_compatibility_label` is a weighted blend of documented pollutant evidence,
known pH/temperature optima and a neutral salinity term. It is **not** an experimental
degradation rate (µg·h⁻¹, % mass loss, half-life, …). The model regresses toward this
label, so its RMSE/R²/Spearman report **agreement with the derived label** — never
biological performance. All reports carry this disclaimer.

## 2. Small, heterogeneous training set

Only 70 unique enzyme sequences are embeddable. The dataset mixes verified demo records,
PAZy nylonases, PDB structures and literature-curated entries with heterogeneous
provenance. 90.7% of rows lack a UniProt accession, 88% lack pH/temperature optima, and
**100% lack salinity tolerance**. This is the strongest constraint on the MLP's capacity:
a small frozen-embedding MLP plus sklearn baselines is deliberately chosen, and baselines
are kept as first-class comparators, not straw men.

## 3. No enzyme-environment experimental labels exist

There is no matched dataset of “did this enzyme degrade this pollutant at this
pH/temperature/salinity?”. The scenarios themselves are synthetic grid points, flagged
`scenario_source = derived_conservative_grid`. Nothing in this pipeline claims to predict
experimental activity.

## 4. Missing metadata lowers confidence but is not recovered automatically

Missing sequence, pH, temperature and salinity are flagged (`has_*`, `unknown_feature_count`,
`salinity_metadata_available = 0`) and reduce `confidence_score`/`metadata_completeness`.
They are **never imputed from data distributions** and **never downloaded automatically**.
The `sequence_recovery_log.csv` records the identifiers and a UniProt retrieval template;
an explicit, user-approved download is required, and even then the new sequence must be
re-validated before it enters training.

## 5. Salinity has zero documented coverage

Every salinity score is the neutral 0.5 term. Recommending a salinity explicitly for an
enzyme therefore cannot be supported by data; the engine says so in explanations.

## 6. Grouped splits limit leakage but not label synergy

Row-level random splits would leak (same enzyme in train and test), so we split by
`enzyme_id` (asserted `no_leakage`). But because every enzyme shares the same pollutant
grid, an enzyme pair with the same pollutant and evidence types still produces highly
similar labels — expectations of generalisation should remain modest.

## 7. Frozen embeddings are representation features, not physics

ESM-2 embeddings are learned protein representations, not structure, energetics or
thermostability. The MLP adds parameter learning on top of a frozen backbone; we never
claim physics-based simulation or docking accuracy.

## 8. Mutation candidates are computational screening aids only

`mutation_prep.py` ranks single-point candidates by residue-property delta and a crude
solvent-context heuristic. There is no ΔΔG, active-site analysis or simulated annealing.
Each candidate is labelled computational-only and every summary repeats the caveat.

## 9. Offline fallback changes dimensionality

When the 650M checkpoint is unavailable, the pipeline falls back to `esm2_t12_35M`
(480-dim). Numbers below the embedding layer are comparable, but the exact scores across
runs with different backbones are not directly transferable; `metrics.json` records which
model produced each run.

## 10. Scope

EnzAIme is an in-silico decision-support tool (MVP). It prioritises the upstream
enzyme cataloguing (75 records) and transparent ranking over any claim of wet-lab
predictive power.