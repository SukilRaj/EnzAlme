"""EnzAIme v2: one API and built frontend, without legacy model loading."""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.app.api.neural import router as neural_router
from backend.app.api.mutations import router as mutations_router
from backend.app.api.workspace import router as workspace_router

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend/dist"
app = FastAPI(title="EnzAIme Research Workspace", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(neural_router, prefix="/api")
app.include_router(mutations_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def frontend():
    if (DIST / "index.html").is_file():
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
    return {"service": "EnzAIme", "docs": "/docs", "detail": "Build frontend with npm run build, or use the Vite development server."}


@app.get('/favicon.svg', include_in_schema=False)
def favicon():
    return FileResponse(ROOT / 'frontend/public/favicon.svg')


@app.get("/api/{path:path}", include_in_schema=False)
def missing_api(path: str):
    raise HTTPException(404, "Unknown API endpoint")
