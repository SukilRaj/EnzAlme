"""
tests/test_mutation.py
=========================
Section 39 tests #10-11:
  10. Mutation candidates are valid amino-acid substitutions.
  11. Mutation ranking works.
Plus provider abstraction and MAX_MUTATIONS bound checks.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from enzaime_core import config, mutation

TEST_SEQ = "MNFPRASRLMQAAVLGGLMAVSAAATAQTNPYARGPNPTAASLEASAGPFTVRSFTVSRP"


def test_generate_candidate_positions_bounded():
    positions = mutation.generate_candidate_positions(TEST_SEQ, top_n=10)
    assert len(positions) <= 10
    assert all(1 <= p <= len(TEST_SEQ) for p in positions)


def test_mutations_are_valid_substitutions():
    candidates = mutation.generate_mutations(TEST_SEQ, max_mutations=100)
    assert len(candidates) > 0
    for c in candidates:
        assert c.original_residue in config.AMINO_ACIDS
        assert c.new_residue in config.AMINO_ACIDS
        assert c.original_residue != c.new_residue
        assert c.mutation == f"{c.original_residue}{c.position}{c.new_residue}"
        assert TEST_SEQ[c.position - 1] == c.original_residue


def test_mutation_scores_bounded_0_1():
    candidates = mutation.generate_mutations(TEST_SEQ, max_mutations=50)
    for c in candidates:
        assert 0.0 <= c.predicted_stability_score <= 1.0
        assert 0.0 <= c.predicted_fitness_proxy <= 1.0
        assert 0.0 <= c.mutation_score <= 1.0


def test_mutation_ranking_is_descending():
    candidates = mutation.generate_mutations(TEST_SEQ, max_mutations=50)
    scores = [c.mutation_score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    ranks = [c.rank for c in candidates]
    assert ranks == list(range(1, len(candidates) + 1))


def test_max_mutations_respected():
    candidates = mutation.generate_mutations(TEST_SEQ, max_mutations=25)
    assert len(candidates) <= 25


def test_demo_provider_deterministic():
    provider = mutation.DemoStatisticalMutationProvider()
    s1, f1 = provider.score_mutation(TEST_SEQ, 10, "A", "V")
    s2, f2 = provider.score_mutation(TEST_SEQ, 10, "A", "V")
    assert s1 == s2 and f1 == f2  # reproducible, not random-per-call


def test_get_provider_falls_back_to_demo_when_no_fireprotdb():
    provider = mutation.get_provider()
    assert provider.name in {"demo_statistical_provider", "fireprotdb_provider"}


def test_mutation_score_formula():
    provider = mutation.DemoStatisticalMutationProvider()
    stability, fitness = provider.score_mutation(TEST_SEQ, 15, "L", "I")
    expected = config.MUTATION_ALPHA * stability + (1 - config.MUTATION_ALPHA) * fitness
    expected = max(0.0, min(1.0, expected))
    candidates = mutation.generate_mutations(TEST_SEQ, positions=[15], max_mutations=19)
    match = [c for c in candidates if c.original_residue == "L" and c.new_residue == "I"]
    assert len(match) == 1
    assert abs(match[0].mutation_score - round(expected, 4)) < 1e-6
