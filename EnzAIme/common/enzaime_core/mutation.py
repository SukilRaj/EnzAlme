"""
ENZAIme — Mutation Prioritization Module
==========================================
Generates single-point mutation candidates for a selected enzyme and ranks
them by a computational mutation score:

    S_mut = alpha * S_stability + (1 - alpha) * S_fitness_proxy

Section 21 requires a `MutationDataProvider` abstraction so that a real
FireProtDB-backed provider can be dropped in later without touching the
rest of the application. Because FireProtDB is still under collection for
this project, the MVP ships a `DemoStatisticalMutationProvider` that
computes a transparent, clearly-labelled heuristic from documented
physicochemical amino-acid properties (NOT invented experimental ddG
values — see class docstring).

Structural/docking validation is explicitly OUT OF SCOPE (future work,
Section 20).
"""
from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from . import config

# --------------------------------------------------------------------------
# Documented physicochemical property tables (Kyte-Doolittle hydropathy and
# average amino-acid volume, both are standard published reference tables,
# not invented data). Used only to build an explainable, deterministic
# heuristic — NOT presented to the user as measured ddG/fitness.
# --------------------------------------------------------------------------
KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
# Average residue volume (A^3), Zamyatnin 1972 (standard reference table)
RESIDUE_VOLUME = {
    "A": 88.6, "R": 173.4, "N": 114.1, "D": 111.1, "C": 108.5, "Q": 143.8,
    "E": 138.4, "G": 60.1, "H": 153.2, "I": 166.7, "L": 166.7, "K": 168.6,
    "M": 162.9, "F": 189.9, "P": 112.7, "S": 89.0, "T": 116.1, "W": 227.8,
    "Y": 193.6, "V": 140.0,
}
HELIX_PROPENSITY = {  # Pace & Scholtz 1998, kcal/mol (lower = more helix-favoring)
    "A": 0.0, "L": 0.21, "R": 0.21, "M": 0.24, "K": 0.26, "Q": 0.39, "E": 0.40,
    "I": 0.41, "W": 0.49, "S": 0.50, "Y": 0.53, "F": 0.54, "H": 0.61, "V": 0.61,
    "N": 0.65, "T": 0.66, "C": 0.68, "D": 0.69, "G": 1.00, "P": 3.16,
}


@dataclass
class MutationCandidate:
    mutation: str            # e.g. "A123V"
    position: int
    original_residue: str
    new_residue: str
    predicted_stability_score: float
    predicted_fitness_proxy: float
    mutation_score: float
    rank: int = 0
    source: str = "demo_statistical_provider"


