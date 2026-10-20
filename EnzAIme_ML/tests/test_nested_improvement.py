"""Check isolation and recompute completed experiment results independently."""
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from scripts.run_nested_model_improvement import feature_pair, select_inner

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/results/nested_improvement_20261012T152329Z"


class NestedImprovementTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.groups = np.repeat(np.arange(8).astype(str), 2)
        self.environment = rng.normal(size=(16, 3))
        self.embeddings = np.repeat(rng.normal(size=(8, 12)), 2, axis=0)
        self.y = np.arange(16, dtype=float) + 1
        self.train, self.test = np.arange(12), np.arange(12, 16)

    def test_preprocessing_train_independent_of_test_features(self):
        for kind in ["env", "env_poly", "combined", "interactions"]:
            with self.subTest(kind=kind):
                first, _ = feature_pair(self.environment, self.embeddings, self.groups, self.train, self.test, kind)
                changed_environment, changed_embeddings = self.environment.copy(), self.embeddings.copy()
                changed_environment[self.test] += 1e4
                changed_embeddings[self.test] -= 1e4
                second, _ = feature_pair(changed_environment, changed_embeddings, self.groups, self.train, self.test, kind)
                np.testing.assert_allclose(first, second)

    def test_inner_selection_never_reads_outer_test(self):
        specs = [dict(name="median", features="env", model="median", target="raw"),
                 dict(name="ridge", features="combined", model="ridge", target="log", alpha=100)]
        first = select_inner(specs, self.y, self.groups, self.train, self.environment, self.embeddings)
        changed_target = self.y.copy()
        changed_target[self.test] = 1e9
        second = select_inner(specs, changed_target, self.groups, self.train, self.environment, self.embeddings)
        self.assertEqual(first, second)
        for split in first[2]:
            self.assertFalse(set(split["train_rows"] + split["test_rows"]) & set(self.test))
            self.assertFalse(set(split["train_proteins"]) & set(split["test_proteins"]))

    @unittest.skipUnless(RUN.is_dir(), "Completed local research run is not bundled")
    def test_saved_metrics_and_all_fold_membership(self):
        predictions = pd.read_csv(RUN / "oof_predictions.csv", dtype={"protein_id": str})
        summary = json.loads((RUN / "summary.json").read_text())
        manifest = json.loads((RUN / "fold_manifest.json").read_text())
        self.assertEqual(len(predictions), 221)
        self.assertEqual(predictions.protein_id.nunique(), 25)
        seen = []
        for split in manifest:
            seen.extend(split["test_rows"])
            self.assertFalse(set(split["train_proteins"]) & set(split["test_proteins"]))
            for inner in split["inner_splits"]:
                self.assertTrue(set(inner["train_rows"] + inner["test_rows"]) <= set(split["train_rows"]))
                self.assertFalse(set(inner["train_proteins"]) & set(inner["test_proteins"]))
        self.assertEqual(sorted(seen), list(range(221)))
        for name, reported in summary["pooled"].items():
            self.assertAlmostEqual(mean_absolute_error(predictions.actual_um, predictions[name]), reported["mae_um"], places=8)
            self.assertAlmostEqual(mean_squared_error(predictions.actual_um, predictions[name])**.5, reported["rmse_um"], places=8)


if __name__ == "__main__":
    unittest.main()
