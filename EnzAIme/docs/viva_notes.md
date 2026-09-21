# Viva Notes

Anticipated questions for a project review/defense, answered directly.

## What problem are we solving?

Choosing a plastic-degrading enzyme for a given real-world environment (a specific
pollutant, pH, temperature, salinity) currently requires manually cross-referencing
scattered literature/database records. ENZAIme automates that cross-referencing into a
ranked, explained recommendation, and adds a mutation-prioritization step for further
wet-lab investigation of the chosen candidate.

## Why enzymes?

Enzymatic depolymerization is a proposed lower-energy, potentially more selective
alternative to thermal/chemical plastic recycling, and is an active research area
(IsPETase, LCC, engineered variants). Choosing *which* enzyme suits *which* site
condition is the practical bottleneck this project targets.

## Why plastic?

Plastic pollution (PET especially) is a large, well-characterized, high-relevance
problem with a growing body of enzyme literature to draw on — enough to build a
credible, if small, verified dataset (Section 6).

## Why environmental conditions?

An enzyme's in-vitro optimum tells you little about whether it will function at a real
site's pH/temperature/salinity. Conditioning the recommendation on the actual
environment — not just "this enzyme degrades PET" — is the project's core novelty.

## Why ESM-2?

It provides a general-purpose, structure-free protein sequence representation, useful
context if/when the neural refinement model is trained on more data. ESM-2 itself is
not claimed as novel — it is a widely-used, publicly available pretrained model.

## Why not fine-tune ESM-2?

The verified plastic-active enzyme dataset assembled for this MVP has fewer than 100
records (9 in the shipped demo set). Fine-tuning a 650M-parameter transformer on that
few examples would overfit essentially immediately and produce an unreliable,
untrustworthy representation. Using it frozen (as a fixed feature extractor) is the
scientifically defensible choice at this data scale.

## Why compatibility scoring (the rule-based engine)?

Because there is no large matched enzyme-environment experimental suitability dataset
to train a fully data-driven model against. The transparent compatibility formula
(Section 12) is auditable, requires no training data, and doubles as the *reference
target* if/when a neural model is trained. It is also the system's required, always-on
fallback (Section 14/35-37) — the application never breaks just because a model isn't
trained yet.

## What is our novelty?

Not ESM-2, not neural networks, not directed evolution — the novelty is the
**environment-aware integration**: combining protein sequence information with explicit
pollutant/pH/temperature/salinity conditioning for context-specific enzyme suitability
prediction and recommendation, with mutation prioritization as a downstream step. See
`reports/evaluation_summary.json` (`environment_conditioning_effect`) for a concrete,
computed demonstration that conditioning on environment changes which enzyme ranks
#1 versus a pollutant-only baseline.

## What is the role of BRENDA / PAZy / FireProtDB?

- **PAZy** (Plastics-Active enZymes database) — the primary source of curated
  plastic-active enzyme records; the most directly relevant existing data for this MVP.
- **BRENDA** — the intended source of precise, curated pH/temperature/kinetic ranges.
  Where BRENDA curation wasn't completed for a given enzyme in this MVP, the
  corresponding fields are flagged `demo_assumption = true` rather than left silently
  wrong.
- **FireProtDB** — the intended source of experimentally-measured mutation stability
  (ΔΔG) data for the mutation module. Still under collection for this project.

## Why is FireProtDB optional in the MVP?

Because the `MutationDataProvider` abstraction (Section 21) lets the system substitute
a clearly-labelled statistical/heuristic provider when FireProtDB coverage is
unavailable, without changing any API or UI code. The mutation module still produces
ranked, useful output — just explicitly marked "computational prediction, experimental
validation required" rather than "FireProtDB-verified."

## Why is docking future work?

Structural/docking validation requires 3D structural models (from PDB or predicted via
AlphaFold/ESMFold) and a docking/molecular-dynamics pipeline — a substantial separate
undertaking beyond an MVP's scope. It is explicitly out of scope here and called out as
future work everywhere mutation results are shown.

## What is the difference between predicted suitability and experimental degradation?

Predicted suitability (this system's output) is a computed compatibility score derived
from documented enzyme properties and environmental input — it estimates whether an
enzyme is *likely to function* under given conditions. Experimental degradation
efficiency is a measured lab result (e.g. % PET mass loss over time under specific
conditions). This project never conflates the two; every score is labeled as predicted/
compatibility, never as measured.

## What happens if salinity data is unavailable?

The compatibility engine uses a neutral default score (`SALINITY_UNKNOWN_SCORE = 0.8`)
and flags the result `salinity_status: "unknown"` end-to-end — in the API response and
explicitly in the UI ("Salinity tolerance: Unknown"). It is never presented as a
measured value.

## How do we prevent overfitting?

- ESM-2 kept frozen (no fine-tuning) given the small dataset.
- The optional neural model is small (Section 13) with dropout (0.3) and weight decay.
- Early stopping on an enzyme-level validation split.
- Training is skipped entirely (graceful fallback to the rule-based engine) if there
  isn't enough labeled+embedded data to fit a model responsibly
  (`MIN_TRAINING_ROWS_REQUIRED`).

## How do we prevent data leakage?

Synthetic environmental scenarios multiply each enzyme into many rows (one per
pH/T/salinity/pollutant combination). A naive row-level split would put near-identical
rows (same enzyme, slightly different environment) into both train and test. Instead,
`scripts/06_train_model.py:enzyme_level_folds` splits on `enzyme_id`, guaranteeing no
enzyme's embedding appears in both the training and evaluation sets of the same fold
(Section 16).
