# Architecture

## Overview

ENZAIme is a three-tier application: a React/Vite frontend, a FastAPI backend, and a
shared Python core package (`common/enzaime_core`) that holds every piece of scientific
logic (compatibility scoring, mutation prioritization, data loading, the optional
ESM-2/neural model). Both the backend and the offline data-pipeline scripts import the
same core package, so there is exactly one implementation of the scoring formula, the
mutation heuristic, and the data-loading fallback logic.

```
frontend/ (React + Vite)
   |  fetch() over HTTP (CORS-enabled)
   v
backend/ (FastAPI)
   |  imports
   v
common/enzaime_core/ (framework-agnostic core logic)
   |  reads
   v
data/processed/enzymes.csv  <-  data/demo/enzymes_demo.csv (fallback)
artifacts/ (optional trained model + cached embeddings)
```

## Pipeline (per-request)

```
User input (pollutant, pH, temperature, salinity)
        |
        v
Environment validation (Pydantic schema, Section 53)
        |
        v
Candidate enzyme database (pandas DataFrame, pollutant pre-filter)
        |
        +--> enzyme sequence
        +--> pollutant evidence
        +--> pH information
        +--> temperature information
        +--> salinity information
        +--> enzyme properties
        |
        v
Protein representation (cached ESM-2 embedding, if available)
        |
        v
Environmental feature encoding (categorical pollutant + normalized pH/T/S)
        |
        v
Compatibility engine (transparent, always computed)
        |
        +--> pollutant compatibility
        +--> pH compatibility
        +--> temperature compatibility
        +--> salinity compatibility
        |
        v
Environment-aware suitability model
        |  (trained neural net if DEMO_MODE=false AND artifacts exist,
        |   otherwise the compatibility engine's own weighted sum)
        v
Candidate scoring -> Ranking -> Top 2-3 recommendations -> Explanation
        |
        v
[User selects an enzyme]
        |
        v
Mutation module
        |
        +--> generate candidate single-point mutations
        +--> predict stability/fitness (FireProtDB if present, else demo heuristic)
        +--> rank mutations
        |
        v
Result (UI clearly labels "computational prediction — experimental validation required")
        |
        v
[Future work: structural / docking validation — not implemented in this MVP]
```

## Why this split

- **`common/enzaime_core`** has no FastAPI/React dependency. It can be imported by
  `scripts/*.py`, the Kaggle notebook, the backend, and `tests/` identically. This is
  what lets the offline pipeline and the live API guarantee they compute the same score
  for the same enzyme/environment pair.
- **The backend never computes ESM-2 embeddings per-request.** `model_service.py` loads
  cached embeddings (`artifacts/embeddings/*.npy`) once at startup. If no trained model
  exists, requests are served entirely from `pandas` + arithmetic — no GPU, no network,
  sub-millisecond scoring per candidate.
- **DEMO_MODE is a first-class, visible state**, not an implementation detail. Every
  `/recommend` response and the frontend's mode badge report whether the compatibility
  engine or the trained model produced the score.

## Component responsibilities

| Component | Responsibility |
|---|---|
| `common/enzaime_core/config.py` | Every tunable parameter (weights, deltas, model name, ports) |
| `common/enzaime_core/data_loader.py` | Data abstraction layer — processed dataset first, demo dataset fallback |
| `common/enzaime_core/scoring.py` | Transparent compatibility engine (Sections 11-12) |
| `common/enzaime_core/mutation.py` | Mutation generation + provider abstraction (Section 20-22) |
| `common/enzaime_core/embeddings.py` | ESM-2 loading/embedding with automatic small-model fallback |
| `common/enzaime_core/model.py` | Small fusion neural network definition |
| `backend/app/main.py` | FastAPI routes, CORS, startup/shutdown, validation error handling |
| `backend/app/services/model_service.py` | DEMO_MODE / trained-model state machine |
| `backend/app/services/recommendation_service.py` | Orchestrates filter -> score -> rank -> explain |
| `backend/app/services/mutation_service.py` | API-facing wrapper over the mutation module |
| `scripts/01-07` | Independently executable offline data/training pipeline |
| `frontend/src` | React UI: recommendation form, results, enzyme detail, mutation table |
