"""Read-only artifact probes; outputs are confined to this audit directory."""
import csv
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def rows(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def manifest():
    paths = [ROOT / 'master_dataset.csv', ROOT / 'fireprotdb_20251015-164116.csv']
    for folder in ['models', 'data', 'reports', 'backend', 'scripts', 'frontend/src']:
        paths.extend((ROOT / folder).rglob('*'))
    return {str(p.relative_to(ROOT)): hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
            for p in paths if p.is_file() and OUT not in p.parents and '__pycache__' not in p.parts}


def inspect():
    import joblib
    import numpy as np
    packages = {d.metadata['Name']: d.version for d in metadata.distributions()}
    save('current_packages.json', {'python': sys.version, 'executable': sys.executable, 'packages': packages})
    original = rows('data/tpa_pet_ml_dataset.csv')
    confirmed = rows('data/processed/tpa_pet_ml_confirmed.csv')
    excluded = rows('data/processed/tpa_pet_ambiguous_excluded.csv')
    keys = ['protein_id', 'temperature_c', 'ph', 'duration_value', 'duration_unit']
    excluded_details = []
    for row in excluded:
        matches = [i for i, old in enumerate(original) if all(old[k] == row[k] for k in keys)
                   and float(old['target_activity']) == float(row['target_value'])]
        excluded_details.append({k: row[k] for k in keys + ['protein_name','target_value','target_unit','assay_index','exclusion_reason']} | {'original_zero_based_row_matches': matches})
    def env_summary(data):
        def hours(r):
            if r.get('duration_hours'): return float(r['duration_hours'])
            return float(r['duration_value']) * {'h':1, 'd':24, 'min':1/60}[r['duration_unit']]
        a = np.array([[float(r['temperature_c']), float(r['ph']), hours(r)] for r in data])
        return {'mean': a.mean(axis=0).tolist(), 'population_variance': a.var(axis=0).tolist()}
    artifact_info = {}
    for name in ['pca', 'scaler', 'ridge_model']:
        obj = joblib.load(ROOT / 'models' / (name + '.pkl'))
        info = {'class': type(obj).__module__ + '.' + type(obj).__name__, 'parameters': obj.get_params()}
        for key in ['n_samples_', 'n_samples_seen_', 'n_features_in_', 'n_components_']:
            if hasattr(obj, key): info[key] = np.asarray(getattr(obj,key)).tolist()
        if name == 'scaler':
            info['environment_mean_last_three'] = obj.mean_[-3:].tolist()
            info['environment_variance_last_three'] = obj.var_[-3:].tolist()
        artifact_info[name] = info
    def counts(data):
        from collections import Counter
        return dict(Counter(r['protein_id'] for r in data))
    save('lineage_evidence.json', {'counts': {'original':len(original),'confirmed':len(confirmed),'excluded':len(excluded)},
        'original_protein_counts':counts(original),'confirmed_protein_counts':counts(confirmed),
        'original_environment':env_summary(original),'confirmed_environment':env_summary(confirmed),
        'artifacts':artifact_info,'excluded_records':excluded_details})
    sequence = next(r['sequence'] for r in original if r['protein_id']=='1')
    request = {'sequence':sequence,'ph':8,'temperature':40,'duration':48}
    req = urllib.request.Request('http://127.0.0.1:8000/api/predict', data=json.dumps(request).encode(), headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response: result=json.load(response)
        save('live_api_prediction.json', {'request':request,'response':result,'sequence_sha256':hashlib.sha256(sequence.encode()).hexdigest()})
    except Exception as error:
        save('live_api_prediction.json', {'request':request,'error':str(error)})


def verify_lineage():
    from collections import Counter
    from decimal import Decimal
    original=rows('data/tpa_pet_ml_dataset.csv')
    confirmed=rows('data/processed/tpa_pet_ml_confirmed.csv')
    excluded=rows('data/processed/tpa_pet_ambiguous_excluded.csv')
    def key(r):
        return (r['protein_id'],r['sequence'],r['substrate'],
            *(str(Decimal(r[c]).normalize()) for c in ['temperature_c','ph','duration_value']),
            r['duration_unit'],str(Decimal(r.get('target_activity',r.get('target_value'))).normalize()),
            r.get('unit',r.get('target_unit')).replace('μ','µ'))
    original_keys=Counter(map(key,original))
    confirmed_keys=Counter(map(key,confirmed))
    excluded_keys=Counter(map(key,excluded))
    cv=json.loads((ROOT/'reports/results/cross_validation_results.json').read_text())
    metrics=json.loads((ROOT/'models/training_metrics.json').read_text())
    saved_means={k:sum(f[k] for f in cv['folds'])/len(cv['folds']) for k in ['mae','rmse','r2','spearman']}
    sequence_sets=lambda rr:{(r['protein_id'],r['sequence']) for r in rr}
    save('dataset_reconciliation.json',{'original_equals_confirmed_plus_excluded_multiset':original_keys==confirmed_keys+excluded_keys,
        'matching_fields':['protein_id','sequence','substrate','temperature_c','ph','duration_value','duration_unit','original_target','original_unit'],
        'same_protein_sequence_pairs':sequence_sets(original)==sequence_sets(confirmed),
        'fold_test_record_counts':[f['records'] for f in cv['folds']], 'fold_record_sum':sum(f['records'] for f in cv['folds']),
        'rounded_fold_metric_means':saved_means,'training_metrics':metrics})


def worker():
    import numpy as np
    from backend.app.services.predictor import Predictor
    embedding = np.asarray(json.load(sys.stdin), dtype=np.float32)
    value = Predictor().predict(embedding, temperature=40, ph=8, duration_hours=48)
    print(json.dumps({'prediction_um':value,'float_hex':value.hex(),'python':sys.version,
        'packages':{n:metadata.version(n) for n in ['scikit-learn','numpy','scipy','joblib','threadpoolctl']}}))


def compare(compatible_python):
    import subprocess
    import numpy as np
    from backend.app.services.esm_encoder import ESMEncoder
    sequence = next(r['sequence'] for r in rows('data/tpa_pet_ml_dataset.csv') if r['protein_id']=='1')
    encoder = ESMEncoder()
    embedding = encoder.encode(sequence)
    results = {'sequence_sha256':hashlib.sha256(sequence.encode()).hexdigest(),
        'embedding_sha256':hashlib.sha256(embedding.tobytes()).hexdigest(),
        'encoder_device':str(encoder.device),'encoder_dtype':str(next(encoder.model.parameters()).dtype),
        'encoder_revision':getattr(encoder.model.config,'_commit_hash',None),
        'conditions':{'ph':8,'temperature':40,'duration':48}}
    # Pass one fresh inference vector through stdin; never persist or replace embeddings.
    for label, executable in [('current',sys.executable),('compatible',compatible_python)]:
        proc = subprocess.run([executable,'-B',str(Path(__file__).resolve()),'worker'],
            input=json.dumps(embedding.tolist()),text=True,capture_output=True,check=False)
        (OUT / (label + '_worker_stderr.log')).write_text(proc.stderr,encoding='utf-8')
        sys.stderr.write(proc.stderr)
        if proc.returncode: raise RuntimeError(proc.stderr)
        results[label] = json.loads(proc.stdout)
    current, compatible = results['current']['prediction_um'],results['compatible']['prediction_um']
    results['compatible_minus_current_um'] = compatible-current
    results['absolute_difference_um'] = abs(compatible-current)
    results['relative_difference'] = abs(compatible-current)/abs(current) if current else None
    results['live_api'] = json.loads((OUT / 'live_api_prediction.json').read_text(encoding='utf-8'))
    index=json.loads((ROOT/'data/embeddings/index.json').read_text())
    stored=np.load(ROOT/'data/embeddings'/index['1'],allow_pickle=False)
    results['stored_embedding_comparison']={'shape':list(stored.shape),'max_abs_difference':float(np.max(np.abs(stored-embedding))), 'exact_equal':bool(np.array_equal(stored,embedding))}
    save('prediction_comparison.json',results)
    print(json.dumps(results,indent=2))


if __name__ == '__main__':
    mode=sys.argv[1]
    if mode=='baseline': save('preservation_before.json',manifest())
    elif mode=='verify':
        before=json.loads((OUT/'preservation_before.json').read_text())
        after=manifest()
        save('preservation_check.json',{'checked_files':len(before),'changed_or_missing':[p for p,h in before.items() if after.get(p)!=h], 'new_files_outside_audit':[p for p in after if p not in before]})
    elif mode=='inspect': inspect()
    elif mode=='lineage': verify_lineage()
    elif mode=='worker': worker()
    elif mode=='compare': compare(sys.argv[2])
