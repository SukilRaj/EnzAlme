"""
backend/app/services/mutation_service.py
===========================================
Thin API-facing wrapper around enzaime_core.mutation. Handles the
"sequence unavailable" graceful-degradation case explicitly (Section 21):
if the selected enzyme has no known sequence, the API returns a clear,
actionable error instead of fabricating mutation candidates.
"""
from __future__ import annotations

from enzaime_core import config as core_config
from enzaime_core import data_loader, mutation


class SequenceUnavailableError(Exception):
    pass


class EnzymeNotFoundError(Exception):
    pass


def analyze_mutations(enzyme_id: str, max_mutations: int | None, top_n: int | None) -> dict:
    row = data_loader.get_enzyme_by_id(enzyme_id)
    if row is None:
        raise EnzymeNotFoundError(f"No enzyme found with enzyme_id='{enzyme_id}'.")

    sequence = row.get("sequence")
    if not isinstance(sequence, str) or len(sequence.strip()) == 0:
        raise SequenceUnavailableError(
            f"Sequence unavailable for enzyme '{row.get('enzyme_name', enzyme_id)}' "
            f"({enzyme_id}). Mutation analysis requires a known amino-acid sequence. "
            "Select an enzyme with a verified sequence (e.g. PETase/IsPETase or MHETase "
            "in the shipped demo dataset), or add the real sequence via the data pipeline."
        )

    max_mutations = max_mutations or core_config.MAX_MUTATIONS
    candidates = mutation.generate_mutations(sequence, max_mutations=max_mutations)
    provider_name = candidates[0].source if candidates else mutation.get_provider().name

    top_n = top_n or len(candidates)
    top = candidates[:top_n]

    return {
        "enzyme_id": row["enzyme_id"],
        "enzyme_name": row["enzyme_name"],
        "sequence_length": len(sequence),
        "provider": provider_name,
        "n_candidates_generated": len(candidates),
        "n_candidates_returned": len(top),
        "mutations": [
            {
                "rank": c.rank,
                "mutation": c.mutation,
                "position": c.position,
                "original_residue": c.original_residue,
                "new_residue": c.new_residue,
                "predicted_stability_score": c.predicted_stability_score,
                "predicted_fitness_proxy": c.predicted_fitness_proxy,
                "mutation_score": c.mutation_score,
            }
            for c in top
        ],
    }
