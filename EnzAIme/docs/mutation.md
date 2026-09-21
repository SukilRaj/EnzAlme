# Mutation Module

## Scope

Given a selected enzyme (with a known sequence), generates single-point amino-acid
substitution candidates and ranks them by a computational mutation score. **Structural
or docking validation is explicitly out of scope for this MVP** — see "Future work"
below.

## Candidate generation

`common/enzaime_core/mutation.py:generate_candidate_positions` selects
`TOP_CANDIDATE_POSITIONS` (default 20) positions spread evenly across the sequence
(excluding the first 3 and last 2 residues), rather than scanning every position — this
keeps runtime bounded. At each selected position, all 19 alternative amino acids are
considered, capped overall at `MAX_MUTATIONS` (default 500, configurable).

## Scoring

```
S_mut = alpha * S_stability + (1 - alpha) * S_fitness_proxy
```

`alpha` (`MUTATION_ALPHA`) defaults to 0.7.

## Provider abstraction (Section 21)

`MutationDataProvider` is an abstract interface with two implementations:

1. **`FireProtDBProvider`** — used automatically if `data/mutation/fireprotdb_subset.csv`
   exists. Looks up `(position, wild_type, mutant)` in the curated table; falls back to
   the demo provider for any mutation not covered.
2. **`DemoStatisticalMutationProvider`** — the MVP default (FireProtDB is still under
   collection for this project). Computes a deterministic, explainable heuristic from
   three **published, static physicochemical reference tables**:
   - Kyte–Doolittle hydropathy
   - Zamyatnin residue volume
   - Pace & Scholtz helix propensity

   These are standard textbook reference values, not invented experimental
   measurements. The provider explicitly does **not** claim to produce real ΔΔG or
   fitness values — every mutation response is labeled "Computational prediction —
   experimental validation required."

`get_provider()` automatically selects the FireProtDB provider when the curated table
is present, otherwise the demo provider — no code changes needed when real FireProtDB
data is added later.

## Sequence availability (graceful degradation)

Mutation analysis requires a known sequence. If the selected enzyme's `sequence` field
is blank (7 of 9 records in the shipped demo dataset — see `data/demo/SOURCES.md`),
`POST /mutations` returns **HTTP 422** with a clear message rather than fabricating
results. The two enzymes with verified sequences (IsPETase, MHETase) are fully
supported end-to-end.

## Output

Each ranked candidate reports:

| Field | Meaning |
|---|---|
| `mutation` | e.g. `A123V` |
| `position`, `original_residue`, `new_residue` | |
| `predicted_stability_score` | Heuristic proxy, [0,1] |
| `predicted_fitness_proxy` | Heuristic proxy, [0,1] |
| `mutation_score` | Weighted combination, used for ranking |
| `rank` | 1 = highest scoring |

## Future work (explicitly out of scope for this MVP)

- Structural modeling / molecular docking of mutation candidates against the target
  polymer.
- Integration of a real, curated FireProtDB subset with experimentally-measured ΔΔG
  values (the provider interface is ready; only the data is pending).
- Combinatorial (multi-site) mutation screening.