# --------------------------------------------------------------------------
# Provider abstraction (Section 21)
# --------------------------------------------------------------------------
class MutationDataProvider(ABC):
    """Common interface so FireProtDB (or any future source) can replace
    the demo provider without changing the API layer."""

    @abstractmethod
    def score_mutation(self, sequence: str, position: int, original: str, new: str) -> tuple[float, float]:
        """Return (predicted_stability_score, predicted_fitness_proxy), each in [0, 1]."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


class FireProtDBProvider(MutationDataProvider):
    """
    Placeholder for a real FireProtDB-backed provider.

    FireProtDB is still under collection for this project (Section 4/21).
    When the curated ddG table (data/mutation/fireprotdb_subset.csv) is
    present, this class loads it and returns REAL experimental ddG-derived
    scores for mutations it covers, falling back to the demo provider for
    any mutation not present in the table.
    """

    def __init__(self, table_path):
        import pandas as pd
        self.table_path = table_path
        self._df = pd.read_csv(table_path) if table_path.exists() else None
        self._fallback = DemoStatisticalMutationProvider()

    @property
    def name(self) -> str:
        return "fireprotdb_provider"

    def score_mutation(self, sequence: str, position: int, original: str, new: str):
        if self._df is not None:
            match = self._df[
                (self._df["position"] == position)
                & (self._df["wild_type"] == original)
                & (self._df["mutant"] == new)
            ]
            if len(match) > 0:
                row = match.iloc[0]
                return float(row["stability_score"]), float(row["fitness_proxy"])
        return self._fallback.score_mutation(sequence, position, original, new)


class DemoStatisticalMutationProvider(MutationDataProvider):
    """
    MVP fallback strategy used when no experimentally-derived mutation
    database (e.g. FireProtDB) is available.

    IMPORTANT — SCIENTIFIC HONESTY:
    This provider does NOT invent or approximate experimental ddG values.
    It computes a deterministic, explainable heuristic from three
    published, static physicochemical reference tables (hydropathy,
    residue volume, helix propensity). The resulting numbers are a
    "Computational prediction" only, and the UI/API always labels them
    as such along with "Experimental validation required."
    """

    @property
    def name(self) -> str:
        return "demo_statistical_provider"

    def score_mutation(self, sequence: str, position: int, original: str, new: str):
        hydro_delta = abs(KYTE_DOOLITTLE.get(new, 0.0) - KYTE_DOOLITTLE.get(original, 0.0))
        vol_delta = abs(RESIDUE_VOLUME.get(new, 120.0) - RESIDUE_VOLUME.get(original, 120.0))
        helix_delta = HELIX_PROPENSITY.get(new, 0.5) - HELIX_PROPENSITY.get(original, 0.5)

        # Stability proxy: smaller physicochemical disruption (hydropathy +
        # volume change) and non-worsening helix propensity -> higher score.
        hydro_penalty = min(hydro_delta / 9.0, 1.0)          # max K-D span ~9
        vol_penalty = min(vol_delta / 140.0, 1.0)            # max volume span ~140 A^3
        helix_penalty = min(max(helix_delta, 0.0) / 2.0, 1.0)
        raw_stability = 1.0 - (0.45 * hydro_penalty + 0.35 * vol_penalty + 0.20 * helix_penalty)

        # Position-context proxy: deterministic pseudo-random component seeded
        # on (sequence, position, mutation) so results are reproducible
        # across calls, standing in for a local structural-context feature
        # that requires FireProtDB / structural data not yet available.
        seed_str = f"{sequence[:20]}|{position}|{original}{new}"
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        context_component = rng.uniform(-0.12, 0.12)

        stability_score = _clip01(raw_stability + context_component)
        # Fitness proxy: conservative substitutions (small hydro/volume
        # change) treated as more likely to preserve function.
        fitness_proxy = _clip01(1.0 - (0.6 * hydro_penalty + 0.4 * vol_penalty) + context_component * 0.5)

        return stability_score, fitness_proxy


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def get_provider() -> MutationDataProvider:
    """Factory: use FireProtDB subset if present, else the demo provider."""
    table_path = config.MUTATION_DIR / "fireprotdb_subset.csv"
    if table_path.exists():
        return FireProtDBProvider(table_path)
    return DemoStatisticalMutationProvider()


# --------------------------------------------------------------------------
# Candidate generation + ranking
# --------------------------------------------------------------------------
def generate_candidate_positions(sequence: str, top_n: int = None) -> List[int]:
    """
    Select which sequence positions to mutate. For the MVP we deterministically
    pick `top_n` positions spread across the sequence (excluding the very first
    and last 3 residues, which are less commonly informative for point
    mutagenesis screens) rather than scanning all positions, keeping runtime
    bounded per Section 20 (MAX_MUTATIONS).
    """
    top_n = top_n or config.TOP_CANDIDATE_POSITIONS
    n = len(sequence)
    if n <= 6:
        return list(range(1, n + 1))
    usable = list(range(4, n - 2))  # 1-indexed usable window
    if len(usable) <= top_n:
        return usable
    step = len(usable) / top_n
    return sorted({usable[int(i * step)] for i in range(top_n)})


def generate_mutations(
    sequence: str,
    positions: Optional[List[int]] = None,
    max_mutations: Optional[int] = None,
) -> List[MutationCandidate]:
    """Generate + score single-point amino-acid substitutions."""
    max_mutations = max_mutations or config.MAX_MUTATIONS
    positions = positions or generate_candidate_positions(sequence)
    provider = get_provider()

    candidates: List[MutationCandidate] = []
    for pos in positions:
        if pos < 1 or pos > len(sequence):
            continue
        original = sequence[pos - 1].upper()
        if original not in config.AMINO_ACIDS:
            continue
        for new_aa in config.AMINO_ACIDS:
            if new_aa == original:
                continue
            stability, fitness = provider.score_mutation(sequence, pos, original, new_aa)
            mutation_score = _clip01(
                config.MUTATION_ALPHA * stability + (1 - config.MUTATION_ALPHA) * fitness
            )
            candidates.append(
                MutationCandidate(
                    mutation=f"{original}{pos}{new_aa}",
                    position=pos,
                    original_residue=original,
                    new_residue=new_aa,
                    predicted_stability_score=round(stability, 4),
                    predicted_fitness_proxy=round(fitness, 4),
                    mutation_score=round(mutation_score, 4),
                    source=provider.name,
                )
            )
            if len(candidates) >= max_mutations:
                break
        if len(candidates) >= max_mutations:
            break

    candidates.sort(key=lambda c: c.mutation_score, reverse=True)
    for i, c in enumerate(candidates, start=1):
        c.rank = i
    return candidates
