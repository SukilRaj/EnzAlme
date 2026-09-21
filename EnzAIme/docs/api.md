# API Reference

Base URL (local default): `http://localhost:8000`. Interactive docs available at
`/docs` (Swagger UI) and `/redoc` once the backend is running.

## `GET /health`

Liveness/readiness check.

```json
{"status": "ok", "demo_mode": true, "model_loaded": false, "n_enzymes_loaded": 9}
```

## `GET /metadata`

Reports the active configuration, including which scoring engine is serving requests
(Section 36 — never hidden).

```json
{
  "app_name": "ENZAIme API",
  "app_version": "0.1.0-mvp",
  "demo_mode": true,
  "scoring_mode": "demo_compatibility_engine",
  "model_name": "facebook/esm2_t33_650M_UR50D",
  "device": "cpu",
  "supported_pollutants": ["PET", "PUR", "PA"],
  "weights": {"pollutant": 0.4, "ph": 0.25, "temperature": 0.25, "salinity": 0.1},
  "n_enzymes_loaded": 9,
  "data_source": "/app/data/processed/enzymes.csv"
}
```

## `GET /enzymes?pollutant=PET`

Lists enzyme summaries. `pollutant` query param is optional (one of `PET`, `PUR`, `PA`).

## `GET /enzyme/{enzyme_id}`

Full enzyme record, including sequence (if known) and `mutation_analysis_available`.
404 if `enzyme_id` doesn't exist.

## `POST /recommend`

Request:

```json
{"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5}
```

Validation (HTTP 400 on failure): `pollutant` must be one of `PET`/`PUR`/`PA`; `ph` in
`[0, 14]`; `temperature` in `[-10, 120]`; `salinity` in `[0, 10]`; no NaN/Infinity.

Response (truncated):

```json
{
  "query": {"pollutant": "PET", "ph": 8.0, "temperature": 35.0, "salinity": 0.5},
  "scoring_mode": "demo_compatibility_engine",
  "demo_mode": true,
  "n_candidates_evaluated": 5,
  "n_candidates_with_pollutant_evidence": 5,
  "disclaimer": "This is an in-silico decision-support recommendation, not a claim of experimentally measured degradation. ...",
  "recommendations": [
    {
      "rank": 1,
      "enzyme_id": "ENZ001",
      "enzyme_name": "PETase (IsPETase)",
      "accession": "A0A0K8P6T7",
      "pollutant": "PET",
      "suitability_score": 0.91,
      "score_percent": 91.0,
      "breakdown": {"pollutant": 1.0, "ph": 0.8, "temperature": 0.85, "salinity": 0.8},
      "evidence": "verified",
      "salinity_status": "unknown",
      "explanation": { "...": "full 'Why this enzyme?' payload" },
      "scoring_mode": "demo_compatibility_engine"
    }
  ]
}
```

Returns the top `TOP_K` (default 3) candidates, ranked descending by `suitability_score`.

## `POST /mutations`

Request:

```json
{"enzyme_id": "ENZ001", "top_n": 20}
```

- 404 if `enzyme_id` doesn't exist.
- **422** if the enzyme has no known sequence (sequence unavailable — Section 21
  graceful degradation, distinct from a 400 input-validation error).

Response (truncated):

```json
{
  "enzyme_id": "ENZ001",
  "enzyme_name": "PETase (IsPETase)",
  "sequence_length": 290,
  "provider": "demo_statistical_provider",
  "n_candidates_generated": 380,
  "n_candidates_returned": 20,
  "mutations": [
    {"rank": 1, "mutation": "A123V", "position": 123, "original_residue": "A", "new_residue": "V",
     "predicted_stability_score": 0.88, "predicted_fitness_proxy": 0.79, "mutation_score": 0.85}
  ],
  "disclaimer": "Computational prediction — experimental validation required. Structural/docking validation is future work (not part of this MVP)."
}
```

## `POST /reload-model`

Re-checks `DEMO_MODE`/artifacts and reloads the enzyme dataset without restarting the
process. Useful after re-running the training pipeline or dropping in a new
`enzymes.csv`.

```json
{"reloaded": true, "demo_mode_config": true, "scoring_mode": "demo_compatibility_engine", "model_loaded": false, ...}
```

## Error format

All validation errors return HTTP 400 with:

```json
{"detail": [{"type": "...", "loc": ["body", "ph"], "msg": "...", "input": "..."}]}
```

Not-found / unavailable-resource errors return 404 / 422 respectively with a plain
`{"detail": "human-readable message"}`.
