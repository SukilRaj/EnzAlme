# Kaggle Execution Guide

This guide documents how to run the full ESM-2 + ML pipeline **locally** and on a
**Kaggle GPU notebook**, including exact commands and what each run should produce.

## Prerequisites

- Python ≥ 3.10.
- `pip install -r requirements.txt` (torch, transformers, scikit-learn, scipy,
  matplotlib, tabulate are now first-class ML requirements).
- A master dataset: `data/processed/master_enzymes.csv` (produced by
  `python src/build_master_dataset.py --input_dir data datasets --output_dir data/processed`).

## Local run (CPU, offline-capable)

The pipeline is fully runnable **without downloading any model**: if the requested
650M checkpoint is not cached, `esm_embedder.py` transparently falls back to a cached
smaller ESM-2 (`t12_35M`, 480-dim).

```bash
cd D:\Final_Year_Project\EnzAIme

# 1. data quality + missingness + recovery plan
python src\data_quality.py

# 2. transparent scenarios + derived labels
python src\label_generation.py

# 3. embeddings (480-dim fallback when 650M not cached)
python src\esm_embedder.py --model-name facebook/esm2_t12_35M_UR50D
#    (use --download with internet to get 650M 1280-dim)

# 4. training — fast smoke run first
python src\train_kaggle.py --smoke --esm-model facebook/esm2_t12_35M_UR50D
#    then a fuller run
python src\train_kaggle.py --esm-model facebook/esm2_t12_35M_UR50D --epochs 80

# 5. explainable inference
python src\inference.py --pollutant PET --ph 8.0 --temperature 35 --salinity 0.5
python src\inference.py --pollutant PET --ml          # ML mode; auto-fallbacks to rule-based

# 6. mutation candidates (computational only)
python src\mutation_prep.py

# 7. tests
python -m pytest tests\ -q
```

### Expected smoke-run numbers (verified locally)

| Item | Value |
| --- | --- |
| master rows / clean | 75 |
| valid sequences | 70 |
| missing (catalogue-only) | 5 |
| scenario rows | 6,900 (69 enzymes × 100) |
| embedding matrix | (70, 480) float32 (35M fallback) |
| grouped split | 55 train enzymes / 14 test enzymes, seed 42 |
| no-leakage assertion | passes |

## Kaggle GPU run

The notebook `notebooks/kaggle_full_training.ipynb` automates everything. Setup:

1. Create a Kaggle dataset from this repo (zip the folder; upload at
   https://www.kaggle.com/datasets). The notebook auto-detects
   `/kaggle/input/enzaime`.
2. New Notebook → select **Accelerator: GPU P100** (or better), **Internet: On**
   (required only for the `--download` ESM-2 650M fetch and `pip`).
3. Import the notebook cells (they are self-contained) or run once then export to a
   Kaggle notebook via the zip upload.

Equivalent non-notebook commands on Kaggle (e.g. add a Timelapse script):

```bash
pip install -q matplotlib tabulate
cd /kaggle/working/enzaime
python src/data_quality.py
python src/label_generation.py
python src/esm_embedder.py --download                 # 650M, 1280-dim, GPU
python src/train_kaggle.py --esm-model facebook/esm2_t33_650M_UR50D --download
python src/inference.py --pollutant PET --ml
python src/mutation_prep.py
```

### Kaggle expected outputs

- `data/processed/esm_embeddings.npy` **(70, 1280)**.
- `artifacts/{best_model.pt, scaler.pkl, feature_config.json, metrics.json}` plus the
  backend-compatible `{model.pt, encoders.pkl, config.json}`.
- `reports/{training_report.md, model_comparison.csv, prediction_examples.csv}`.

### How to download results

On the notebook toolbar select **Run → Save Version**, then on the version page use
**Output** → **Download**. The trained `artifacts/` folder can be dropped back into the
repo and `backend` (with `DEMO_MODE=false`) will load `model.pt` directly.

## Interpreting metrics honestly

`metrics.json` includes this disclaimer and every report repeats it:

> All metrics measure agreement with the DERIVED compatibility label, NOT experimental
> degradation efficiency.

With 70 unique enzymes the baselines frequently match or beat the MLP — the pipeline
always saves whichever model actually performed best on the held-out enzyme group.