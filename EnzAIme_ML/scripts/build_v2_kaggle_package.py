"""Package collected public data and the next controlled Kaggle experiment."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells = []
    def add(kind, source):
        cell = {'cell_type':kind,'metadata':{},'id':f'enzaime-v2-{len(cells)}','source':source.splitlines(keepends=True)}
        if kind == 'code':
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    add('markdown', '# EnzAIme v2: stability and structural-image experiments\n'
        'Attach enzaime_v2_training.zip as a private Kaggle dataset. This package already contains curated public Tm records and 13 sequence-verified structure images. Enable Internet and T4 x2. Run in order. No model in this notebook is a validated mutation-effect oracle.\n')
    add('code', '''from pathlib import Path
import os, shutil, zipfile, sys, subprocess, json
root = Path('/kaggle/working/EnzAIme_v2')
inputs = Path('/kaggle/input')
sources = [p.parent.parent for p in inputs.rglob('train_stability_oracle.py')
           if (p.parent.parent/'data/stability/records.json').is_file()]
archives = list(inputs.rglob('enzaime_v2_training.zip'))
root.mkdir(parents=True, exist_ok=True)
if len(sources) == 1:
    shutil.copytree(sources[0], root, dirs_exist_ok=True)
elif not sources and len(archives) == 1:
    with zipfile.ZipFile(archives[0]) as z:
        assert all((root/n).resolve().is_relative_to(root.resolve()) for n in z.namelist())
        z.extractall(root)
else:
    raise RuntimeError(f'Attach exactly one v2 dataset. Found roots: {sources}; ZIPs: {archives}')
os.chdir(root)
print('Ready:', root)
print(json.loads(Path('data/stability/manifest.json').read_text()))
''')
    add('code', '%pip install -r backend/requirements-neural.txt\n')
    add('code', '''import torch
assert torch.cuda.is_available(), 'Enable GPU in notebook settings'
print('GPUs:', torch.cuda.device_count())
env_activity = dict(os.environ, CUDA_VISIBLE_DEVICES='0')
env_stability = dict(os.environ, CUDA_VISIBLE_DEVICES='1' if torch.cuda.device_count() > 1 else '0')
logs = Path('training_logs'); logs.mkdir(exist_ok=True)
# Start Tm training on the second T4 while activity/image experiments use the first.
stability_log = (logs/'stability.log').open('w')
stability_process = subprocess.Popen([sys.executable, '-u', '-m', 'scripts.train_stability_oracle'],
    env=env_stability, stdout=stability_log, stderr=subprocess.STDOUT)
print('Stability job started; progress in training_logs/stability.log')
''')
    add('code', '''subprocess.run([sys.executable, '-m', 'scripts.prepare_neural_features',
    '--images', 'data/structure_images/protein_views.json', '--output', 'data/neural_features_v2'], env=env_activity, check=True)
subprocess.run([sys.executable, '-m', 'scripts.train_neural_oracle',
    '--features', 'data/neural_features_v2', '--sequence-only', '--output', 'models/neural_sequence'], env=env_activity, check=True)
subprocess.run([sys.executable, '-m', 'scripts.train_neural_oracle',
    '--features', 'data/neural_features_v2', '--output', 'models/neural_images'], env=env_activity, check=True)
''')
    add('markdown', '## Wait for the stability checkpoint\nKeep this cell running until the second job finishes. Failure stops packaging. Read logs rather than restarting duplicate GPU processes.\n')
    add('code', '''import time
while stability_process.poll() is None:
    print('\\n'.join((logs/'stability.log').read_text(errors='replace').splitlines()[-3:]), flush=True)
    time.sleep(30)
stability_log.close()
if stability_process.returncode != 0:
    print((logs/'stability.log').read_text(errors='replace')[-10000:])
    raise RuntimeError('Stability training failed; resolve the logged error before exporting')
for folder in ['neural_sequence','neural_images','stability']:
    manifest = json.loads(Path(f'models/{folder}/manifest.json').read_text())
    print(folder, manifest['test_metrics'])
''')
    add('markdown', '## Return the complete experiment\nReturn all three checkpoints, features and logs. Compare image and sequence models on the same split; do not choose repeatedly on the held-out test set. The current local model is unchanged until these experiments are reviewed.\n')
    add('code', '''output = Path('/kaggle/working/enzaime_v2_results.zip')
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for folder in ['models/neural_sequence','models/neural_images','models/stability','data/neural_features_v2','training_logs']:
        for file in Path(folder).rglob('*'):
            if file.is_file(): archive.write(file, str(file))
print('Download:', output)
''')
    notebook = {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}},'cells':cells}
    nbpath = ROOT/'notebooks/EnzAIme_v2_Kaggle.ipynb'
    nbpath.write_text(json.dumps(notebook,indent=2),encoding='utf-8')
    files = ['backend/__init__.py','backend/app/__init__.py','backend/app/services/__init__.py',
        'backend/app/services/neural_oracle.py','backend/requirements-neural.txt',
        'scripts/prepare_neural_features.py','scripts/train_neural_oracle.py','scripts/train_stability_oracle.py',
        'data/processed/tpa_pet_ml_confirmed.csv','data/stability/records.json','data/stability/manifest.json',
        'data/stability/exclusions.json','data/structure_images/manifest.json','data/structure_images/protein_views.json',
        'notebooks/EnzAIme_v2_Kaggle.ipynb','docs/rebuild_v2.md']
    files += [str(p.relative_to(ROOT)) for p in (ROOT/'data/structure_images/views').glob('*.png')]
    out = ROOT/'outputs/enzaime_v2_training.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT/name, str(Path(name).as_posix()))
    print(out)


if __name__ == '__main__':
    main()
