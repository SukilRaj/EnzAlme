import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import torch
from fastapi.testclient import TestClient
from backend.app.neural_main import app
from backend.app.services.directed_evolution import evolve, pareto_front
from backend.app.services.neural_oracle import AttentionOracle
from backend.app.services.neural_recommender import NeuralRecommender


class NeuralTests(unittest.TestCase):
    def test_padding_and_missing_images_do_not_change_prediction(self):
        torch.manual_seed(3)
        model = AttentionOracle(sequence_dim=4, image_dim=3, hidden=8).eval()
        seq, im, env = torch.randn(1, 3, 4), torch.randn(1, 3), torch.zeros(1, 3)
        score, _ = model(seq, torch.ones(1, 3, dtype=torch.bool), im, torch.zeros(1), env)
        padded = torch.cat([seq, torch.randn(1, 2, 4)*100], dim=1)
        other, weights = model(padded, torch.tensor([[True, True, True, False, False]]), im*50, torch.zeros(1), env)
        torch.testing.assert_close(score, other)
        self.assertEqual(weights[0, 3:].sum().item(), 0)

    def test_search_retains_parent_and_enforces_constraints(self):
        result = evolve("ACDE", lambda s, p: [s[:p]+"W"+s[p+1:]],
                        lambda s: -s.count("W"), ["ACDE", "ACDF"],
                        protected_positions=[1], max_mutations=1, seed=4)
        self.assertEqual(result["candidates"][0]["sequence"], "ACDE")
        self.assertTrue(all(r["sequence"][0] == "A" and len(r["mutations"]) <= 1 for r in result["candidates"]))

    def test_pareto_requires_both_targets(self):
        records = [{"activity": 1., "tm": 60.}, {"activity": 2., "tm": 50.}, {"activity": 1., "tm": 40.}]
        self.assertEqual(pareto_front(records), records[:2])
        with self.assertRaises(ValueError):
            pareto_front([{"activity": 1., "tm": None}])

    def test_api_missing_checkpoint_does_not_use_ridge(self):
        from unittest.mock import patch
        from backend.app.api.neural import service
        service.cache_clear()
        with patch("backend.app.api.neural.NeuralRecommender", side_effect=FileNotFoundError("training required")):
            client = TestClient(app)
            self.assertEqual(client.get("/api/neural/status").json()["status"], "training_required")
            self.assertEqual(client.post("/api/neural/recommend", json={"temperature": 40, "ph": 8, "duration": 48}).status_code, 503)
            self.assertEqual(client.post("/api/neural/recommend", json={"temperature": 40, "ph": 18, "duration": 48}).status_code, 422)
        service.cache_clear()

    def test_training_export_and_serving_contract(self):
        # Synthetic features/labels verify plumbing only, never scientific performance.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            features = root / "features"
            features.mkdir()
            rows, index = [], {}
            for i, residue in enumerate("ACDEFGHIKL"):
                seq = residue+"ACD"
                pid = str(i)
                np.savez(features / f"{i}.npz", sequence=np.full((4, 4), i/10, dtype=np.float32), image=np.zeros(512, dtype=np.float32))
                index[pid] = {"file": f"{i}.npz", "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest(), "image_present": False}
                rows.append({"protein_id": pid, "protein_name": pid, "sequence": seq, "temperature_c": 40, "ph": 8, "duration_hours": 48, "target_value_standardized": i+1})
            dataset = root / "data.csv"
            with dataset.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
            (features / "index.json").write_text(json.dumps({"encoder": "synthetic-test", "image_encoder": "synthetic-test", "proteins": index}))
            subprocess.run([sys.executable, "-m", "scripts.train_neural_oracle", "--dataset", str(dataset),
                            "--features", str(features), "--output", str(root / "model"), "--epochs", "2"], check=True, capture_output=True)
            recommender = NeuralRecommender(root / "model", features, dataset)
            split = recommender.meta["split_sequence_hashes"]
            self.assertFalse(set(split["train"]) & set(split["test"]))
            self.assertFalse(set(split["validation"]) & set(split["test"]))
            result = recommender.recommend(40, 8, 48, 3)
            self.assertEqual(len(result["recommendations"]), 3)
            self.assertTrue(all(r["predicted_tm_c"] is None and not r["image_used"] for r in result["recommendations"]))
            attribution = recommender.attribution('0', 40, 8, 48)
            self.assertEqual(len(attribution['residues']), 4)
            self.assertTrue(all(np.isfinite(r['attribution']) for r in attribution['residues']))
            with self.assertRaises(FileNotFoundError):
                recommender.recommend(40, 8, 48, objective='joint')
            with dataset.open("a") as f:
                f.write("\n")
            with self.assertRaisesRegex(ValueError, "Dataset changed"):
                NeuralRecommender(root / "model", features, dataset)


if __name__ == "__main__":
    unittest.main()
