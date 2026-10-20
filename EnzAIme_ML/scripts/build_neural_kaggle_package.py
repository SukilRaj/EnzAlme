"""Build a portable, explicit-file training handoff without local environments or weights."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]

SETUP_CELL = '''from pathlib import Path
import os, shutil, zipfile

inputs = Path('/kaggle/input')
root = Path('/kaggle/working/EnzAIme_ML')
required = ['backend/requirements-neural.txt',
            'scripts/prepare_neural_features.py',
            'scripts/train_neural_oracle.py',
            'data/processed/tpa_pet_ml_confirmed.csv']

# Kaggle may unpack an uploaded ZIP into the dataset directory.
sources = sorted({p.parent.parent for p in inputs.rglob('requirements-neural.txt')
                  if all((p.parent.parent / name).is_file() for name in required)})
archives = sorted(inputs.rglob('neural_kaggle_starter.zip'))
if len(sources) == 1:
    root.mkdir(parents=True, exist_ok=True)
    for name in ['backend', 'scripts', 'data', 'docs', 'notebooks']:
        source = sources[0] / name
        if source.is_dir():
            shutil.copytree(source, root / name, dirs_exist_ok=True)
    print('Copied extracted starter from:', sources[0])
elif not sources and len(archives) == 1:
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        if not all((root / name).resolve().is_relative_to(root.resolve())
                   for name in archive.namelist()):
            raise ValueError('ZIP contains a path outside the working directory')
        archive.extractall(root)
    print('Extracted:', archives[0])
else:
    print('Input entries:', [str(p) for p in inputs.iterdir()] if inputs.exists() else [])
    print('Matching extracted starters:', [str(p) for p in sources])
    print('Matching ZIPs:', [str(p) for p in archives])
    raise RuntimeError('Attach one EnzAIme starter dataset using Add Input; remove duplicate starter datasets.')

missing = [name for name in required if not (root / name).is_file()]
if missing:
    raise RuntimeError(f'Starter is incomplete: {missing}')
os.chdir(root)
print('Ready:', Path.cwd())
'''


def main():
    def markdown(text):
        return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}

    def code(text):
        return {"cell_type": "code", "metadata": {}, "execution_count": None,
                "outputs": [], "source": text.splitlines(keepends=True)}

    cells = [markdown("# EnzAIme neural activity feasibility baseline\n"
        "This notebook does not train thermostability or establish mutation improvements. "
        "No paired images are included. Read docs/multimodal_training.md. Enable a T4 GPU and Internet. "
        "Upload neural_kaggle_starter.zip as a private Kaggle dataset before running.\n"),
        code(SETUP_CELL),
        code("%pip install -r backend/requirements-neural.txt\n"),
        code("import torch\nprint('GPU count:', torch.cuda.device_count())\n"
             "assert torch.cuda.is_available(), 'Enable GPU in Kaggle settings'\n"
             "!python -m scripts.prepare_neural_features\n"),
        markdown("## Train and evaluate\nExact sequence groups are held apart. "
                 "Homologous proteins and publications may still cross splits. "
                 "This is a feasibility check, not a final generalization result.\n"),
        code("!python -m scripts.train_neural_oracle --sequence-only --output models/neural\n"
             "import json\nprint(json.dumps(json.loads(Path('models/neural/manifest.json').read_text()), indent=2))\n"),
        markdown("## Optional second T4\nUse separate seeds/outputs on the two GPUs. "
                 "Do not repeatedly choose models based on held-out test scores. "
                 "Image fusion requires a verified view manifest; see the guide.\n"),
        code("import zipfile\noutput = Path('/kaggle/working/enzaime_neural_results.zip')\n"
             "with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:\n"
             "    for folder in ['models/neural', 'data/neural_features']:\n"
             "        for file in Path(folder).rglob('*'):\n"
             "            if file.is_file(): archive.write(file, str(file))\n"
             "print('Download and return:', output)\n")]
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "cells": cells}
    for i, cell in enumerate(cells):
        cell["id"] = f"enzaime-{i:02d}"
    notebook_path = ROOT / "notebooks/EnzAIme_Neural_Kaggle.ipynb"
    notebook_path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    files = ["backend/__init__.py", "backend/app/__init__.py", "backend/app/services/__init__.py",
             "backend/app/services/neural_oracle.py", "backend/requirements-neural.txt",
             "scripts/prepare_neural_features.py", "scripts/train_neural_oracle.py",
             "data/processed/tpa_pet_ml_confirmed.csv", "docs/multimodal_training.md",
             "notebooks/EnzAIme_Neural_Kaggle.ipynb"]
    out = ROOT / "outputs/neural_kaggle_starter.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT / name, name)
    print(out)


if __name__ == "__main__":
    main()
