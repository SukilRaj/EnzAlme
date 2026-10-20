"""Review a Kaggle export; activation is explicit and backs up served artifacts.

Usage: python -m scripts.import_v2_results path/to/enzaime_v2_results.zip
       Add --activate images or --activate sequence after reviewing results.
This checks artifact integrity and compatibility, not biological validity.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

import numpy as np
from backend.app.services.neural_recommender import NeuralRecommender, ROOT
from backend.app.services.stability_oracle import StabilityOracle

ALLOWED = ('models/neural_sequence/', 'models/neural_images/', 'models/stability/',
           'data/neural_features_v2/', 'training_logs/')


def extract_checked(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 5000 or sum(i.file_size for i in members) > 2_000_000_000:
            raise ValueError('Unexpectedly large result archive')
        seen = set()
        for info in members:
            name = info.filename
            parts = PurePosixPath(name).parts
            if ('\\' in name or ':' in name or '..' in parts or name.startswith('/')
                or not name.startswith(ALLOWED) or name.casefold() in seen
                or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError(f'Unsafe or unexpected archive entry: {name}')
            seen.add(name.casefold())
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Archive path escapes its destination')
        z.extractall(destination)


def disjoint_splits(splits):
    groups = [set(splits[k]) for k in ('train', 'validation', 'test')]
    if not all(groups) or any(groups[i] & groups[j] for i,j in ((0,1),(0,2),(1,2))):
        raise ValueError('Empty or overlapping training/evaluation splits')


def measured_metrics(rows, target):
    observed = np.array([r['observed_'+target] for r in rows], dtype=float)
    predicted = np.array([r['predicted_'+target] for r in rows], dtype=float)
    if not len(rows) or not np.isfinite(observed).all() or not np.isfinite(predicted).all():
        raise ValueError('Missing or nonfinite held-out measurements')
    error = predicted-observed
    denominator = np.sum((observed-observed.mean())**2)
    return {'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt(np.mean(error**2))),
            'r2':float(1-np.sum(error**2)/denominator) if denominator else None,'test_rows':len(rows)}


def review(directory, project=ROOT):
    directory, project = Path(directory), Path(project)
    stability_dir = directory/'models/stability'
    stability = StabilityOracle(stability_dir)
    raw = (project/'data/stability/records.json').read_bytes()
    if stability.meta['dataset_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('Stability data differs from the local training dataset')
    disjoint_splits(stability.meta['split_record_ids'])
    records = {r['record_id']:r for r in json.loads(raw)}
    for field in ('sequence_sha256', 'family_group'):
        disjoint_splits({k:[records[i][field] for i in ids] for k,ids in stability.meta['split_record_ids'].items()})
    held = json.loads((stability_dir/'held_out_predictions.json').read_text())
    if {r['record_id'] for r in held} != set(stability.meta['split_record_ids']['test']):
        raise ValueError('Tm evaluation records do not match the declared test split')
    for r in held:
        if not np.isclose(r['observed_tm_c'], records[r['record_id']]['tm_c']):
            raise ValueError('Tm evaluation labels differ from source records')
    report = {'stability':measured_metrics(held,'tm_c'), 'activity':{},
              'scope':'Artifact compatibility review, not scientific validation.'}
    models = {}
    for name in ('neural_sequence', 'neural_images'):
        model = NeuralRecommender(directory/f'models/{name}', directory/'data/neural_features_v2',
            project/'data/processed/tpa_pet_ml_confirmed.csv', stability_dir)
        disjoint_splits(model.meta['split_sequence_hashes'])
        held = json.loads((directory/f'models/{name}/held_out_predictions.json').read_text())
        observed_test = {model.index['proteins'][r['protein_id']]['sequence_sha256'] for r in held}
        if observed_test != set(model.meta['split_sequence_hashes']['test']):
            raise ValueError('Activity evaluation does not match declared test proteins')
        validation = model.meta.get('validation_metrics', {}).get('log_mse')
        if validation is None or not np.isfinite(validation):
            raise ValueError('Finite validation loss is required for model comparison')
        result = model.recommend(40,8,48,3,objective='joint')
        report['activity'][name] = {**measured_metrics(held,'um'), 'validation_log_mse':validation,
            'image_trained':model.meta['image_trained'], 'smoke_test_candidates':len(result['recommendations'])}
        models[name] = model
    if models['neural_sequence'].meta['split_sequence_hashes'] != models['neural_images'].meta['split_sequence_hashes']:
        raise ValueError('Activity experiments did not use the same data split')
    if models['neural_sequence'].meta['image_trained'] or not models['neural_images'].meta['image_trained']:
        raise ValueError('Sequence/image experiment flags are inconsistent')
    # Selection uses validation only; test outcomes remain an unbiased diagnostic of this fixed choice.
    report['lower_validation_loss_model'] = min(report['activity'], key=lambda k: report['activity'][k]['validation_log_mse'])
    return report


def activate(directory, choice, backup, project=ROOT):
    """Copy complete pairs; restore existing artifacts if any copy fails."""
    project, directory, backup = map(Path, (project,directory,backup))
    mappings = [(f'models/neural_{choice}','models/neural'),
                ('models/stability','models/stability'),('data/neural_features_v2','data/neural_features')]
    existed = []
    for _, target in mappings:
        destination = project/target
        if destination.exists():
            shutil.copytree(destination, backup/target)
            existed.append(target)
    try:
        for source, target in mappings:
            shutil.copytree(directory/source, project/target, dirs_exist_ok=True)
    except Exception:
        for _, target in mappings:
            destination = (project/target).resolve()
            if not destination.is_relative_to(project.resolve()):
                raise ValueError('Invalid rollback destination')
            if destination.exists():
                shutil.rmtree(destination)
            if target in existed:
                shutil.copytree(backup/target, destination)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--activate', choices=['sequence','images'])
    args = p.parse_args()
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT/'outputs/imports'/run
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='staged-', dir=output) as temporary:
        staged = Path(temporary)
        extract_checked(args.archive, staged)
        report = review(staged)
        report['archive_sha256'] = hashlib.sha256(args.archive.read_bytes()).hexdigest()
        report['activated'] = args.activate
        if args.activate:
            activate(staged, args.activate, output/'backup')
        (output/'review.json').write_text(json.dumps(report, indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
        print('Saved review:', output/'review.json')
        if args.activate:
            print('Restart with Start-EnzAIme.ps1 -Restart to load the reviewed artifacts.')


if __name__ == '__main__':
    main()
