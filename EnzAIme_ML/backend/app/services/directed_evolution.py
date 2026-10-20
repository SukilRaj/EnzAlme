"""Bounded paper-inspired search; biological validity depends on supplied oracles.

The k=1 importance rule combines normalized corpus TF-IDF and token entropy.
Parent retention follows the paper. Pareto selection is our two-objective extension.
"""
from collections import Counter
import math
import random

AA = "ACDEFGHIKLMNPQRSTVWY"


def validate_sequence(sequence):
    if not sequence or len(sequence) > 1022 or set(sequence) - set(AA):
        raise ValueError("Use 1..1022 standard amino-acid residues")


def importance(sequence, corpus):
    counts = Counter(sequence)
    total = Counter("".join(corpus))
    size = sum(total.values())
    relevance, entropy = {}, {}
    for residue in counts:
        df = sum(residue in s for s in corpus)
        # Clipping handles the negative ubiquitous-token weight in paper Eq. 3.
        relevance[residue] = max(0., counts[residue]/len(sequence) * math.log(len(corpus)/(1+df)))
        probability = total[residue]/size if size else 0
        entropy[residue] = -probability*math.log(probability) if probability else 0.
    rsum, esum = sum(relevance.values()), sum(entropy.values())
    return [(relevance[x]/rsum if rsum else 0.) + (entropy[x]/esum if esum else 0.) for x in sequence]


def pareto_front(records):
    """Both activity and Tm must be finite and larger-is-better, for the SAME sequence."""
    for r in records:
        if any(r.get(k) is None or not math.isfinite(r[k]) for k in ("activity", "tm")):
            raise ValueError("Joint optimization needs both validated model outputs per candidate")
    return [r for r in records if not any(
        q["activity"] >= r["activity"] and q["tm"] >= r["tm"] and
        (q["activity"] > r["activity"] or q["tm"] > r["tm"]) for q in records)]


def evolve(sequence, propose, score, corpus, rounds=3, population=8, beam=4,
           random_ratio=0.6, max_mutations=3, protected_positions=(), seed=42):
    """Callbacks: propose(sequence, zero_based_position)->sequences; score(sequence)->float.

    Protected positions use ONE-based reference numbering. No LLM textual scores.
    This scalar search is for a validated objective; Pareto filtering is separate.
    """
    validate_sequence(sequence)
    if not corpus or any(not s or set(s)-set(AA) for s in corpus):
        raise ValueError("A nonempty valid training-only corpus is required")
    if not 1 <= rounds <= 20 or not 1 <= population <= 128 or not 1 <= beam <= 8:
        raise ValueError("Search exceeds configured compute bounds")
    if not 0 <= random_ratio <= 1 or not 1 <= max_mutations <= len(sequence):
        raise ValueError("Invalid mutation budget or random ratio")
    if any(p < 1 or p > len(sequence) for p in protected_positions):
        raise ValueError("Protected position outside the reference sequence")
    allowed = [i for i in range(len(sequence)) if i+1 not in protected_positions]
    if not allowed:
        raise ValueError("All positions are protected")
    rng, cache = random.Random(seed), {}

    def evaluate(s):
        if s not in cache:
            cache[s] = float(score(s))
            if not math.isfinite(cache[s]):
                raise ValueError("Oracle returned a nonfinite score")
        return cache[s]

    parents = [sequence]
    history = []
    evaluate(sequence)
    for iteration in range(rounds):
        candidates = set(parents)
        for parent in parents:
            weights = importance(parent, corpus)
            for _ in range(beam):
                position = rng.choice(allowed) if rng.random() < random_ratio else min(allowed, key=lambda i: (weights[i], i))
                for child in list(propose(parent, position))[:beam]:
                    validate_sequence(child)
                    if len(child) != len(sequence):
                        continue
                    if any(child[i] != parent[i] for i in range(len(child)) if i != position):
                        continue
                    if sum(a != b for a, b in zip(sequence, child)) <= max_mutations:
                        candidates.add(child)
        parents = sorted(candidates, key=lambda s: (-evaluate(s), s))[:population]
        history.append({"round": iteration+1, "best_score": evaluate(parents[0]), "unique_evaluated": len(cache)})
    return {"candidates": [{"sequence": s, "predicted_fitness": evaluate(s),
                "mutations": [f"{a}{i+1}{b}" for i, (a, b) in enumerate(zip(sequence, s)) if a != b]} for s in parents],
            "history": history, "status": "In-silico proposals; not experimental improvements"}


class ESMProposer:
    """Lazy masked-token protein LM; checkpoint downloaded only when constructed."""
    def __init__(self, model_name="facebook/esm2_t12_35M_UR50D", top_k=4):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be 1..20")
        self.torch = torch
        self.top_k = top_k
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name).eval()
        self.valid_ids = [self.tokenizer.convert_tokens_to_ids(a) for a in AA]

    def __call__(self, sequence, position):
        validate_sequence(sequence)
        if not 0 <= position < len(sequence):
            raise ValueError("Mask position outside sequence")
        tokens = self.tokenizer(sequence, return_tensors="pt")
        tokens["input_ids"][0, position+1] = self.tokenizer.mask_token_id
        with self.torch.inference_mode():
            logits = self.model(**tokens).logits[0, position+1, self.valid_ids]
        return [sequence[:position]+AA[i]+sequence[position+1:] for i in logits.topk(self.top_k).indices.tolist()]
