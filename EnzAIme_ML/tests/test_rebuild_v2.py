"""Contract checks; synthetic labels do not validate biological performance."""
import hashlib
import csv
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from backend.app.workspace_app import app
from backend.app.services import local_llm
from backend.app.services.stability_oracle import StabilityOracle
from scripts.train_stability_oracle import ENCODER, linked_groups
from scripts.import_v2_results import extract_checked, disjoint_splits, activate, review


class RebuildTests(unittest.TestCase):
    def test_llm_preserves_verified_units_and_rejects_unknown_facts(self):
        evidence = {'recommendations':[{'protein_name':'Sub1','predicted_activity_um':278.01,
            'predicted_tm_c':None,'image_used':False,'outside_training_conditions':False}], 'test_metrics':{'r2':-2.3}}
        with patch.object(local_llm, 'health', return_value={'status':'ready'}):
            with patch.object(local_llm, 'call', return_value={'message':{'content':'{"evidence_ids":["images"]}'}}):
                result = local_llm.explain(evidence)
                self.assertIn('278.01 µM', result['text'])
                self.assertIn('weak', result['text'])
                self.assertIn('not been predicted', result['text'])
            with patch.object(local_llm, 'call', return_value={'message':{'content':'{"evidence_ids":["invented"]}'}}):
                with self.assertRaises(RuntimeError):
                    local_llm.explain(evidence)
        with patch.object(local_llm, 'health', return_value={'status':'offline','detail':'Offline'}):
            with self.assertRaisesRegex(RuntimeError, 'Offline'):
                local_llm.explain(evidence)

    def test_group_links_are_transitive(self):
        groups = linked_groups([{'sequence_sha256':a,'family_group':b} for a,b in [('a','1'),('a','2'),('b','2'),('c','3')]])
        self.assertEqual(len(set(groups[:3])), 1)
        self.assertNotEqual(groups[0], groups[3])

    def test_unified_server_contract(self):
        client = TestClient(app)
        self.assertEqual(client.get('/api/health').json()['version'], '2.0.0')
        self.assertEqual(client.get('/api/does-not-exist').status_code, 404)

    def test_result_import_rejects_traversal_and_preserves_backups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('models/neural_images/../../outside.txt','bad')
            with self.assertRaises(ValueError):
                extract_checked(archive,root/'stage')
            for folder in ['models/neural_sequence','models/stability','data/neural_features_v2']:
                source = root/'stage'/folder; source.mkdir(parents=True,exist_ok=True)
                (source/'test.txt').write_text('new')
            old = root/'project/models/neural'; old.mkdir(parents=True)
            (old/'test.txt').write_text('old')
            activate(root/'stage','sequence',root/'backup',root/'project')
            self.assertEqual((root/'backup/models/neural/test.txt').read_text(),'old')
            self.assertEqual((old/'test.txt').read_text(),'new')
        with self.assertRaises(ValueError):
            disjoint_splits({'train':['a'],'validation':['b'],'test':['a']})

    def test_cached_structure_and_image_match_catalog(self):
        client = TestClient(app)
        result = client.get('/api/structures/catalog/1')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['inspection']['coverage'],1)
        self.assertEqual(client.get('/api/structures/catalog/1/image').headers['content-type'],'image/png')
        self.assertEqual(client.get('/api/structures/catalog/999999').status_code,404)

    def test_stability_training_and_serving(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            features = root/'features'; features.mkdir()
            rows = []
            for i, aa in enumerate('ACDEFGHIKL'):
                seq = aa+'ACD'; sha = hashlib.sha256(seq.encode()).hexdigest()
                np.savez(features/f'{sha}.npz', sequence=np.full((4,480), i/10, dtype=np.float32), encoder=np.array(ENCODER))
                rows.append({'record_id':str(i),'protein_id':str(i),'family_group':str(i),'sequence':seq,
                    'sequence_sha256':sha,'tm_c':40.+i,'ph':7. if i%2 else None,
                    'target_kind':'Tm','target_unit':'degC','sequence_mapping_verified':True})
            records = root/'records.json'; records.write_text(json.dumps(rows))
            subprocess.run([sys.executable,'-m','scripts.train_stability_oracle','--records',str(records),
                '--features',str(features),'--output',str(root/'model'),'--epochs','2'], check=True, capture_output=True)
            model = StabilityOracle(root/'model')
            prediction = model.predict({'sequence':np.zeros((4,480),dtype=np.float32),'image':np.zeros(512,dtype=np.float32)},7.)
            self.assertTrue(np.isfinite(prediction))
            split = model.meta['split_record_ids']
            self.assertFalse(set(split['train']) & set(split['test']))
            self.assertFalse(set(split['validation']) & set(split['test']))
            # Exercise the complete returned-archive contract with synthetic training runs.
            project = root/'project'
            (project/'data/stability').mkdir(parents=True)
            shutil.copy2(records,project/'data/stability/records.json')
            stage = root/'stage'
            shutil.copytree(root/'model',stage/'models/stability')
            activity_features = stage/'data/neural_features_v2'
            activity_features.mkdir(parents=True)
            index, activity = {}, []
            for i,r in enumerate(rows):
                np.savez(activity_features/f'{i}.npz',sequence=np.full((4,480),i/10,dtype=np.float32),image=np.full(512,i/20,dtype=np.float32))
                index[str(i)] = {'file':f'{i}.npz','sequence_sha256':r['sequence_sha256'],'image_present':True}
                activity.append({'protein_id':str(i),'protein_name':f'Test{i}','sequence':r['sequence'],
                    'temperature_c':40,'ph':8,'duration_hours':48,'target_value_standardized':i+1})
            (activity_features/'index.json').write_text(json.dumps({'encoder':ENCODER,'image_encoder':'synthetic','proteins':index}))
            dataset = project/'data/processed/tpa_pet_ml_confirmed.csv'
            dataset.parent.mkdir()
            with dataset.open('w',newline='') as f:
                writer = csv.DictWriter(f,fieldnames=list(activity[0])); writer.writeheader(); writer.writerows(activity)
            for experiment in ['sequence','images']:
                command = [sys.executable,'-m','scripts.train_neural_oracle','--dataset',str(dataset),
                    '--features',str(activity_features),'--output',str(stage/f'models/neural_{experiment}'),'--epochs','2']
                if experiment == 'sequence':
                    command.append('--sequence-only')
                subprocess.run(command,check=True,capture_output=True)
            report = review(stage,project)
            self.assertTrue(report['activity']['neural_images']['image_trained'])
            self.assertGreater(report['activity']['neural_images']['smoke_test_candidates'],0)


if __name__ == '__main__':
    unittest.main()
