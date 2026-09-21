# data/mutation/

Optional FireProtDB-derived curated mutation table. FireProtDB collection was still
in progress for this project (see project brief Section 4/21) — this directory is
intentionally empty in the shipped MVP.

## Expected file: `fireprotdb_subset.csv`

If present, columns: `position` (int), `wild_type` (str), `mutant` (str),
`stability_score` (float, 0-1), `fitness_proxy` (float, 0-1).

`common/enzaime_core/mutation.py:FireProtDBProvider` will automatically load and use
this file for any `(position, wild_type, mutant)` triple it covers, and fall back to
the demo statistical provider for anything not covered. No code changes are needed to
enable it — just drop the curated CSV here.

Until then, `common/enzaime_core/mutation.py:get_provider()` automatically selects
`DemoStatisticalMutationProvider`, which computes a transparent, documented heuristic
from published physicochemical reference tables (see `docs/mutation.md`) — never
invented experimental ΔΔG values.
