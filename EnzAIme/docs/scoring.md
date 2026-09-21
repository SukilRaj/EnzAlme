# Environment-Aware Suitability Score

## Terminology

This is a **project-defined compatibility score**, not an experimentally measured
degradation efficiency. Referred to throughout the codebase and UI as:

- "predicted suitability" / "Environment-Aware Suitability Score"
- "compatibility score"
- "computational recommendation"

Never as "actual degradation efficiency" or "experimental accuracy" unless a real
experimentally-measured label backs the claim (it does not, in this MVP).

## Formula

```
S = w_poll * L_poll + w_pH * L_pH + w_T * L_T + w_S * L_S
```

clipped to `[0, 1]`, then reported as a percentage. Default weights (validated to sum
to 1.0 at startup, configurable via the `WEIGHTS` environment variable):

| Factor | Weight |
|---|---|
| Pollutant | 0.40 |
| pH | 0.25 |
| Temperature | 0.25 |
| Salinity | 0.10 |

## Pollutant compatibility (`L_poll`)

| Evidence | Score |
|---|---|
| Verified activity on the queried pollutant | 1.0 |
| Predicted / homologous evidence | 0.7 |
| No evidence / pollutant mismatch | 0.0 |

Candidates with `L_poll = 0` are excluded before ranking (Section 11.1).

## pH and temperature compatibility (`L_pH`, `L_T`)

If the enzyme has a documented `[min, max]` range and the input falls inside it:
`compatibility = 1.0`. Outside the range, compatibility decays linearly to 0 over a
configurable tolerance window:

```
L = max(0, 1 - |input - nearest_boundary| / DELTA)
```

- `DELTA_PH` default: 2.0 pH units
- `DELTA_TEMP` default: 20°C

If only an optimum value (`pH_opt` / `T_opt`) is documented and no range, the same
decay is applied around a configurable symmetric window centered on the optimum
(`PH_OPT_TOLERANCE` = 1.5 pH units, `TEMP_OPT_TOLERANCE` = 10°C by default). This
assumption is applied consistently and is documented here rather than hidden in code.

## Salinity compatibility (`L_S`)

If salinity tolerance is documented (`salinity_evidence = true` and
`salinity_min`/`salinity_max` present): same range-decay logic as pH/temperature.

If unknown (the common case in this MVP — no industrial wastewater dataset is
integrated yet): a **neutral default** (`SALINITY_UNKNOWN_SCORE`, default 0.8) is used,
and the API/UI always report `salinity_status: "unknown"`. This is never presented as
an experimental measurement — the UI explicitly displays "Salinity tolerance: Unknown."

## Worked example

Query: PET, pH 8.0, 35°C, salinity 0.5%. Enzyme: IsPETase, verified PET activity,
`pH_opt = 9.0` (no range documented), `T_opt = 30.0` (no range documented), salinity
unknown.

```
L_poll = 1.0                                    (verified)
L_pH   = max(0, 1 - |8.0 - 7.5| / 2.0) = 0.75    (8.0 is just inside the [7.5, 10.5] opt window)
L_T    = max(0, 1 - |35 - 40| / 20.0) = 0.75     (35 is inside the [20, 40] opt window)
L_S    = 0.8                                     (unknown, neutral default)

S = 0.40*1.0 + 0.25*0.75 + 0.25*0.75 + 0.10*0.8 = 0.855  ->  85.5%
```

(Exact numbers depend on the live tolerance windows in `data/processed/enzymes.csv`;
see `/recommend`'s `breakdown` field for the live computed values.)

## Explanation payload

Every recommendation includes a full breakdown (`scoring.explain`) shown in the UI's
"Why this enzyme?" panel: the input value, the reported range (or an explicit "not
documented" note), and the resulting compatibility for each of the four factors. No
assumption is hidden from the user (Section 28).
