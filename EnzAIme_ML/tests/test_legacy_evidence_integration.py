"""Real-artifact checks; no training, data writes, or mocked predictions."""
import csv
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.app.api.evaluation import get_evaluation
from backend.app.api.cross_validation import get_cross_validation
from backend.app.schemas.prediction import PredictionResponse
from backend.app.schemas.recommendation import RecommendationResponse
from backend.app.services.predictor import Predictor
from backend.app.services import recommender as service

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'data/tpa_pet_ml_dataset.csv'
CONFIRMED = ROOT / 'data/processed/tpa_pet_ml_confirmed.csv'


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


class LegacyEvidenceIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = Predictor()
        cls.current = service.Recommender(cls.predictor)
        # Change only the input dataset for the baseline; both paths score real artifacts.
        with patch.object(service, 'DATASET_PATH', LEGACY):
            cls.legacy = service.Recommender(cls.predictor)

    def test_same_candidates_and_confirmed_counts(self):
        pairs = lambda candidates: {(c['protein_id'], c['sequence']) for c in candidates}
        self.assertEqual(service.DATASET_PATH, CONFIRMED)
        self.assertEqual(len(self.current.candidates), 25)
        self.assertEqual(pairs(self.current.candidates), pairs(self.legacy.candidates))
        old = {c['protein_id']: c['activity_record_count'] for c in self.legacy.candidates}
        new = {c['protein_id']: c['activity_record_count'] for c in self.current.candidates}
        self.assertEqual(sum(old.values()), 227)
        self.assertEqual(sum(new.values()), 221)
        self.assertEqual({k:(old[k],v) for k,v in new.items() if old[k]!=v},
                         {'41':(3,2), '42':(22,20), '44':(77,75), '185':(8,7)})
        from collections import Counter
        excluded = Counter(r['protein_id'] for r in read_rows(ROOT/'data/processed/tpa_pet_ambiguous_excluded.csv'))
        self.assertEqual({k:old[k]-new[k] for k in old if old[k]!=new[k]}, dict(excluded))
        self.assertEqual({r['classification'] for r in read_rows(CONFIRMED)}, {'TPA_CONFIRMED'})

    def test_all_scores_and_order_unchanged(self):
        for ph, temperature, duration in [(8,40,48),(7,25,24),(9,70,96)]:
            with self.subTest(ph=ph,temperature=temperature,duration=duration):
                kwargs = dict(ph=ph,temperature=temperature,duration_hours=duration,top_n=25)
                before=self.legacy.recommend(**kwargs)
                after=self.current.recommend(**kwargs)
                score_fields=lambda rr:[(r['rank'],r['protein_id'],r['predicted_activity_um']) for r in rr]
                self.assertEqual(score_fields(before),score_fields(after))
                for r in after:
                    self.assertIn('legacy research model',r['prediction_status'])
                    self.assertIn('unresolved',r['validation_note'])
                    self.assertIn('data/processed/tpa_pet_ml_confirmed.csv',r['evidence']['source'])
                payload=RecommendationResponse(target='TPA',substrate='PET',
                    conditions={'ph':ph,'temperature':temperature,'duration':duration},recommendations=after)
                self.assertEqual(len(payload.model_dump()['recommendations']),25)

    def test_prediction_and_reported_metrics_unchanged(self):
        value=self.predictor.predict(self.current.embedding_cache['1'],temperature=40,ph=8,duration_hours=48)
        saved=json.loads((ROOT/'reports/results/served_model_audit/live_api_prediction.json').read_text())
        self.assertEqual(value,saved['response']['predicted_activity_um'])
        prediction=PredictionResponse(predicted_activity_um=value,target='TPA',substrate='PET',conditions={}).model_dump()
        evaluation=get_evaluation()
        folds=get_cross_validation()
        for payload in [prediction,evaluation,folds]:
            self.assertIn('legacy research model',payload['model'])
            self.assertIn('Exact training/evaluation row membership is unresolved',payload['lineage_note'])
        metrics=json.loads((ROOT/'models/training_metrics.json').read_text())
        self.assertEqual(evaluation['training_records'],227)
        for key, source in [('mae','MAE'),('rmse','RMSE'),('r2','R2'),('spearman','Spearman')]:
            for stat in ['mean','std']:
                self.assertEqual(evaluation['cross_validation'][key][stat],metrics[f'cv_{source}_{stat}'])
        original_folds=json.loads((ROOT/'reports/results/cross_validation_results.json').read_text())
        self.assertEqual(folds['folds'],original_folds['folds'])

    def test_research_files_preserved(self):
        baseline=json.loads((ROOT/'reports/results/served_model_audit/preservation_before.json').read_text())
        for path, expected in baseline.items():
            if path.startswith(('data/','data\\','models/','models\\','reports/','reports\\')) or path.endswith('master_dataset.csv') or path.startswith('fireprotdb_'):
                with self.subTest(path=path), (ROOT/path).open('rb') as file:
                    self.assertEqual(hashlib.file_digest(file,'sha256').hexdigest(),expected)


if __name__=='__main__':
    unittest.main(verbosity=2)
