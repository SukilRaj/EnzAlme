# Deployment

## Local development (recommended for the project review)

**Backend:**

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env      # adjust if needed; defaults work out of the box
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/health`

**Frontend** (separate terminal):

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev
```

Open the printed local URL (default `http://localhost:5173`).

## Production-ish build

```bash
cd frontend && npm run build   # outputs frontend/dist — serve with any static host
```

Serve `frontend/dist` with any static file server (nginx, `npx serve`, etc.) and point
`VITE_API_BASE_URL` (baked in at build time) at your deployed backend URL. Run the
backend with a process manager, e.g.:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Enabling the trained AI model

1. Run the data + training pipeline (locally with GPU, or via
   `notebooks/EnzAIme_Kaggle_Training.ipynb` on Kaggle).
2. Copy the resulting `artifacts/` folder (must contain `model.pt`, `scaler.pkl`,
   `encoders.pkl`, `config.json`, and ideally `embeddings/`) into the project root,
   replacing the empty placeholder.
3. Set `DEMO_MODE=false` in `.env`.
4. Restart the backend, or call `POST /reload-model` on a running instance.
5. Confirm via `GET /metadata` → `"scoring_mode": "ai_model"`.

If any artifact is missing or fails to load, the backend automatically and silently
(from the user's perspective, "silently" meaning no crash — the mode badge will still
correctly show "Demo / Compatibility Engine") falls back to the rule-based engine. This
is required behavior, not a bug (Section 35-37).

## Docker (optional)

No `docker-compose.yml` is included by default per Section 45 ("avoid unnecessary
complexity" for a one-person final-year project) — the two `uvicorn`/`npm run dev`
commands above are sufficient for a project review. A minimal Dockerfile for the
backend, if needed:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Environment variables

See `.env.example` (root, for the backend) and `frontend/.env.example` (for the
frontend). All backend variables have sensible defaults defined in
`common/enzaime_core/config.py` — nothing is required to get the MVP running.
