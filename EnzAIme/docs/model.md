# Model

## ESM-2 protein representation

- Used strictly as a **frozen encoder** — no fine-tuning. The verified plastic-active
  enzyme dataset available to this MVP has fewer than 100 records, far too small to
  fine-tune a transformer without catastrophic overfitting.
- Default: `facebook/esm2_t33_650M_UR50D`. Configurable via `MODEL_NAME`.
- Automatic fallback to a smaller checkpoint (`MODEL_NAME_FALLBACK`, default
  `facebook/esm2_t6_8M_UR50D`) if the primary model fails to load (OOM, no
  internet/GPU/time budget) — see `common/enzaime_core/embeddings.py:resolve_and_load_model`.
- Pipeline: sequence -> tokenizer -> frozen ESM-2 -> per-residue hidden states ->
  attention-mask-aware mean pooling -> fixed-size embedding.
- Embeddings are computed once (`scripts/05_generate_embeddings.py` or the Kaggle
  notebook) and cached to `artifacts/embeddings/*.npy`. The backend never recomputes
  them per-request (Section 54).

## Small fusion neural network (`common/enzaime_core/model.py`)

```
ESM-2 embedding --> Linear+ReLU+Dropout (128) --\
                                                  +--> concat --> Linear+ReLU+Dropout (160)
env features    --> Linear+ReLU+Dropout (32)  --/                      |
                                                                        v
                                                          Linear+ReLU+Dropout (64)
                                                                        |
                                                                        v
                                                              Linear(1) + Sigmoid -> [0,1]
```

Deliberately small given the dataset size (Section 13: "do not build an unnecessarily
deep architecture"). Regularized with dropout (0.3) and weight decay (1e-4); trained
with early stopping on an enzyme-level validation split.

## Training target — the label problem (Section 14)

No large matched enzyme-environment experimental suitability dataset exists publicly.
The model is trained to **regress toward the transparent compatibility score**
(`scoring.py`) computed for each (enzyme, synthetic scenario) pair. This keeps the
system scientifically honest: the neural model is a learned smoothing/refinement of a
known, auditable reference function — never an independent claim of ground truth.

## Data splitting (Section 16)

Because every synthetic scenario reuses the same small set of enzymes, row-level random
splitting would leak near-identical rows (same enzyme, different pH/T/S) across
train/test. `scripts/06_train_model.py:enzyme_level_folds` splits on `enzyme_id`
instead:

- If ≥5 unique enzymes have embeddings: 5-fold enzyme-level cross-validation.
- If <5: a single documented 70/30 enzyme-level holdout (explicitly logged as such in
  `metrics.json["split_strategy"]`).

## Required fallback behavior (Section 14 / 35-37)

If `torch`/`transformers` are unavailable, if fewer than
`MIN_TRAINING_ROWS_REQUIRED` (default 200) labeled+embedded rows exist, or if no cached
embeddings exist at all, `scripts/06_train_model.py` **skips training the proposed
model** and records why in `artifacts/metrics.json["proposed_model"]["reason"]`. This
is not treated as an error — the application is designed to run correctly on the
rule-based compatibility engine alone (`DEMO_MODE=true`, the shipped default).

At serving time, `backend/app/services/model_service.py` implements the same
philosophy: it only switches to `"ai_model"` scoring if `DEMO_MODE=false` **and** all
four artifact files (`model.pt`, `scaler.pkl`, `encoders.pkl`, `config.json`) load
successfully. Any failure at any point falls back to `"demo_compatibility_engine"`
automatically, and the active mode is always reported in `/metadata` and every
`/recommend` response.

## Baselines (Section 15)

| Model | Description |
|---|---|
| Baseline 1 | Pollutant-only: score = 1.0 if pollutant matches, else 0.0. Ignores pH/T/salinity entirely. |
| Baseline 2 | The rule-based compatibility engine itself — used as the reference target (MAE against itself is 0 by construction). |
| Proposed | ESM-2 embedding + environment features -> small fusion network, trained where data supports it. |

`scripts/07_evaluate_model.py` also reports what fraction of synthetic scenarios
produce a **different top-ranked enzyme** under the environment-aware reference score
versus the pollutant-only baseline — direct evidence that environmental conditioning
changes recommendations, which is the project's core novelty claim.

All reported numbers are labeled "agreement with the compatibility reference score,"
never as experimental prediction accuracy (Section 46/56).
