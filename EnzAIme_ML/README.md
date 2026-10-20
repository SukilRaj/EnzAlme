# EnzAIme

Local PET-enzyme research workspace with neural recommendations, sequence/structure inspection, residue attribution, evaluation and Ollama explanations.

Start the rebuilt application from PowerShell in this folder:

```powershell
.\Start-EnzAIme.ps1
```

Open http://127.0.0.1:8001. The launcher starts the API, serves the built frontend and starts Ollama when necessary. After code changes, build with `npm run build` in `frontend`, then use `.\Start-EnzAIme.ps1 -Restart`.

The imported activity checkpoint is running without a Ridge fallback. Its held-out R² is −2.30, so its predictions are research outputs with weak measured performance. Llama 3.2 1B selects explanation evidence; verified wording preserves names, units and scores. Residue gradients report model sensitivity, not causal mutation effects.

The next training package contains 5,622 sequence-linked Tm measurements from FireProtDB (660 sequences) and 13 sequence-verified structural distance images derived from AlphaFold structures. Stability and image branches still require training and evaluation. Joint ranking remains disabled until a compatible stability checkpoint exists.

- [Rebuild guide and current scientific scope](docs/rebuild_v2.md)
- [Next Kaggle notebook](notebooks/EnzAIme_v2_Kaggle.ipynb)
- [Complete v2 training input](outputs/enzaime_v2_training.zip)

- [Neural training, base-paper datasets, data requirements and limitations](docs/multimodal_training.md)
- [Kaggle notebook](notebooks/EnzAIme_Neural_Kaggle.ipynb)
- [Portable Kaggle starter](outputs/neural_kaggle_starter.zip)

Run from the project root in an environment with `backend/requirements-neural.txt` installed:

```bash
python -m uvicorn backend.app.neural_main:app --port 8001
```

For frontend development, use `npm run dev` in `frontend`; Vite proxies `/api` to port 8001. Missing checkpoints produce an explicit training-required state, with no Ridge fallback. See the training guide before using model scores in research claims.
